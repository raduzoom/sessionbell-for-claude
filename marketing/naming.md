# Naming check

Run 2026-11-17, following `~/Dropbox/hosts/devsite/projects/general-app-knowledge/docs/app-naming-and-trademark-check.md`.
Not legal advice; a lawyer's clearance search is the real answer if a lot rides on the name.

## Why not "Claude Dashboard" or "Work Dashboard for Claude"

- Anthropic's trademark guidelines (effective 2024-08-01) cover "our names", allow use only "as specifically
  permitted by us", and forbid anything implying "sponsorship or endorsement". There's no carve-out for
  "for Claude" or "works with Claude" naming. Anthropic made Clawdbot rename over a name that only sounded
  like Claude, so they do enforce.
- "Work Dashboard" is generic: unsearchable, impossible to own, and TMview shows unrelated dashboard
  marks around it. Google and Reddit search would bury it.
- Use: **own name + descriptive tagline**, e.g. "Turnbell: see which Claude Code sessions are waiting on
  you", plus "Not affiliated with Anthropic" in the README and site footer.

## Competitors found (same job, by 2026-11)

AgentManager (closed, paid, macOS panel), c9watch (MIT macOS app), OpenAgentPeek (menu bar), Muxara,
OpsDeck, claudectl, cctop (terminal), claude-sessions-ui (browser), and a "claude code dashboard" page.
Most watch CLI/terminal sessions; ours reads the **desktop app's Code tab**. That's the line to lead with,
and the answer to "how is this different from X" on Reddit.

## Candidates

RDAP: 404 = free. TMview "contains" search (control: "feathermark" returned 2 rows, so empty results are real).

| Name | .com | .app | .dev | Same-category apps | TMview |
|---|---|---|---|---|---|
| **Turnbell** | taken | **free** | **free** | none found | no rows |
| **Nudgeboard** | taken | **free** | **free** | none ("Nudge" to-do apps exist) | no rows |
| **Holdbell** | taken | **free** | **free** | not searched | no rows |
| **Sessionbell** | taken | **free** | **free** | not searched | no rows |
| Turnboard | taken | taken | free | Turnboards task app, Turnable "Turnboard" | not searched |
| Handraise | taken | taken | free | Handraise (funded co.), Handraiser | not searched |
| Callbell | taken | taken | free | Callbell (support chat SaaS) | not searched |
| Waitingon | taken | taken | free | — | not searched |
| Work Dashboard | taken | taken | free | generic | many "dashboard" marks |
| Beckon, Deskbell, Yourturn, Agentbell | taken | taken | taken | — | — |

## Decision (2026-11-17): Sessionbell

The user chose **Sessionbell** over the recommended Turnbell. Extra checks that day:

- Web: no app or software named Sessionbell or "Session Bell". Nearest: Echobell (a notifications app,
  different name), Session (booking platform).
- npm, PyPI, GitHub user/org and GitHub repos: all free (404 / 0 results). Homebrew lookup returned 503,
  not re-checked.
- Domains to register: `sessionbell.app`, `sessionbell.dev` (both free on 2026-11-17; `.com` is taken).
- Still to do: the USPTO search by hand.

## Recommendation (before the decision)

1. **Turnbell**: "your turn" + a bell. Says what it does (it rings when it's your turn), short, no
   collisions, `turnbell.app` and `turnbell.dev` free.
2. **Nudgeboard**: clearer as a dashboard, but "Nudge" is a crowded app word.

Before deciding: run the USPTO search by hand (doc above, "USPTO"), and check `turnbell` on GitHub and npm.
After deciding: rename user-visible text and, since nothing is released, the launchd labels
(`local.sessions-attention.*`) and the PWA manifest name.
