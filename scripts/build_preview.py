"""Build a browser-only preview of the real frontend into ./preview (not committed).

The preview answers every API call in the browser with sample data (app/static/js/demo.js),
so you can try layouts or take screenshots without a server:

    python scripts/build_preview.py
    python -m http.server 8099 -d preview
"""
import json
import shutil
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from app.store import initial, COLORS


def build(out=root / 'preview'):
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(root / 'app/static', out)
    html = (out / 'index.html').read_text(encoding='utf-8').replace('<html lang="en">', '<html lang="en" data-demo="true">')
    (out / 'index.html').write_text(html, encoding='utf-8')
    shutil.copyfile(root / 'CHANGELOG.md', out / 'CHANGELOG.md')
    seed = initial()
    # Stable IDs keep the preview reproducible.
    for i, link in enumerate(seed['links']):
        link['id'] = f'preview-link-{i}'
    seed['links'] += [
        {'id': 'preview-plex', 'name': 'Plex', 'url': 'https://app.plex.tv', 'description': 'Your movies, TV and music, ready to play.', 'category': 'homelab', 'icon': '▶', 'color': COLORS[3], 'pinned': True, 'image': '', 'visits': 24, 'lastVisited': 1793228400000},
        {'id': 'preview-glances', 'name': 'Glances', 'url': 'https://nicolargo.github.io/glances/', 'description': 'Your server, at a glance.', 'category': 'homelab', 'icon': '>_', 'color': COLORS[0], 'pinned': True, 'image': '', 'visits': 12, 'lastVisited': 1793224800000},
        {'id': 'preview-sonarr', 'name': 'Sonarr', 'url': 'https://sonarr.tv', 'description': 'Keep up with your favourite series.', 'category': 'homelab', 'icon': 'S', 'color': COLORS[4], 'pinned': False, 'image': '', 'visits': 8, 'lastVisited': 1793221200000},
    ]
    seed['links'] = seed['links'][-3:] + seed['links'][:-3]
    seed['home']['favourites'] = ['camera.front_door', 'light.living_room_lamp', 'media_player.living_room_speaker', 'climate.thermostat']
    seed['home']['quick'] = ['light.living_room_lamp', 'light.living_room_ceiling', 'light.bedroom_bulb', 'switch.desk_plug']
    seed['revision'] = 1
    (out / 'seed.json').write_text(json.dumps(seed, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Built {out.relative_to(root)} from app/static')


if __name__ == '__main__':
    build()
