"""The page re-applies state.json itself (Phase 4); its hide rule and sort must match the scanner's.

Runs the page's own functions (cut out of index.html) in Node on made-up cards and compares them with
scanner.py. Skipped when Node isn't installed: Node is a test tool here, never part of the dashboard."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import scanner  # noqa: E402

NODE = shutil.which("node") or ("/usr/local/bin/node" if os.path.exists("/usr/local/bin/node") else None)
NOW = 1794500000000
H = 3600_000
DAY = 24 * H


def page_functions():
    with open(os.path.join(HERE, "index.html"), encoding="utf-8") as f:
        page = f.read()
    helpers = [re.search(r"  function %s\(.*?\n" % name, page).group(0) for name in ("num", "own")]
    rule = page[page.index("  var SNOOZE_MAX_MS"):page.index("  var loadSeq = 0;")]
    return "".join(helpers) + rule


def run_page(script_body, data):
    js = page_functions() + "\nvar DATA = " + json.dumps(data) + ";\n" + script_body
    out = subprocess.run([NODE, "-e", js], capture_output=True, text=True, timeout=20, check=True)
    return json.loads(out.stdout)


def card(sid, last, state="asked"):
    return {"sessionId": sid, "title": "Made-up " + sid, "state": state, "lastActivityAt": last}


CASES = [
    ({"kind": "snooze", "until": NOW + H}, NOW - H),
    ({"kind": "snooze", "until": NOW}, NOW - H),                       # ended exactly now
    ({"kind": "snooze", "until": NOW - 1}, NOW - H),
    ({"kind": "snooze", "until": NOW + 8 * DAY}, NOW - H),             # the cap itself
    ({"kind": "snooze", "until": NOW + 8 * DAY + 1}, NOW - H),         # beyond the cap
    ({"kind": "snooze", "until": "tomorrow"}, NOW - H),
    ({"kind": "snooze"}, NOW - H),
    ({"kind": "dismiss", "lastActivityAt": NOW - H}, NOW - H),         # unchanged since
    ({"kind": "dismiss", "lastActivityAt": NOW - H}, NOW - H + 1),     # newer activity
    ({"kind": "dismiss", "lastActivityAt": NOW - H + 0.5}, NOW - H),   # fractional
    ({"kind": "dismiss", "lastActivityAt": None}, NOW - H),
    ({"kind": "dismiss"}, NOW - H),
    ({"kind": "archive", "until": NOW + H}, NOW - H),
    ("not an entry", NOW - H),
    (None, NOW - H),
]


@unittest.skipUnless(NODE, "node isn't installed")
class PageRuleTests(unittest.TestCase):
    def test_hidden_by_matches_the_scanner(self):
        cards, states = [], []
        for i, (entry, last) in enumerate(CASES):
            c = card("local_r%d" % i, last)
            st = {"version": 1, "hidden": {} if entry is None else {c["sessionId"]: entry}}
            cards.append(c)
            states.append(st)
        js = ("var now = %d; console.log(JSON.stringify(DATA.cards.map(function (c, i) {"
              " return hiddenBy(c, DATA.states[i], now); })));" % NOW)
        got = run_page(js, {"cards": cards, "states": states})
        want = [scanner.hidden_by(c, st, NOW) for c, st in zip(cards, states)]
        for case, g, w in zip(CASES, got, want):
            self.assertEqual(g, w, case)

    def test_apply_state_matches_the_scanner_split_and_sort(self):
        now = scanner_now = NOW
        lists = {
            "main": [card("local_m1", now - 3 * H, "unread"), card("local_m2", now - H), card("local_m3", now - 2 * H)],
            "scheduled": [card("local_s1", now - H, "blocked")],
            "stale": [card("local_t1", now - 9 * DAY)],
            "quiet": [card("local_q1", now - H, "review_ready")],
        }
        state = {"version": 1, "hidden": {
            "local_m2": {"kind": "snooze", "until": now + H, "at": now},
            "local_s1": {"kind": "dismiss", "lastActivityAt": now - H, "at": now},
            "local_q1": {"kind": "dismiss", "lastActivityAt": now - 2 * H, "at": now},   # changed since
        }}
        # What the scanner would write with no state (all visible), as the page receives it ...
        raw = {k: [dict(c) for c in v] for k, v in lists.items()}
        raw.update({"hidden": [], "working": [card("local_w1", now, "working")], "error": None})
        # ... and what it writes with the state: the page must reach the same split from the raw one.
        want = {"hidden": []}
        for section, cs in lists.items():
            visible = []
            for c in cs:
                by = scanner.hidden_by(c, state, scanner_now)
                if by:
                    want["hidden"].append(dict(c, section=section, hiddenBy=by))
                else:
                    visible.append(c)
            want[section] = scanner._sort(visible)
        want["hidden"] = scanner._sort(want["hidden"])
        js = ("Date.now = function () { return %d; };"
              "var out = applyState(DATA.raw, DATA.state);"
              "console.log(JSON.stringify(out));" % NOW)
        got = run_page(js, {"raw": raw, "state": state})
        for key in ("main", "scheduled", "stale", "quiet", "hidden"):
            self.assertEqual(got[key], want[key], key)
        self.assertEqual(got["working"], raw["working"])

        # Restoring brings scanner-hidden cards back to their own section (Undo, Show again).
        hidden_raw = dict(raw, **{k: want[k] for k in ("main", "scheduled", "stale", "quiet", "hidden")})
        got = run_page(js, {"raw": hidden_raw, "state": {"version": 1, "hidden": {}}})
        for key in ("main", "scheduled", "stale", "quiet"):
            self.assertEqual(got[key], scanner._sort([dict(c) for c in lists[key]]), key)
        self.assertEqual(got["hidden"], [])


    def test_is_pinned_matches_the_scanner(self):
        states = [{"pinned": {"local_a": {"at": 1}}}, {"pinned": {"local_a": True}}, {"pinned": ["local_a"]},
                  {"pinned": None}, {}, None, {"pinned": {"local_b": {}}}]
        js = "console.log(JSON.stringify(DATA.map(function (st) { return isPinned('local_a', st); })));"
        got = run_page(js, states)
        self.assertEqual(got, ["local_a" in scanner.pinned_ids(st or {}) for st in states])

    def test_apply_state_pins_in_place_and_unpins_at_once(self):
        raw = {"main": [card("local_m1", NOW - H), card("local_m2", NOW - 2 * H)],
               "scheduled": [], "stale": [],
               "quiet": [card("local_q1", NOW - H, "unread"), dict(card("local_r1", NOW - 3 * H, "read"), pinned=True)],
               "working": [card("local_w1", NOW, "working")],
               "hidden": [dict(card("local_h1", NOW - 3 * H), section="main", hiddenBy={"kind": "dismiss"})],
               "error": None}
        state = {"version": 1, "pinned": {sid: {"at": NOW} for sid in ("local_m2", "local_w1", "local_h1", "local_r1")},
                 "hidden": {"local_h1": {"kind": "dismiss", "lastActivityAt": NOW, "at": NOW}}}
        js = ("Date.now = function () { return %d; };"
              "function ids(l) { return l.map(function (c) { return [c.sessionId, c.pinned === true]; }); }"
              "function all(o) { return {main: ids(o.main), quiet: ids(o.quiet), working: ids(o.working), hidden: ids(o.hidden)}; }"
              "console.log(JSON.stringify({a: all(applyState(DATA.raw, DATA.state)),"
              " b: all(applyState(DATA.raw, {version: 1, hidden: {}, pinned: {}}))}));" % NOW)
        got = run_page(js, {"raw": raw, "state": state})
        # Pinned: same sections and order, a pin flag, and a pinned hidden card comes back to its section.
        self.assertEqual(got["a"], {"main": [["local_m1", False], ["local_m2", True], ["local_h1", True]],
                                    "quiet": [["local_q1", False], ["local_r1", True]],
                                    "working": [["local_w1", True]], "hidden": []})
        # Unpinned: flags go, and the read card leaves the list as the next scan would.
        self.assertEqual(got["b"], {"main": [["local_m1", False], ["local_m2", False], ["local_h1", False]],
                                    "quiet": [["local_q1", False]], "working": [["local_w1", False]], "hidden": []})

if __name__ == "__main__":
    unittest.main()
