"""Release-based updates of the mounted checkout, with a supervised rollback."""
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = 'https://github.com/bhxuk/null_gate.git'
API = 'https://api.github.com/repos/bhxuk/null_gate'
TOKEN_CHARS = re.compile(r'^[A-Za-z0-9_]+$')
PRIVATE_HINT = ('GitHub could not find the null_gate repository. If you update from a private fork, add a GitHub token in '
                'Settings → Updates.')

def version_tuple(value):
    if not re.fullmatch(r'v?\d+\.\d+\.\d+', value):
        raise ValueError('Invalid release version')
    return tuple(map(int, value.lstrip('v').split('.')))

class Updater:
    def __init__(self, root, store):
        self.root, self.store = Path(root), store
        self.current = (self.root / 'app/VERSION').read_text().strip()
        self.lock = threading.Lock()
        self.state, self.latest, self.error, self.checked = 'idle', None, None, None
        self.notes, self.log = '', []

    # ---- Optional GitHub token (rate limits or private forks) -----------
    @property
    def token_path(self):
        return self.store.root / 'github.json'

    def token(self):
        try:
            value = json.loads(self.token_path.read_text())['token']
            return value if isinstance(value, str) and TOKEN_CHARS.fullmatch(value) else ''
        except (OSError, ValueError, KeyError, TypeError):
            return ''

    def _api(self, path, token=None):
        token = self.token() if token is None else token
        headers = {'User-Agent': 'null_gate (bhxuk.com)', 'Accept': 'application/vnd.github+json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        request = urllib.request.Request(API + path, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                return json.loads(response.read(1024 * 1024))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403) and token:
                raise RuntimeError('GitHub rejected the token. Create a new one with read access to bhxuk/null_gate.') from None
            if exc.code == 404:
                raise RuntimeError(PRIVATE_HINT if not token else
                                   'The token cannot see bhxuk/null_gate. Give it read access to Contents for that repository.') from None
            raise RuntimeError(f'GitHub returned HTTP {exc.code}') from None

    def set_token(self, raw):
        """Save (after testing) or remove the GitHub token. Never returned to the browser."""
        if raw.get('remove'):
            self.token_path.unlink(missing_ok=True)
            return self.status()
        token = raw.get('token')
        if not isinstance(token, str) or not 20 <= len(token.strip()) <= 255 or not TOKEN_CHARS.fullmatch(token.strip()):
            raise ValueError('Paste a GitHub token (it starts with github_pat_ or ghp_).')
        token = token.strip()
        try:
            self._api('/releases/latest', token)
        except RuntimeError as exc:
            raise ValueError(str(exc)) from None
        temp = self.token_path.with_suffix('.tmp')
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump({'token': token}, f)
        os.replace(temp, self.token_path)
        return self.check()

    def _auth_config(self):
        """Git config arguments that authenticate fetches from GitHub, if a token is saved."""
        token = self.token()
        if not token:
            return []
        basic = base64.b64encode(f'x-access-token:{token}'.encode()).decode()
        return ['-c', f'http.https://github.com/.extraheader=AUTHORIZATION: basic {basic}']

    def git(self, *args, timeout=120):
        result = subprocess.run(['git', '-c', f'safe.directory={self.root}', '-C', str(self.root), *args],
                                text=True, capture_output=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout).strip()[-800:])
        return result.stdout.strip()

    def capability(self):
        if os.getenv('INSTALL_METHOD') != 'docker' or not os.getenv('NULL_GATE_SUPERVISED'):
            return False, 'Install with the supplied Docker Compose file to enable one-click updates.'
        if not (self.root / '.git').is_dir() or not shutil.which('git'):
            return False, 'The Git checkout must be mounted at /app.'
        return True, ''

    # ---- automatic updates -------------------------------------------
    def auto_enabled(self):
        try:
            return self.store.read()['settings'].get('autoUpdate', True)
        except Exception:
            return False

    def _rolled_back(self, version):
        """True if this exact version already failed and was rolled back, so we don't loop."""
        try:
            result = json.loads((self.store.root / 'update-result.json').read_text())
            return result.get('status') == 'rolled_back' and result.get('version') == version
        except (OSError, ValueError):
            return False

    def auto_tick(self):
        """Check GitHub and install a newer release if automatic updates are on."""
        if not self.capability()[0] or not self.auto_enabled() or self.state in ('updating', 'restarting'):
            return False
        self.check()
        if self.status()['available'] and not self._rolled_back(self.latest):
            self.log = []
            return self.start()
        return False

    def run_automatic(self, first_delay=120, interval=3600):
        """Background loop: first check shortly after start-up, then hourly."""
        def loop():
            time.sleep(first_delay)
            while True:
                try:
                    self.auto_tick()
                except Exception as exc:  # never let the loop die
                    print(f'Automatic update check failed: {exc}', flush=True)
                time.sleep(interval)
        threading.Thread(target=loop, daemon=True, name='auto-update').start()

    def status(self):
        ok, reason = self.capability()
        available = self.latest is not None and version_tuple(self.latest) > version_tuple(self.current)
        try:
            recovery = json.loads((self.store.root / 'update-result.json').read_text())
        except (OSError, ValueError):
            recovery = None
        return dict(current=self.current, latest=self.latest, available=available, canUpdate=ok, reason=reason, auto=self.auto_enabled(), hasToken=bool(self.token()),
                    state=self.state, error=self.error, checked=self.checked, notes=self.notes, log=self.log[-100:], recovery=recovery)

    def check(self):
        if not self.lock.acquire(blocking=False):
            return self.status()
        try:
            data = self._api('/releases/latest')
            tag = data['tag_name']
            version_tuple(tag)
            self.latest = tag.lstrip('v')
            self.notes = str(data.get('body', ''))[:30000]
            self.error = None
        except Exception as exc:
            self.error = str(exc) if isinstance(exc, RuntimeError) else f'Could not check GitHub releases: {exc}'
        finally:
            self.checked = time.time()
            self.lock.release()
        return self.status()

    def start(self):
        ok, reason = self.capability()
        if not ok:
            self.error = reason
            return False
        if not self.lock.acquire(blocking=False):
            return False
        if not self.latest or version_tuple(self.latest) <= version_tuple(self.current):
            self.error = 'Check for a newer release first.'
            self.lock.release()
            return False
        self.state, self.error, self.log = 'updating', None, []
        threading.Thread(target=self._run, daemon=True).start()
        return True

    def _run(self):
        pending = self.store.root / 'update-pending.json'
        try:
            if self.git('remote', 'get-url', 'origin').removesuffix('.git').rstrip('/') != REPO.removesuffix('.git'):
                raise RuntimeError('The update remote must be https://github.com/bhxuk/null_gate.git')
            if self.git('status', '--porcelain', '--untracked-files=normal'):
                raise RuntimeError('Local source changes found. Back them up and commit or stash them before updating.')
            self.log.append('Fetching the published release…')
            tag = 'v' + self.latest
            try:
                self.git(*self._auth_config(), 'fetch', '--no-tags', 'origin', f'refs/tags/{tag}:refs/tags/{tag}', timeout=180)
            except RuntimeError as exc:
                if 'Authentication' in str(exc) or 'could not read Username' in str(exc) or 'not found' in str(exc).lower():
                    raise RuntimeError(PRIVATE_HINT) from None
                raise
            target = self.git('rev-parse', f'{tag}^{{commit}}')
            before = self.git('rev-parse', 'HEAD')
            self.git('merge-base', '--is-ancestor', before, target)
            self.log.append('Validating the release before changing your install…')
            with tempfile.TemporaryDirectory() as directory:
                self.git('worktree', 'add', '--detach', directory, target)
                try:
                    actual = (Path(directory) / 'app/VERSION').read_text().strip()
                    if actual != self.latest:
                        raise RuntimeError('Release tag and app version do not match')
                    result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'], cwd=directory,
                        capture_output=True, text=True, timeout=90)
                    if result.returncode:
                        raise RuntimeError('Release self-tests failed; installed code was left unchanged.')
                finally:
                    self.git('worktree', 'remove', '--force', directory)
            backup = self.store.backup()
            pending.write_text(json.dumps({'before': before, 'target': target, 'version': self.latest, 'backup': backup}))
            self.log.append(f'Dashboard backed up to backups/{backup}')
            self.git('merge', '--ff-only', target)
            self.state = 'restarting'
            self.log.append('Restarting. The supervisor will restore the previous code if the health check fails.')
            time.sleep(1.5)
            os._exit(3)
        except Exception as exc:
            pending.unlink(missing_ok=True)
            self.error, self.state = str(exc), 'error'
            self.log.append(self.error)
        finally:
            self.lock.release()
