# Phase 2: Scanner and calibration (read-only)

Status: **done** (2026-11-12). Built, reviewed, calibrated. See "Build record" at the end.

Goal: `scanner.py` reads the Claude app's session files and writes `status.json`, the file every display
reads. It is read-only towards the app and never notifies in this phase. The phase ends when the printed list
matches your own count of sessions that need you.

Sources: `handoff/handoff.html` §2, §3, §5, §6, §13, §14 (behaviour, which wins), `plans/roadmap.md`
(Phase 2). The handoff calls this "Phase 0"; the roadmap renumbered it.

## Global constraints

- macOS only; local Code-tab sessions only; every account/org folder.
- Python 3 standard library only. **Runs on Python 3.9** (`/usr/bin/python3` is 3.9.6 on this Mac; 3.14 is
  on the PATH). No `match`, and `from __future__ import annotations` for type hints.
- Read-only towards `~/Library/Application Support/Claude/`. Never write, rename or lock anything there.
- `status.json`, `state.json` and `logs/` hold real titles: git-ignored, never uploaded, never pasted into a
  chat. Tests use made-up data only.
- No git commands unless asked. Delete with `trash`, never `rm`.
- Port 8790 is for Phase 3; nothing listens in this phase.

## Review focus (what would hurt you most)

| # | Failure | How this phase tests it |
|---|---|---|
| 1 | A wrong "0 need you" shown as calm (format drift, empty folder, bad `projects.json`) | Every error path writes `error` with empty lists; tests for each |
| 2 | A session that asked a question is missing, or filtered into the wrong project | Classification and folder-matching tests; calibration against your count |
| 3 | A long-finished session shows as stuck, or a running one does | Stuck-rule tests from handoff §14 |
| 4 | Real titles leak into a chat or a file outside the project | The agent reads only `--summary` (counts, no titles); tests never copy real files |
| 5 | A hidden card stays hidden forever | Snooze and dismiss rules tested; a broken `state.json` hides nothing |

## Facts checked before planning (2026-11-12)

- Sessions folder exists: 1 account/org pair, 51 `local_*.json` files, all readable.
- Every file has `sessionId`, `title`, `lastActivityAt`, `lastFocusedAt`, `cwd`, `isArchived`.
  `postTurnSummary` 49, `turnWrapUp` 15, `lastTurnEdgeAt` 24. `status_category`: completed 41, blocked 6,
  review_ready 2, none 2.
- No scheduled-task runs on disk right now, so that path is covered by fixtures only.
- Only counts and field names were read; no titles or folders.

## Files

| File | Purpose |
|---|---|
| `scanner.py` | The scanner: library functions plus a small CLI |
| `tests/test_scanner.py` | `unittest` tests; builds made-up session files in a temp folder |
| `projects.json` | Your project menu and folder rules (you edit it; I draft the structure) |
| `.gitignore` | Add `__pycache__/` |

## Tasks (tests first, each one red before green)

### 1. Load and validate `projects.json`

`load_projects(path) -> tuple[dict | None, str | None]` returns `(config, None)` or `(None, error)`.

Tests (`ProjectsTests`): `test_valid_file`, `test_missing_file`, `test_bad_json`,
`test_rule_names_unknown_project`, `test_subproject_under_wrong_parent`, `test_default_names_unknown_project`.
Error text starts with `projects.json: `, for example
`projects.json: the rule for ~/work/client-d-bot names an unknown project "client-d".`

### 2. Folder to project

`project_for(cwd, rules, default) -> tuple[str, str | None, str]` returns `(project, subproject, repo)`.

- Cut any `/.claude/worktrees/…` from `cwd` first; `repo` is the folder's last part, plus ` (worktree)` when
  it was cut.
- Expand `~` in rules. The longest matching rule wins; a rule matches its own folder and its subfolders,
  compared as `folder + "/"`.
- No match goes to `default`.

Tests (`FolderTests`): `test_exact_folder`, `test_subfolder`, `test_worktree_inherits_repo`,
`test_lookalike_prefix_does_not_match` (`tools-old` vs `tools`), `test_longest_rule_wins`,
`test_no_match_goes_to_default`.

### 3. Read session files and check health

`read_sessions(sessions_dir) -> tuple[list[dict], int, int]` returns `(sessions, problems, total)`. It globs
`*/*/local_*.json`. A problem is a file that isn't valid JSON or lacks `sessionId`, `title` or
`lastActivityAt`.

`health_error(sessions, problems, total) -> str | None`:

| Condition | Error |
|---|---|
| No files | `No session files found. The Claude app may have moved its sessions folder.` |
| Problems over 10% of files | `Can't read session status, format may have changed (P of T files unreadable).` |
| No session has `postTurnSummary` or `turnWrapUp` | `Can't read session status, format may have changed (no file has a status field).` |

Tests (`HealthTests`): `test_empty_folder`, `test_all_unreadable`, `test_ten_percent_is_ok`,
`test_over_ten_percent_fails`, `test_missing_required_field_counts_as_problem`, `test_no_status_fields`,
`test_scans_every_account_and_org`.

### 4. Classify

`classify(s, now) -> str | None` exactly as handoff §6, and `needs_text(s) -> str`
(`wrap.needsUser or summary.needs_action or summary.status_detail or wrap.description or ""`).

Tests (`ClassifyTests`): `test_asked`, `test_blocked`, `test_review_ready`, `test_unread`,
`test_finished_and_seen_is_none`, `test_stuck_after_five_quiet_minutes`, `test_running_now_is_not_stuck`,
`test_old_session_without_edge_is_never_stuck` (the §14 pitfall), `test_needs_text_order`.

### 5. Scheduled tasks

`collapse_scheduled(sessions) -> tuple[list, list]` returns `(regular, latest_runs)`: one run per
`scheduledTaskId`, the newest by `lastActivityAt`. A task shows only when its latest run is asked, blocked
or stuck.

Tests (`ScheduledTests`): `test_keeps_only_latest_run`, `test_latest_run_finished_hides_task`,
`test_older_run_asked_does_not_show`.

### 6. Hidden (reading `state.json`)

`hidden_by(card, state, now) -> dict | None`. Snooze hides while `now < until`. Dismiss hides while the
session's `lastActivityAt` is no newer than the stored one. A missing or broken `state.json` hides nothing.
The scanner only reads this file.

Tests (`HiddenTests`): `test_snooze_active`, `test_snooze_expired`, `test_dismiss_until_new_activity`,
`test_missing_state_hides_nothing`, `test_broken_state_hides_nothing`.

### 7. Build `status.json`

`build_status(sessions, problems, total, projects, state, now) -> dict` in the handoff §5 shape:
`schema`, `generatedAt`, `error`, `projects`, `main`, `scheduled`, `stale`, `quiet`, `hidden`, `counts`.

- Skip archived sessions.
- Asked, blocked or stuck with no activity for more than 7 days goes to `stale`; otherwise `main`.
  Review-ready and unread go to `quiet`.
- Sort: asked > stuck > blocked > review > unread, newest first within each.
- Card: `sessionId`, `title`, `state`, `project`, `subproject`, `repo`, `needs` (empty for stuck: the page
  shows the fixed stuck note), `lastActivityAt`, `waitingMs`, `link` (`claude://claude.ai/epitaxy/<id>`).
- `counts.main` is main plus scheduled lines (the total the tab title shows); `counts.asked` counts asked
  cards in both; `counts.scanned` is the file count.
- With an error: the error text, empty lists, `counts.scanned` only.

Tests (`StatusTests`): `test_archived_skipped`, `test_stale_after_seven_days`, `test_sort_order`,
`test_card_fields`, `test_counts_include_scheduled`, `test_error_status_has_empty_lists`,
`test_hidden_cards_move_to_hidden_with_section`, `test_projects_menu_copied`.

### 8. Write atomically

`write_status(status, path)` writes a temp file in the same folder, then `os.replace`.

Tests (`WriteTests`): `test_replaces_file`, `test_no_temp_file_left`, `test_output_is_valid_json`.

### 9. Command line

`python3 scanner.py [--sessions-dir D] [--projects P] [--state S] [--out O] [--print | --summary]`

- Defaults: the app's sessions folder, and `projects.json`, `state.json`, `status.json` next to
  `scanner.py`.
- Always writes `status.json`. Exit code 1 when the status has an error, so a manual run shows it.
- `--print`: the grouped list with titles, project, state and waiting time, then **folders that fell to the
  default project** (to help you write rules). For your own terminal.
- `--summary`: counts only (per group, per project, per state), no titles or folders. This is the only
  output I read from real data.

Tests (`CliTests`): `test_writes_status_to_out`, `test_exit_code_on_error`, `test_summary_has_no_titles`,
`test_print_lists_unmatched_folders`.

### 10. Calibration (with you, on real data)

1. I draft `projects.json` with the menu from the design (Client A with US and Canada, Client B and C coming
   soon, Internal Tools, Knowledge Base, Other) and placeholder folders. You fill in the real folders,
   helped by the unmatched list from `--print`.
2. You run `python3 scanner.py --print` in your terminal and compare the "Needs you" list with your own count.
   I run `--summary` and see the numbers only. Any mismatch: you tell me which session (by its group and
   project, or the title if you're fine sharing it) and I fix the rule, test first.
3. Deep link: you pick one session; I run `open "claude://claude.ai/epitaxy/<id>"` and check that its
   `lastFocusedAt` changed, then you switch back. This opens the Claude app, so it waits for your OK.
4. Error paths on the real machine: `--sessions-dir` pointed at an empty temp folder, and at a temp folder of
   made-up broken files. Both must exit 1 with the error text.

### 11. Check and close

- `python3 -m unittest -v` and `/usr/bin/python3 -m unittest -v` both pass.
- A fresh reviewer (most capable model) gets this plan, handoff §2–§6 and §13–§14, the review focus above and
  the rulings, and proves any claimed bug with a probe test. One fix pass.
- Add a "Scanner" section to `AGENTS.md` (how to run it, the `--summary` rule), set the roadmap status line,
  and report every ruling and deferred minor.

## Done when

- Both Python versions pass every test above.
- Your "Needs you" count matches the printed list (and the agent-visible `--summary` agrees).
- The deep link opened the right session.
- An empty folder, unreadable files and each `projects.json` error give an error status and exit code 1.

## Decisions this plan makes (overrule any)

1. **Notifications wait for Phase 3.** The scanner never notifies here, and `--no-notify` arrives with the
   notifier. The roadmap listed the flag in Phase 2; there's nothing for it to switch off yet.
2. **Python 3.9 floor**, so the Phase 4 login agent can use `/usr/bin/python3` with nothing installed.
3. **`--summary` is the only real-data output the agent reads.** Titles and folders stay in your terminal.
4. **`counts.main` includes scheduled lines**, matching the design's tab title "(8) Sessions needing attention".
5. **A scheduled task's latest run never goes to Stale.** A recurring task's latest run is always recent;
   if it needs you, it belongs in the main list.
6. **Expired entries in `state.json` are ignored, not removed.** Pruning belongs to the server, its only
   writer (Phase 4).
7. **Stuck cards carry an empty `needs`.** The page shows the fixed stuck note from the design.
8. **Exit code 1 on an error status**, 0 otherwise.
9. **The run is one-shot.** The 60-second loop is launchd's job (Phase 4), not a loop inside the scanner.

## How to run it

My suggestion: native, one agent implementing task by task with tests first, then the fresh review. The
`superpowers:test-driven-development` skill matches that loop; I'd only use it with your yes.

## Build record (2026-11-12)

Built natively (no skill). 57 planned tests written first and seen failing with `NotImplementedError`, then
`scanner.py` until green. After the review, 65 tests pass on Python 3.14.7 and `/usr/bin/python3` 3.9.6.

First real run (`--summary`, counts only): 51 files scanned; needs you 3 (asked 1, blocked 2), stale 4,
quiet 7, hidden 0; 27 folders with no rule while `projects.json` still has placeholders. No file has a
`null` `lastTurnEdgeAt`.

**Calibration (task 10.1–10.2):** `projects.json` now holds a real menu built from the folders in your
`--print` output: Apps, AI video, Claude tools, Other dev projects (a catch-all rule for
`~/Dropbox/hosts/devsite/projects`, beaten by the longer rules for specific repos), Personal, Other (default).
No sub-projects yet. 10 folders still fall to Other; they were masked in the shared output, so you review
them in your own terminal. **You confirmed the "Needs you" list matches your own count** (2026-11-12). It
changes minute to minute: 3 at your `--print` run (one stuck that later finished, this chat while it waited
on you, one blocked), 1 a few minutes later.

**Error paths on this Mac (task 10.4):** an empty `--sessions-dir` gives "No session files found…" and exit 1;
a folder of 4 made-up files, 3 broken, gives "…format may have changed (3 of 4 files unreadable)", empty
lists and exit 1. Both wrote to a scratch `--out`; the real `data/status.json` was untouched.

**Deep link (task 10.3), checked 2026-11-12 with your OK:** `open "claude://claude.ai/epitaxy/<sessionId>"`
on a finished, already-seen session (picked by id only) moved its `lastFocusedAt` forward 1.6 s after the
call. The link opens the right session. The handoff measured about 4 s.

**Rulings** (decided during the build; the reviewer agreed with all of them):
1. `tests/__init__.py` added, so `python3 -m unittest` finds the tests.
2. One test was wrong, not the code: a lone stuck session has no status fields, which the health rule
   correctly calls an error. The test now adds a finished session beside it.
3. `lastTurnEdgeAt: null` counts as absent (the handoff says "present"). The safe side: it can't make a
   finished session look stuck.
4. `--summary` shows projects by menu position, not name, because names may be real client names.
5. `status.json` is written with mode 0600 (the temp file's default, kept by `os.replace`).
6. A missing sessions folder reads as empty and gives the "No session files found" error.
7. A missing or non-text `cwd` goes to the default project.
8. A `lastActivityAt` that isn't a finite number, or a `scheduledTaskId` that isn't text, makes the file a
   problem; problems count toward the 10% limit.
9. Only `isArchived is True` skips a session.
10. A non-number `lastFocusedAt` counts as 0 for the unread rule.
11. `needs_text` skips blank strings and trims spaces.

**Fresh review** (most capable model, made-up data only, every finding proved by a probe test):

| # | Finding | Grade | Fix |
|---|---|---|---|
| 1 | A non-text `project`/`subproject` in `projects.json` crashed the scanner, leaving the old calm `status.json` | Important | Rules need text values; tests `test_non_text_project_or_subproject_is_an_error_not_a_crash`, `test_every_projects_error_writes_an_error_status` |
| 2 | A non-text `scheduledTaskId` crashed it the same way | Important | Counts as a problem file (`test_non_text_scheduled_task_id_is_a_problem`). Plus a safety net: any exception now writes an error status (`test_crash_still_writes_an_error_status`) |
| 3 | `--summary` printed the full error on stderr, which can carry folders and project ids | Important | In `--summary` the error line gives only its kind (`test_summary_stderr_has_no_names_or_folders`) |
| 4 | Each atomic write drops extended attributes on `status.json`, including a Dropbox "ignored" marker | Minor | Deferred: a question for you (below) |
| 5 | A snooze or dismiss with `Infinity` hid a card forever | Minor | Non-finite values hide nothing (`test_non_finite_values_hide_nothing`). The 8-day cap on snoozes belongs to the server's validation (Phase 4) |
| 6 | Sessions with no folder were missing from `--print`'s unmatched list; two rules for the same folder passed | Minor | Fixed (`test_print_counts_sessions_without_a_folder`, `test_two_rules_for_the_same_folder`) |

**Decided after the review: real data moves to `data/`** (review finding 4, your call, 2026-11-12).
`status.json`, `state.json` and later `logs/` live in `data/`, marked `com.dropbox.ignored`, so they stay on
this Mac. The scanner's defaults point there, and it recreates and marks `data/` if it's missing (best effort,
via `/usr/bin/xattr`). Tests: `test_real_data_lives_in_the_data_folder`, `test_creates_a_missing_out_folder`
(67 tests, both Pythons). The `status.json` written earlier at the top level synced to Dropbox before the move;
it has been moved into `data/`, so Dropbox treats it as deleted (its copy stays in Dropbox's deleted-files
history for the usual retention period). Phases 3 and 4 use `data/` for the server, page and logs.

**Deferred and open:**
- **An archived latest run** of a scheduled task lets an older asked run show (handoff §6 order, kept as is).
- **Case-sensitive folder matching**: macOS paths aren't case-sensitive. The unmatched list in `--print`
  catches a mismatch during calibration.
- **Renamed inner fields** (`needsUser`, `status_category`) would go unnoticed by the health check; the
  handoff has the same limit. Watch it after app updates.
- Notifications and `--no-notify`: Phase 3 (decision 1).
