# Phase 4: Snooze, Dismiss and running at login

Status: **draft for your review** (2026-11-12).

Goal: hide a session for a while (Snooze 1 hour, Snooze until tomorrow 9:00) or until it changes (Dismiss),
with Undo and Show again; and have the scanner and the server start by themselves at login, so the
dashboard is always there at `http://127.0.0.1:8790` without terminal loops.

Sources, in this order when they disagree: `handoff/handoff.html` §5 (state.json), §8 (server guards),
§9 (page actions), §10 (running at login), §13 (tests) > the approved copy > `index.html`'s current design >
the canvas boards s04, s05, s06 and s12. Also `plans/roadmap.md` (Phase 4) and the deferred items of
Phases 2 and 3.

## Global constraints

- macOS only; Python 3 standard library only; **Python 3.9+** (`/usr/bin/python3`).
- Server on `127.0.0.1:8790` only. Read-only towards the Claude app.
- Real data lives in `data/` (Dropbox-ignored): `status.json`, `state.json` and now `logs/`.
- **The server is the only writer of `state.json`**; the scanner and the page only read it.
- Never screenshot or read the text of the live page; design checks use made-up snapshots.
- No git commands unless asked. Delete with `trash`, never `rm`.

## Review focus (what would hurt you most)

| # | Failure | How this phase tests it |
|---|---|---|
| 1 | A hidden session stays hidden forever | Snooze capped at 8 days (server and scanner), Dismiss ends on new activity, pruning, Show again; tests |
| 2 | Another web page writes `state.json` | Host, Origin, Content-Type, size and strict validation on `POST /state`; tests for each |
| 3 | A click hides the wrong session, or Undo doesn't bring it back | Round-trip tests; browser walk-through on snapshots |
| 4 | The login agents silently don't run, so the page shows old data | `install.sh` checks both agents after loading; the page's late state ("(!)") still covers it |
| 5 | Real titles end up outside `data/` | Logs in `data/logs/`; `state.json` holds ids and times only |

## Facts checked before planning (2026-11-12)

- `~/Dropbox` is a normal folder (not a CloudStorage link), so a LaunchAgent can run scripts from it.
- `~/Library/LaunchAgents` exists; no `local.sessions-attention.*` agent is installed.
- `/usr/bin/plutil`, `/bin/launchctl` and `/usr/bin/trash` exist. macOS 27.2.1, user id 501.
- Right now the server runs from a chat session and the scanner from your terminal loop; both stop before
  install.

## Files

| File | Purpose |
|---|---|
| `server.py` | Gains `GET /state.json` and `POST /state` |
| `scanner.py` | Caps snoozes at 8 days when reading `state.json` |
| `index.html` | Snooze menu, Dismiss, Undo toast, Show again, the 800 "More actions" menu |
| `install.sh`, `uninstall.sh` | The two LaunchAgents |
| `tests/test_state.py` | `POST /state` and `state.json` |
| `tests/test_install.py` | The generated plists (dry run, no loading) |
| `tests/test_page.py`, `tests/test_scanner.py` | Updated |

## Tasks (tests first; browser checks for the page)

### 1. `state.json` and `POST /state` (server)

`data/state.json`: `{"version": 1, "hidden": {"local_…": {"kind": "snooze", "until": ms, "at": ms} |
{"kind": "dismiss", "lastActivityAt": ms, "at": ms}}}` (handoff §5). Ids and times only.

`POST /state` with a JSON body:

| Action | Body | Effect |
|---|---|---|
| snooze | `{"action": "snooze", "sessionId": "local_…", "until": ms}` | Hidden until `until` |
| dismiss | `{"action": "dismiss", "sessionId": "local_…", "lastActivityAt": ms}` | Hidden until the session has newer activity |
| restore | `{"action": "restore", "sessionId": "local_…"}` | Shown again (Undo, Show again) |

Guards, checked in this order:

| Check | Answer |
|---|---|
| `Host` is `127.0.0.1:8790` or `localhost:8790` | else 403 |
| `Origin` is exactly the page's own origin (`http://` + the same host) | else 403 |
| `Content-Type` is `application/json` | else 415 |
| `Content-Length` present and 2 KB or less | 411 / 413 |
| Body is a JSON object; `sessionId` matches `^local_[A-Za-z0-9_-]{1,80}$`; `action` is one of the three; `until` is after now and at most 8 days ahead; `lastActivityAt` is a finite number | else 400 |

On success: lock, read, change, prune, write atomically (temp file, then `os.replace`, mode 0600), answer
200 with the new state. Pruning drops ended snoozes, dismissals older than 90 days, and keeps the 1,000
newest entries. `GET /state.json` returns the state; a missing or broken file reads as nothing hidden.

Tests (`StateTests`): `test_snooze_round_trip`, `test_dismiss_round_trip`, `test_restore`,
`test_get_state_missing_is_empty`, `test_broken_state_reads_empty`, `test_survives_a_server_restart`,
`test_foreign_host_403`, `test_missing_origin_403`, `test_foreign_origin_403`, `test_wrong_content_type_415`,
`test_missing_length_411`, `test_body_over_2kb_413`, `test_bad_json_400`, `test_bad_session_id_400`,
`test_unknown_action_400`, `test_until_in_the_past_400`, `test_until_beyond_8_days_400`,
`test_dismiss_needs_last_activity_400`, `test_state_file_private_and_atomic`, `test_prune_ended_snoozes`,
`test_prune_old_dismissals`, `test_keep_newest_1000`, `test_concurrent_posts_keep_every_entry`,
`test_post_writes_only_under_data`.

### 2. The scanner's side

The scanner already moves hidden cards to `hidden` and treats them as seen for notifications. New: a snooze
more than 8 days ahead is ignored (the server never writes one, but a hand-edited file can't hide a session
for longer). Tests: `test_snooze_beyond_8_days_hides_nothing`.

### 3. The page: actions

- **Snooze**: the menu with "Snooze 1 hour (back at 15:42)" and "Snooze until tomorrow 9:00" (local time).
- **Dismiss**: hides until the session changes.
- **Undo**: the toast "Snoozed until 15:42 · Undo" / "Dismissed until it changes · Undo" for 8 seconds;
  Undo restores. Focus moves to the next session after Snooze or Dismiss, and back after Undo.
- **Show again** on each Hidden row.
- Where: the detail action bar at 1280 and on the phone; each row's "More actions" menu at 800 (as on the
  canvas board s12). Working rows get no actions.
- **Immediate:** the page fetches `/state.json` with `/status.json` and applies the same rule as the scanner,
  so a card moves to Hidden at once instead of after the next scan.
- **Failure:** if the POST fails, nothing moves and the toast says "Couldn't save. Try again."
- Snapshots: a `window.__STATE_SINK__` hook lets the made-up snapshots run the actions without a server.

Static tests (`PageTests`): the Phase 4 labels are present (the Phase 3 "absent" test turns around);
`POST` uses `Content-Type: application/json` and a same-origin URL; the state hook is present.

### 4. Login agents

`install.sh` writes two LaunchAgents into `~/Library/LaunchAgents` and loads them with
`launchctl bootstrap gui/$(id -u)`. It's safe to run again (it boots both out first).

| Label | Runs | When |
|---|---|---|
| `local.sessions-attention.scanner` | `/usr/bin/python3 -I scanner.py` | every 60 s, and at load |
| `local.sessions-attention.server` | `/usr/bin/python3 -I server.py` | kept alive, started at load |

Both: `WorkingDirectory` = the project folder; output to `data/logs/scanner.log` and `data/logs/server.log`;
`plutil -lint` before loading; after loading, `install.sh` checks that both agents are listed and that
`127.0.0.1:8790` answers `/health`. It warns if something else already holds port 8790.
`install.sh --dry-run <folder>` writes and lints the plists without loading anything (for tests).

`uninstall.sh` boots both out and moves the plists to the Trash (`/usr/bin/trash`).

Tests (`InstallTests`, dry run only): `test_both_plists_pass_plutil`, `test_absolute_python_and_paths`,
`test_scanner_every_60_seconds`, `test_server_kept_alive`, `test_logs_under_data`, `test_scripts_parse`
(`bash -n`).

## Checks and exit

1. `python3 -B -m unittest` and `/usr/bin/python3 -B -m unittest` pass.
2. Browser walk-through on the snapshots (made-up data) at 1280, 800 and 375, light and dark: Snooze menu,
   both snoozes, Dismiss, Undo, Show again, focus after each, the failure toast; contrast on the toast and
   menus.
3. Fresh review (most capable model, made-up data only, probe tests), including the project bar and the
   Working section that missed the Phase 3 review; one fix pass.
4. **With your OK**: stop the chat's server and your terminal loop, run `./install.sh`, check (counts and
   headers only) that both agents run, `status.json` refreshes every minute, and the server listens on
   127.0.0.1 only.
5. **You**: snooze and dismiss a real session, restart the server (`launchctl kickstart -k …`), and see that
   they stay hidden; then log out and back in, and see that the page is live.
6. Close: `AGENTS.md` (install, uninstall, logs), the roadmap status line, rulings and deferred items.

## Done when

- Every test above passes on both Pythons.
- Snooze and Dismiss survive a server restart and a login.
- Both agents run after a logout and login, and the page is live without any terminal open.
- The review's Critical and Important findings are fixed.

## Decisions this plan makes (overrule any)

1. **The page applies `state.json` itself**, using the scanner's rule (handoff §5 says both use it), so
   hiding is instant. That brings back `GET /state.json`, which Phase 3 left out.
2. **Undo is "restore"**: it removes the entry, even if the session had an older snooze before.
3. **Actions on every listed session except Working**: Needs you, scheduled tasks, Stale and Quieter.
4. **The 8-day snooze cap is enforced twice**: the server rejects it, and the scanner ignores a longer one
   (closes the Phase 2 deferred item).
5. **`/usr/bin/python3`** in both agents (3.9, always there), not the 3.14 on your PATH.
6. **Logs in `data/logs/`**, inside the Dropbox-ignored folder, not `logs/` at the top level.
7. **One lock in the server process** is enough: the server is the only writer.
8. **`uninstall.sh` uses `/usr/bin/trash`** for the plists, never `rm`.
9. **The scanner keeps notifying from the agent**; banners still show under Script Editor (handoff §7 wart).

## How to run it

Native: one agent, tests first for the server, scanner and install scripts, browser checks for the page,
then the fresh review. The `superpowers:test-driven-development` skill matches the tested parts; I'd only
use it with your yes.

## Build record (2026-11-12)

Status: **done**, except the logout/login check (yours, not yet seen).

- Built as planned: `GET /state.json` and `POST /state` in `server.py`; the scanner's 8-day snooze cap;
  `install.sh` / `uninstall.sh`; the page's Snooze menu, Dismiss, Undo toast, Show again, the 800 "More
  actions" menu, the failure toast; `__STATE_SINK__` and a `savefail` snapshot. All tests pass on Python 3.14
  and 3.9.
- Browser walk-through on made-up snapshots at 1280, 800 and 375, light and dark: every action, focus after
  each, keyboard in the menus, the failure toast. Contrast: toast text 13.6:1 (light) / 12.9:1 (dark), menu
  text 16:1 / 13.5:1, menu icons above 8:1.
- Found during the walk-through: on the phone the toast covered Snooze and Dismiss (now above the action
  bar); after a failed save focus fell to the page (now back on the button that opened the menu).
- Fresh review, 11 findings, all fixed:
  1. A poll that started before a save could bring the old state back for up to 30 s: a save now
     invalidates any poll in flight.
  2. Toast: the timer pauses while the pointer or focus is on it; a separate live region announces it;
     ⌘Z / Ctrl+Z undoes from anywhere.
  3. Re-running `install.sh` could leave nothing running: it checks the port before stopping anything, waits
     for the port, retries the start once.
  4. Deeply nested JSON crashed the request on Python 3.9: now a 400.
  5. A client that stopped sending held a thread forever: 10 s handler timeout.
  6. Dismiss accepted any number (1e308, -5) and rounded fractions: now 0 < time ≤ now + 1 day, kept exactly.
  7. A state entry without `at` hid in the scanner but not on the page: the server now keeps it (as `at` 0).
  8. The project bar lost its Tab stop when the saved project wasn't listed: "All" is then the stop.
  9. Acting on the only listed session left focus nowhere: it now lands on the Hidden row.
  10. Repeated "More actions" / "Show again" buttons had the same name: each now names its session.
  11. No behavioural check of the page's rule: `tests/test_page_rule.py` runs it in Node against the
      scanner (catches each of three deliberate breaks). Also: the handoff PDF's full build works again.
- Install: both agents loaded; the scanner ran every 60 s with exit 0; the server listens on 127.0.0.1:8790
  only, with the security headers. Your snooze and dismiss were still saved after a fresh server restart.
- Ruling during the build: the toast's visible copy stays as approved; the ⌘Z hint is spoken only.

