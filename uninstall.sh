#!/bin/bash
# Sessionbell: stop both login agents and move their plists to the Trash.
#
#   ./uninstall.sh            stop and remove
#   ./uninstall.sh --dry-run  only print what it would do
#
# Leaves data/ (status, state, logs) in place.
set -uo pipefail

# local.sessions-attention: the labels before the rename to Sessionbell (2026-11-17), if still installed.
DEST="$HOME/Library/LaunchAgents"
DOMAIN="gui/$(id -u)"
DRY=""
[ "${1:-}" = "--dry-run" ] && DRY=1

for label in local.sessionbell.scanner local.sessionbell.server local.sessions-attention.scanner local.sessions-attention.server; do
  plist="$DEST/$label.plist"
  if [ -n "$DRY" ]; then
    echo "would run: launchctl bootout $DOMAIN/$label"
    echo "would move to the Trash: $plist"
    continue
  fi
  /bin/launchctl bootout "$DOMAIN/$label" 2>/dev/null || true
  if [ -e "$plist" ]; then
    /usr/bin/trash "$plist"
  fi
done

[ -z "$DRY" ] && echo "Uninstalled. Both agents are stopped; data/ is untouched."
exit 0
