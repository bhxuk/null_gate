# Contributing to null_gate

Thanks for helping. Bug reports, ideas and pull requests are welcome.

## Before you open a pull request

Run the checks CI runs:

```bash
python3 -m unittest discover -s tests -v
for f in app/static/js/*.js docs/site.js; do node --check "$f"; done
node --test tests/importer.test.mjs
bash -n install.sh
```

## Ground rules

- **No new runtime dependencies.** The backend uses the Python standard library only and the frontend has no build step.
- **Keep data backwards compatible.** `dashboard.json` stays at schema 1 so an automatic rollback to an older release can still read it. New fields must be optional with sensible defaults.
- **LAN-only by design.** Do not add features that expose null_gate to the internet or weaken the Host/Origin checks.
- **Smart home goes through Home Assistant.** Keep the action allow-list in `app/homeassistant.py` narrow (no locks, alarms or arbitrary services).
- **Never log or return tokens** (`data/homeassistant.json`, `data/github.json`).

## Releases

Every release bumps `app/VERSION` and adds a matching `## [x.y.z] - YYYY-MM-DD` entry to `CHANGELOG.md`. When `main` builds successfully, GitHub Actions tests the app, builds the Docker image, publishes `ghcr.io/bhxuk/null_gate`, creates the GitHub release and deploys the website. Installs pick the release up automatically.

Changes to `scripts/supervisor.py`, the `Dockerfile` or the runtime need a manual rebuild by users; say so in the release notes.
