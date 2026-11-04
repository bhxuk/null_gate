# Changelog

All notable changes to null_gate are listed here. Versions follow [semantic versioning](https://semver.org/).
Each release is published on [GitHub Releases](https://github.com/bhxuk/null_gate/releases), and installs pick it up automatically.

## [1.0.2] - 2026-11-04

- The clock tile is shorter by default and lines up with the greeting next to it, with no empty space underneath.
- Seconds now sit on the same line as the hours and minutes instead of floating above them, in every clock theme.
- The changelog now includes the pre-release history.
- Already customised your overview? Your saved tile sizes are kept. Click **✎ Customise** and drag the clock's ◢ corner up to match.

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

## Pre-release history

null_gate grew out of a private homelab dashboard. These are the development releases that led to 1.0.0.

## [0.9.0] - 2026-11-03

- Customisable overview: every block is a tile (greeting, clock, weather, quote, smart home, Favourites, each category and GitHub). Click **✎ Customise**, drag a tile by ⠿ to move it, drag the ◢ corner to resize it, ✕ to hide it and **+ Add tile** to bring it back.
- Tiles with more content than fits scroll inside the tile, with a soft fade showing there's more.
- The clock scales with its tile, and details hide themselves when the tile is small.
- Six clock themes: Neon, Minimal, Widget, Retro LED, Flip and Analog. Tap 🎨 on the clock to cycle through them, or pick one in Settings → Appearance (12h/24h too).
- The layout is saved on the server, so it's the same on every device.

## [0.8.1] - 2026-11-03

- Hidden scroll bars on the page, the sidebar and scrolling rows. Everything still scrolls with the mouse wheel, touchpad or touch.
- The clock shows your weather town instead of the time zone's city when both are in the same time zone.

## [0.8.0] - 2026-11-03

- Live clock card: large time with rolling digits, glowing seconds, a seconds bar, a LIVE badge, a 12h/24h switch and a fullscreen wall-clock mode.
- Sunrise-to-sunset daylight bar showing where the sun is today.
- World clocks became cards with the time difference and day/night.
- Change the weather location straight from the weather card.
- Quick lights in the top bar on every page: pick up to 12 lights or switches with **+**, then tap to switch them. They glow in the bulb's colour when on.

## [0.7.0] - 2026-11-03

- Drag and drop links anywhere: reorder within a section, drop into Favourites to pin, drop into another category to move it, or drop onto a category or Favourites in the sidebar.
- Drop zones highlight while you drag, and an empty Favourites shows a drop area.
- Long icon text shrinks to fit inside the icon.

## [0.6.0] - 2026-11-03

- Live weather with an animated sky: sun, moon and stars, drifting clouds, rain, snow, fog and thunderstorms. Shows feels-like, high/low, humidity, wind, sunrise and sunset, the next 12 hours and 6 days. Powered by Open-Meteo, no API key.
- Analog clock with a sweeping second hand next to the digital time.
- Quote of the day, changing daily, with a button for another one.
- GitHub page: newest repositories for a username you choose and the most-starred new repositories this week, with a summary on the overview.
- Optional links file: links listed in a text file are added on startup, once each, so links you delete stay deleted.
- Optional GitHub token for update checks.
- Fixed link and device accent colours not showing.

## [0.5.0] - 2026-11-02

- Removed the Tasks panel so the overview uses the full width and every category shows all its links.
- Status chips on the overview and Smart home page: lights on (tap to switch them all off), average temperature and humidity, thermostat, what's playing, motion and open doors/windows.
- Room cards on the Smart home page with temperature, humidity, lights and media for each room, and one switch for all the room's lights.
- Quick actions moved into a compact button row under the greeting.
- Existing tasks and notes stay in the data file and backups.

## [0.4.0] - 2026-11-02

- Automatic updates: checks GitHub every hour, backs up your data, updates and rolls back by itself if the new version fails to start. Turn it off in Settings → Updates.
- With automatic updates off, a banner shows when an update is ready, with an **Update now** button.
- Open pages reload themselves after an update.
- Removed the Notes panel from the overview. Existing notes stay in backups and the data file.

## [0.3.0] - 2026-11-01

- Rebuilt from the ground up: modular JavaScript, a rewritten stylesheet and a tidier Python server. Same LAN-only Docker setup and no extra dependencies.
- Smart home through Home Assistant: lights with brightness, warmth and colour; Google Nest speakers, Nest Hubs and Chromecasts; thermostats; switches, plugs, fans, blinds, vacuums, scenes, scripts and sensors, grouped by room.
- Cameras view with live-refreshing snapshots and a full-screen live view.
- Pin any device with ★ to show it on the overview; hide devices you never use.
- The Home Assistant token stays on the server (owner-only file), is never sent to the browser and is not included in exports. Only a fixed list of safe actions can be sent; locks and alarms are read-only.
- New overview with greeting, quick actions, favourite devices, favourite links and every category at a glance.
- Server apps starter covers the common homelab: Plex, Sonarr, Radarr, Prowlarr, Bazarr, qBittorrent, Seerr, Tautulli, Home Assistant, Portainer, Glances and more, with editable ports.
- Search covers links and devices. Configurable world clocks. Categories can be renamed, re-iconed, reordered and deleted.
- Mobile layout with a slide-out menu.

## [0.2.0] - 2026-10-29

- Bulk-add links by pasting URLs, named lists, CSV/TSV or Markdown links.
- Import multiple `.url`, `.webloc`, text list and browser bookmark HTML files.
- Review and select links before import, with validation, duplicate detection, default categories and optional favourites.
- Compact default layout, a dense table/list view and a TV launcher with horizontal category shelves, arrow-key navigation and fullscreen.
- Switch layouts from the dashboard or Settings; the choice is saved across devices.

## [0.1.0] - 2026-10-29

- First working version: navy panels, cyan accents, sidebar navigation and responsive layouts.
- Clock and date, world clocks, search, categories, favourites, frequent and recent links.
- Link editing, custom icons and colours, preview images and optional embedded previews.
- Homelab starter pack with editable server address and app shortcuts.
- Drag-and-drop ordering, keyboard move controls, light/dark themes and backgrounds.
- JSON export/import and automatic backup before imports and updates.
- Server storage with conflict detection between tabs and same-origin write protection.
- Docker Compose deployment without Docker socket access, release checks and one-click updates with validation, backup and automatic rollback.
