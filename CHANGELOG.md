# Changelog

All notable changes to null_gate are listed here. Versions follow [semantic versioning](https://semver.org/).
Each release is published on [GitHub Releases](https://github.com/bhxuk/null_gate/releases), and installs pick it up automatically.

## [1.0.1] - 2026-11-04

- **The installer now finds a free port.** It checks which ports are already used by other services and Docker containers, then lets you pick from a short list of free, easy-to-remember ports (4242, 7777, 3141…), type your own, or press Enter for the first one. This fixes installs failing with "port is already allocated" when 8088 was taken.
- Run `bash install.sh` again at any time to change the port. Your data and settings are kept.
- Set `NULL_GATE_PORT=8090 bash install.sh` to skip the question.

## [1.0.0] - 2026-11-04

First public release of null_gate, a self-hosted dashboard for your local network. Designed by [bhxuk.com](https://bhxuk.com).

### Dashboard
- Customisable overview built from tiles: greeting, clock, weather, daily quote, smart home, Favourites, each category and GitHub. Drag to move, drag the corner to resize, hide or add tiles. The layout is saved on your server.
- Live clock with six themes (Neon, Minimal, Widget, Retro LED, Flip, Analog), 12h/24h, optional seconds, fullscreen wall-clock mode, a daylight bar and up to four world clocks.
- Live weather with an animated sky, hourly and 6-day forecast. Change the town from the weather tile. No API key needed (Open-Meteo).
- Dark and light themes, six accent colours and three backgrounds. Scroll bars stay hidden; everything still scrolls.

### Links and apps
- Add, edit, pin, categorise, search and sort your links. Drag and drop between sections, Favourites and categories.
- Four layouts: Compact, Cards, Table and an Android TV-style launcher with keyboard navigation.
- Bulk import from pasted lists, CSV/TSV, Markdown, `.url`, `.webloc` and browser bookmark exports, with a review step that flags duplicates.
- Homelab starter: one-click shortcuts for Plex, the *arr apps, qBittorrent, Seerr, Tautulli, Home Assistant, Portainer, Glances and more, with editable ports.
- Optional `data/links.txt` file: links listed there are added on startup, once each.
- Preview panel with descriptions, your own preview images and optional live embeds.

### Smart home
- Home Assistant bridge: status chips, room cards, quick lights in the top bar and full controls for lights, speakers, Chromecasts, thermostats, plugs, sensors and scenes.
- Camera snapshots and a full-screen live view.
- The Home Assistant token stays on your server; a narrow allow-list of actions only (locks and alarms are read-only).

### Running it
- One Docker container, one Python service, no third-party Python packages and no frontend build step.
- Interactive installer for SSH sessions: detects your LAN address, user and time zone, then builds and starts the container.
- Automatic updates from GitHub releases with validation, a snapshot first and automatic rollback if the new version fails to start.
- Export/import backups and server snapshots; conflict detection across browser tabs.
- LAN-only by design: binds to your LAN address, checks Host/Origin on writes and rejects public clients.
