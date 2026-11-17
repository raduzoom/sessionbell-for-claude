# Reply bar in the detail pane

Asked 2026-11-12. Built 2026-11-12, after the other sessions in this folder went idle.

As built, differences from the plan below: Snooze and Dismiss (Phase 4, added meanwhile) moved from the
footer into a header "More actions" menu; below desktop width Open session shows its icon only (tooltip
and aria-label); on a phone the header avatar hides. After a send, the app that was in front comes back.

## What changes

1. **Open session moves into the detail header**, right of the "waiting / working 1m" time. On phone width it
   shows the icon only (the label stays as its `aria-label`).
2. **The footer becomes a reply bar** in place of the hint and the button: a text box (grows to about 6
   lines) and a **Send reply** button. Enter sends, Shift+Enter adds a line. While sending: spinner and
   "Sending…", box locked. Then "Sent to <title>" and the box clears; on failure the text stays and the
   error shows under the box.
3. **One filled button per screen:** Send reply is the filled accent button; Open session in the header
   becomes the outlined secondary.

## How a reply is sent (the user chose "type it in for me", and said to disregard the handoff)

The Claude app has no API for this, so the server types it in through macOS:

1. Page: `POST /reply` with `{"sessionId": "local_…", "text": "…"}`.
2. Server checks, same guards as `POST /state`: Host, Origin is the page's own, `Content-Type:
   application/json`, small body; `sessionId` matches `^local_[A-Za-z0-9_-]{1,80}$` **and** is in the
   current `data/status.json`; text is 1–4000 characters, control characters other than newline and tab
   removed. One send at a time (409 while busy).
3. Server runs `open claude://claude.ai/epitaxy/<id>`, then waits (up to about 8 s) until that session's
   file shows a newer `lastFocusedAt`, so it knows the app switched to it.
4. `osascript` (text passed as argv, never put into the script): check Claude is frontmost, save the whole
   clipboard (every item and type, via NSPasteboard), put the reply on it marked transient (clipboard
   managers skip it), press Cmd+V then Return, put the old clipboard back.
5. Answers: 200 sent; 409 busy; 400 bad input; 404 session not in the list; 503 with a plain fix when
   macOS hasn't allowed Accessibility for the program running the server, or when Claude didn't come to the
   front (nothing is typed then).

## Tests (made-up data, the sender replaced, like the banner tests)

Server: each guard's status code, unknown session 404, long text 400, busy 409, the osascript call gets the
text as argv. Page: the header holds Open session, the reply bar posts the right JSON, Enter vs
Shift+Enter, the sending and error states. Snapshots in light and dark at 1280, 800 and 375.

## Needs the user

- A one-time Accessibility allow (System Settings › Privacy & Security › Accessibility) for the app that
  runs the server (Terminal now, python3 once it runs at login).
- The first real send, from the dashboard, to a session they choose.
