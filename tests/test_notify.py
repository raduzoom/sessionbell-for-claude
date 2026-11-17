"""Notification tests (handoff §7). No real banner is ever shown: the sender is replaced by a recorder."""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner  # noqa: E402

NOW = 1_800_000_000_000
MIN = 60_000


def card(sid, state="asked", needs="Ship it?", title=None):
    return {"sessionId": sid, "title": title or ("Title " + sid), "state": state, "needs": needs,
            "lastActivityAt": NOW - MIN}


def status(main=(), scheduled=(), stale=(), hidden=(), error=None):
    return {"schema": 1, "generatedAt": NOW, "error": error, "projects": [],
            "main": list(main), "scheduled": list(scheduled), "stale": list(stale), "quiet": [],
            "hidden": list(hidden), "counts": {}}


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, title, body):
        self.calls.append((title, body))


class NotifyTests(unittest.TestCase):
    def setUp(self):
        self.sent = Recorder()
        original = scanner._osascript
        scanner._osascript = self.sent
        self.addCleanup(setattr, scanner, "_osascript", original)

    def test_new_question(self):
        new = scanner.new_questions(status([card("local_a")]), status([card("local_a"), card("local_b")]))
        self.assertEqual([c["sessionId"] for c in new], ["local_b"])

    def test_unchanged_list_is_silent(self):
        same = status([card("local_a"), card("local_b", "blocked", "Sign in")])
        self.assertEqual(scanner.new_questions(same, same), [])

    def test_no_baseline_is_silent(self):
        self.assertEqual(scanner.new_questions(None, status([card("local_a")])), [])

    def test_previous_error_is_silent(self):
        self.assertEqual(scanner.new_questions(status(error="boom"), status([card("local_a")])), [])

    def test_current_error_is_silent(self):
        self.assertEqual(scanner.new_questions(status([card("local_a")]), status(error="boom")), [])

    def test_changed_question_same_session(self):
        new = scanner.new_questions(status([card("local_a", needs="Q1?")]), status([card("local_a", needs="Q2?")]))
        self.assertEqual([c["needs"] for c in new], ["Q2?"])

    def test_snooze_ending_is_silent(self):
        previous = status(hidden=[dict(card("local_a"), section="main", hiddenBy={"kind": "snooze"})])
        self.assertEqual(scanner.new_questions(previous, status([card("local_a")])), [])

    def test_question_back_from_stale_is_silent(self):
        self.assertEqual(scanner.new_questions(status(stale=[card("local_a")]), status([card("local_a")])), [])

    def test_blocked_and_stuck_never_notify(self):
        current = status([card("local_b", "blocked", "Sign in"), card("local_s", "stuck", "")])
        self.assertEqual(scanner.new_questions(status(), current), [])

    def test_working_never_notifies(self):
        current = status([card("local_a")])
        current["working"] = [card("local_w", "working", "")]
        self.assertEqual([c["sessionId"] for c in scanner.new_questions(status(), current)], ["local_a"])

    def test_scheduled_question_notifies(self):
        new = scanner.new_questions(status(), status(scheduled=[card("local_t")]))
        self.assertEqual([c["sessionId"] for c in new], ["local_t"])

    def test_body_is_title_only(self):
        scanner.notify([card("local_a", needs="Call +1 555 0100 now?", title="TICKET-1 Routing")])
        self.assertEqual(self.sent.calls, [("Sessionbell", "TICKET-1 Routing")])

    def test_three_or_more_become_one_banner(self):
        scanner.notify([card("local_%d" % i) for i in range(2)])
        self.assertEqual(len(self.sent.calls), 2)
        self.sent.calls.clear()
        scanner.notify([card("local_%d" % i) for i in range(4)])
        self.assertEqual(self.sent.calls, [("Sessionbell", "4 sessions asked you something")])

    def test_text_goes_as_argv_not_script(self):
        seen = []
        scanner._osascript = scanner._osascript_with  # the real sender, with a fake process runner
        self.addCleanup(setattr, scanner, "_osascript", self.sent)
        title, body = 'Title "quoted"', 'Body" & (do shell script "x") & "'
        scanner._osascript_with(title, body, run=lambda args, **kw: seen.append(args))
        args = seen[0]
        self.assertEqual(args[:3], ["/usr/bin/osascript", "-e", scanner.NOTIFY_SCRIPT])
        self.assertEqual(args[3:], [title, body])
        self.assertNotIn("quoted", scanner.NOTIFY_SCRIPT)
        self.assertIn("argv", scanner.NOTIFY_SCRIPT)


class NotifyCliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="notify-test-")
        self.addCleanup(shutil.rmtree, self.dir)
        self.sent = Recorder()
        original = scanner._osascript
        scanner._osascript = self.sent
        self.addCleanup(setattr, scanner, "_osascript", original)
        self.projects = os.path.join(self.dir, "projects.json")
        with open(self.projects, "w", encoding="utf-8") as f:
            json.dump({"projects": [{"id": "other", "name": "Other"}], "default": "other", "rules": []}, f)
        self.out = os.path.join(self.dir, "data", "status.json")

    def add_session(self, sid, question):
        folder = os.path.join(self.dir, "sessions", "acct", "org")
        os.makedirs(folder, exist_ok=True)
        s = {"sessionId": sid, "title": "Title " + sid, "lastActivityAt": NOW, "lastFocusedAt": NOW,
             "cwd": "/x", "turnWrapUp": {"needsUser": question}, "postTurnSummary": {"status_category": "completed"}}
        with open(os.path.join(folder, sid + ".json"), "w", encoding="utf-8") as f:
            json.dump(s, f)

    def run_cli(self, *extra):
        args = ["--sessions-dir", os.path.join(self.dir, "sessions"), "--projects", self.projects,
                "--state", os.path.join(self.dir, "data", "state.json"), "--out", self.out] + list(extra)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return scanner.main(args)

    def test_no_notify_flag(self):
        self.add_session("local_a", "First?")
        self.run_cli()                                   # baseline: silent
        self.add_session("local_b", "Second?")
        self.run_cli("--no-notify")                      # new question, but notifications off
        self.assertEqual(self.sent.calls, [])
        self.add_session("local_c", "Third?")
        self.run_cli()                                   # only local_c is new now
        self.assertEqual(self.sent.calls, [("Sessionbell", "Title local_c")])

    def test_notify_test_sends_made_up_text_only(self):
        self.add_session("local_a", "Real question?")
        code = self.run_cli("--notify-test")
        self.assertEqual(code, 0)
        self.assertEqual(self.sent.calls, [("Sessionbell", "Test: a session asked you something")])
        self.assertFalse(os.path.exists(self.out))       # a test banner doesn't scan or write


if __name__ == "__main__":
    unittest.main()
