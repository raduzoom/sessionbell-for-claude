# Design brief: Sessions needing attention

A redesign of a small local dashboard. Please design the full UI described here, in light and dark, at
desktop, half-screen and phone widths. All data in this package is made up.

## 1. What it is

People who run 5–10 Claude Code sessions at once (in the Claude desktop app) lose track of which ones
have stopped and are waiting for them. This page answers one question:

> **In under 3 seconds: how many sessions need me, which ones, and what does each one want? Then one click
> takes me into it.**

- **Who:** one person, on their own Mac, glancing at it many times a day. Often in a half-screen browser
  window next to the Claude app.
- **Where:** a local web page (`http://127.0.0.1:8790`). It refreshes itself every 30 s. Nothing is hosted.
- **What it can do:** show sessions, open one in the Claude app, and hide one for a while (Snooze, Dismiss).
- **What it can't do** (don't design for it): reply to a session, show its transcript, archive or delete it,
  sign in, settings, search. There are no people, only sessions.

## 2. Today's page and why it changes

`reference/today-*.png` and `reference/today-snapshot.html` (opens from disk; add `?state=empty`,
`?state=late` or `?state=error`) show the current page. It works, and its behaviour stays. It looks like a
plain admin list: one column of identical bordered cards, every card with three buttons, and very little
warmth. We want it to feel **friendly and familiar, like a messaging app's chat list, with a light
glassmorphic finish**.

Keep from today: the project menu with counts, the "N more need you in other projects" note, the scanner
status line in the header, and the single filled **Open session** button.

## 3. The product model (fixed: design around it, don't change it)

### Session states, most urgent first

| State | Meaning | "Needs" line |
|---|---|---|
| **asked** | The session asked you a question and is waiting for the answer | The question |
| **stuck** | A turn started and never finished (maybe a permission prompt) | Fixed text: "Turn started but never finished: may be a permission prompt or a slow tool." |
| **blocked** | Waiting on something you do outside the app (make a call, sign in) | What it needs |
| **review** | Finished, ready for you to review | Short summary |
| **unread** | Finished, and you haven't looked since | Short summary |

"asked" is the one that matters most: it's the equivalent of an unread message.

### Sections

1. **Needs you** (asked, stuck, blocked). Scheduled tasks appear here too, one line per task.
2. **Stale: archive or revive?** Needs-you items with no activity for more than 7 days. Collapsed by default.
3. **Quieter** (review, unread).
4. **Hidden** (snoozed or dismissed), each with **Show again**. Collapsed by default.

Within a section: asked, then stuck, then blocked, then review, then unread; newest first within each.

### Projects

Sessions belong to a project, and some to a sub-project (e.g. *Client A → US, Canada*). The menu shows
**All**, then each project with its count of Needs-you items and how many of those asked. Some projects are
"coming soon": visible but quiet. Picking a project with sub-projects shows a second row: **All**, the
sub-projects with short labels ("US", "Canada"), and **General** (the parent's sessions with no
sub-project). A filter applies to every section. When filtered, the page says "3 more need you in other
projects" with **Show all projects**. The browser tab title always shows the total across all projects.

### Actions on a session

- **Open session** opens it in the Claude app. Opening doesn't clear it: it stays until its state changes.
- **Snooze** opens a small menu: "Snooze 1 hour (back at 15:42)" and "Snooze until tomorrow 9:00".
- **Dismiss** hides it until the session has new activity.
- Snooze and Dismiss show an **Undo** toast for 8 seconds, and focus moves to the next session.

### Page-level states

| State | What shows |
|---|---|
| Normal | Lists, header line "Scanned just now · 120 session files" |
| Empty | Nothing needs you (Quieter may still have items). A calm, positive state |
| Scanner late | The header line turns into a warning: "Scanner hasn't run for 9m". The lists still show |
| Error | A red banner with the reason, **instead of** any count. Never show "0" when we don't know |

## 4. Visual direction

### WhatsApp patterns, with our own identity

Use the patterns people already know from WhatsApp (desktop and phone). Don't copy its logo, name, wallpaper
or brand green (`#25D366`, `#00A884`); choose our own friendly green.

| WhatsApp pattern | Here |
|---|---|
| Chat list row: avatar, name, last message, time, unread badge | Session row: project avatar, title, the "needs" line, time waiting, state badge |
| Unread badge (green count) | "asked" |
| Bold name + dot for unread | "unread" in Quieter |
| Two panes on desktop: list left, open chat right | List left, the selected session right |
| An incoming message bubble | The session's question, as a bubble from the session |
| The composer bar at the bottom of a chat | The action bar: **Open session**, Snooze, Dismiss |
| "Archived (4)" row at the top of the list | "Stale (4)" and "Hidden (2)" rows |
| Filter pills (All / Unread / Groups) | Project pills with counts, sub-project second row |
| "Chat archived · Undo" toast | "Snoozed until 15:42 · Undo" |
| Phone: list → tap → chat view with a back arrow | Phone: list → tap → session view with a back arrow |

**Important:** the action bar must not look like a text input. There's no reply here, and a fake composer
would promise one.

### From the moodboard (`reference/moodboard.png`), take

- The soft, cool grey-blue backdrop and frosted white panels with large radii.
- A slim left icon rail, round icon buttons, and the light/dark toggle at the bottom of the rail.
- The black filled pill for the active tab.
- The avatar strip with small count badges (here: projects, not people).
- The generous white space and calm, low-contrast chrome.

### From the moodboard, leave

- The flow/journey board and the CRM content.
- People photos: sessions have no people. Use **project monograms** (e.g. "CA", "IT", "KB") on soft,
  muted colours instead.
- Red count badges: red is for errors only.
- Rows of unlabeled icon buttons. Only universal icons go without a label (close, back, theme toggle).
  The rail holds only things that exist: projects (optional, see §6) and the theme toggle.

### Glass rules

- Blur only on large surfaces: the rail, the list panel, the detail panel, menus and the toast. **Never per
  row.**
- Every text, chip and icon must pass contrast (below) over the **worst** part of the backdrop, in both
  themes. Make the panel tint opaque enough; don't rely on the blur.
- Give a solid, non-blurred version of each surface for `prefers-reduced-transparency` and for browsers
  without `backdrop-filter`. It should look intentional, not broken.
- Backdrop: soft neutral tones. No purple-to-blue gradients, no busy blobs.
- Dark theme: a deep, slightly cool backdrop with smoky glass, not pure black.

## 5. Hard rules

- **Spacing:** an 8 pt grid (8, 16, 24, 32…); 4 only inside a control. Even padding.
- **Type:** one family is fine (system UI: SF Pro). Clear steps between title, section heading, row title and
  body. Body line height 1.4–1.6. Lines 45–75 characters. Near-black ink (about `#1E1E1E`), never `#000`.
- **Contrast:** 4.5:1 for body text, labels and chips; 3:1 for large text (24 px, or 19 px bold) and for
  icons and borders that carry meaning. Both themes.
- **Buttons:** one filled primary per screen (**Open session** for the selected session), outlined
  secondary, text-only tertiary. Verb + object labels. Five states each: default, hover, pressed, disabled,
  loading. Targets 44–48 px tall with about 8 px between them.
- **Colour:** two base colours plus one accent (our green). The accent goes on the primary action and at most
  one other element (the "asked" badge). State colours are semantic. Red only for errors. Project avatar
  colours must be muted and must not be confused with state colours.
- **State without colour:** every state also has a text label or a distinct shape, so it reads in
  greyscale and for colour-blind users.
- **No "AI look":** no nested cards, no gradient buttons, no emoji labels, no uneven spacing.
- **Motion:** short and calm (150–200 ms). Respect `prefers-reduced-motion`.
- **Keyboard:** visible focus on everything. Arrow, Home and End keys move through the project menu and the
  list; Enter opens the selected session.

## 6. Layout

- **Desktop (1280 px):** rail · list panel · detail panel. The most urgent session is selected on load, so
  the detail panel and its **Open session** button are always there. Choose where the project menu lives:
  pills above the list (my default), or project avatars in the rail like the moodboard's avatar strip. Show
  the one you recommend, and a small sketch of the other.
- **Half-screen (800 px):** your call: two narrower panes, or the list only with the detail sliding over it.
  It's the width people use most, so it must not feel cramped.
- **Phone (375 px):** the list fills the screen; tapping a row pushes the session view with a back arrow.
  The project menu becomes a horizontally scrolling row. No horizontal page scroll.

### The detail panel shows (and nothing else)

The project avatar and name, the sub-project, the session title, the state label, "waiting 25m", the
repo (e.g. "client-a-bot (worktree)"), the question or "needs" line as a bubble from the session, and the
action bar. There is no transcript or history.

## 7. Fixed copy (use word for word)

- Page title: **Sessions needing attention**
- Sections: **Needs you** · **Stale: archive or revive?** · **Quieter** · **Hidden**
- Buttons: **Open session** · **Snooze** · **Dismiss** · **Show again** · **Show all projects** · **Undo**
- Snooze menu: **Snooze 1 hour (back at 15:42)** · **Snooze until tomorrow 9:00**
- Menu: **All** · **General** (sub-project row) · counts like "4" and "3 asked"
- Filter note: **3 more need you in other projects**
- Header: **Scanned just now · 120 session files** / warning: **Scanner hasn't run for 9m**
- Stuck note: **Turn started but never finished: may be a permission prompt or a slow tool.**
- Time: **waiting 8m**, **waiting 22h**, **waiting 2d**

**Drafts you may improve** (keep the meaning): empty state "Nothing needs you right now · Checked just
now"; toasts "Snoozed until 15:42 · Undo" and "Dismissed until it changes · Undo"; the error banner
heading "Can't show sessions right now", followed by the reason from the data.

## 8. Data

`status-fixture.json` is the exact shape the page receives (with times made relative so screens never look
old: `*AgoMs` means "this long ago"). Every screen should be designable from it.

```
counts:   { main, asked, stale, quiet, hidden, scanned }
projects: [ { id, name, comingSoon?, children: [ { id, name } ] } ]
main | scheduled | stale | quiet | hidden: [ card ]
card:     { sessionId, title, state, project, subproject, repo, needs, waitingMs, link }
hidden card also: { section, hiddenBy: { kind: "snooze", untilInMs } | { kind: "dismiss" } }
error:    null, or a one-line reason (then every list is empty)
```

`fixture-states/`: `empty`, `scanner-late`, `busy` (12 asked: test badge overflow, e.g. "9+"),
`error-format`, `error-projects`.

**Real text lengths:** titles up to ~70 characters (many start with a ticket key like "TICKET-240"),
questions up to ~160 characters (show two lines in the list, all of it in the detail panel), repo names up to
~30, up to 8 projects, project names up to ~20.

## 9. Screens to deliver

Each in **light and dark**:

1. Main view, All projects, normal data — at 1280, 800 and 375 px.
2. A sub-project selected (Client A → Canada), with the "more in other projects" note.
3. The phone session view (after tapping a row).
4. The Snooze menu open.
5. The Undo toast.
6. Stale and Hidden expanded.
7. Empty.
8. Scanner late.
9. Error (both reasons).
10. Busy (badge overflow, long titles and two-line questions).
11. The solid (reduced-transparency) version of the main view.

## 10. What to send back

1. **Tokens** for both themes: colours (backdrop, glass tint, glass border, ink levels, accent, state
   colours, avatar palette), blur and saturation, radii, spacing, type scale, shadows.
2. **Component inventory with every state:** session row (each session state; selected, hover, focus),
   state badge, project avatar, project pill (active, with counts, coming soon), section header (collapsed
   and open), detail panel, question bubble, action bar, buttons (5 states each), snooze menu, toast,
   header status line (normal and late), error banner, empty state.
3. **The screens** in §9.
4. **A contrast table:** every text-on-glass and badge pair, with its ratio, in both themes.
5. A short note on anything in this brief you changed or think should change, and why.
