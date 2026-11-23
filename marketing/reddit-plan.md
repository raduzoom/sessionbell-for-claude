# Reddit marketing plan

Written 2026-11-17. For the public release of the dashboard (named Sessionbell on 2026-11-17; see `naming.md`).

## What we're selling, in one breath

You run ten Claude Code sessions in the Claude desktop app. Some are waiting on you: a question, a
permission prompt, a finished turn. This is a free, local, open-source page that lists only those, says
what each one wants, and opens it in one click. Runs on your Mac, Python standard library, nothing uploaded.

The pain is specific and widely felt by heavy users. Reddit rewards exactly that: a maker showing a small
tool that scratches their own itch, with a GIF. It punishes ads, link drops and marketing voice.

## Goal and how we'll know

| Metric | Target after 4 weeks | Where to read it |
|---|---|---|
| GitHub stars | 300 | repo page |
| Unique cloners | 150 | GitHub → Insights → Traffic |
| Issues / PRs from strangers | 10 | repo |
| Top post upvotes | 200+ in r/ClaudeAI | the post |
| Referrers | Reddit as top source | Insights → Traffic → Referring sites |

The targets are guesses for a niche tool; the point is to compare posts against each other, not hit a number.
Record each post's numbers at +24 h and +7 days in the log at the end of this file.

## Before the first post (blockers)

1. **Name.** "Claude" in the product name is Anthropic's trademark, and mods of Claude subreddits may treat
   it as an official tool. Use a name of our own with "for Claude" as a descriptor (e.g. "Waitlist for
   Claude Code", "Nudge: sessions waiting on you"). Run the check in
   `~/Dropbox/hosts/devsite/projects/general-app-knowledge/docs/app-naming-and-trademark-check.md` first.
2. **Public repo** with a license (MIT), and `replyEnabled: false` in the published `config.json`.
3. **Demo GIF, 8–15 s**, from `snapshot-demo-light.html` (made-up sessions): list → click a "Needs you"
   card → pane shows the question → Open session. Also a dark-mode still. Never the live page.
4. **README top**: the GIF, one-line pitch, the two install commands. Reddit readers click through and
   decide in five seconds.
5. **Reddit account.** Post from the user's own account with some history in these subs. A brand-new
   account with a link post gets auto-removed in most of them. If the account is new, spend week 0
   commenting helpfully in r/ClaudeAI and r/ClaudeCode first (see "Ongoing").
6. **Read each sub's rules, pinned posts and flairs before writing its post, not just before posting.**
   Turn the rules into a checklist next to the post text and tick it. r/ClaudeAI's bot removed the first
   post for not saying how Claude helped build it (2026-11-17). See
   `~/Dropbox/hosts/devsite/projects/general-app-knowledge/docs/reddit-launch-posts.md`.

## Where to post, in order

Ranked by fit (heavy Claude Code desktop users on Macs) over size.

| Wave | Subreddit | Angle | Notes |
|---|---|---|---|
| 1 | r/ClaudeAI | "I kept losing track of which sessions were waiting on me" | Core audience. Use the project/tool flair. |
| 1 | r/ClaudeCode | Same story, more technical: how it reads session state, the "stuck" rule | Post 1–2 days after r/ClaudeAI, not the same day. |
| 2 | r/macapps | Native-feeling Mac utility, local, free, installs as a Dock app | Strict about dev self-promotion; check the current rule and flair. |
| 2 | r/selfhosted | Local-only, loopback server, LaunchAgents, no telemetry | They care about privacy and how it runs, not about AI. Lead with that. |
| 3 | r/Python | Standard-library-only Python 3.9, no deps, launchd | Many Python subs allow showcase posts only on set days or in a thread. |
| 3 | r/SideProject | Built for myself, now public | Low-stakes, friendly to makers. |
| 3 | r/vibecoding, r/ChatGPTCoding | Juggling many agent sessions | Only if waves 1–2 went well; same pain, broader crowd. |

Skip: r/programming (bans most self-promotion), r/MacOS (prefers news and help), anything unrelated.
One sub per day at most, never a cross-post of the same text: each post is written for its crowd.

## Timeline

- **Week of 17 Nov (now):** blockers above. Name, repo, GIF, README.
- **Week of 24 Nov:** skip launching. US Thanksgiving (26 Nov) empties Reddit. Comment in the target subs.
- **Tue 1 Dec:** r/ClaudeAI. **Thu 3 Dec:** r/ClaudeCode.
- **Week of 7 Dec:** r/macapps (Tue), r/selfhosted (Thu). Fix whatever wave 1 reported first, and say so.
- **Week of 14 Dec:** r/Python (on its showcase day), r/SideProject.
- **From then on:** the ongoing loop below, plus one "update" post per sub only when there's a real release
  (e.g. menu-bar count, Phase 5) and at least a month has passed.

Post Tuesday to Thursday, 8–10 am US Eastern (14:00–16:00 in Romania), when US and Europe overlap.
Clear the next 3 hours: early replies decide whether a post rises.

## How to write the posts

- First person, maker voice: "I built", "I kept", "it's rough in places". No "game-changer", no emojis, no
  "Introducing".
- Problem first, tool second, link last. The GIF in the post itself (image/video post with the link in the
  first comment, or a text post with the GIF linked at the top; check what the sub allows).
- Say what it doesn't do: macOS only, desktop app's Code tab only, reads undocumented files that a Claude
  update can break. Saying it up front wins trust and saves the top comment.
- Say it's free and has no account, telemetry or model calls. People will ask.
- End with one real question to start comments: "How do you keep track of yours?"

## Images

All in `marketing/images/`, all made-up data (`tools/demo-fixture.json`). Never a screenshot of the live page
or the real Claude sidebar; delete any such screenshot before posting.

| Image | File | Use it in |
|---|---|---|
| Demo video, about 20 s: All → the Pocket Shop tab → dismiss the stuck session (Undo toast) → pin the dark-mode question → click an Asked card → Open session | `sessionbell-demo.mp4`, `.gif` | Every post: the lead image |
| Wide view, light / dark | `sessionbell-wide-*.png` | r/ClaudeAI (light), r/ClaudeCode and r/selfhosted (dark) |
| Narrow (half-screen) view, light / dark | `sessionbell-narrow-*.png` | Gallery second image; r/macapps |
| macOS banner close-up: "Sessionbell / Fix dark mode on the settings screen" | `sessionbell-banner.png` (crop), `sessionbell-banner-scene.png` (whole desktop) | Gallery; shows it nudges you while you're elsewhere. Mock-up: the real banner shows Script Editor's icon, not Sessionbell's, until a native app exists |
| Before / after: a cluttered sidebar of ten sessions vs. Sessionbell's three that need you | `sessionbell-before-after.png` | r/ClaudeAI, r/SideProject: the problem in one look |
| Later: Dock badge close-up | — | r/macapps |
| Later: how-it-runs diagram (scanner → JSON → 127.0.0.1 server → browser, no network) | — | r/selfhosted, r/Python |
| Later: reply bar in use | — | Only where the post mentions replying; say it's off by default |

Remake them: the screenshots and video come from `design/page-check/build/snapshot-demo-*.html` (run
`python3 -I tools/snapshot.py` first); the banner and before/after from `marketing/images/src/*.html`, rendered
with headless Chrome at 1600×1000, 2×. The video is recorded by `marketing/images/src/record.py` (Playwright, installed Chrome, fake cursor, `claude://` clicks blocked), then encoded with ffmpeg; the commands are at the top of that file. It ends on a title card ("Free · runs on your Mac · open source").

Reddit galleries take up to 20 images, but lead with the video and keep it to 3–4 images.

## Draft posts

### r/ClaudeAI

Final text: see `reddit-claudeai-post.md`.

### r/macapps

**Title:** [Free/open source] A local dashboard that tells you which Claude Code sessions are waiting on you

Lead with: installs as a Dock app (PWA), Dock badge count, light and dark, two LaunchAgents, uninstall
script that leaves nothing running. Mention it's not a native Swift app yet and a menu-bar version is
planned, before someone asks.

### r/selfhosted

**Title:** Loopback-only dashboard for Claude Code desktop sessions: stdlib Python, launchd, no telemetry

Lead with how it runs: scanner every 10 s writes a JSON file, a stdlib HTTP server on 127.0.0.1 with Host
and Origin checks serves it, state in a Dropbox-ignored folder. The AI part is the use case, not the pitch.

### r/Python

**Title:** Standard library only, runs on macOS's /usr/bin/python3 (3.9): a dashboard for agent sessions

Lead with the constraints and what they cost: no deps, `http.server`, reading big JSONL tails cheaply
(1 → 4 → 16 MB until a whole plan list is found), atomic writes, tests that run the page's JS in Node
against the Python rule.

## Questions to have answers ready for

| They'll ask | Answer |
|---|---|
| How is this different from AgentManager / c9watch / claudectl? | Those mostly watch terminal (CLI) sessions; this reads the desktop app's Code tab, and says what each session wants. See `naming.md`. |
| Doesn't the app already notify you? | It marks unread sessions; this shows *what* each wants, groups them, and catches stuck turns. |
| Windows / Linux / the CLI? | Not now. It reads the desktop app's files on macOS. Say if you'd use a CLI version. |
| Why does the reply box need Accessibility? | The app has no API, so it types into the message box. Off by default; explain the four steps from the README. |
| Will an update break it? | Possibly. It fails loudly (red banner) rather than showing zero. |
| Is it safe / what does it read? | Read-only on the Claude app's folder, loopback only, no network calls. Point to the code. |
| Is this official? | No. Unaffiliated with Anthropic. Put that line in the README too. |

## While a post is live

- Reply to every comment in the first 3 hours, briefly and without defensiveness. Thank bug reports and
  open an issue for each, then link it.
- Never ask friends to upvote, never use a second account, never post the same link to several subs in
  one day. Reddit's spam filters and mods catch all three, and a ban on r/ClaudeAI ends this plan.
- If a mod removes the post, message the mods politely, ask what to change, and don't repost without a yes.
- Note feature requests that come up more than twice: those decide the next release, and the next post.

## Ongoing (the part that compounds)

- A few times a week, search r/ClaudeAI and r/ClaudeCode for "multiple sessions", "parallel", "lose track",
  "which session", "waiting for input". Answer the question properly; mention the tool only when it
  answers it, and say it's yours.
- Keep roughly nine helpful comments for every one that mentions the tool.
- Each real release: short changelog post in the one sub where it matters most, with a new GIF.

## Log

| Date | Sub | Title (short) | +24 h up / comments | +7 d stars | Notes |
|---|---|---|---|---|---|
| 2026-11-17 | r/ClaudeAI | I kept missing which of my Claude Code sessions… | | | First try removed by the mod bot (rule 7 b/c); the repost with "How I built it with Claude" was removed by the one-post-per-hour flood bot. Third try an hour after the repost. [Link](https://www.reddit.com/r/ClaudeAI/comments/1xynmr4/) |
