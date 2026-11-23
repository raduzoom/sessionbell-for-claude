#!/usr/bin/env python3
"""Build snapshot pages of index.html with MADE-UP data, for design and contrast checks.

Each snapshot is index.html with a fixture fed through window.__STATUS_SOURCE__. The fixtures come from the
design package (they passed make_handoff.py's forbidden-name check) and use relative times (*AgoMs), which
are rebased to "now" when the page loads, so a snapshot never looks out of date.

    python3 -I tools/snapshot.py        writes design/page-check/build/snapshot-<state>-<theme>.html

It also copies pwa/ next to the snapshots (so their <link>s resolve) and writes build/pwa-root/: index.html,
pwa/ and a made-up data/status.json, for running the real server.py on made-up data (launch.json
"pwa-check", port 8792) to check the installed app: manifest, service worker, offline start.

Never point this at real data: the live page is never screenshotted.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(HERE, "design", "sessions-dashboard-claude-design")
OUT = os.path.join(HERE, "design", "page-check", "build")
# Invented sessions with no client names, for public screenshots and the demo GIF (snapshot-demo-*.html).
with open(os.path.join(HERE, "tools", "demo-fixture.json"), encoding="utf-8") as _f:
    DEMO = json.load(_f)
MARK = "<script>\n(function () {"

STATES = {
    "normal": ("status-fixture.json", {}),
    "filtered": ("status-fixture.json", {"view": "project=client-a&sub=client-a%2Fcanada"}),
    "empty": ("fixture-states/empty.json", {}),
    "late": ("fixture-states/scanner-late.json", {}),
    "error-format": ("fixture-states/error-format.json", {}),
    "error-projects": ("fixture-states/error-projects.json", {}),
    "busy": ("fixture-states/busy.json", {}),
    "solid": ("status-fixture.json", {"solid": True}),
    # Format drift: an unknown schema must show the red banner, never a calm 0.
    "drift": ({"schema": 2, "error": None, "generatedAgoMs": 20000, "sessions": []}, {}),
    # Phase 4: every Snooze, Dismiss, Undo and Show again fails, to show "Couldn't save. Try again."
    "savefail": ("status-fixture.json", {"saveFails": True}),
    # The reply bar is off by default (config.json "replyEnabled"): the pane has no footer.
    "demo": (DEMO, {}),
    "replyoff": ("status-fixture.json", {"reply": False}),
    "pinned": ("status-fixture.json", {}),
}

REBASE = """
// Card times are rebased once (to when the page loaded), so a Dismiss keeps holding across polls; only the
// scan time follows the clock, so the snapshot never looks late.
var SN_BASE = Date.now();
function snRebase(d) {
  var now = SN_BASE;
  d = JSON.parse(JSON.stringify(d));
  d.generatedAt = Date.now() - (d.generatedAgoMs || 0);
  ['main', 'scheduled', 'working', 'stale', 'quiet', 'hidden', 'caughtUp'].forEach(function (k) {
    (d[k] || []).forEach(function (c) {
      c.lastActivityAt = now - (c.lastActivityAgoMs || c.waitingMs || 0);
      if (c.startedAgoMs) c.startedAt = now - c.startedAgoMs;
      if (c.hiddenBy && c.hiddenBy.untilInMs) c.hiddenBy.until = now + c.hiddenBy.untilInMs;
    });
  });
  (d.folders || []).forEach(function (f) { if (f.lastUsedAgoMs != null) f.lastUsedAt = now - f.lastUsedAgoMs; });
  return d;
}
// Stands in for GET /state.json and POST /state (server.py's rules), seeded from the fixture's hidden and
// pinned cards.
function snStateSink(fails) {
  var state = null;
  function copy(x) { return JSON.parse(JSON.stringify(x)); }
  function seed() {
    state = { version: 1, hidden: {}, pinned: {} };
    ['main', 'scheduled', 'working', 'stale', 'quiet'].forEach(function (k) {
      (SN_FIXTURE[k] || []).forEach(function (c) { if (c.pinned) state.pinned[c.sessionId] = { at: SN_BASE }; });
    });
    (snRebase(SN_FIXTURE).hidden || []).forEach(function (c) {
      var by = c.hiddenBy || {};
      state.hidden[c.sessionId] = by.kind === 'snooze' ? { kind: 'snooze', until: by.until, at: SN_BASE }
                                                       : { kind: 'dismiss', lastActivityAt: c.lastActivityAt, at: SN_BASE };
    });
  }
  return {
    get: function () { if (!state) seed(); return copy(state); },
    post: function (b) {
      if (fails) return Promise.reject(new Error('made-up save failure'));
      if (!state) seed();
      var now = Date.now();
      if (b.action === 'pin') { delete state.hidden[b.sessionId]; state.pinned[b.sessionId] = { at: now }; }
      else if (b.action === 'unpin') delete state.pinned[b.sessionId];
      else if (b.action === 'snooze') { state.hidden[b.sessionId] = { kind: 'snooze', until: b.until, at: now }; delete state.pinned[b.sessionId]; }
      else if (b.action === 'dismiss') { state.hidden[b.sessionId] = { kind: 'dismiss', lastActivityAt: b.lastActivityAt, at: now }; delete state.pinned[b.sessionId]; }
      else delete state.hidden[b.sessionId];
      return copy(state);
    },
    // Stands in for POST /reply: nothing is typed anywhere. "savefail" shows the server's refusal.
    reply: function () {
      return new Promise(function (resolve, reject) {
        setTimeout(function () {
          if (!fails) return resolve({ ok: true });
          var e = new Error("Claude's message box doesn't have focus. Nothing was typed.");
          e.status = 503;
          reject(e);
        }, 900);
      });
    }
  };
}
"""

# The design fixtures predate the Working section: add two made-up working sessions to the states that
# show lists. One is active, one has been quiet for 15 minutes (the long-tool-call case).
WORKING = [
    {"sessionId": "local_example-90", "title": "Made-up: rebuild the export step", "state": "working",
     "project": "tools", "subproject": None, "repo": "internal-tools", "needs": "", "doing": "Rebuilding the export step",
     "lastActivityAgoMs": 30000, "startedAgoMs": 1620000, "link": "claude://claude.ai/epitaxy/local_example-90"},
    {"sessionId": "local_example-91", "title": "TICKET-250 Made-up: holiday routing table", "state": "working",
     "project": "client-a", "subproject": "client-a/us", "repo": "client-a-bot", "needs": "",
     "lastActivityAgoMs": 900000, "startedAgoMs": 2400000, "link": "claude://claude.ai/epitaxy/local_example-91"},
]
WITH_WORKING = ("normal", "filtered", "busy", "late", "solid", "savefail", "pinned")
# Pinned (added 2026-11-15): a pinned card stays in its own section with a small pin. The snapshot pins the
# first Needs-you card and adds one you've read, which stays at the end of Quieter.
READ_PINNED = {"sessionId": "local_example-95", "title": "Made-up: compare two export formats", "state": "read",
               "pinned": True, "project": "tools", "subproject": None, "repo": "internal-tools",
               "needs": "Both formats work; CSV is smaller.", "lastActivityAgoMs": 14400000,
               "link": "claude://claude.ai/epitaxy/local_example-95"}

# Caught up (added 2026-11-17): finished sessions you've read in the last week, folded under Quieter.
CAUGHT_UP = [
    {"sessionId": "local_example-96", "title": "Made-up: tidy the onboarding checklist", "state": "read",
     "project": "tools", "subproject": None, "repo": "internal-tools", "needs": "Checklist trimmed to six steps.",
     "lastActivityAgoMs": 2700000, "link": "claude://claude.ai/epitaxy/local_example-96"},
    {"sessionId": "local_example-97", "title": "TICKET-260 Made-up: second reference image for prompts", "state": "read",
     "project": "client-a", "subproject": "client-a/us", "repo": "client-a-bot", "needs": "Both references still work.",
     "lastActivityAgoMs": 10800000, "link": "claude://claude.ai/epitaxy/local_example-97"},
    {"sessionId": "local_example-98", "title": "Made-up: rename the settings keys", "state": "read",
     "project": "tools", "subproject": None, "repo": "internal-tools", "needs": "",
     "lastActivityAgoMs": 172800000, "link": "claude://claude.ai/epitaxy/local_example-98"},
]


def with_pins(fixture):
    fixture = json.loads(json.dumps(fixture))
    if fixture.get("main"):
        fixture["main"][0]["pinned"] = True
    fixture["quiet"] = list(fixture.get("quiet") or []) + [READ_PINNED]
    return fixture


def with_folders(fixture):
    """The New session picker's folders (added 2026-11-16), made up from the fixture's own cards: one per
    folder name, under a made-up home, plus one never-used folder."""
    if "folders" in fixture or fixture.get("schema") != 1:
        return fixture
    seen = {}
    for key in ("main", "scheduled", "working", "stale", "quiet", "hidden", "caughtUp"):
        for c in fixture.get(key) or []:
            repo = str(c.get("repo") or "").replace(" (worktree)", "")
            ago = c.get("lastActivityAgoMs") or c.get("waitingMs") or 0
            if repo and (repo not in seen or ago < seen[repo]["lastUsedAgoMs"]):
                seen[repo] = {"folder": "/Users/you/projects/" + repo, "name": repo, "path": "~/projects/" + repo,
                              "project": c.get("project"), "subproject": c.get("subproject"), "lastUsedAgoMs": ago}
    folders = sorted(seen.values(), key=lambda f: f["lastUsedAgoMs"])
    other = (fixture.get("projects") or [{}])[-1].get("id")
    folders.append({"folder": "/Users/you/projects/scratch-ideas", "name": "scratch-ideas",
                    "path": "~/projects/scratch-ideas", "project": other, "subproject": None, "lastUsedAgoMs": None})
    return dict(fixture, folders=folders)


def build(page, fixture, options):
    options = dict(options)
    fails = "true" if options.pop("saveFails", False) else "false"
    data = json.dumps(fixture, ensure_ascii=False).replace("</", "<\\/")
    inject = ("<script>\n" + REBASE + "var SN_FIXTURE = " + data + ";\n"
              "window.__SN_OPTIONS__ = " + json.dumps(options) + ";\n"
              "window.__STATUS_SOURCE__ = function () { return snRebase(SN_FIXTURE); };\n"
              "window.__STATE_SINK__ = snStateSink(" + fails + ");\n</script>\n")
    return page.replace(MARK, inject + MARK, 1)


def main():
    with open(os.path.join(HERE, "index.html"), encoding="utf-8") as f:
        page = f.read()
    if page.count(MARK) != 1:
        sys.exit("snapshot: can't find the page script in index.html")
    os.makedirs(OUT, exist_ok=True)
    written = []
    for state, (name, options) in STATES.items():
        if isinstance(name, dict):
            fixture = name
        else:
            with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
                fixture = json.load(f)
        if state in WITH_WORKING:
            fixture = dict(fixture, working=WORKING, caughtUp=CAUGHT_UP)
        if state == "pinned":
            fixture = with_pins(fixture)
        fixture = with_folders(fixture)
        for theme in ("light", "dark"):
            path = os.path.join(OUT, "snapshot-%s-%s.html" % (state, theme))
            with open(path, "w", encoding="utf-8") as f:
                f.write(build(page, fixture, dict(options, theme=theme)))
            written.append(os.path.relpath(path, HERE))
    print("\n".join(written))
    written += write_pwa(page)
    print("\n".join(written))
    return 0


def rebased(d, now):
    """The same rebase as snRebase, for a status.json the real server serves."""
    d = json.loads(json.dumps(d))
    d["generatedAt"] = now - d.pop("generatedAgoMs", 0)
    for key in ("main", "scheduled", "working", "stale", "quiet", "hidden", "caughtUp"):
        for c in d.get(key) or []:
            c["lastActivityAt"] = now - (c.get("lastActivityAgoMs") or c.get("waitingMs") or 0)
            if c.get("startedAgoMs"):
                c["startedAt"] = now - c["startedAgoMs"]
            if (c.get("hiddenBy") or {}).get("untilInMs"):
                c["hiddenBy"]["until"] = now + c["hiddenBy"]["untilInMs"]
    for f in d.get("folders") or []:
        if f.get("lastUsedAgoMs") is not None:
            f["lastUsedAt"] = now - f.pop("lastUsedAgoMs")
    return d


def write_pwa(page):
    pwa = os.path.join(HERE, "pwa")
    root = os.path.join(OUT, "pwa-root")
    os.makedirs(os.path.join(root, "pwa"), exist_ok=True)
    os.makedirs(os.path.join(root, "data"), exist_ok=True)
    written = []
    for name in sorted(os.listdir(pwa)):
        for folder in (OUT, os.path.join(root, "pwa")):
            shutil.copyfile(os.path.join(pwa, name), os.path.join(folder, name))
        written.append(os.path.relpath(os.path.join(OUT, name), HERE))
    with open(os.path.join(root, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    with open(os.path.join(FIXTURES, "status-fixture.json"), encoding="utf-8") as f:
        fixture = with_folders(dict(json.load(f), working=WORKING, caughtUp=CAUGHT_UP))
    with open(os.path.join(root, "data", "status.json"), "w", encoding="utf-8") as f:
        json.dump(rebased(fixture, int(time.time() * 1000)), f, ensure_ascii=False)
    written.append(os.path.relpath(root, HERE) + "/ (index.html, pwa/, data/status.json: made-up)")
    return written


if __name__ == "__main__":
    sys.exit(main())
