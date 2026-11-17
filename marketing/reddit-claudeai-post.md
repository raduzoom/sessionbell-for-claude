# r/ClaudeAI post

Post type: **video** (`images/sessionbell-demo.mp4`). Flair: the sub's project / "built with Claude" flair.
Before posting: the repo is public, has an MIT LICENSE file, and `config.json` has `"replyEnabled": false`.
Replace `<repo link>` in the first comment.

## Title

I kept missing which of my Claude Code sessions were waiting on me, so I built a small dashboard that tells me

## Body

Most of my day is in the Claude desktop app's Code tab with 8 to 10 sessions open. Some stop with a
question, some hit a permission prompt, some finish and wait for me to review. I'd only find out by
clicking through the sidebar, and a session could sit there for an hour before I noticed.

So I built Sessionbell. It's a local page that lists only the sessions waiting on you, shows what each one
asked, and opens it in the app with one click.

What it does:

- Questions first, then sessions blocked on you, then ones that look stuck (a turn that went quiet for
  30 minutes, which is usually a permission prompt)
- Shows what each working session is doing right now, taken from its plan
- A macOS banner when a session asks something new, and a count on its Dock icon if you install it as an app
- Groups sessions by project, using folder rules you write once
- Snooze, dismiss until it does something new, or pin

How it runs: everything stays on your Mac. It's plain Python (standard library only) with a small server on
127.0.0.1. It doesn't call any model and doesn't send anything anywhere. Free and open source (MIT).

The limits, up front:

- macOS and the desktop app's Code tab only, not the CLI
- It reads the app's session files, which aren't documented, so a Claude update can break it until I fix
  it. When the files look wrong it shows a red warning instead of a calm "0".
- It's a side project and not affiliated with Anthropic

The sessions in the video are made up. Repo link in the comments.

How do you keep track of yours when you run a lot of them at once?

## First comment (post it right after)

Repo: <repo link>

Install is two commands (clone, then `./install.sh`). It starts at login, and `./uninstall.sh` removes it.
Happy to answer questions, and bug reports are very welcome. It has only run on my own Mac so far.

## If the sub allows images in comments: second comment

Image: `images/sessionbell-before-after.png`

> Before and after: ten sessions in a sidebar vs. just the ones waiting on you.

## Gallery version (only if a video post isn't possible)

Title and body as above. Images and captions, in this order:

1. `sessionbell-before-after.png`: "Ten sessions open. Which ones are waiting on you?"
2. `sessionbell-demo.gif`: "Click a session to see what it asked, then open it in the app."
3. `sessionbell-wide-light.png`: "Questions first, grouped by project. Working sessions show what they're doing."
4. `sessionbell-banner.png`: "A banner when a session asks something new, even when you're in another app."
