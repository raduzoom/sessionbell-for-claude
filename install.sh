#!/bin/bash
# Sessionbell: start the scanner (every scanEverySeconds from config.json) and the server (always on) at login.
#
#   ./install.sh                     write both LaunchAgents to ~/Library/LaunchAgents and load them
#   ./install.sh --dry-run <folder>  only write and lint the plists into <folder> (loads nothing)
#
# Safe to run again: it boots both agents out first. Undo with ./uninstall.sh. Logs go to data/logs/
# (inside data/, which Dropbox ignores). Uses /usr/bin/python3 (always present; launchd has a minimal PATH).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PY=/usr/bin/python3
PREFIX=local.sessionbell
OLD_PREFIX=local.sessions-attention   # the labels before the rename to Sessionbell (2026-11-17)
PORT=8790
DEST="$HOME/Library/LaunchAgents"
DRY=""

if [ "${1:-}" = "--dry-run" ]; then
  DRY=1
  DEST="${2:?usage: install.sh --dry-run <folder>}"
fi

# Write both plists with plistlib, so no path can break the XML.
write_plists() {
  "$PY" -I - "$DEST" "$HERE" "$PY" "$PREFIX" <<'PYEOF'
import json, os, plistlib, sys
dest, here, py, prefix = sys.argv[1:5]
logs = os.path.join(here, "data", "logs")
# config.json: how often the scanner runs (5 to 120 s; 10 when the file or the value is missing or wrong).
every = 10
try:
    with open(os.path.join(here, "config.json"), encoding="utf-8") as f:
        value = json.load(f).get("scanEverySeconds")
    if isinstance(value, int) and not isinstance(value, bool) and 5 <= value <= 120:
        every = value
    else:
        print("config.json: scanEverySeconds must be a whole number from 5 to 120; using 10.", file=sys.stderr)
except (OSError, ValueError, AttributeError):
    print("config.json is missing or unreadable; scanning every 10 s.", file=sys.stderr)
common = {"WorkingDirectory": here, "RunAtLoad": True, "LimitLoadToSessionType": "Aqua"}
agents = {
    "scanner": dict(common, StartInterval=every, ProcessType="Background"),
    "server": dict(common, KeepAlive=True),
}
for name, extra in agents.items():
    label = prefix + "." + name
    plist = dict(extra, Label=label,
                 ProgramArguments=[py, "-I", os.path.join(here, name + ".py")],
                 StandardOutPath=os.path.join(logs, name + ".log"),
                 StandardErrorPath=os.path.join(logs, name + ".log"))
    with open(os.path.join(dest, label + ".plist"), "wb") as f:
        plistlib.dump(plist, f)
PYEOF
}

mkdir -p "$DEST"
write_plists
for name in scanner server; do
  /usr/bin/plutil -lint -s "$DEST/$PREFIX.$name.plist"
done

if [ -n "$DRY" ]; then
  echo "Dry run: wrote and linted $DEST/$PREFIX.scanner.plist and $DEST/$PREFIX.server.plist"
  exit 0
fi

# data/ holds real titles: create it if needed and keep it off Dropbox (same as the scanner does).
if [ ! -d "$HERE/data" ]; then
  mkdir -m 700 "$HERE/data"
  /usr/bin/xattr -w com.dropbox.ignored 1 "$HERE/data" || true
fi
mkdir -p "$HERE/data/logs"

DOMAIN="gui/$(id -u)"
port_busy() { /usr/sbin/lsof -nP -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; }

# Something else on the port would make the server agent restart over and over. Check before stopping
# anything, so a failed run leaves the running agents alone; our own server agent on the port is fine.
if port_busy && ! /bin/launchctl print "$DOMAIN/$PREFIX.server" >/dev/null 2>&1 &&
   ! /bin/launchctl print "$DOMAIN/$OLD_PREFIX.server" >/dev/null 2>&1; then
  echo "Port $PORT is already in use:" >&2
  /usr/sbin/lsof -nP -iTCP:$PORT -sTCP:LISTEN >&2 || true
  echo "Stop that process (for example a server.py you started by hand), then run ./install.sh again." >&2
  exit 1
fi

for name in scanner server; do
  /bin/launchctl bootout "$DOMAIN/$PREFIX.$name" 2>/dev/null || true
  # Agents installed under the old name: stop them and move their plists to the Trash.
  /bin/launchctl bootout "$DOMAIN/$OLD_PREFIX.$name" 2>/dev/null || true
  if [ -e "$DEST/$OLD_PREFIX.$name.plist" ]; then /usr/bin/trash "$DEST/$OLD_PREFIX.$name.plist"; fi
done

# The old server may take a moment to let go of the port.
for _ in 1 2 3 4 5 6 7 8 9 10; do
  port_busy || break
  sleep 0.5
done
if port_busy; then
  echo "Port $PORT is still in use after stopping the old server agent:" >&2
  /usr/sbin/lsof -nP -iTCP:$PORT -sTCP:LISTEN >&2 || true
  exit 1
fi

# Right after a bootout, bootstrap can fail once with "Input/output error": try again after a second.
for name in scanner server; do
  /bin/launchctl bootstrap "$DOMAIN" "$DEST/$PREFIX.$name.plist" 2>/dev/null ||
    { sleep 1; /bin/launchctl bootstrap "$DOMAIN" "$DEST/$PREFIX.$name.plist"; }
done

# Check that both agents are loaded and the server answers.
for name in scanner server; do
  if ! /bin/launchctl print "$DOMAIN/$PREFIX.$name" >/dev/null 2>&1; then
    echo "The $name agent did not load. See $HERE/data/logs/$name.log" >&2
    exit 1
  fi
done
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if /usr/bin/curl -fsS -m 1 -o /dev/null "http://127.0.0.1:$PORT/health" 2>/dev/null; then
    echo "Installed. Both agents run at login; the dashboard is at http://127.0.0.1:$PORT"
    exit 0
  fi
  sleep 1
done
echo "The agents are loaded, but the server doesn't answer yet. See $HERE/data/logs/server.log" >&2
exit 1
