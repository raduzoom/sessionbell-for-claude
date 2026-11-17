# Claude Design result: Sessions needing attention

Source files of the Claude Design canvas built from `design/sessions-dashboard-claude-design/DESIGN-BRIEF.md`.

- Canvas: https://claude.ai/artifact/PFmL1YPNoUSqKJbkpyU5KU (private until shared)
- Saved from version `1794503645-b4b3` on 2026-11-12, after the first review round, a render check, a keyboard check (800 slide-over keeps focus inside while open) and builder fixes B1–B3 (projects in the rail, 520 px list with two-line titles, one-click rows and "More actions" at 800, tab title counts everything that needs you, header theme toggle fixed). Edits made on the canvas after that are not in this folder.
- All data is the made-up fixture data from the brief package.

## Files

| File | What it is | Brief section |
|---|---|---|
| `sn.css` | All tokens (light, dark, solid) and component styles | §10.1 |
| `Main.dc.html` | Interactive prototype; every screen below imports it with props | §6, §9 |
| `s01-desktop`, `s01-half`, `s01-phone` | Main view at 1280, 800, 375 | §9.1 |
| `s02-subproject`, `s02b-subproject-half` | Client A → Canada with the "more in other projects" note, at 1280 and 800 | §9.2 |
| `s03-phone-session`, `s03b-half-session` | Phone session view; 800 px slide-over | §9.3 |
| `s12-half-row-menu` | 800 px row "More actions" menu open (Snooze, Dismiss) | review round 1 |
| `s04-snooze`, `s05-toast` | Snooze menu open; Undo toast | §9.4, §9.5 |
| `s06-stale-hidden` | Stale and Hidden expanded | §9.6 |
| `s07-empty`, `s08-late` | Empty; scanner late | §9.7, §9.8 |
| `s09-error-format`, `s09-error-projects` | Both error reasons | §9.9 |
| `s10-busy`, `s10b-busy-half` | 12 asked, badge overflow, long titles, at 1280 and 800 | §9.10 |
| `s11-solid` | Reduced-transparency version | §9.11 |
| `tokens.dc.html` | Token board | §10.1 |
| `components.dc.html` | Component inventory with states | §10.2 |
| `contrast.dc.html` | Contrast table, both themes | §10.4 |
| `alt-rail.dc.html` | Early sketch of projects in the rail, now adopted | §6 |
| `canvas.json` | Board layout, titles, and the "what changed" note | §10.5 |

Every screen board shows light and dark side by side. The `.dc.html` files only render inside the Claude Design canvas.
