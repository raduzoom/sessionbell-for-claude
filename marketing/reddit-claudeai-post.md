# r/ClaudeAI post

Rewritten 2026-11-23 from the user's own draft (their voice, their angle: many projects, the sidebar, Codex).
The earlier "I kept missing which sessions were waiting on me" version is in the log of `reddit-plan.md`.

Post type: **image gallery** (or text post with the images inline). Flair: the sub's project /
"built with Claude" flair.

Before posting:

- [x] The local work is on GitHub (pushed 2026-11-23): `"replyEnabled": false`, MIT LICENSE, README
      installs from `https://github.com/raduzoom/sessionbell-for-claude.git` into `sessionbell-for-claude`.
- [ ] Image 1 (your Claude sidebar) shows only made-up titles, or is blurred. Real titles never go public.

## Title

I juggle 30 projects in the Claude desktop app and the Code tab makes it hard to find the next one that needs me, so I built a dashboard

## Body

I usually have around 30 projects in the Claude desktop app's Code tab and work in 4 or 5 of them at
once. Once I send a prompt off in one project, finding the next one that needs me is frustrating.

I tried a few sidebar setups. This one works best for me:

*[Image 1: your sidebar, made-up or blurred titles. Caption: "The sidebar setup that works best for me"]*

But it doesn't actually sort by last updated. I'd say even the Codex app's dashboard does this better.

How have you solved this?

For me, I built a small tool that's been a lifesaver: **Sessionbell**. It's free and open source (MIT).

*[Image 2: `images/sessionbell-wide-light.jpg`. Caption: "Sample data, of course"]*

What it does:

- Lists only the sessions waiting on you: questions first, then blocked ones, then ones that look stuck
- A macOS banner when a session asks something new, and a count on its Dock icon if you install it as an app
- Groups sessions by project, using folder rules you write once
- Snooze, dismiss until it does something new, or pin
- Opens any session in the app with one click

*[Image 3: `images/sessionbell-banner.jpg`. Caption: "A banner when a session asks you something"]*

Setup is short. On a Mac with the Claude desktop app:

1. `git clone https://github.com/raduzoom/sessionbell-for-claude`
2. `cd sessionbell-for-claude && ./install.sh`
3. Open http://127.0.0.1:8790, and install it as an app from Chrome or Safari if you want the Dock badge

It starts at login, and `./uninstall.sh` removes it. Everything stays on your Mac: plain Python, a small
server on 127.0.0.1, no model calls, nothing sent anywhere.

Two things I could use help with:

- **Replying from Sessionbell.** I tried answering a session straight from the dashboard, but it's flaky
  right now. The app has no API for this, so it opens the session and pastes into the message box through
  macOS Accessibility. It's off by default. If you've made typing into an Electron app reliable, I'd love
  suggestions.
- **App updates.** It reads the app's session files, which aren't documented. When the Claude app changes
  them, Sessionbell needs an update. Until then it shows a red warning instead of a wrong "0".

**How I built it with Claude**

I built it with Claude Code, in the same desktop app it watches. I made the decisions and reviewed each
step; Claude Code wrote the code.

- Planning: I wrote a handoff doc with the behaviour and the privacy rules (the session titles never leave
  the Mac). Claude Code turned it into a roadmap of phases, and every phase started with a plan file I
  reviewed before any code was written.
- Design: Claude Code packed a design brief with made-up sessions into a zip, I gave it to Claude Design,
  and the page's look came back from there. Claude Code then built the page from that result and checked
  it against the brief.
- The tricky part: the app's session files aren't documented. Claude Code worked out which fields mean
  "asked you something", "blocked" or "finished", reading only field names and counts so my real session
  titles never ended up in the chat. It also found the `claude://` link the app uses to open a session.
- Testing: it writes the tests first, on made-up data. There are about 250 now, and none of them opens a
  real session.
- Every time the app changed something (a field it stopped saving, background agents that made busy
  sessions look idle), I'd describe what I saw and Claude Code tracked it down and fixed it.

Limits: macOS and the desktop app's Code tab only (not the CLI, not Cowork). It's a side project and not
affiliated with Anthropic.

## First comment (post it right after)

Repo: https://github.com/raduzoom/sessionbell-for-claude

Happy to answer questions about it or about building it with Claude Code. Bug reports are very welcome;
it has only run on my own Mac so far.

## Mod rule 7 (Showcase), checked 2026-11-17

The first try was removed for missing (b), "how Claude helped". This body covers: built it myself (a),
built with Claude Code and for Claude (b), what it is and how Claude helped (c), free with install steps
in the body (d), plain language (e), no affiliate links (f), no job seeking (g). The flood bot allows one
post per hour.

## Video version (if you'd rather lead with the demo)

Post type video, `images/sessionbell-demo.mp4`. Same title and body, without the image placeholders.
