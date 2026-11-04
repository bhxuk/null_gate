"""Validated, atomic on-disk dashboard storage. No third-party dependencies.

The file format stays at schema 1 so that an automatic code rollback to an
older release can still read data written by this one. New sections (``home``,
``settings.clocks``) are optional and default sensibly when missing.
"""
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

COLORS = ['#22d3ee', '#a78bfa', '#34d399', '#fbbf24', '#f472b6', '#60a5fa']
LAYOUTS = ('compact', 'cards', 'table', 'tv')
THEMES = ('dark', 'light')
BACKGROUNDS = ('aurora', 'plain', 'grid')
DEFAULT_CLOCKS = ['America/New_York', 'UTC', 'Asia/Tokyo']
CLOCK_THEMES = ('neon', 'minimal', 'widget', 'retro', 'flip', 'analog')
DEFAULT_PLACE = {'name': 'London', 'lat': 51.5074, 'lon': -0.1278}
ENTITY_ID = re.compile(r'^[a-z0-9_]+\.[a-z0-9_]+$')
IDENT = re.compile(r'^[a-zA-Z0-9_-]+$')
WIDGET_ID = re.compile(r'^(?:greeting|clock|weather|quote|devices|favourites|github|cat:[a-zA-Z0-9_-]{1,64})$')

MAX_LINKS, MAX_CATEGORIES, MAX_TASKS = 2000, 50, 100


def web_url(value, optional=False):
    if optional and not value:
        return ''
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError('URL is too long')
    try:
        parts = urlsplit(value)
        if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password \
                or any(ord(c) < 33 for c in value):
            raise ValueError()
        _ = parts.port
    except ValueError:
        raise ValueError('Use a complete http:// or https:// URL without credentials') from None
    return value


def text(value, limit=200):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f'Text must be at most {limit} characters')
    return value.strip()


def zone(value):
    value = text(value, 80)
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f'Unknown time zone: {value}') from None
    return value


def entity_list(value, limit=500):
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError('Too many smart home devices selected')
    out = []
    for item in value:
        if not isinstance(item, str) or not ENTITY_ID.fullmatch(item):
            raise ValueError('Invalid smart home device id')
        if item not in out:
            out.append(item)
    return out


def validate(raw):
    """Return a clean copy of ``raw`` or raise ValueError with a readable message."""
    if not isinstance(raw, dict) or raw.get('schema') != 1:
        raise ValueError('Not a null_gate backup (schema 1 required)')
    cats, links = raw.get('categories'), raw.get('links')
    if not isinstance(cats, list) or not 1 <= len(cats) <= MAX_CATEGORIES \
            or not isinstance(links, list) or len(links) > MAX_LINKS:
        raise ValueError(f'Use 1–{MAX_CATEGORIES} categories and no more than {MAX_LINKS:,} links')

    seen = set()

    def ident(value):
        value = text(value, 64)
        if not IDENT.fullmatch(value) or value in seen:
            raise ValueError('Each item needs a unique identifier')
        seen.add(value)
        return value

    categories = []
    for c in cats:
        if not isinstance(c, dict):
            raise ValueError('Invalid category')
        name = text(c.get('name'), 40)
        if not name:
            raise ValueError('Category name is required')
        categories.append({'id': ident(c.get('id')), 'name': name, 'icon': text(c.get('icon', '◈'), 8)})
    category_ids = {c['id'] for c in categories}

    clean_links = []
    for link in links:
        if not isinstance(link, dict) or link.get('category') not in category_ids:
            raise ValueError('Every link must belong to an existing category')
        name = text(link.get('name'), 80)
        if not name:
            raise ValueError('Link name is required')
        color = link.get('color', COLORS[0])
        if color not in COLORS:
            raise ValueError('Choose one of the available colours')
        clean_links.append({
            'id': ident(link.get('id')), 'name': name, 'url': web_url(link.get('url')),
            'description': text(link.get('description', ''), 500), 'category': link['category'],
            'icon': text(link.get('icon', ''), 8), 'image': web_url(link.get('image', ''), optional=True),
            'color': color, 'pinned': bool(link.get('pinned', False)),
            'visits': max(0, min(int(link.get('visits', 0)), 1_000_000_000)),
            'lastVisited': max(0, min(float(link.get('lastVisited', 0)), 1e13)),
        })

    s = raw.get('settings', {})
    if not isinstance(s, dict):
        raise ValueError('Invalid settings')
    if s.get('theme', 'dark') not in THEMES or s.get('background', 'aurora') not in BACKGROUNDS:
        raise ValueError('Invalid theme or background')
    layout = s.get('layout', 'compact')
    if layout not in LAYOUTS:
        raise ValueError('Choose cards, compact, table or TV layout')
    clocks = s.get('clocks', DEFAULT_CLOCKS)
    if not isinstance(clocks, list) or len(clocks) > 4:
        raise ValueError('Use up to four world clocks')
    clocks = [zone(c) for c in clocks]
    place = s.get('weather', DEFAULT_PLACE)
    if not isinstance(place, dict):
        raise ValueError('Invalid weather location')
    lat, lon = place.get('lat'), place.get('lon')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (lat, lon)) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('Invalid weather location')
    place = {'name': text(place.get('name', ''), 80) or 'Weather', 'lat': float(lat), 'lon': float(lon)}
    github_user = text(s.get('githubUser', ''), 39)
    if github_user and not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})', github_user):
        raise ValueError('Invalid GitHub username')

    tasks = raw.get('tasks', [])
    if not isinstance(tasks, list) or len(tasks) > MAX_TASKS:
        raise ValueError(f'Use no more than {MAX_TASKS} tasks')
    clean_tasks = []
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError('Invalid task')
        clean_tasks.append({'id': ident(task.get('id')), 'text': text(task.get('text'), 200), 'done': bool(task.get('done'))})

    widgets = raw.get('widgets', [])
    if not isinstance(widgets, list) or len(widgets) > 120:
        raise ValueError('Invalid overview layout')
    clean_widgets, widget_ids = [], set()
    for w in widgets:
        if not isinstance(w, dict) or not isinstance(w.get('id'), str) or not WIDGET_ID.fullmatch(w['id']) or w['id'] in widget_ids:
            raise ValueError('Invalid overview tile')
        size = [w.get('w'), w.get('h')]
        if any(isinstance(v, bool) or not isinstance(v, int) for v in size) or not 1 <= size[0] <= 12 or not 1 <= size[1] <= 30:
            raise ValueError('Invalid overview tile size')
        widget_ids.add(w['id'])
        clean_widgets.append({'id': w['id'], 'w': size[0], 'h': size[1], 'hidden': bool(w.get('hidden', False))})

    synced = raw.get('synced', [])
    if not isinstance(synced, list) or len(synced) > 5000 or not all(isinstance(x, str) and len(x) <= 2048 for x in synced):
        raise ValueError('Invalid synced link list')

    home = raw.get('home', {})
    if not isinstance(home, dict):
        raise ValueError('Invalid smart home settings')
    interval = home.get('cameraInterval', 10)
    if isinstance(interval, bool) or not isinstance(interval, (int, float)) or not 2 <= interval <= 300:
        raise ValueError('Camera refresh must be between 2 and 300 seconds')

    return {
        'schema': 1, 'categories': categories, 'links': clean_links,
        'notes': text(raw.get('notes', ''), 20000), 'tasks': clean_tasks,
        'settings': {
            'name': text(s.get('name', 'My dashboard'), 60), 'timezone': zone(s.get('timezone', 'Europe/London')),
            'theme': s.get('theme', 'dark'), 'background': s.get('background', 'aurora'),
            'accent': s.get('accent') if s.get('accent') in COLORS else COLORS[0],
            'layout': layout, 'compact': layout == 'compact', 'seconds': bool(s.get('seconds', False)),
            'clocks': clocks, 'autoUpdate': bool(s.get('autoUpdate', True)),
            'weather': place, 'githubUser': github_user, 'clock24': bool(s.get('clock24', True)),
            'clockTheme': s.get('clockTheme') if s.get('clockTheme') in CLOCK_THEMES else 'neon',
        },
        'synced': sorted(set(synced)),
        'widgets': clean_widgets,
        'home': {
            'favourites': entity_list(home.get('favourites', [])),
            'hidden': entity_list(home.get('hidden', [])),
            'quick': entity_list(home.get('quick', []), 12),
            'cameraInterval': int(interval),
        },
    }


def initial():
    categories = [{'id': 'everyday', 'name': 'Everyday', 'icon': '◈'}, {'id': 'homelab', 'name': 'Homelab', 'icon': '▣'},
                  {'id': 'work', 'name': 'Work', 'icon': '▤'}, {'id': 'tools', 'name': 'Tools', 'icon': '⌘'}]
    items = [('GitHub', 'https://github.com', 'Your repositories and projects.', 'everyday', 'GH', True),
             ('YouTube', 'https://www.youtube.com', 'Watch something worth your time.', 'everyday', '▶', True),
             ('Outlook', 'https://outlook.office.com', 'Email, calendar and the daily essentials.', 'work', 'O', True),
             ('Notion', 'https://www.notion.so', 'Notes, projects and a place for your ideas.', 'work', 'N', False),
             ('CyberChef', 'https://gchq.github.io/CyberChef/', 'Encode, decode and transform data.', 'tools', '⌘', False),
             ('Regex101', 'https://regex101.com', 'Build and test regular expressions.', 'tools', '.*', False)]
    links = [dict(id=uuid.uuid4().hex, name=n, url=u, description=d, category=c, icon=i, pinned=p, color=COLORS[k % 6])
             for k, (n, u, d, c, i, p) in enumerate(items)]
    return validate({'schema': 1, 'categories': categories, 'links': links, 'settings': {}, 'notes': '', 'tasks': []})


def link_key(url):
    """Compare URLs loosely: case-insensitive scheme/host and no trailing slash."""
    return url.strip().rstrip('/').lower()


def parse_links_file(text):
    """Parse ``Name | URL | Category | Description`` lines. A leading * pins the link."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = [p.strip() for p in line.split('|')]
        if len(parts) == 1:
            parts = ['', parts[0]]
        name, url = parts[0], parts[1]
        pinned = name.startswith('*')
        name = name.lstrip('*').strip()
        try:
            web_url(url)
        except ValueError:
            print(f'links.txt: skipped invalid line: {line[:120]}', flush=True)
            continue
        rows.append({'name': (name or urlsplit(url).hostname)[:80], 'url': url,
                     'category': (parts[2] if len(parts) > 2 else '')[:40] or 'Links',
                     'description': (parts[3] if len(parts) > 3 else '')[:500], 'pinned': pinned})
    return rows


class Conflict(Exception):
    pass


class Store:
    def __init__(self, directory):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'dashboard.json'
        self.lock = threading.RLock()
        if not self.path.exists():
            self._write(dict(initial(), revision=1))
        # Fail clearly on corrupt storage; never silently replace user data.
        validate(self.read())

    def _write(self, state):
        temp = self.path.with_suffix('.tmp')
        with temp.open('w') as f:
            json.dump(state, f, ensure_ascii=False, allow_nan=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, self.path)

    def read(self):
        with self.lock:
            raw = json.loads(self.path.read_text())
        # Fill in sections added after the file was written, without rewriting it.
        clean = validate(raw)
        clean['revision'] = raw.get('revision', 1)
        return clean

    def save(self, raw):
        clean = validate(raw)
        with self.lock:
            current = self.read()
            if raw.get('revision') != current['revision']:
                raise Conflict('Dashboard changed in another tab. Reload to get the latest version.')
            # Keep visit counters recorded while the editor was open.
            by_id = {x['id']: x for x in current['links']}
            for item in clean['links']:
                old = by_id.get(item['id'])
                if old:
                    item['visits'] = max(item['visits'], old['visits'])
                    item['lastVisited'] = max(item['lastVisited'], old['lastVisited'])
            clean['revision'] = current['revision'] + 1
            self._write(clean)
            return clean

    def visit(self, link_id):
        with self.lock:
            state = json.loads(self.path.read_text())
            link = next((x for x in state['links'] if x['id'] == link_id), None)
            if not link:
                raise ValueError('Link not found')
            link['visits'] = link.get('visits', 0) + 1
            link['lastVisited'] = time.time() * 1000
            self._write(state)
            return {'visits': link['visits'], 'lastVisited': link['lastVisited']}

    def sync_links(self, path):
        """Add links from ``links.txt`` in the data folder.

        Each URL is added once. If you delete it in null_gate it is remembered and not
        added again, so the dashboard stays yours to edit.
        """
        path = Path(path)
        if not path.is_file():
            return 0
        rows = parse_links_file(path.read_text(encoding='utf-8-sig'))
        with self.lock:
            state = self.read()
            synced = set(state['synced'])
            present = {link_key(l['url']) for l in state['links']}
            added = 0
            for i, row in enumerate(rows):
                key = link_key(row['url'])
                if key in synced:
                    continue
                synced.add(key)
                if key in present or len(state['links']) >= MAX_LINKS:
                    continue
                category = next((c for c in state['categories'] if c['name'].lower() == row['category'].lower()), None)
                if not category:
                    if len(state['categories']) >= MAX_CATEGORIES:
                        category = state['categories'][0]
                    else:
                        category = {'id': uuid.uuid4().hex, 'name': row['category'], 'icon': '◈'}
                        state['categories'].append(category)
                state['links'].append({'id': uuid.uuid4().hex, 'name': row['name'], 'url': row['url'],
                    'description': row['description'], 'category': category['id'], 'icon': '', 'image': '',
                    'color': COLORS[(len(state['links']) + i) % len(COLORS)], 'pinned': row['pinned'],
                    'visits': 0, 'lastVisited': 0})
                present.add(key)
                added += 1
            if synced != set(state['synced']):
                state['synced'] = sorted(synced)
                clean = validate(state)
                clean['revision'] = state['revision'] + 1
                self._write(clean)
            return added

    def backup(self):
        with self.lock:
            folder = self.root / 'backups'
            folder.mkdir(exist_ok=True)
            name = time.strftime('dashboard-%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6] + '.json'
            (folder / name).write_text(self.path.read_text())
            return name
