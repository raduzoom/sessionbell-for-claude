"""Builds the Claude Design handoff zip (Phase 1). Standard library only.

    python3 -I design/claude-design-handoff/make_handoff.py

1. Writes made-up fixtures (status.json shape, relative times) into build/.
2. Copies the brief, the moodboard and today's page (screenshots + a cleaned snapshot) into build/.
3. Checks every text file for real client names, phone numbers and real ticket keys.
4. Zips build/ into design/sessions-dashboard-claude-design.zip.
Exits 1 and writes no zip if any check fails.
"""
import copy
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BUILD = HERE / "build"
ZIP = HERE.parent / "sessions-dashboard-claude-design.zip"
OLD = ROOT / "handoff" / "build"

# Names that must never leave this Mac. This script is not part of the zip.
FORBIDDEN = re.compile(r"merry|maids|gutters|\bfhf\b|replicant|cleaning-quote|587|zendesk|prismatic", re.I)
PHONE = re.compile(r"\+?\d[\d ().-]{7,}\d")
TICKET_KEY = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")

M, H, D = 60_000, 3_600_000, 86_400_000
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

# section, state, (project, subproject), repo, title, needs, ago (ms)
CARDS = [
    ("main", "asked", US, "client-a-bot (worktree)", "TICKET-240 Web chat: foreign address",
     "Run the regression check now, or ship as is?", 8 * M),
    ("main", "asked", CA, "client-a-bot-canada", "TICKET-231 Lead routing: local test calls",
     "Will you make the two test calls now? I need one from a local number and one from abroad, then the "
     "call IDs from the log so I can compare the two routing paths.", 25 * M),
    ("main", "asked", TL, "internal-tools",
     "Release checklist generator: pull merged changes from the last two weeks",
     "Use the release branch or main as the source?", 40 * M),
    ("main", "asked", CA, "client-a-bot-canada", "TICKET-218 Out-of-coverage reply",
     "Send me the call ID once you've made the call?", 1 * H),
    ("main", "stuck", CA, "client-a-bot-canada", "TICKET-207 Contact text update", "", 22 * H),
    ("main", "blocked", TL, "internal-tools", "Test dashboard port conflict",
     "Stop the old dashboard on port 8110, then tell me to restart it", 3 * H),
    ("main", "blocked", KB, "knowledge-base", "Latest config changes",
     "Pick a fix: drop the transfer step (my pick) or reorder the steps", 2 * D),
    ("scheduled", "blocked", OT, "chat-ping", "Scheduled task: chat-mention-ping",
     "Sign the chat connector back in with /mcp", 4 * M),
    ("stale", "stuck", CA, "client-a-bot-canada", "Multi-phase ticket planning", "", 12 * D),
    ("stale", "blocked", CA, "client-a-bot-canada", "Country analytics from caller location",
     "Confirm the reporting tenant before I post the request", 20 * D),
    ("stale", "blocked", KB, "knowledge-base", "Examples showcase phase 0", "Commit and push, or review first?", 37 * D),
    ("stale", "blocked", OT, "scratch", "Claude settings: permissions default",
     "Check the status line for auto mode; press Shift+Tab if it's off", 44 * D),
    ("quiet", "review_ready", CA, "client-a-bot-canada", "TICKET-241 Office number fallback",
     "Down to the last run: regression check", 4 * M),
    ("quiet", "review_ready", US, "client-a-bot", "Voice handoff with foreign address",
     "Replied on both review threads; open gaps go into the drafts", 13 * D),
    ("quiet", "unread", TL, "internal-tools", "Flow map: path shown by default",
     "Bordered 'Read again' button added; checked at 1500 px", 5 * D),
    ("quiet", "unread", CA, "client-a-bot-canada", "TICKET-190 Ticket inquiry",
     "Integration logs checked; spec updated, not committed", 8 * D),
    ("quiet", "unread", KB, "knowledge-base", "Release walkthrough docs", "Docs updated; deploy table fixed", 9 * D),
    ("quiet", "unread", OT, "scheduler-app", "Mac scheduler app", "Login item registered; restart to verify", 7 * D),
    ("hidden:snooze", "asked", KB, "knowledge-base", "Glossary cleanup",
     "Merge the two 'handoff' entries into one?", 2 * H),
    ("hidden:dismiss", "blocked", OT, "scratch", "Font licence check",
     "Buy the desktop licence, or switch to the free family?", 3 * D),
]

# Extra asked sessions for the "busy" state (badge overflow: 9+ asked).
BUSY_EXTRA = [
    (US, "client-a-bot", "TICKET-244 Holiday hours message", "Use the short or the long greeting?"),
    (US, "client-a-bot", "TICKET-245 Retry on dropped calls", "Retry once or twice before handing off?"),
    (CA, "client-a-bot-canada", "TICKET-233 French greeting", "Is the new French greeting text final?"),
    (CA, "client-a-bot-canada", "TICKET-236 Booking window", "Allow same-day bookings, or next day only?"),
    (TL, "internal-tools", "Log viewer: colour by level", "Keep warnings amber, or match the error red?"),
    (KB, "knowledge-base", "Onboarding page order", "Move 'First week' above 'Accounts'?"),
    (OT, "scratch", "Backup script schedule", "Run nightly at 02:00, or hourly?"),
    (OT, "scheduler-app", "Menu bar icon size", "Use the 16 pt or the 18 pt icon?"),
]


def card(i, state, project_sub, repo, title, needs, ago):
    project, sub = project_sub
    sid = f"local_example-{i:02d}"
    return {"sessionId": sid, "title": title, "state": state, "project": project, "subproject": sub,
            "repo": repo, "org": "acct/org", "needs": needs, "lastActivityAgoMs": ago, "waitingMs": ago,
            "link": f"claude://claude.ai/epitaxy/{sid}"}


def with_counts(s):
    s["counts"] = {"main": len(s["main"]) + len(s["scheduled"]),
                   "asked": sum(c["state"] == "asked" for c in s["main"]),
                   "stale": len(s["stale"]), "quiet": len(s["quiet"]), "hidden": len(s["hidden"]), "scanned": 120}
    return s


def normal():
    s = {"schema": 1, "error": None, "generatedAgoMs": 20_000, "projects": PROJECTS,
         "main": [], "scheduled": [], "stale": [], "quiet": [], "hidden": []}
    for i, (section, state, ps, repo, title, needs, ago) in enumerate(CARDS):
        c = card(i, state, ps, repo, title, needs, ago)
        if section.startswith("hidden:"):
            kind = section.split(":")[1]
            c["section"] = "main"
            c["hiddenBy"] = {"kind": "snooze", "untilInMs": 1 * H} if kind == "snooze" else {"kind": "dismiss"}
            s["hidden"].append(c)
        else:
            s[section].append(c)
    return with_counts(s)


def states(base):
    out = {}
    empty = copy.deepcopy(base)
    empty["main"], empty["scheduled"] = [], []
    out["empty"] = with_counts(empty)
    late = copy.deepcopy(base)
    late["generatedAgoMs"] = 9 * M
    out["scanner-late"] = late
    busy = copy.deepcopy(base)
    for j, (ps, repo, title, needs) in enumerate(BUSY_EXTRA):
        busy["main"].insert(0, card(50 + j, "asked", ps, repo, title, needs, (2 + 3 * j) * M))
    out["busy"] = with_counts(busy)
    for name, msg in [
        ("error-format", "Can't read session status, format may have changed (120 of 120 files unreadable)."),
        ("error-projects", 'projects.json: the rule for ~/work/client-d-bot names an unknown project "client-d".'),
    ]:
        err = {k: ([] if isinstance(v, list) and k != "projects" else v) for k, v in base.items()}
        err["error"] = msg
        out[name] = with_counts(err)
    return out


def clean_snapshot(text):
    # The old page has one comment that names a real client; replace it with the made-up names.
    return re.sub(r"// \"[^\"]*\" under \"[^\"]*\" reads as", '// "Client A Canada" under "Client A" reads as', text)


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)


def check(build):
    errors = []
    for f in sorted(build.rglob("*")):
        if f.suffix not in {".json", ".md", ".html"}:
            continue
        text = f.read_text(encoding="utf-8")
        rel = f.relative_to(build)
        for m in sorted({m.group(0) for m in FORBIDDEN.finditer(text)}):
            errors.append(f"{rel}: forbidden name {m!r}")
        if f.suffix == ".json":
            for s in strings(json.loads(text)):
                for m in PHONE.finditer(s):
                    errors.append(f"{rel}: phone-like number {m.group(0)!r}")
                for m in TICKET_KEY.finditer(s):
                    if not m.group(0).startswith("TICKET-"):
                        errors.append(f"{rel}: ticket key {m.group(0)!r}")
    return errors


def main():
    if BUILD.exists():
        subprocess.run(["trash", str(BUILD)], check=True)  # generated folder, rebuilt every run
    (BUILD / "fixture-states").mkdir(parents=True)
    (BUILD / "reference").mkdir()

    base = normal()
    (BUILD / "status-fixture.json").write_text(json.dumps(base, indent=2) + "\n", encoding="utf-8")
    for name, s in states(base).items():
        (BUILD / "fixture-states" / f"{name}.json").write_text(json.dumps(s, indent=2) + "\n", encoding="utf-8")

    shutil.copy(HERE / "DESIGN-BRIEF.md", BUILD / "DESIGN-BRIEF.md")
    shutil.copy(HERE / "reference-src" / "moodboard.png", BUILD / "reference" / "moodboard.png")
    for png in sorted((OLD / "screenshots").glob("*.png")):
        shutil.copy(png, BUILD / "reference" / f"today-{png.name}")
    snap = clean_snapshot((OLD / "snapshot.html").read_text(encoding="utf-8"))
    (BUILD / "reference" / "today-snapshot.html").write_text(snap, encoding="utf-8")

    errors = check(BUILD)
    if errors:
        print("checks failed, no zip written:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1

    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(BUILD.rglob("*")):
            if f.is_file():
                z.write(f, Path("sessions-dashboard-claude-design") / f.relative_to(BUILD))
    print(f"wrote {ZIP} ({ZIP.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
