# Sessionbell (folder: claude-sessions-needing-attention)

A local dashboard that shows which Claude desktop app (Code tab) sessions are waiting on the user, what
each one wants, and opens it in one click. macOS only, runs only on this Mac.

## Public name: Sessionbell (decided 2026-11-17)

When you write anything users or the public see (README, page title, PWA manifest, posts), the product is
**Sessionbell**, never "Claude Dashboard" or any name with "Claude" in it (Anthropic's trademark rules).
"Claude Code" may appear only to describe what it works with, with "Not affiliated with Anthropic" nearby.
Renamed on 2026-11-17: README, page and tab title, PWA manifest, banner title, server header, launchd labels.
Old plans, design files and the handoff keep the old name as history. The folder keeps its name (Dropbox
paths and session history point at it). Checks and reasons:
`marketing/naming.md`. Reddit launch: `marketing/reddit-plan.md`.

## Read first

- `handoff/handoff.html` (or its PDF): the behaviour, data contracts, security rules and pitfalls. It wins
  over everything else on behaviour.
- `plans/roadmap.md`: phases, global constraints, review focus, status.

## Rules

- Python 3 standard library only. The page is one static `index.html` (inline CSS + plain JS), no build step.
- Server port: **8790**, bound to `127.0.0.1` only.
- Never write to `~/Library/Application Support/Claude/`. The one thing the tool does to the Claude app is the
  reply bar typing a reply (below), which the user decided on 2026-11-12, setting aside the handoff's
  "the tool never changes the app".
- `status.json`, `state.json` and `logs/` hold real session titles: git-ignored, never uploaded, never
  screenshotted. Design work uses made-up data only.
- They all live in **`data/`**, which is marked ignored by Dropbox (`xattr -w com.dropbox.ignored 1 data`),
  so they stay on this Mac (decided 2026-11-12). Never mark single files: an atomic write drops the mark.
  If `data/` is missing, the scanner recreates and marks it; check with `xattr -p com.dropbox.ignored data`.
- `projects.json` stays at the top level and does sync: it holds project names and folders, no titles.
- Not a git repo (decided 2026-11-12). No git commands unless the user asks.

## Timers: `config.json` (added 2026-11-14)

When you change how fast the dashboard updates, edit `config.json` (top level, syncs, no titles), not the code:

- `scanEverySeconds` (5–120, default 10): the scanner agent's `StartInterval`. Read by `install.sh` only, so
  re-run `./install.sh` after changing it.
- `pageRefreshSeconds` (2–300, default 5): how often the page re-reads the status. The server reads the file
  on every `GET /config.json` and serves only this key; the page asks once, so reload the page. No restart.
- `replyEnabled` (default `false`): turns the reply bar on (see "Reply bar"). Only `true` turns it on. The
  server reads it on every `POST /reply` and `GET /config.json`, so reload the page; no restart.
- `config.local.json` (top level, git-ignored, added 2026-11-17) overrides `config.json` key by key, read by
  the server (`read_config`) and `install.sh`. `config.json` is the published default; this Mac's own
  choices go in the local file. A broken local file is ignored, never turns replies on.
- A missing file or a wrong value falls back to the default. Worst-case delay is the two added together.
  Before 2026-11-14 they were fixed at 60 s and 30 s.

## Scanner (Phase 2)

    python3 scanner.py              # writes data/status.json; exit 1 when the status is an error
    python3 scanner.py --print      # grouped list with titles + folders with no rule: the user's terminal only
    python3 scanner.py --summary    # counts only: the only real-data output an agent may read
    python3 -B -m unittest          # tests (made-up data); also run with /usr/bin/python3 (3.9)

- Agents never run `--print` and never read `data/` or the app's session files beyond counts and field
  names. Real titles must not enter a chat.
- The scanner must run on Python 3.9 (`/usr/bin/python3`), standard library only.
- `--no-notify` skips banners; `--notify-test` sends one made-up banner and exits. Tests replace the
  banner sender, so no test ever shows a real banner.
- A turn in progress is "working" until 30 minutes of quiet, then "stuck" (changed from the handoff's 5).
- A finished turn whose background subagents still run is "working" too (asked/blocked still win). The session
  file can't show this; `subagent_activity` reads `~/.claude/projects/*/<cliSessionId>/subagents/agent-*.meta.json`
  (`finished: true` once done) and the matching `.jsonl`'s file time, never its text. An unfinished agent quiet
  for 30 minutes no longer counts (found 2026-11-13). Nor does one started over 72 hours ago (the meta file's
  time, `SUBAGENT_MAX_AGE_MS`): old transcripts from before the app wrote `finished` get their `.jsonl` file
  time bumped by other tools, which showed 39-day-old sessions as Working (found 2026-11-16). A subagent
  stopped with TaskStop (or Stop) never gets `finished: true`; its `.jsonl`'s last entry is a user message
  starting `[Request interrupted`, and `_was_stopped` skips it (only that prefix is compared). Before this, a
  finished turn that stopped its agents showed as Working for 30 minutes (found 2026-11-21).
- A Working card has a `doing` line (added 2026-11-13), shown bottom-left of its row: the plan step marked
  in progress, read from the last 1 MB of the CLI transcript by replaying `mcp__ccd_turn__update_plan` (and
  `TodoWrite`) calls; with no plan, the first line of your latest typed message. No model call: the text
  never leaves this Mac. Its time reads "for 27m", so "Working" shows only in the section header and badge.
  The plan list can sit 2 to 6 MB back (image reads fill the tail; later calls only say "advance"), which
  left the line as "In progress" (found 2026-11-15). So `transcript_doing` reads 1, then 4, then 16 MB
  (`DOING_TAILS`) until it holds a whole list; past the first step, lines over 50 KB are parsed only if
  they name a plan tool, which keeps it at a few ms.
- A btw session (`btwLoweredFrom` set) is never "blocked": the app's `postTurnSummary` can report the parent's
  blocked request, because the fork's transcript starts with the parent's history. It counts as review-ready,
  and its subtitle skips `needs_action` (found 2026-11-12; a change from the handoff's rule).
- The app no longer saves the next-step question (`turnWrapUp.needsUser` is in none of the session files,
  found 2026-11-12). For a finished turn with a `turnWrapUp`, the scanner reads the last 1 MB of the CLI
  transcript `~/.claude/projects/*/<cliSessionId>.jsonl`: the latest `mcp__ccd_turn__wrap_up` call's `ask`,
  unless a typed message came after it, makes the session "asked". Only `type: "assistant"` entries count
  (`api-request-blob` entries replay old messages). Transcripts hold real text: same rules as `data/`.

## Server and page (Phase 3)

    python3 server.py                   # http://127.0.0.1:8790 (loopback only)
    python3 -I tools/snapshot.py        # made-up snapshots in design/page-check/build/ (git-ignored)

- Demo GIFs and public screenshots use `snapshot-demo-light.html` / `-dark.html` (added 2026-11-15): invented
  sessions from `tools/demo-fixture.json`, with no client names. Clicks, Snooze, Dismiss and Send reply all work
  against fakes, and nothing touches the Claude app. Edit that file to change the story.
- Never screenshot or read the text of the live page. Live checks read only the tab-title count, console
  errors and HTTP headers. Design and contrast checks use the snapshots.
- Snapshots are served for the built-in browser by `.claude/launch.json` ("snapshots") on
  **`127.0.0.1:8791`**; it serves only `design/page-check/build/`. The browser pane has a tab limit: reuse
  one tab and `navigate` it.
- `index.html` holds the approved design's stylesheet inline (from `design/claude-design-result/sn.css`);
  edit it there. The project bar (top) and the Working section are later changes the canvas doesn't show.

## Running at login (Phase 4)

    ./install.sh             # both LaunchAgents: scanner on a timer, server always on; safe to re-run
    ./uninstall.sh           # stops both, moves the plists to the Trash; leaves data/ alone
    launchctl kickstart -k gui/$(id -u)/local.sessionbell.server    # restart after editing server.py
    launchctl print gui/$(id -u)/local.sessionbell.scanner           # state, runs, last exit code

- Labels `local.sessionbell.scanner` and `.server` (before 2026-11-17: `local.sessions-attention.*`; install.sh and uninstall.sh remove those), in `~/Library/LaunchAgents/`. Both run
  `/usr/bin/python3 -I` (3.9: launchd has a minimal PATH), so code must stay 3.9-compatible.
- Logs: `data/logs/scanner.log` and `server.log` (Dropbox-ignored). They can hold real titles: agents check
  only their size or count lines, never read them.
- The page loads code fresh on reload, but the server keeps its Python code until restarted (the kickstart
  line above). Don't start a second `server.py` by hand on 8790: install.sh refuses to run while one holds it.
- Snooze, Dismiss, Undo, Show again and Pin write `data/state.json` through `POST /state` (the server is its only
  writer). The page applies the same hide rule as the scanner (`hiddenBy` / `applyState`);
  `tests/test_page_rule.py` runs the page's code in Node against `scanner.hidden_by` (skipped without Node).
  Change both sides together.
- Snapshots get a fake state store (`window.__STATE_SINK__`); the `savefail` snapshot shows the failure toast.

## Caught up (added 2026-11-17)

A finished session you've read (nothing asked, not blocked or review-ready, focused after its last activity)
used to vanish from the list. Now it goes to **Caught up**, a folded section between Quieter and Hidden, so it
can still be opened. The user chose the name (other options were Recent, Done, History).

- `status.json` `"caughtUp"`: cards with state `"read"`, unarchived and unpinned, last activity within
  `CAUGHT_UP_MS` (7 days), newest first, at most `CAUGHT_UP_MAX` (50). `counts.caughtUp` is its length.
  Never counted in Needs you, the badge or banners.
- Optional like `working`: the server's shape check and `listed_sessions` accept it (so a reply works from it).
- A read card's menu has Pin and Dismiss (no Snooze; Dismiss added 2026-11-18, the user's ask). A dismissed
  caught-up card goes to Hidden with `"section": "caughtUp"` until the session has new activity (or past the
  7 days); Show again or Undo puts it back. Scanner (`build_status`) and page (`applyState`) share the rule. Pinning moves it to the end of Quieter (as before); unpinning a read card
  sends it to Caught up. The page (`applyState`, `CAUGHT_UP_MS` / `CAUGHT_UP_MAX`) and the scanner share the
  rule; `tests/test_page_rule.py` checks it.
- Snapshots: `CAUGHT_UP` in `tools/snapshot.py`, added wherever the Working cards are.

## Dismissing a Working card (added 2026-11-21)

The user's manual override for a session that only looks busy. Dismiss on a Working card hides it (Hidden,
`"section": "working"`) until the session's `lastActivityAt` moves, the same rule as every dismiss; a pin
wins. Scanner (`build_status`) and page (`applyState`) share it; `tests/test_page_rule.py` checks it. A
session that really runs moves `lastActivityAt` often, so it comes back on its next activity.

## Pinned (added 2026-11-15)

A pinned session keeps its place: same section, same order, with a pin in a ringed circle before its title
(and "Pinned" in the session pane). It never gets its own section (the user's call, 2026-11-15). Once you've
read it, when it would drop off the list, it stays at the end of Quieter with a grey "Read" badge until you
unpin it. Pin / Unpin is the first item in the "More actions" menu; a pinned card's menu has only Unpin, a
working card's Pin and Dismiss. Right-clicking a list row opens the same menu at the pointer in every layout (added
2026-11-16: `openCtx` / `placeCtx` in `index.html`, kept inside the list).
While any of these menus is open, **P** runs Pin / Unpin and **D** runs Dismiss (added 2026-11-21, the user's
ask); each item shows its letter on the right (`keyHint`, `menuKeys`). A menu without Dismiss ignores D.

- `state.json` has `"pinned": {sessionId: {"at": ms}}`, written by `POST /state` with `action` `pin` / `unpin`.
  Pins never expire; the server keeps the newest 200 (`MAX_PINS`). The latest choice wins: pinning clears a
  snooze or dismissal, and snoozing or dismissing unpins. Restore never touches a pin.
- In `status.json` a pinned card has `"pinned": true`; a read one has state `"read"` and sits in `quiet`.
  A pin beats any hide entry. Counts and banners are unchanged by pinning (`counts.pinned` is just a count).
- Page and scanner share the rule (`isPinned` / `pinned_ids`; `applyState` drops a `read` card once
  unpinned); `tests/test_page_rule.py` checks it. Snapshot `pinned` pins one Needs-you card and adds a read one.
- Archived sessions lose their place; their pin stays in `state.json` until it falls past the 200.

## New session (added 2026-11-16)

The header's **New session** button (outlined, so Send reply stays the one filled button) opens a picker:
a search box, then folders grouped by project (the project you're viewing first), then "Another folder".
A folder row is a plain link, `claude://code/new?folder=<URL-encoded absolute path>`: the Claude app opens
its Code tab on a new session with that folder chosen, and you write the first message there. "Another
folder" is `claude://code/new` with no folder. The app also reads `q=` (a first prompt); we don't send one.

- Found 2026-11-16 in the app's link handler (`app.asar`, host `code`, path `/new`, params `folder`, `q` or
  `prompt`, `file`). It's undocumented: if the app changes it, rows will open the app but not the folder.
- The scanner writes `status.json` `"folders"` (`folder_list`): every folder a session ran in, archived ones
  too, worktrees cut back to the repo, newest use first, then the `projects.json` rule folders never used
  (`lastUsedAt: null`). Missing folders and `/tmp/`, `/private/`, `/var/folders/` are left out; at most 200.
  `path` shows the home folder as `~`. Folder paths are private data like titles: same rules as `data/`.
- `folders` is optional: the server doesn't check it, and the page drops entries that aren't absolute paths
  (`goodFolder`), so a bad list only empties the picker. Snapshots make up folders from their own cards
  (`with_folders` in `tools/snapshot.py`).
- The click is a real link; the picker closes 50 ms later, because a link removed from the page doesn't open.

## Reply bar (added 2026-11-12)

The session pane's footer is a reply box (Enter sends, Shift+Enter adds a line); Open session and a "More
actions" menu (Snooze, Dismiss) sit in its header. Plan: `plans/reply-bar.md`.

- **Off by default** (decided 2026-11-15, before sharing the tool): it types into another app with
  Accessibility permissions, so a new user must opt in with `"replyEnabled": true` in `config.json`. While
  it's off the pane has no footer, Open session is the filled button, and `POST /reply` answers 403 before
  doing anything. `config.json` keeps it `false` (the published default); this Mac turns it on in
  `config.local.json` (the user's choice, 2026-11-15; moved there 2026-11-17). Snapshot
  `replyoff` shows the off state, the others show it on.
- `POST /reply {"sessionId", "text"}` has the same guards as `POST /state` (Host, Origin, JSON), a 64 KB body,
  1–4,000 characters, and only goes to a session in the current `data/status.json`. One send at a time (409).
- The Claude app has no API for this. `type_into_claude` in `server.py` opens the `claude://` link, waits
  until that session's `lastFocusedAt` moves on (the only field it reads), then runs `TYPE_SCRIPT` through
  `osascript`, with the text as argv, never inside the script. The script types only when Claude is
  frontmost and the focused element is an `AXTextArea`. It pastes and presses Return, puts the whole
  clipboard back (the reply is marked transient), then brings back the app that was in front.
- It needs macOS permissions for whatever runs the server (the login agent runs `/usr/bin/python3`):
  **Device Control and Data Access** (this macOS's name for Accessibility) and Automation for System Events.
  When a permission is missing, the page shows how to fix it; the reply bar's ⓘ tooltip says so too.
- Claude is an Electron app: macOS can't see its message box until a client sets `AXManualAccessibility`
  on it (without that, `AXFocusedUIElement` fails: found 2026-11-13), and then takes about 2.5 s to show
  it. So the server turns it on (`PREPARE_SCRIPT`) before opening the session, the typing script waits up to
  6 s for the focused `AXTextArea`, and the setting is put back afterwards, also when a send stops early.
- Tests replace `httpd.reply_sender`, and `SenderTests` replace `subprocess.run`: no test ever opens a
  session or types into the app. Agents never send a real reply; the user does the first real send.
- Snapshots get a fake `reply` in `window.__STATE_SINK__`; in `savefail` it fails, to show the error under the box.

## Installed app (PWA, added 2026-11-12)

    python3 -I tools/make_icons.py      # redraws pwa/icon*.png, apple-touch-icon.png, icon.svg (stdlib, ~10 s)

- `pwa/` holds the manifest, `sw.js` and icons. `server.py` serves only the files listed in `STATIC`; add a
  file there and in `tests/test_pwa.py`, or it 404s. CSP has `manifest-src 'self'; worker-src 'self'`.
- `sw.js` caches only the page shell (`/`, which holds no session data), network first, so the app window
  opens while the server is down and shows the red "Can't reach" banner. It must never cache or answer
  `/status.json` or `/state.json` (real titles); `tests/test_pwa.py` checks this. Bump `CACHE` when you change
  its caching.
- The page sets the Dock badge to the tab-title count (a dot for "(!)") and keeps `theme-color` in step
  with the theme. Snapshots (`window.__STATUS_SOURCE__`) never register the worker or touch the badge.
- Install: Chrome at `http://127.0.0.1:8790` → Install icon in the address bar (or ⋮ → Cast, save and
  share → Install page as app); Safari → File → Add to Dock. The app is per origin: install from
  `127.0.0.1`, not `localhost`. The server must run (login agent, Phase 4) for live data.
- PWA checks run on made-up data: `python3 -I tools/snapshot.py` writes `design/page-check/build/pwa-root/`,
  and `.claude/launch.json` "pwa-check" runs the real `server.py` on it at **`127.0.0.1:8792`**. Stopping that
  preview and reloading tests the offline start.

## Handoff PDF

When you change `handoff/handoff.html`, rebuild the PDF (needs `uv`, from Homebrew; uses installed Chrome):

    uv run --with playwright==1.63.0 python handoff/build_pdf.py --pdf-only

- Without `--pdf-only` it also retakes the 5 screenshots (made-up data, through `tools/snapshot.py`'s
  `build()`); run that when the page's look changes. `--pdf-only` reuses `handoff/build/screenshots/`.

## Design handoff (Phase 1)

When you change anything in `design/claude-design-handoff/`, rebuild and check the zip:

    python3 -I design/claude-design-handoff/make_handoff.py

It fails if a real client name, a phone number or a non-`TICKET-` ticket key is in the package. The
forbidden-name list lives only in that script, which is not part of the zip.
