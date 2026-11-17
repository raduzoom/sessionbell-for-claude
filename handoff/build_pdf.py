"""Builds the generic "build a project like this" handoff PDF.

    uv run --with playwright==1.63.0 python handoff/build_pdf.py
    uv run --with playwright==1.63.0 python handoff/build_pdf.py --pdf-only

1. Builds build/snapshot-<shot>.html: today's index.html with a GENERIC made-up fixture (no client names),
   fed through window.__STATUS_SOURCE__ by tools/snapshot.py's build() (the same as the page snapshots).
2. Screenshots them into build/screenshots/.
3. Prints handoff.html to sessions-dashboard-build-handoff.pdf (A4).
Exits 1 on any page error, or if a forbidden name shows up in the PDF's HTML.

--pdf-only skips steps 1 and 2 and reuses the screenshots already in build/screenshots/.
"""
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUILD = HERE / "build"
SHOTS = BUILD / "screenshots"
OUT_PDF = HERE / "sessions-dashboard-build-handoff.pdf"

# Names that must never appear in this generic handoff.
FORBIDDEN = re.compile(r"merry|maids|gutters|\bfhf\b|replicant|cleaning-quote|587|zendesk|prismatic", re.I)

H, D = 60, 24 * 60
PROJECTS = [
    {"id": "client-a", "name": "Client A", "children": [
        {"id": "client-a/us", "name": "Client A US"},
        {"id": "client-a/canada", "name": "Client A Canada"},
    ]},
    {"id": "client-b", "name": "Client B", "comingSoon": True, "children": []},
    {"id": "client-c", "name": "Client C", "comingSoon": True, "children": []},
    {"id": "tools", "name": "Internal Tools", "children": []},
    {"id": "kb", "name": "Knowledge Base", "children": []},
    {"id": "other", "name": "Other", "children": []},
]
CA, US = ("client-a", "client-a/canada"), ("client-a", "client-a/us")
TL, KB, OT = ("tools", None), ("kb", None), ("other", None)
CARDS = [
    ("main", "asked", CA, "client-a-bot-canada", "TICKET-231 Lead routing: local test calls",
     "Will you make the two test calls now?", 25),
    ("main", "asked", CA, "client-a-bot-canada", "TICKET-218 Out-of-coverage reply",
     "Send me the call ID once you've made the call?", 1 * H),
    ("main", "asked", US, "client-a-bot (worktree)", "TICKET-240 Web chat: foreign address",
     "Run the regression check now, or ship as is?", 8),
    ("main", "stuck", CA, "client-a-bot-canada", "TICKET-207 Contact text update", "", 22 * H),
    ("main", "blocked", TL, "internal-tools", "Test dashboard port conflict",
     "Stop the old dashboard on port 8110, then tell me to restart it", 3 * H),
    ("main", "blocked", KB, "knowledge-base", "Latest config changes",
     "Pick a fix: drop the transfer step (my pick) or reorder the steps", 2 * D),
    ("scheduled", "blocked", OT, "chat-ping", "Scheduled task: chat-mention-ping",
     "Sign the chat connector back in with /mcp", 4),
    ("stale", "stuck", CA, "client-a-bot-canada", "Multi-phase ticket planning", "", 12 * D),
    ("stale", "blocked", CA, "client-a-bot-canada", "Country analytics from phone number",
     "Confirm the reporting tenant before I post the request", 20 * D),
    ("stale", "blocked", KB, "knowledge-base", "Examples showcase phase 0", "Commit and push, or review first?", 37 * D),
    ("stale", "blocked", OT, "scratch", "Claude settings: permissions default",
     "Check the status line for auto mode; press Shift+Tab if it's off", 44 * D),
    ("quiet", "review_ready", CA, "client-a-bot-canada", "TICKET-241 Office number fallback",
     "Down to the last run: regression check", 4),
    ("quiet", "review_ready", US, "client-a-bot", "Voice handoff with foreign address",
     "Replied on both review threads; open gaps go into the drafts", 13 * D),
    ("quiet", "unread", TL, "internal-tools", "Flow map: path shown by default",
     "Bordered 'Read again' button added; checked at 1500 px", 5 * D),
    ("quiet", "unread", CA, "client-a-bot-canada", "TICKET-190 Ticket inquiry",
     "Integration logs checked; spec updated, not committed", 8 * D),
    ("quiet", "unread", KB, "knowledge-base", "Release walkthrough docs", "Docs updated; deploy table fixed", 9 * D),
    ("quiet", "unread", OT, "scheduler-app", "Mac scheduler app", "Login item registered; restart to verify", 7 * D),
]


def fixture() -> dict:
    out = {"schema": 1, "error": None, "generatedAgoMs": 20_000, "projects": PROJECTS,
           "main": [], "scheduled": [], "stale": [], "quiet": [], "hidden": [], "problems": []}
    for i, (section, state, (project, sub), repo, title, needs, minutes) in enumerate(CARDS):
        sid = f"local_example-{i:02d}"
        out[section].append({"sessionId": sid, "title": title, "repo": repo, "org": "acct/org", "state": state,
                             "project": project, "subproject": sub, "needs": needs,
                             "lastActivityAgoMs": minutes * 60_000, "link": f"claude://claude.ai/epitaxy/{sid}"})
    out["counts"] = {"main": len(out["main"]) + len(out["scheduled"]),
                     "asked": sum(c["state"] == "asked" for c in out["main"]),
                     "stale": len(out["stale"]), "quiet": len(out["quiet"]), "hidden": 0, "scanned": 120}
    return out


def build_snapshot(name: str, theme: str, view: str) -> Path:
    sys.path.insert(0, str(ROOT / "tools"))
    import snapshot  # tools/snapshot.py: injects the fixture, the relative-time rebase and a fake state store
    page = (ROOT / "index.html").read_text(encoding="utf-8")
    if page.count(snapshot.MARK) != 1:
        raise SystemExit("index.html changed: can't find the main <script> to inject before")
    data = dict(fixture(), working=snapshot.WORKING)
    BUILD.mkdir(parents=True, exist_ok=True)
    snap = BUILD / f"snapshot-{name}.html"
    snap.write_text(snapshot.build(page, data, {"theme": theme, "view": view}), encoding="utf-8")
    return snap


# name, theme, saved view, viewport, action
SHOT_LIST = [
    ("all-light", "light", "project=all&sub=all", (1280, 860), None),
    ("all-dark", "dark", "project=all&sub=all", (1280, 860), None),
    ("subproject-light", "light", "project=client-a&sub=client-a%2Fcanada", (1280, 760), None),
    ("snooze-light", "light", "project=all&sub=all", (1280, 560), "snooze"),
    ("mobile-light", "light", "project=all&sub=all", (375, 812), None),
]


def main() -> int:
    pdf_only = "--pdf-only" in sys.argv[1:]
    if pdf_only:
        missing = [name for name, *_ in SHOT_LIST if not (SHOTS / f"{name}.png").is_file()]
        if missing:
            raise SystemExit(f"--pdf-only needs the existing screenshots; missing: {missing}")
    else:
        SHOTS.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")  # installed Chrome: no browser download needed
        for name, theme, view, (w, h), action in [] if pdf_only else SHOT_LIST:
            snap = build_snapshot(name, theme, view)
            ctx = browser.new_context(viewport={"width": w, "height": h}, color_scheme=theme, device_scale_factor=2)
            page = ctx.new_page()
            page.on("pageerror", lambda e, n=name: errors.append(f"{n}: {e}"))
            page.goto(snap.as_uri())
            page.wait_for_selector("#app:not([aria-busy])")
            page.wait_for_timeout(250)
            if action == "snooze":
                page.click('[data-key="snooze"]')       # the selected session's Snooze menu (Phase 4)
                page.wait_for_selector('[role="menu"]')
                page.wait_for_timeout(200)
            page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=False)
            ctx.close()

        html = (HERE / "handoff.html").read_text(encoding="utf-8")
        bad = sorted({m.group(0) for m in FORBIDDEN.finditer(html)})
        if bad:
            errors.append(f"handoff.html contains forbidden names: {bad}")
        ctx = browser.new_context(color_scheme="light")
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(f"pdf: {e}"))
        page.goto((HERE / "handoff.html").as_uri())
        page.wait_for_timeout(300)
        page.pdf(
            path=str(OUT_PDF), format="A4", print_background=True,
            margin={"top": "18mm", "bottom": "18mm", "left": "16mm", "right": "16mm"},
            display_header_footer=True,
            header_template="<span></span>",
            footer_template=('<div style="font: 8px Helvetica, Arial, sans-serif; color: #888; width: 100%; '
                             'padding: 0 16mm; display: flex; justify-content: space-between;">'
                             '<span>Sessions dashboard: build handoff</span>'
                             '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'),
        )
        ctx.close()
        browser.close()
    if errors:
        print("errors:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1
    print(f"wrote {OUT_PDF}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
