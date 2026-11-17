# Sessions needing attention: roadmap

Status: **approved** (2026-11-12) with the recommended answers to the open questions (see Decisions).

Source of truth for behaviour: [`handoff/handoff.html`](../handoff/handoff.html) (the build handoff:
data rules, contracts, security, pitfalls). This roadmap changes only the **look** (WhatsApp-like
and glassmorphic) and the order of work. Where the two disagree on behaviour, the handoff wins.

## Global constraints

- macOS only, local Code-tab sessions only, every account/org folder. Nothing hosted, nothing deployed.
- Python 3 standard library only. The page is one static `index.html` (inline CSS + plain JS), no build step.
- Server on `127.0.0.1:8790` only (never 3000). Record the port in `AGENTS.md`.
- Read-only towards the Claude app. The tool's own state lives in its own folder.
- One scanner writes `status.json`; every display only reads it. Only the server writes `state.json`.
- `status.json`, `state.json`, `logs/` are git-ignored from the first file (they hold real titles). They live in
  `data/`, marked ignored by Dropbox so they never sync (2026-11-12; the handoff had them at the top level).
- Design work uses made-up data only. Never screenshot the live page.
- No git commands unless asked. Delete with `trash`, never `rm`.

## Review focus (what would hurt the user most)

| # | Failure | Phase that owns the test |
|---|---|---|
| 1 | A wrong "0 waiting" (format drift, scanner dead, bad `projects.json`) shown as calm | 2, 3 |
| 2 | A session that asked a question is missing from the list, or is filtered out of view | 2, 3 |
| 3 | Real session titles leak (design upload, screenshots, notifications on the lock screen) | 1, 3 |
| 4 | Glass styling makes text unreadable (contrast under 4.5:1 on some backdrop, or in dark mode) | 1, 3 |
| 5 | Snooze/Dismiss hides something forever, or a cross-site page writes `state.json` | 4 |

---

## Phase 0: Scaffolding (small, needs your OK)

- `AGENTS.md` + `CLAUDE.md` symlink: what the project is, port 8790, the rules above, "read `handoff/handoff.html` first".
- `.gitignore`: `status.json`, `state.json`, `logs/`, `design/**/build/`, `*.zip`.
- `git init`? Only if you want it (see open questions).
- **Done when:** the files exist; nothing runs yet.

## Phase 1: Claude Design handoff (the first real phase)

**Goal:** a zip you upload to Claude Design that lets it design the whole UI in one go: a friendly,
WhatsApp-like dashboard with a glassmorphic finish, in light and dark, desktop, half-screen and phone.

### 1a. What goes in the package (`design/claude-design-handoff/`)

| File | Contents |
|---|---|
| `DESIGN-BRIEF.md` | The brief (outline below) |
| `status-fixture.json` | Made-up data in the real `status.json` shape, relative times (`*AgoMs`) so it never looks old. Includes edge cases: very long title, empty "needs", 2-line question, 9+ asked, a scheduled task, stale and hidden items, a sub-project |
| `fixture-states/` | `normal`, `empty`, `scanner-late`, `error`, `one-project-selected` variants |
| `reference/moodboard.png` | Your attached screenshot, with notes on what to take and what to leave |
| `reference/today-*.png` | The current page (`handoff/build/screenshots/`), as "what exists, what to improve" |
| `reference/today-snapshot.html` | The current page with made-up data, opens from disk (`handoff/build/snapshot.html`) |
| `make_handoff.py` | Writes the fixtures, checks them for forbidden names / phone numbers / real ticket keys, copies references, zips everything |

### 1b. Brief outline (`DESIGN-BRIEF.md`)

1. **Purpose in one line:** in under 3 seconds, how many sessions need me, which ones, what each wants, then one click into it.
2. **Who:** one person, own Mac, glancing many times a day; often a half-screen window.
3. **The product model** (from handoff §3): states asked > stuck > blocked > review > unread; sections Needs you, Scheduled, Stale (collapsed), Quieter, Hidden; projects and sub-projects; Snooze (1 h / tomorrow 9:00) and Dismiss-until-it-changes, both with Undo.
4. **The visual direction**
   - **WhatsApp patterns, our own identity** (no WhatsApp logo, name or exact brand green):
     | WhatsApp pattern | Our meaning |
     |---|---|
     | Chat list row: avatar, name, last message, time, unread badge | Session: project avatar, title, the "needs" line, time waiting, state badge |
     | Unread count badge | "asked" (a question waiting for you) |
     | Open chat on the right, message bubble | Selected session: its question as an incoming bubble, details, actions |
     | Composer bar at the bottom of the chat | Action bar: **Open session** (the one primary), Snooze, Dismiss |
     | "Archived" row at the top of the list | "Stale (4)" and "Hidden (2)" rows |
     | Filter pills (All / Unread / Groups) | Project pills, sub-project second row |
     | "Chat archived · Undo" toast | "Snoozed until 15:42 · Undo" |
     | Phone: list, tap pushes the chat view | Phone: list, tap pushes the session view, Back returns |
   - **From the moodboard (take):** soft cool-grey backdrop, frosted white panels with large radii, a left icon rail, round icon buttons, black filled pill for the active tab, an avatar strip with count badges, generous whitespace, light/dark toggle at the bottom of the rail.
   - **From the moodboard (leave):** the flow/journey board, people photos (sessions have no people: use project monograms or simple glyphs), red count badges (red is for errors only), many equal-weight icon buttons without labels.
   - **Glass rules:** blur only on large surfaces (rail, list panel, detail panel), never per row; panel tint opaque enough that every text passes 4.5:1 over the worst part of the backdrop, in both themes; a solid fallback for `prefers-reduced-transparency` and no `backdrop-filter`; no purple-to-blue gradients.
5. **Hard rules** (from `~/Dropbox/Configs/claude/.claude/guides/ui-design.md`): 8 pt grid; body line height 1.4–1.6; near-black ink; one filled primary per screen; verb + object labels; five button states; targets 44–48 px; two base colours + one accent, accent on the main action plus at most one other element; status colours semantic, red for errors only.
6. **Fixed UI copy, word for word:** Open session · Snooze · Snooze 1 hour (back at 15:42) · Snooze until tomorrow 9:00 · Dismiss · Undo · Show again · Show all projects · "3 more need you in other projects" · "Scanner hasn't run for 9m" · "Turn started but never finished: may be a permission prompt or a slow tool." · section names. The empty state ("Nothing needs you right now", with when it last checked) and the error banner text are drafts the designer may improve.
7. **Real text lengths:** titles up to ~70 chars, questions up to ~160 chars, repo names up to ~30, up to 8 projects.
8. **Screens to deliver:** main view (all projects), a sub-project selected, a session selected (detail pane), the Snooze menu, the Undo toast, Stale and Hidden open, empty, scanner late, error; each in light and dark; at 1280, 800 and 375 px.
9. **What to send back:** tokens (colour, glass tint/blur/border, radius, spacing, type, shadow) for both themes, a component inventory with all states, the screens above, and contrast numbers for every text-on-glass pair.

### 1c. Checks and exit

- `make_handoff.py` fails on any forbidden name, phone-number pattern or real ticket key in the zip.
- I read the zip's file list and the brief once more before you upload.
- **Done when:** you have uploaded the zip and Claude Design's result is back in `design/claude-design-result/`.
- **Then (1d):** I check the result against the brief and list the gaps. I don't fill them in; you take them back to Claude Design. Sources rank: handoff behaviour > fixed copy > tokens > components > screens.

## Phase 2: Scanner and calibration (read-only)

- `scanner.py` per handoff §6, `--print` and `--no-notify`; `projects.json` with your real folders.
- Test the deep link opens the right session; test the error paths (empty folder, unreadable files, every `projects.json` error).
- **Done when:** the printed list matches your own count of sessions that need you.

## Phase 3: Server, page and notifications (read-only UI)

- `server.py` with every guard in handoff §8 (Host check, 127.0.0.1, no-store…), `GET` routes only for now.
- `index.html` built from the Claude Design result: chat-style list + detail pane, project pills, Stale/Hidden rows, glass with solid fallback, light/dark, keyboard navigation, `__STATUS_SOURCE__` snapshot hook, `textContent` only.
- Notifications for new questions only, titles only, `osascript` with `argv`.
- Compare built screens with the boards in light and dark at 1280/800/375; measure contrast with a tool.
- **Done when:** the count matches the app, no console errors, a test notification appears, screenshots match the boards (differences listed).

## Phase 4: Snooze, Dismiss and running at login

- `POST /state` with the Origin/Content-Type/size/validation guards; `state.json` atomic writes and pruning; Undo toast; Show again.
- `install.sh` / `uninstall.sh` (two LaunchAgents, absolute `python3`, `plutil -lint`).
- **Done when:** Snooze and Dismiss survive a restart, the server tests in handoff §13 pass, both agents run after a logout/login.

## Phase 5 (optional): Menu-bar count

Native Swift `NSStatusItem` app, read-only: "N need you", one row per session that opens it, "Open dashboard"; own notifications (fixes the Script Editor wart). Uses the Phase 1 tokens.

## Phase 6 (optional): In-app pane

A Claude Code mod that reads `status.json` and draws the list beside the chat. Check first whether it can open another session; if not, ship it read-only.

## Every phase

Plan file `plans/phase-NN-<name>.md` → your review → build with tests first → run the checks → fresh review → one fix pass → report rulings and deferred items → your check before the next phase.

## Decisions (2026-11-12)

1. **Accent:** our own friendly green (not WhatsApp's brand green) on the primary action and the "asked" badge; black pills for the active tab.
2. **Desktop layout:** two panes like WhatsApp desktop (list + selected session); the most urgent session is selected on load.
3. **Avatars:** project monograms on muted colours. No people photos.
4. **Git:** not a repo. No git commands (handoff decision 18).

## Phase 1 rulings (changes from the plan above)

- `make_handoff.py` is **not** in the zip: it holds the forbidden-name list. It lives in `design/claude-design-handoff/` and writes `build/` and `design/sessions-dashboard-claude-design.zip`.
- No `one-project-selected` fixture: a filter is a view, not data. It's screen 2 in the brief instead.
- Added fixture states `busy` (12 asked, badge overflow) and split `error` into `error-format` and `error-projects`.
- `handoff/build/snapshot.html` has a real client name in one code comment. The zip's copy replaces it; the original file is left as it was.

## Status

- Phase 0: done (2026-11-12): `AGENTS.md`, `CLAUDE.md` symlink, `.gitignore`.
- Phase 1: done (2026-11-12). Zip built and checked; Claude Design result reviewed (1d) in `design/claude-design-review.md`; second round made A1–A3 and B1–B3; re-check (review §F) passed. Final result: canvas version `1794503645-b4b3`, saved in `design/claude-design-result/`. The five new copy strings in review §F are approved. Phase 3 notes: rail scrolling on short windows, test Escape on the real page, phone keyboard.
- Phase 2: done (2026-11-12). `scanner.py` writes `data/status.json` (Dropbox-ignored); 67 tests pass on Python 3.14 and 3.9; fresh review fixed 3 Important and 3 Minor findings; your count matched the "Needs you" list; the `claude://` link opened the right session in 1.6 s; empty-folder and broken-file runs give an error and exit 1. Rulings and deferred items in `plans/phase-02-scanner.md` (Build record).
- Phase 3: done (2026-11-12). `server.py` on 127.0.0.1:8790, `index.html` from the approved design, notifications in the scanner; 121 tests pass on Python 3.14 and 3.9; snapshots match the boards (on purpose: a top project bar instead of the rail, and a new Working section, both your calls); contrast lowest 4.81:1; fresh review fixed 1 Critical, 3 Important and 4 Minor findings; live tab count matched the scanner. Open on your side: confirm the test banner appeared and the count matches the Claude app. Details in `plans/phase-03-page.md` (Close-out).
- Fix (2026-11-12): "asked" never fired, because the app stopped saving `turnWrapUp.needsUser`. The scanner now reads the question from the CLI transcript's latest wrap-up (AGENTS.md, Scanner; handoff §2, §6, §14); 133 tests pass on Python 3.14 and 3.9; live count went from 0 to 1 asked. Handoff PDF rebuilt with `build_pdf.py --pdf-only` (existing screenshots); its screenshot step is broken until Phase 4 brings back the Snooze menu (AGENTS.md, Handoff PDF).
- Phase 4: done (2026-11-12). Snooze, Dismiss, Undo and Show again write `data/state.json` through `POST /state`; the page applies the scanner's hide rule at once; two LaunchAgents (scanner every 60 s, server always on) installed and running. Fresh review: all 11 findings fixed (poll/save race, Python 3.9 crash on nested JSON, stalled requests, dismiss-time checks, re-run of install.sh, toast and focus accessibility, a page-vs-scanner rule test in Node); details in the plan's Build record. Your snooze and dismiss survived a server restart. Not yet seen: a logout and login. Handoff PDF full build fixed.
- Reply bar (2026-11-12, your request): Open session moved into the session header beside the time, Snooze and Dismiss into a header "More actions" menu, and the footer is now a reply box. `POST /reply` opens the session in the Claude app and types the reply (osascript, text as argv, only into a focused text area of a frontmost Claude), then restores the clipboard and the previous app. You set the handoff's "never changes the app" rule aside for this. Tests pass on Python 3.9; checked on snapshots at 1280, 800 and 375 in light and dark; lowest new contrast 5.65:1. First real send worked on 2026-11-13 (from the installed app), after two fixes: Claude's accessibility view has to be switched on (`AXManualAccessibility`) and given ~2.5 s, and a raise-and-retry halfway through the wait. Details in `plans/reply-bar.md` and AGENTS.md, Reply bar.
- Reply bar off by default (2026-11-15, your request, before sharing): on only with `"replyEnabled": true` in `config.json`; the server refuses `POST /reply` (403) otherwise and the page hides the footer. AGENTS.md, Reply bar.
