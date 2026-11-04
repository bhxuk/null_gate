#!/usr/bin/env bash
# null_gate installer. Run from the cloned repository: bash install.sh
# Skip the port question with: NULL_GATE_PORT=8090 bash install.sh
set -euo pipefail

if [ -t 1 ]; then C=$'\e[36m'; M=$'\e[2m'; B=$'\e[1m'; G=$'\e[32m'; Y=$'\e[33m'; R=$'\e[0m'; else C=''; M=''; B=''; G=''; Y=''; R=''; fi

cat <<BANNER

${C}  ▦  ${B}null_gate${R}${C}  ▌${R}
${M}  ─────────────────────────────────────────────${R}
  Your links, apps and smart home in one place.
  Designed by ${B}bhxuk.com${R}  ·  github.com/bhxuk/null_gate
${M}  ─────────────────────────────────────────────${R}

BANNER

step() { printf '%s›%s %s\n' "$C" "$R" "$1"; }
fail() { printf '\n  %s\n\n' "$1" >&2; exit 1; }
setenv() { sed -i "s|^$1=.*|$1=$2|" .env; grep -q "^$1=" .env || echo "$1=$2" >> .env; }

# ---- ports -----------------------------------------------------------------
# Memorable ports to offer, with a short note each. Only free ones are shown.
CANDIDATES=(
  '8088:the classic'
  '1337:leet'
  '4242:the answer, twice'
  '7777:lucky sevens'
  '3141:pi'
  '8484:easy to type'
  '6060:clean and round'
  '5050:fifty-fifty'
  '9999:all nines'
  '2112:a good year'
  '8800:double eight hundred'
  '4040:not found, but found'
)

# Ports in use: anything listening on this host, plus ports Docker publishes.
used_ports() {
  {
    if command -v ss >/dev/null; then ss -Hltn 2>/dev/null | awk '{print $4}'
    elif command -v netstat >/dev/null; then netstat -ltn 2>/dev/null | awk 'NR>2 {print $4}'
    fi
    docker ps --format '{{.Ports}}' 2>/dev/null | tr ',' '\n'
  } | grep -oE ':[0-9]+(->|$| )' | grep -oE '[0-9]+' | sort -un
}

port_free() { ! grep -qx "$1" <<<"$USED"; }

valid_port() { [[ "$1" =~ ^[0-9]+$ ]] && [ "$1" -ge 1024 ] && [ "$1" -le 65535 ]; }

pick_port() {
  local current=$1 free=() line port note i choice
  for line in "${CANDIDATES[@]}"; do
    port=${line%%:*}
    port_free "$port" && free+=("$line")
    [ ${#free[@]} -ge 6 ] && break
  done
  # Fall back to the first free port above 8088 if every favourite is taken.
  if [ ${#free[@]} -eq 0 ]; then
    port=8089; while ! port_free "$port"; do port=$((port + 1)); done
    free+=("$port:next free port")
  fi

  # Not interactive (piped install, CI): take the first free suggestion.
  if [ -z "${TTY_IN:-}" ] && [ ! -t 0 ] && [ ! -e /dev/tty ]; then
    PICKED=${free[0]%%:*}; return
  fi

  if port_free "$current"; then
    printf '\n  Port %s%s%s is free. Pick it or choose another:\n\n' "$B" "$current" "$R"
  else
    printf '\n  %sPort %s is already in use%s on this server. Pick a free one:\n\n' "$Y" "$current" "$R"
  fi
  i=1
  for line in "${free[@]}"; do
    printf '    %s%d)%s  %s%-5s%s  %s%s%s\n' "$C" "$i" "$R" "$B" "${line%%:*}" "$R" "$M" "${line#*:}" "$R"
    i=$((i + 1))
  done
  printf '    %sc)%s  custom port\n\n' "$C" "$R"

  local default=${free[0]%%:*}
  port_free "$current" && default=$current
  # Read answers from the terminal even when the script itself is piped in.
  if ! exec 3<"${TTY_IN:-/dev/tty}"; then PICKED=$default; return; fi
  while true; do
    printf '  Choice [Enter = %s]: ' "$default"
    if ! read -r -u 3 choice; then echo; PICKED=$default; exec 3<&-; return; fi
    case "$choice" in
      '') PICKED=$default; exec 3<&-; return ;;
      c|C)
        printf '  Port (1024-65535): '
        read -r -u 3 port || port=''
        if ! valid_port "$port"; then echo "  ${Y}Use a number from 1024 to 65535.${R}"
        elif ! port_free "$port"; then echo "  ${Y}Port $port is in use. Try another.${R}"
        else PICKED=$port; exec 3<&-; return; fi ;;
      *)
        if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le ${#free[@]} ]; then
          PICKED=${free[$((choice - 1))]%%:*}; exec 3<&-; return
        elif valid_port "$choice" && port_free "$choice"; then
          PICKED=$choice; exec 3<&-; return
        fi
        echo "  ${Y}Pick a number from the list, c, or a free port.${R}" ;;
    esac
  done
}

# Allow sourcing for tests without running the installer.
[ "${NULL_GATE_INSTALL_LIB:-}" = 1 ] && return 0

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
  setenv LAN_IP "$address"; setenv PUID "$(id -u)"; setenv PGID "$(id -g)"; setenv TZ "${zone:-UTC}"
  fresh=1
else
  step 'Keeping your existing .env'
  fresh=0
fi

step 'Looking for a free port'
current=$(awk -F= '/^NULL_GATE_PORT=/{print $2}' .env); current=${current:-8088}
# If null_gate is already running, its own port counts as free.
docker compose stop null_gate >/dev/null 2>&1 || true
USED=$(used_ports)
if [ -n "${NULL_GATE_PORT:-}" ]; then
  valid_port "$NULL_GATE_PORT" || fail "NULL_GATE_PORT must be a number from 1024 to 65535."
  port_free "$NULL_GATE_PORT" || fail "Port $NULL_GATE_PORT is already in use. Pick another or run without NULL_GATE_PORT to choose from a list."
  PICKED=$NULL_GATE_PORT
elif [ "$fresh" = 0 ] && port_free "$current"; then
  PICKED=$current
else
  pick_port "$current"
fi
setenv NULL_GATE_PORT "$PICKED"
printf '  Using port %s%s%s\n\n' "$B" "$PICKED" "$R"

step 'Building and starting the container (the first build takes a minute)'
docker compose up -d --build

ip=$(awk -F= '/^LAN_IP=/{print $2}' .env)

cat <<DONE

${G}  ✓ null_gate is running${R}

    Open   ${B}http://${ip}:${PICKED}${R}
    Data   $(pwd)/data
    Logs   docker compose logs -f null_gate

  Updates install automatically. Change that in Settings → Updates.
  Change the port any time: bash install.sh again, or edit NULL_GATE_PORT in .env.

${M}  null_gate · designed by bhxuk.com${R}

DONE
