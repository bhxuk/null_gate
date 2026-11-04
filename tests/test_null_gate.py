import copy
import http.client
import importlib.util
import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from app.store import Store, Conflict, initial, validate
from app.main import Server, Handler, private_ip, allowed_host, VERSION
from app.homeassistant import HomeAssistant
from app.feeds import Feeds, FeedError
import app.feeds as feeds_module
from app.updater import Updater, version_tuple

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)

    def test_persistence_conflict_and_visit_merge(self):
        state = self.store.read()
        stale = copy.deepcopy(state)
        link = state['links'][0]
        self.store.visit(link['id'])
        state['notes'] = 'Important notes\nwith another line'
        saved = self.store.save(state)
        self.assertEqual(saved['links'][0]['visits'], 1)
        self.assertEqual(Store(self.temp.name).read()['notes'], state['notes'])
        with self.assertRaises(Conflict):
            self.store.save(stale)

    def test_backup_and_import_round_trip(self):
        original = self.store.read()
        name = self.store.backup()
        self.assertEqual(json.loads((Path(self.temp.name) / 'backups' / name).read_text()), original)
        original['categories'].append({'id': 'new-category', 'name': 'Servers', 'icon': '▣'})
        original['links'][0].update(category='new-category', url='http://192.168.1.100:32400/web')
        saved = self.store.save(original)
        self.assertEqual(saved['links'][0]['category'], 'new-category')
        self.assertEqual(validate(saved)['links'][0]['url'], 'http://192.168.1.100:32400/web')

    def test_invalid_import_does_not_change_data(self):
        original = self.store.path.read_bytes()
        for url in ['javascript:alert(1)', 'file:///etc/passwd', 'https://u:p@example.com', '//example.com', 'https://example.com:bad']:
            bad = self.store.read()
            bad['links'][0]['url'] = url
            with self.assertRaises(ValueError):
                self.store.save(bad)
            self.assertEqual(self.store.path.read_bytes(), original)
        bad = self.store.read()
        bad['links'][0]['category'] = 'missing'
        with self.assertRaises(ValueError):
            validate(bad)
        bad = self.store.read()
        bad['categories'].append(bad['categories'][0])
        with self.assertRaises(ValueError):
            validate(bad)

    def test_layouts_persist_and_old_backups_stay_compatible(self):
        old = self.store.read()
        old['settings'].pop('layout', None)
        old['settings']['compact'] = False
        self.assertEqual(validate(old)['settings']['layout'], 'compact')
        for layout in ('cards', 'compact', 'table', 'tv'):
            current = self.store.read()
            current['settings']['layout'] = layout
            current['notes'] = 'Keep these notes'
            saved = self.store.save(current)
            self.assertEqual(saved['settings']['layout'], layout)
            self.assertEqual(Store(self.temp.name).read()['notes'], 'Keep these notes')
        invalid = self.store.read()
        invalid['settings']['layout'] = 'unknown'
        with self.assertRaises(ValueError):
            self.store.save(invalid)

    def test_v1_data_without_new_sections_loads(self):
        old = self.store.read()
        old.pop('home')
        old['settings'].pop('clocks')
        self.store.path.write_text(json.dumps(old))
        state = Store(self.temp.name).read()
        self.assertEqual(state['home'], {'favourites': [], 'hidden': [], 'quick': [], 'cameraInterval': 10})
        self.assertEqual(state['settings']['clocks'], ['America/New_York', 'UTC', 'Asia/Tokyo'])
        state['home']['favourites'] = ['light.lamp', 'camera.front_door', 'light.lamp']
        saved = self.store.save(state)
        self.assertEqual(saved['home']['favourites'], ['light.lamp', 'camera.front_door'])
        for bad in (['not an id'], 'light.lamp'):
            state = self.store.read()
            state['home']['favourites'] = bad
            with self.assertRaises(ValueError):
                validate(state)
        state = self.store.read()
        state['settings']['clocks'] = ['Mars/Olympus']
        with self.assertRaises(ValueError):
            validate(state)

    def test_links_file_sync_adds_once(self):
        path = Path(self.temp.name) / 'links.txt'
        path.write_text('# comment\n*Plex | http://192.168.1.20:32400/web | Media | Films\nGitHub | https://github.com/ | Everyday\n'
                        'bad line | javascript:alert(1)\nhttps://example.org\n')
        before = len(self.store.read()['links'])
        self.assertEqual(self.store.sync_links(path), 2)  # GitHub already exists
        state = self.store.read()
        self.assertEqual(len(state['links']), before + 2)
        plex = next(l for l in state['links'] if l['name'] == 'Plex')
        self.assertTrue(plex['pinned'])
        self.assertEqual(next(c['name'] for c in state['categories'] if c['id'] == plex['category']), 'Media')
        # Deleting a synced link in null_gate is remembered across saves and syncs.
        state['links'] = [l for l in state['links'] if l['name'] != 'Plex']
        self.store.save(state)
        self.assertEqual(self.store.sync_links(path), 0)
        self.assertFalse(any(l['name'] == 'Plex' for l in self.store.read()['links']))
        path.write_text(path.read_text() + 'Sonarr | http://192.168.1.20:8989 | Media\n')
        self.assertEqual(self.store.sync_links(path), 1)
        self.assertEqual(self.store.sync_links(Path(self.temp.name) / 'missing.txt'), 0)

    def test_corrupt_storage_is_not_replaced(self):
        self.store.path.write_text('broken')
        with self.assertRaises(ValueError):
            Store(self.temp.name)
        self.assertEqual(self.store.path.read_text(), 'broken')

class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.server = Server(('127.0.0.1', 0), Handler)
        cls.server.store = Store(cls.temp.name)
        cls.server.home = HomeAssistant(cls.temp.name)
        cls.server.feeds = Feeds()
        cls.server.updater = Updater(Path(__file__).resolve().parents[1], cls.server.store)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.temp.cleanup()

    def request(self, path, method='GET', body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        h = {'Content-Type': 'application/json'}
        h.update(headers or {})
        conn.request(method, path, json.dumps(body) if body is not None else None, h)
        r = conn.getresponse()
        data, code, response_headers = r.read(), r.status, dict(r.getheaders())
        conn.close()
        return code, data, response_headers

    def test_api_lifecycle_and_export(self):
        code, data, headers = self.request('/api/state')
        self.assertEqual(code, 200)
        state = json.loads(data)
        state['notes'] = 'Saved via the API'
        code, saved, _ = self.request('/api/state', 'PUT', state)
        self.assertEqual(code, 200)
        code, _, _ = self.request('/api/state', 'PUT', state)
        self.assertEqual(code, 409)
        code, data, h = self.request('/api/export')
        self.assertEqual(json.loads(data)['notes'], 'Saved via the API')
        self.assertIn('attachment', h['Content-Disposition'])
        code, _, _ = self.request('/api/backup', 'POST', {})
        self.assertEqual(code, 200)

    def test_browser_security_and_path_traversal(self):
        code, _, _ = self.request('/api/state', 'PUT', {}, {'Origin': 'https://evil.example'})
        self.assertEqual(code, 403)
        code, _, _ = self.request('/api/state', 'PUT', {}, {'Content-Type':'text/plain'})
        self.assertEqual(code, 415)
        code, _, _ = self.request('/', headers={'Host': 'evil.example'})
        self.assertEqual(code, 403)
        code, _, _ = self.request('/../../app/main.py')
        self.assertEqual(code, 404)
        code, _, _ = self.request('/api/visit', 'POST', {'id':'missing'})
        self.assertEqual(code, 400)
        code, _, _ = self.request('/api/state', 'PUT', None, {'Content-Length': '9999999'})
        self.assertEqual(code, 413)

    def test_static_and_version(self):
        code, html, h = self.request('/')
        self.assertEqual(code, 200)
        self.assertIn(b'js/main.js', html)
        self.assertIn("script-src 'self'", h['Content-Security-Policy'])
        code, _, h = self.request('/js/main.js')
        self.assertEqual(code, 200)
        self.assertTrue(h['Content-Type'].startswith('text/javascript'))
        for path in ['/app.css', '/icon.svg', '/js/home.js', '/js/importer.js', '/api/changelog', '/api/updates', '/api/health', '/api/home/config']:
            self.assertEqual(self.request(path)[0], 200, path)
        self.assertEqual(json.loads(self.request('/api/health')[1])['version'], VERSION)

    def test_network_boundaries(self):
        for host in ['127.0.0.1','192.168.1.100','10.1.2.3','172.18.0.2','::1','fd00::1']:
            self.assertTrue(private_ip(host), host)
        for host in ['8.8.8.8','1.1.1.1','100.64.0.1','not-an-ip']:
            self.assertFalse(private_ip(host), host)
        self.assertTrue(allowed_host('nas.local'))
        self.assertFalse(allowed_host('attacker.example'))

class FeedTests(unittest.TestCase):
    FORECAST = {
        'timezone': 'Europe/London',
        'current': {'time': '2026-11-03T10:00', 'temperature_2m': 12.3, 'apparent_temperature': 10.1, 'relative_humidity_2m': 80,
                    'weather_code': 61, 'is_day': 1, 'wind_speed_10m': 11, 'precipitation': 0.4},
        'hourly': {'time': [f'2026-11-03T{h:02d}:00' for h in range(24)], 'temperature_2m': list(range(24)),
                   'weather_code': [3] * 24, 'precipitation_probability': [50] * 24, 'is_day': [1] * 24},
        'daily': {'time': ['2026-11-03', '2026-11-04'], 'weather_code': [61, 0], 'temperature_2m_max': [14, 15], 'temperature_2m_min': [7, 6],
                  'sunrise': ['2026-11-03T06:58', '2026-11-04T07:00'], 'sunset': ['2026-11-03T16:32', '2026-11-04T16:30'],
                  'precipitation_probability_max': [80, 0]},
    }

    def test_weather_is_shaped_and_cached(self):
        feeds = Feeds()
        with patch.object(feeds_module, 'get_json', return_value=self.FORECAST) as get:
            w = feeds.weather({'name': 'London', 'lat': 51.5, 'lon': -0.12})
            feeds.weather({'name': 'London', 'lat': 51.5, 'lon': -0.12})
        self.assertEqual(get.call_count, 1)
        self.assertEqual(w['current']['code'], 61)
        self.assertEqual(w['timezone'], 'Europe/London')
        self.assertEqual(w['hours'][0]['time'], '2026-11-03T10:00')
        self.assertEqual(len(w['hours']), 12)
        self.assertEqual(w['days'][1]['max'], 15)
        # Upstream failure later serves the cached copy instead of an error.
        feeds.cache.items = {k: (0, v) for k, (_, v) in feeds.cache.items.items()}
        with patch.object(feeds_module, 'get_json', side_effect=FeedError('offline')):
            self.assertEqual(feeds.weather({'name': 'London', 'lat': 51.5, 'lon': -0.12})['current']['temp'], 12.3)

    def test_github_lists_and_reports_errors(self):
        repo = {'name': 'null_gate', 'full_name': 'octocat/null_gate', 'html_url': 'https://github.com/octocat/null_gate', 'stargazers_count': 3,
                'created_at': '2026-10-28T00:00:00Z', 'owner': {'login': 'octocat'}}
        def fake(url, headers=None):
            if '/search/' in url:
                raise FeedError('rate limited')
            self.assertIn('/users/octocat/repos', url)
            self.assertEqual(headers.get('Authorization'), 'Bearer tok')
            return [repo]
        with patch.object(feeds_module, 'get_json', side_effect=fake):
            out = Feeds(lambda: 'tok').github('octocat')
        self.assertEqual(out['mine'][0]['full'], 'octocat/null_gate')
        self.assertEqual(out['trending'], [])
        self.assertEqual(out['errors'], ['rate limited'])

    def test_overview_layout_and_clock_theme(self):
        state = initial()
        self.assertEqual(state['widgets'], [])
        self.assertEqual(state['settings']['clockTheme'], 'neon')
        state['widgets'] = [{'id': 'clock', 'w': 4, 'h': 9}, {'id': 'cat:media', 'w': 12, 'h': 6, 'hidden': True}]
        state['settings']['clockTheme'] = 'retro'
        clean = validate(state)
        self.assertEqual(clean['widgets'][1], {'id': 'cat:media', 'w': 12, 'h': 6, 'hidden': True})
        self.assertEqual(clean['settings']['clockTheme'], 'retro')
        state['settings']['clockTheme'] = 'nope'
        self.assertEqual(validate(state)['settings']['clockTheme'], 'neon')
        for bad in ([{'id': 'clock', 'w': 13, 'h': 2}], [{'id': 'evil<script>', 'w': 2, 'h': 2}], [{'id': 'clock', 'w': 2, 'h': 2}] * 2):
            state['widgets'] = bad
            with self.assertRaises(ValueError):
                validate(state)

    def test_quick_lights_and_clock_format(self):
        state = initial()
        self.assertEqual(state['home']['quick'], [])
        self.assertTrue(state['settings']['clock24'])
        state['home']['quick'] = ['light.office', 'switch.desk_plug']
        state['settings']['clock24'] = False
        clean = validate(state)
        self.assertEqual(clean['home']['quick'], ['light.office', 'switch.desk_plug'])
        self.assertFalse(clean['settings']['clock24'])
        state['home']['quick'] = [f'light.l{i}' for i in range(13)]
        with self.assertRaises(ValueError):
            validate(state)

    def test_settings_validate_weather_and_github_user(self):
        state = initial()
        self.assertEqual(state['settings']['weather']['name'], 'London')
        self.assertEqual(state['settings']['githubUser'], '')
        for bad in [{'name': 'X', 'lat': 200, 'lon': 0}, {'name': 'X', 'lat': True, 'lon': 0}, 'London']:
            state = initial()
            state['settings']['weather'] = bad
            with self.assertRaises(ValueError):
                validate(state)
        state = initial()
        state['settings']['githubUser'] = 'bad user/../'
        with self.assertRaises(ValueError):
            validate(state)


class UpdateTests(unittest.TestCase):
    def test_only_semantic_release_versions(self):
        self.assertGreater(version_tuple('v1.10.0'), version_tuple('1.9.0'))
        for value in ['main','v1.0.0; rm -rf /','1.0','../v1.0.0']:
            with self.assertRaises(ValueError):
                version_tuple(value)

    def test_update_disabled_without_supervisor(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(folder)
            updater = Updater(Path(__file__).resolve().parents[1], store)
            with patch.dict(os.environ, {'INSTALL_METHOD':'manual', 'NULL_GATE_SUPERVISED':''}):
                self.assertFalse(updater.start())
                self.assertIn('Docker', updater.status()['error'])

    def test_automatic_updates(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(folder)
            updater = Updater(Path(__file__).resolve().parents[1], store)
            updater.current = '2.0.0'
            def fake_check():
                updater.latest = '2.1.0'
                return updater.status()
            with patch.object(updater, 'capability', return_value=(True, '')), \
                    patch.object(updater, 'check', side_effect=fake_check) as check, \
                    patch.object(updater, 'start', return_value=True) as start:
                # On by default: a newer release is installed.
                self.assertTrue(updater.status()['auto'])
                self.assertTrue(updater.auto_tick())
                start.assert_called_once()
                # A version that already failed and was rolled back is not retried.
                (Path(folder) / 'update-result.json').write_text(json.dumps({'status': 'rolled_back', 'version': '2.1.0'}))
                self.assertFalse(updater.auto_tick())
                self.assertEqual(start.call_count, 1)
                # Turned off in settings: no check at all.
                state = store.read()
                state['settings']['autoUpdate'] = False
                store.save(state)
                check.reset_mock()
                self.assertFalse(updater.auto_tick())
                check.assert_not_called()
                self.assertFalse(updater.status()['auto'])
            # Never runs outside the supervised Docker install.
            with patch.dict(os.environ, {'INSTALL_METHOD': 'manual', 'NULL_GATE_SUPERVISED': ''}):
                self.assertFalse(updater.auto_tick())

    def test_github_token_is_private_and_used(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(folder)
            updater = Updater(Path(__file__).resolve().parents[1], store)
            token = 'github_pat_' + 'A1b2' * 10
            self.assertEqual(updater._auth_config(), [])
            with self.assertRaises(ValueError):
                updater.set_token({'token': 'not a token!'})
            with patch.object(updater, '_api', return_value={'tag_name': 'v9.0.0'}) as api:
                status = updater.set_token({'token': token})
            self.assertTrue(status['hasToken'])
            self.assertNotIn(token, json.dumps(status))
            self.assertEqual(oct((Path(folder) / 'github.json').stat().st_mode & 0o777), '0o600')
            self.assertIn('extraheader', updater._auth_config()[1])
            self.assertNotIn(token, json.dumps(store.read()))
            # A token GitHub rejects is not saved.
            with patch.object(updater, '_api', side_effect=RuntimeError('GitHub rejected the token.')):
                with self.assertRaises(ValueError):
                    updater.set_token({'token': 'github_pat_' + 'Z9' * 15})
            self.assertEqual(updater.token(), token)
            self.assertFalse(updater.set_token({'remove': True})['hasToken'])

    def test_failed_validation_preserves_checkout(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL).decode().strip()
            git('init', '-b', 'main')
            git('config', 'user.name', 'Test')
            git('config', 'user.email', 'test@example.invalid')
            (root/'app').mkdir()
            (root/'app/VERSION').write_text('1.0.0')
            git('add', '.')
            git('commit', '-m', 'initial')
            before=git('rev-parse','HEAD')
            git('remote', 'add', 'origin', 'https://github.com/bhxuk/null_gate.git')
            store=Store(root/'data')
            updater=Updater(root,store)
            updater.latest='1.1.0'
            updater.lock.acquire()
            # Fetch fails before merge. Network-free test of the failure path.
            original_git=updater.git
            def fail_fetch(*args, **kwargs):
                if args[0]=='status':return ''
                if args[0]=='fetch':raise RuntimeError('offline')
                return original_git(*args,**kwargs)
            updater.git=fail_fetch
            updater._run()
            self.assertEqual(updater.state, 'error')
            self.assertEqual(git('rev-parse','HEAD'),before)
            self.assertFalse((store.root/'update-pending.json').exists())

    def test_supervisor_rolls_code_back_and_keeps_dashboard(self):
        path=Path(__file__).resolve().parents[1]/'scripts/supervisor.py'
        spec=importlib.util.spec_from_file_location('supervisor_test',path)
        mod=importlib.util.module_from_spec(spec)
        # Imports must not alter the test runner's signal handlers.
        with patch('signal.signal'):
            spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as folder:
            mod.data=Path(folder)
            saved=mod.data/'dashboard.json'
            saved.write_text('{"notes":"keep this"}')
            pending={'before':'abc123','version':'1.1.0','backup':'snapshot.json'}
            with patch.object(mod.subprocess,'run') as run:
                run.return_value.returncode=0
                mod.rollback(pending)
                self.assertEqual(run.call_args.args[0][-3:],['reset','--hard','abc123'])
            self.assertEqual(saved.read_text(),'{"notes":"keep this"}')
            self.assertEqual(json.loads((mod.data/'update-result.json').read_text())['status'],'rolled_back')

if __name__ == '__main__':
    unittest.main()
