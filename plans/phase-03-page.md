# Phase 3: Server, page and notifications (read-only UI)

Status: **done** (2026-11-12), with two checks still open on your side (see "Close-out" at the end).

Goal: open `http://127.0.0.1:8790` and see your real sessions in the dashboard you approved on the canvas,
in light and dark, at 1280, 800 and phone widths, with a notification when a session asks you a new question.
The page only reads in this phase; Snooze, Dismiss and running at login are Phase 4.

Sources, in this order when they disagree: `handoff/handoff.html` §7, §8, §9, §13, §14 (behaviour) > the
approved copy > `design/claude-design-result/sn.css` (tokens and components) > the canvas boards (screens).
Also `design/claude-design-review.md` §F (the build notes) and `plans/roadmap.md` (Phase 3).

## Global constraints

- macOS only; Python 3 standard library only; **Python 3.9+** (`/usr/bin/python3`).
- The page is one static `index.html`: inline CSS and plain JavaScript, no build step, no outside requests
  (no CDN, no web fonts).
- Server on `127.0.0.1:8790` only. Port 8790 was free on 2026-11-12.
- Read-only towards the Claude app. Real data lives in `data/` (Dropbox-ignored).
- **Never screenshot or read the text of the live page**: it shows real titles. Design checks use made-up
  snapshots. Live checks read only the tab-title count, console errors and HTTP headers.
- No git commands unless asked. Delete with `trash`, never `rm`.

## Review focus (what would hurt you most)

| # | Failure | How this phase tests it |
|---|---|---|
| 1 | The page shows a calm "0" when it doesn't know (scanner stopped, status missing, error) | Late (over 3 min), missing-file and error states tested on snapshots and in server tests; tab shows "(!)" |
| 2 | A session that asked is hidden by a filter | The tab title always shows the all-projects total; "N more need you in other projects" tested |
| 3 | Real titles leak: another web page reads `status.json`, the lock screen shows a question, a screenshot | Host check (DNS rebinding) and headers tested; notifications carry titles only; no live screenshots |
| 4 | A crafted title runs script or a link opens something else | `textContent` only; only `claude://claude.ai/epitaxy/local_…` links render; static and server tests |
| 5 | Glass makes text unreadable | Contrast measured in the browser on the solid snapshot, both themes |

## Facts checked before planning (2026-11-12)

- Port 8790 has no listener. `/usr/bin/osascript` exists. `/usr/bin/python3` 3.9.6 has
  `http.server.ThreadingHTTPServer`.
- The approved design is in `design/claude-design-result/` (canvas `1794503645-b4b3`): `sn.css` holds every
  token and component state; `Main.dc.html` holds the layout and behaviour as a prototype.
- Made-up fixtures already exist and passed the forbidden-name check: `design/sessions-dashboard-claude-design/`
  `status-fixture.json` and `fixture-states/` (empty, scanner-late, busy, error-format, error-projects).

## Files

| File | Purpose |
|---|---|
| `server.py` | The server: `GET /`, `GET /status.json`, `GET /health` |
| `index.html` | The whole page |
| `scanner.py` | Gains notifications, `--no-notify` and `--notify-test` |
| `tests/test_server.py` | Server tests on a free port, made-up data |
| `tests/test_notify.py` | Notification tests with a fake sender (no real banners) |
| `tests/test_page.py` | Static safety checks on `index.html` |
| `tools/snapshot.py` | Builds made-up snapshot pages in `design/page-check/build/` (git-ignored) |

## Tasks (tests first where code can be tested; browser checks for the page)

### 1. Notifications in the scanner

`new_questions(previous, current) -> list[card]`: asked cards in `main` and `scheduled` whose
`(sessionId, needs)` pair wasn't anywhere in the previous status (its `main`, `scheduled`, `stale` or
`hidden`). No previous file, or a previous error, gives `[]`. Hidden cards count as seen.

`notify(cards, send=_osascript)`: one banner per new question, title "Sessions needing attention", body
the session title only. Three or more at once give one banner: "3 sessions asked you something". The text
goes to `osascript` as argv (`on run argv … display notification (item 2 of argv) with title (item 1 of argv)`),
never into the script. No sound.

The scanner reads the previous `data/status.json` before writing the new one. `--no-notify` skips sending.
`--notify-test` sends one made-up banner ("Test: a session asked you something") and exits.

Tests (`NotifyTests`): `test_new_question`, `test_unchanged_list_is_silent`, `test_no_baseline_is_silent`,
`test_previous_error_is_silent`, `test_changed_question_same_session`, `test_snooze_ending_is_silent`,
`test_blocked_and_stuck_never_notify`, `test_three_or_more_become_one_banner`,
`test_text_goes_as_argv_not_script`, `test_body_is_title_only`, `test_no_notify_flag`.

### 2. Server

`server.py [--port 8790] [--root <project folder>]`, a `ThreadingHTTPServer` bound to `127.0.0.1`.

| Route | Answer |
|---|---|
| `GET /` | `index.html`, read from disk on each request |
| `GET /status.json` | `data/status.json`; if missing or unreadable, a status object whose `error` says the scanner hasn't run yet |
| `GET /health` | `{"ok": true}` |
| anything else | 404; other methods 405 (`POST /state` arrives in Phase 4) |

Guards on every answer: the `Host` must be `127.0.0.1:<port>` or `localhost:<port>`, otherwise 403;
`Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`,
`X-Frame-Options: DENY`, and a `Content-Security-Policy` that allows only the page's own inline code and
same-origin fetches (`default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline';
connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`).
Quiet logs: no lines for routine 2xx answers.

Tests (`ServerTests`, server started on a free port in a thread): `test_page_served`,
`test_status_served`, `test_missing_status_is_an_error_object`, `test_broken_status_is_an_error_object`,
`test_health`, `test_foreign_host_403`, `test_missing_host_403`, `test_localhost_host_ok`,
`test_security_headers`, `test_unknown_path_404`, `test_path_traversal_404`, `test_post_405`,
`test_binds_loopback_only`.

### 3. The page: structure and tokens

Port `sn.css` into `index.html` (same tokens, light, dark and solid; same class names). Layout by width,
not by props:

| Width | Layout (from the boards) |
|---|---|
| 1100 px and up | rail · list (520 px) · detail; the most urgent session selected on load |
| 640–1099 px | rail · list; one click opens the session in a slide-over (modal for the keyboard) |
| under 640 px | phone: project pill row, list; tap pushes the session view with a back arrow |

The rail scrolls its avatars when the window is short (review §F note). Respect
`prefers-reduced-transparency`, `prefers-reduced-motion` and a missing `backdrop-filter`.

### 4. The page: data

- Fetch `/status.json` on load, every 30 s and when the tab becomes visible again.
- `generatedAt` older than 3 minutes: the header turns into "Scanner hasn't run for 9m" (the lists stay).
- `error` set: the red banner "Can't show sessions right now" with the reason, the header "Last scan …",
  no counts anywhere.
- Tab title: "(8) Sessions needing attention" (`counts.main`, all projects), "(!) Sessions needing attention"
  on an error, plain "Sessions needing attention" before the first load.
- Snapshot hook: if `window.__STATUS_SOURCE__` is a function, render its data instead of fetching.

### 5. The page: what it shows

Everything on the boards except the Phase 4 actions: the rail (All, projects with count badges, "9+",
coming-soon dashed, tooltips), the list header, sub-project pills that wrap, the filter note with
**Show all projects**, Needs you (scheduled tasks as one line), Stale and Hidden as collapsible rows,
Quieter, the empty state, the detail panel (avatar, sub-project, title, state badge, repo, "waiting 25m",
the question as a bubble, the fixed stuck note), and **Open session** with its "Opening…" state.

The view (project, sub-project, theme) is kept in the URL hash and in `localStorage` (wrapped in try/catch).

### 6. The page: keyboard and focus

As tested on the canvas: arrows, Home and End in the list and the rail; Enter opens the session (1280) or
the slide-over (800) or the session view (phone); the slide-over keeps Tab inside and returns focus to the
row on close; Escape closes the slide-over and the phone session view. Visible focus everywhere.

### 7. The page: safety

- All session text set with `textContent`; no `innerHTML`, `insertAdjacentHTML` or `document.write` with data.
- A card's link renders only if it matches `^claude://claude\.ai/epitaxy/local_[A-Za-z0-9_-]{1,80}$`;
  otherwise **Open session** is disabled.

Tests (`PageTests`, static checks on `index.html`): `test_no_html_injection_sinks`,
`test_no_outside_urls`, `test_snapshot_hook_present`, `test_link_pattern_present`,
`test_approved_copy_present` (every fixed string from the brief and review §F).

### 8. Snapshots (made-up data only)

`tools/snapshot.py` writes `design/page-check/build/snapshot-<state>.html`: `index.html` plus a fixture fed
through `__STATUS_SOURCE__`, with relative times rebased to now. States: normal, filtered (Client A →
Canada), empty, late, error-format, error-projects, busy, solid (reduced transparency forced).

## Checks and exit

1. `python3 -B -m unittest` and `/usr/bin/python3 -B -m unittest` pass.
2. **Design comparison** in the built-in browser, snapshots only: every state in light and dark at 1280,
   800 and 375, against the matching board. Differences listed, the ones that matter fixed (hierarchy, type,
   spacing, colour), the rest noted.
3. **Contrast** measured in the browser on the solid snapshot (backgrounds there equal the worst-case glass):
   every text element against its background, both themes; all at least 4.5:1 (3:1 for large text and icons).
4. **Keyboard** walk-through on the snapshot at 1280, 800 and 375, including Escape (it works on a real page).
5. **Live** (with your OK): run the scanner, start the server, open `http://127.0.0.1:8790` in your browser.
   I check only the tab-title count against `--summary`, console errors and the response headers. You look at
   the page and say whether the count matches the Claude app.
6. **Notification**: `python3 scanner.py --notify-test` shows a banner (you confirm it appeared).
7. Fresh review (most capable model, made-up data only, probe tests for claimed bugs), one fix pass, then
   `AGENTS.md` (how to run the server), the roadmap status line and a report of rulings and deferred items.

## Done when

- All tests pass on both Pythons.
- The snapshots match the boards, with the remaining differences listed.
- Every text pair passes contrast in both themes.
- On the live page the count matches the Claude app and the console has no errors.
- A test notification appeared.

## Decisions this plan makes (overrule any)

1. **No dead buttons.** Snooze, Dismiss, "More actions", Show again and the Undo toast arrive with
   `POST /state` in Phase 4. Phase 3 doesn't render them; the Hidden row still shows (empty until Phase 4).
2. **No `GET /state.json` yet.** `status.json` already carries the hidden cards; Phase 4 adds the route only if
   the page needs it.
3. **Width breakpoints** 1100 and 640 px map the three board layouts onto real window sizes.
4. **Stricter headers than the handoff:** a Content-Security-Policy and `X-Frame-Options: DENY` on top of
   the handoff's guards.
5. **Three or more new questions become one banner**, so a burst after a break doesn't stack banners.
6. **`--notify-test`** exists so the "a test notification appears" check uses made-up text.
7. **The scanner stays one-shot.** Until Phase 4's launchd, you run it by hand or in a terminal loop
   (`while true; do python3 scanner.py; sleep 60; done`), and the page shows "Scanner hasn't run" when it's
   older than 3 minutes.
8. **The page has no JavaScript test runner** (standard library only). Its behaviour is checked in the
   browser on snapshots; static tests guard the safety rules.
9. **The server reads `index.html` and `status.json` from disk on every request**, so edits show on reload
   and there's no cache to go stale.
10. **Snapshots go in `design/page-check/build/`**, already git-ignored by `design/**/build/`, and use only
    the design package's made-up fixtures.

## How to run it

Native: one agent, tests first for the scanner and server, browser checks for the page, then the fresh
review. The `superpowers:test-driven-development` skill matches the tested parts; I'd only use it with
your yes.

## Changes during the build (2026-11-12)

- **Projects moved from the rail to a top bar (your request, after seeing the live page).** Full project
  names, counts and "N asked" chips in one row of pills under the header, on a glass strip. It wraps at
  narrower widths instead of hiding projects; the phone keeps its scrolling row. The rail is gone, and the
  theme switch is one button in the header at every width. Sub-project pills stay above the list. This
  replaces review decision A1 (projects in the rail); the canvas boards still show the rail.
- **A Working section under Needs you (your request).** A session whose turn has started and isn't finished
  is "working" until 30 minutes of quiet, then "stuck". The handoff's 5-minute stuck rule flagged a session
  that was busy in a long tool call (quiet 15 minutes). No file field marks a running turn
  (`interruptedAwaitingPerson` is never set), so the rule is inferred from `lastTurnEdgeAt` and quiet time.
  Working rows show "working 27m" from the turn's start, and "Quiet for 15m: may be a permission prompt or a
  slow tool." after 5 minutes of quiet. They don't count in the tab total, never notify, and are never
  hidden. `status.json` gains an optional `working` list and `counts.working`; a scheduled task's running
  run isn't listed. Tests: `test_running_now_is_working`, `test_long_tool_call_is_still_working`,
  `test_stuck_after_thirty_quiet_minutes`, `test_working_sessions_get_their_own_list`,
  `test_working_scheduled_run_is_not_listed`, `test_working_never_notifies`, `test_working_list_is_optional`.

## Close-out (2026-11-12)

**Built:** `server.py` (GET `/`, `/status.json`, `/health`; loopback only, Host check, no-store, nosniff,
no-referrer, CSP, X-Frame-Options DENY; format check on `status.json`), `index.html` (the approved design's
stylesheet, three layouts, project bar, Working section, keyboard, error/late/empty/drift states, snapshot
hook), notifications in `scanner.py` (`--no-notify`, `--notify-test`), `tools/snapshot.py` (18 made-up
snapshots), `.claude/launch.json` (snapshot server on `127.0.0.1:8791`, made-up data only).
121 tests pass on Python 3.14.7 and `/usr/bin/python3` 3.9.6.

**Checks:**
- Design: snapshots compared with the boards at 1280, 800 and 375, light and dark, every state. Differences
  that remain on purpose: the project bar replaces the rail, and the Working section is new (both your calls).
- Contrast: measured in the browser on the solid version, every text element, both themes, all states
  including the project bar and Working rows; lowest 4.81:1.
- Keyboard: list and project bar (arrows, Home, End, Enter), the 800 slide-over (focus inside, Tab wraps,
  Escape returns to the row), the phone session view (Enter, Escape). Escape works on a real page.
- Live (counts, tab title, console and headers only): the tab showed "(1)", matching `--summary`; no console
  errors; every header present; a foreign Host got 403.

**Fresh review** (most capable model, made-up data, probe tests): 1 Critical, 3 Important, 4 Minor, all fixed
tests first (115 tests at the time):

| # | Finding | Fix |
|---|---|---|
| 1 | Critical: the page stopped polling in a background tab, freezing the tab-title count | Polls every 30 s regardless (`test_polls_in_the_background`) |
| 2 | A stopped scanner kept a calm count in the tab | Late (over 3 min) shows "(!)" (`test_late_and_error_titles_are_alarms`) |
| 3 | Format drift showed a calm 0 | Server and page check the shape (`test_unexpected_format_is_an_error_object`, `test_status_shape_is_checked`) |
| 4 | A title cut mid-emoji crashed the scanner's write, leaving the old status | ASCII-escaped JSON (`test_lone_surrogate_in_a_title_still_writes`) |
| 5 | A malformed URL hash killed the page | Safe decoding (`test_hash_decoding_cannot_throw`) |
| 6 | At 800, a session with no valid link opened the slide-over with focus outside it | Focus falls back to Close |
| 7 | With the server down the header said "No scan yet" | Keeps the last scan time |
| 8 | HEAD and OPTIONS skipped the guards | They go through the same checks (`test_head_and_options_go_through_the_guards`) |

Also fixed from its open questions: overlapping refreshes (only the newest answer counts,
`test_stale_answers_are_ignored`) and unexpected state values. The reviewer agreed with all nine rulings.

**Rulings:** no Phase 4 buttons yet; no GET `/state.json` yet; breakpoints 1100 and 640 px in JS; CSP and
X-Frame-Options on top of the handoff; three or more new questions become one banner; `--notify-test`;
theme follows the system unless you pick one; a failed fetch drops the old lists but keeps the last scan
time; avatar colours skip coming-soon projects; the saved view is checked only against real data.

**Open (yours):**
- The test banner: sent with `--notify-test`, but you haven't confirmed seeing it. If it never shows, allow
  Script Editor in System Settings › Notifications.
- The live count against the Claude app: the tab matched the scanner, but you haven't confirmed it matches
  what the app shows.

**Not independently reviewed:** the project bar and the Working section came after the fresh review. They are
covered by tests and browser checks; the Phase 4 review will include them.

**Deferred:** a scheduled task whose newest run is archived (Phase 2); the 8-day snooze cap (Phase 4);
Escape inside the Claude Design canvas (the canvas takes the key; the real page is fine).
