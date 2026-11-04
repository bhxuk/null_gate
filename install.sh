#!/usr/bin/env bash
# null_gate installer. Run from the cloned repository: bash install.sh
set -euo pipefail

if [ -t 1 ]; then C=$'\e[36m'; M=$'\e[2m'; B=$'\e[1m'; G=$'\e[32m'; R=$'\e[0m'; else C=''; M=''; B=''; G=''; R=''; fi

cat <<BANNER

${C}  ▦  ${B}null_gate${R}${C}  ▌${R}
${M}  ─────────────────────────────────────────────${R}
  Your links, apps and smart home in one place.
  Designed by ${B}bhxuk.com${R}  ·  github.com/bhxuk/null_gate
${M}  ─────────────────────────────────────────────${R}

BANNER

step() { printf '%s›%s %s\n' "$C" "$R" "$1"; }
fail() { printf '\n  %s\n\n' "$1" >&2; exit 1; }

step 'Checking Docker, Compose and Git'
command -v docker >/dev/null || fail 'Install Docker Engine and Docker Compose first: https://docs.docker.com/engine/install/'
docker compose version >/dev/null 2>&1 || fail 'Docker Compose v2 is missing. Install the docker-compose-plugin package.'
command -v git >/dev/null || fail 'Install git first (for example: sudo apt install git).'

cd "$(dirname "$(realpath "$0")")"
mkdir -p data

if [ ! -f .env ]; then
  step 'Creating .env'
  cp .env.example .env
  address="${LAN_IP:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
  [ -n "$address" ] || fail 'Could not detect a LAN address. Set LAN_IP in .env and run this again.'
  zone="${TZ:-$(timedatectl show -p Timezone --value 2>/dev/null || cat /etc/timezone 2>/dev/null || echo UTC)}"
  sed -i "s|^LAN_IP=.*|LAN_IP=$address|;s|^PUID=.*|PUID=$(id -u)|;s|^PGID=.*|PGID=$(id -g)|;s|^TZ=.*|TZ=${zone:-UTC}|" .env
else
  step 'Keeping your existing .env'
fi

step 'Building and starting the container (the first build takes a minute)'
docker compose up -d --build

ip=$(awk -F= '/^LAN_IP=/{print $2}' .env)
port=$(awk -F= '/^NULL_GATE_PORT=/{print $2}' .env)

cat <<DONE

${G}  ✓ null_gate is running${R}

    Open   ${B}http://${ip}:${port:-8088}${R}
    Data   $(pwd)/data
    Logs   docker compose logs -f null_gate

  Updates install automatically. Change that in Settings → Updates.

${M}  null_gate · designed by bhxuk.com${R}

DONE
