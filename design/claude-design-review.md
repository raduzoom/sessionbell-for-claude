# Review: Claude Design result vs the brief

Checked 2026-11-12 against `design/claude-design-handoff/DESIGN-BRIEF.md`. Result saved in
`design/claude-design-result/` (canvas version `1794498554-6029`). Round 2 re-checked the same day
against canvas version `1794503645-b4b3`: see **F** at the end. A1–A3 pass and B1–B3 are on the canvas.

**How it was checked:** all source files read (`Main.dc.html`, `sn.css`, the token, component and
contrast boards, `canvas.json`). The desktop (1280) and half-screen (800) boards were viewed on the live
canvas. The phone, state and stress boards were judged from their source, because every board is
`Main.dc.html` with different props. The contrast numbers were recomputed independently (glass
composited over the worst backdrop) and match the table exactly.

## Verdict

Very close. Every screen, token, component state and the contrast table were delivered, and almost every
rule holds. **Three design gaps** need a decision and a round in Claude Design. Everything else is a
builder fix or a yes/no for you.

## A. Design gaps (take back to Claude Design)

| # | Gap | Where | Why it matters |
|---|---|---|---|
| A1 | **Most project pills are hidden at 1280.** The list panel is 440 px wide, so only "All", "Client A" and half of "Client B" show. The other projects sit behind a horizontal scroll with no hint (the scrollbar is hidden, with no fade or arrow). At 800 the "Internal Tools" pill is cut too | `.list { width: 440px }`, `.pills { overflow-x: auto }` | The menu is how you see *where* work is waiting (brief §3). Hidden counts are hidden work |
| A2 | **Titles cut at about 30 characters at 1280** ("TICKET-240 Web chat: foreign a…"), while the detail panel on the right is mostly empty space | `.row-title` is one line with an ellipsis; list 440 px | The title is how you recognise *which* session it is (brief §1). Titles run up to about 70 characters |
| A3 | **No one-click open at 800 px.** The list is shown alone, so every session takes two clicks: the row, then **Open session** in the slide-over. At 1280 only the pre-selected session is one click away. At 800 the top row is also highlighted as selected while nothing is shown | half layout, `pick()` | The brief's goal is "then one click takes me into it", and 800 is the width used most |

**Suggested direction (my pick):**
- **A1:** move the projects into the rail, as in their own `alt-rail` sketch. It holds 8 avatars with count badges at 880 px tall, and the rail is otherwise empty (just a logo and the theme toggle). Sub-projects stay as pills above the list. The other option is pills that wrap onto two rows.
- **A2:** let titles wrap to two lines, and widen the list to about 520 px at 1280.
- **A3:** at 800, clicking a row opens the session directly, and Snooze and Dismiss move into a small menu on the row. Also, don't highlight a row while the slide-over is closed.

**Ready to paste into Claude Design:**

> Three changes, keeping everything else as it is:
> 1. Project menu: at 1280 and 800 only two or three project pills fit and the rest scroll out of sight with no hint. Move the projects into the left rail as monogram avatars with count badges (your "projects in the rail" sketch), with "All" at the top and coming-soon projects dimmed. Keep the sub-project pills above the list. Update screens 1, 2 and 10 at 1280 and 800, light and dark. The phone keeps its scrolling pill row.
> 2. Session titles: let them wrap to two lines in the list, and widen the list panel to about 520 px at 1280 (the detail panel has room to spare).
> 3. At 800 px, make the row itself open the session in one click. Put Snooze and Dismiss in a small menu on each row (one labelled button, "More actions"), and don't show a selected row while the slide-over is closed. Show the row menu open, in light and dark.
> 4. Tab title: show the total that need you, not the asked count: "(8) Sessions needing attention". Update your note.
> 5. Fix: the header theme toggle should show on the phone only; on desktop and 800 it shows next to the title as well as in the rail.

## B. Builder fixes (no design decision needed)

| # | Fix |
|---|---|
| B1 | **Two theme toggles on desktop and 800.** `.hdr-theme { display: none }` loses to `.icon-btn { display: grid }`, which comes later in `sn.css` with the same specificity. The header toggle is meant for the phone only (the rail has the switch). In the build: `.sn .hdr-theme { display: none }` |
| B2 | **The error state still says "Scanned just now · 120 session files"** next to "361 of 361 files unreadable". Partly my fixture's fault (fixed now: the message says 120 of 120). In the build, the header line in an error state says when the scan ran, without the healthy-looking dot |
| B3 | The `.hint` line height is 18 px on 13 px text (1.38). Use 20 px to stay within 1.4–1.6 |

## C. Your call (yes/no)

1. **Tab title count.** They show "(4) Sessions needing attention", which is the *asked* count. The handoff (§9) says the tab shows the *total* that needs you (8 here). Total *(my pick, it matches the handoff)* or asked?
2. **Accent use.** Green is on **Open session**, on every "Asked" badge, and on the "N asked" chips (pills and section header): up to 8 green marks on one screen. The brief allowed the primary action plus one other element. They all mean "asked", so I'd keep it *(my pick)*. The alternative is outlined count chips with green text.
3. **Copy they added** (good, needs your OK): the action-bar hint "Opens it in the Claude app. It stays on this list until its state changes."; bubble labels "The session asked" / "Status" / "Needs from you" / "Summary"; "No counts while the scan is failing…"; "No sessions to show"; loading labels "Opening…", "Snoozing…", "Dismissing…".

## Decisions (2026-11-12, the user took the recommended options)

- A1: projects move into the rail; sub-project pills stay above the list. A2: two-line titles, list about 520 px wide at 1280. A3: at 800 a row click opens the session; Snooze and Dismiss go in a row menu.
- C1: the tab title shows the total that need you. C2: green stays on every "asked" mark. C3: the added copy is approved.

## D. What passes

- **Product model:** state order, sections, Stale and Hidden as "Archived"-style rows, sub-project row with General, the filter applying to every section, "N more need you in other projects" with **Show all projects**, Snooze menu, Dismiss, Undo for 8 s with focus moving to the next session, empty / late / error states with no "0" during an error.
- **WhatsApp patterns:** chat-list rows, unread-style badges, two panes, the question as a bubble, an action bar that doesn't look like a text box, toast with Undo, phone push view with a back arrow.
- **Glass:** blur only on the rail, panels, menu and toast; a solid version through `prefers-reduced-transparency`, `@supports` and a forced class; neutral backdrop; smoky dark theme.
- **Rules:** 8 pt spacing, near-black ink, one filled primary, five button states, targets 44–48 px, states readable without colour (fill, dashed, outline, dot plus label and icon), 160–200 ms motion with reduced motion, keyboard (roving focus in the pills, arrows/Home/End/Enter in the list).
- **Contrast:** 76 pairs, all pass. Recomputed: list glass #EFF2F5 / #1D242C, detail #F6F8FA / #202730, selected row #DEE2E6 / #2F363D, all matching. Badge borders on a selected row also pass (lowest: stuck border 3.43:1 in light).
- **Deliverables:** tokens, components, all 11 screens plus the 800 slide-over, contrast table, change notes, rail sketch.

## E. Boards by roadmap phase

- **Phase 3 (read-only page):** s01 (all widths), s02 and s02b, s03, s03b, s06 (Stale), s07, s08, s09, s10 and s10b, s11, plus tokens, components and contrast.
- **Phase 4 (Snooze, Dismiss):** s04, s05, s06 (Hidden with Show again), and s12 (the 800 row menu from A3).

**Source priority when they disagree:** handoff behaviour > fixed copy > tokens (`sn.css`) > components > screens.

## F. Re-check after round 2 (2026-11-12)

Canvas version `1794503645-b4b3`, saved in `design/claude-design-result/`. Checked from the saved source,
on the live canvas in Chrome (every board, light and dark), and by keyboard on the playable boards.
Round 2 was done in this same session, not by an independent reviewer.

| # | Asked for | Result |
|---|---|---|
| A1 | Projects in the rail at 1280 and 800: "All" first, coming-soon dimmed, count badges; sub-project pills above the list; screens 1, 2 and 10 at 1280 and 800; the phone keeps its pill row | **Pass.** Rail avatars with a badge counting what needs you (green when something asked, "9+" over 9); coming-soon dashed with no badge; name in a hover/focus tooltip and in a list header. Sub-project pills now wrap, so "General" never scrolls out of sight. New boards s02b and s10b; phone unchanged |
| A2 | Two-line titles; list about 520 px at 1280 | **Pass.** `.list` is 520 px; titles clamp at two lines. The 70-character "Release checklist generator…" title shows in full |
| A3 | One click opens at 800; Snooze and Dismiss in a row menu ("More actions"); no selected row while the slide-over is closed; row menu shown open | **Pass.** Row click opens the slide-over with focus inside; the menu holds both Snooze options and Dismiss; selection shows only while it's open; board s12 shows the menu open, in light and dark |
| C1 | Tab title shows the total | **Pass.** Note 9 reads "(8) Sessions needing attention" |
| B1–B3 | Builder fixes | **Done on the canvas** too: one theme toggle (phone header only); error header says "Last scan just now" with no dot or count; hint line height 20 px. Keep them in the build |

**Also added in round 2** (beyond the five asks): the 800 slide-over is modal for the keyboard (Tab stays
inside, focus returns to the row on close, the closed slide-over is out of the Tab order); both menus
follow the menu-button pattern (focus moves to the first item; arrows, Home, End; Escape returns focus);
the 800 and 375 main-view boards are playable; board 6 now shows the Hidden rows; contrast table grew to
82 pairs (the rail badge and coming-soon ring), all passing.

**New copy, approved 2026-11-12:** "More actions"; "Last scan just now" (error header); the list header
"All projects" or the project name; the rail tooltip "Client A · 4 need you · 3 asked"; the "coming soon"
tag in the list header.

**Builder notes for Phase 3:**
- The rail doesn't scroll. With 8 projects it needs about 700 px of height; below that, let the avatar
  list scroll (`overflow-y: auto`) so it never runs into the theme toggle.
- Escape can't be tested inside the canvas (the viewer exits Play on Escape before the board sees it).
  Test the Escape handlers on the real page.
- Keyboard use on the phone board wasn't tested.

**Verdict:** Phase 1 design is complete. Nothing goes back to Claude Design.
