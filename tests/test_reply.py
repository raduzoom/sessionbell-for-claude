"""POST /reply: the guards, validation and the sender's inputs. Made-up data only. The sender is replaced,
so no test ever opens a session or types into the Claude app."""
from __future__ import annotations

import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402

LISTED = "local_aaaa-1111"
WORKING = "local_bbbb-2222"
STATUS = {"schema": 1, "generatedAt": 1, "error": None, "projects": [], "main": [{"sessionId": LISTED}],
          "scheduled": [], "stale": [], "quiet": [], "hidden": [], "working": [{"sessionId": WORKING}],
          "counts": {}}


class ReplyTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="reply-test-")
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, "data"))
        self.write_status(STATUS)
        self.write_config({"replyEnabled": True})
        self.sent = []
        self.httpd = server.make_server(self.root, 0)
        self.httpd.reply_sender = lambda sid, text: self.sent.append((sid, text))
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def write_config(self, data):
        with open(os.path.join(self.root, "config.json"), "w", encoding="utf-8") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))

    def write_status(self, data):
        with open(os.path.join(self.root, "data", "status.json"), "w", encoding="utf-8") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))

    def post(self, payload, headers=None, path="/reply"):
        h = {"Host": "127.0.0.1:%d" % self.port, "Origin": "http://127.0.0.1:%d" % self.port,
             "Content-Type": "application/json"}
        h.update(headers or {})
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.putrequest("POST", path, skip_host=True)
        for k, v in h.items():
            if v is not None:
                conn.putheader(k, v)
        conn.putheader("Content-Length", str(len(body)))
        conn.endheaders(body)
        resp = conn.getresponse()
        out = resp.read()
        conn.close()
        return resp.status, out.decode("utf-8")

    # Sends --------------------------------------------------------------------------------------

    def test_sends_to_a_listed_session(self):
        code, body = self.post({"sessionId": LISTED, "text": "Yes, go ahead"})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body), {"ok": True})
        self.assertEqual(self.sent, [(LISTED, "Yes, go ahead")])

    def test_sends_to_a_working_session(self):
        self.assertEqual(self.post({"sessionId": WORKING, "text": "Also check the tests"})[0], 200)

    def test_text_is_cleaned(self):
        self.post({"sessionId": LISTED, "text": "  line one\r\nline\x07 two\x00\t!  "})
        self.assertEqual(self.sent, [(LISTED, "line one\nline two\t!")])

    def test_unicode_survives(self):
        self.post({"sessionId": LISTED, "text": "Merci ✓ — ünï 🚀"})
        self.assertEqual(self.sent[0][1], "Merci ✓ — ünï 🚀")

    def test_longest_reply_fits_the_body_limit(self):
        text = "✓" * server.MAX_REPLY_CHARS          # escaped as ✓: 6 bytes each
        body = json.dumps({"sessionId": LISTED, "text": text}).encode("ascii")
        self.assertEqual(self.post(body)[0], 200)

    # Off by default ---------------------------------------------------------------------------

    def test_off_unless_config_says_true_403(self):
        for config in (None, "not json", {}, {"replyEnabled": False}, {"replyEnabled": "true"},
                       {"replyEnabled": 1}):
            if config is None:
                os.remove(os.path.join(self.root, "config.json"))
            else:
                self.write_config(config)
            code, body = self.post({"sessionId": LISTED, "text": "hi"})
            self.assertEqual(code, 403, config)
            self.assertIn("replyEnabled", body)
        self.assertEqual(self.sent, [])

    def test_turning_it_on_needs_no_restart(self):
        self.write_config({"replyEnabled": False})
        self.assertEqual(self.post({"sessionId": LISTED, "text": "hi"})[0], 403)
        self.write_config({"replyEnabled": True})
        self.assertEqual(self.post({"sessionId": LISTED, "text": "hi"})[0], 200)

    # Validation ---------------------------------------------------------------------------------

    def test_empty_text_400(self):
        code, body = self.post({"sessionId": LISTED, "text": "  \n "})
        self.assertEqual(code, 400)
        self.assertIn("Type a reply first", body)
        self.assertEqual(self.sent, [])

    def test_too_long_400(self):
        code, _ = self.post({"sessionId": LISTED, "text": "x" * (server.MAX_REPLY_CHARS + 1)})
        self.assertEqual(code, 400)
        self.assertEqual(self.sent, [])

    def test_text_must_be_a_string_400(self):
        self.assertEqual(self.post({"sessionId": LISTED, "text": ["hi"]})[0], 400)

    def test_bad_session_id_400(self):
        for sid in ("../etc", "local_", "local_a/b", "x" * 10, None, 5):
            self.assertEqual(self.post({"sessionId": sid, "text": "hi"})[0], 400, sid)
        self.assertEqual(self.sent, [])

    def test_unlisted_session_404(self):
        code, body = self.post({"sessionId": "local_not-on-the-list", "text": "hi"})
        self.assertEqual(code, 404)
        self.assertIn("Nothing was typed", body)
        self.assertEqual(self.sent, [])

    def test_no_usable_status_503(self):
        for status in ("not json", json.dumps({"schema": 2})):
            self.write_status(status)
            self.assertEqual(self.post({"sessionId": LISTED, "text": "hi"})[0], 503)
        os.remove(os.path.join(self.root, "data", "status.json"))
        self.assertEqual(self.post({"sessionId": LISTED, "text": "hi"})[0], 503)
        self.assertEqual(self.sent, [])

    # Guards (the same as POST /state) -----------------------------------------------------------

    def test_foreign_host_403(self):
        self.assertEqual(self.post({"sessionId": LISTED, "text": "hi"}, {"Host": "evil.example:80"})[0], 403)

    def test_missing_origin_403(self):
        self.assertEqual(self.post({"sessionId": LISTED, "text": "hi"}, {"Origin": None})[0], 403)

    def test_foreign_origin_403(self):
        self.assertEqual(self.post({"sessionId": LISTED, "text": "hi"}, {"Origin": "http://evil.example"})[0], 403)
        self.assertEqual(self.sent, [])

    def test_form_post_415(self):
        code, _ = self.post(b"sessionId=x&text=hi", {"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(code, 415)

    def test_body_over_limit_413(self):
        self.assertEqual(self.post(b"x" * (server.MAX_REPLY_BODY + 1))[0], 413)

    def test_state_keeps_its_2kb_limit(self):
        self.assertEqual(self.post(b"x" * (server.MAX_BODY + 1), path="/state")[0], 413)

    # Sender results -----------------------------------------------------------------------------

    def test_sender_error_is_503_with_its_message(self):
        def fail(sid, text):
            raise server.ReplyError("Claude didn't come to the front. Nothing was typed.")
        self.httpd.reply_sender = fail
        code, body = self.post({"sessionId": LISTED, "text": "hi"})
        self.assertEqual(code, 503)
        self.assertIn("Claude didn't come to the front", body)
        # The lock is released after a failure.
        self.httpd.reply_sender = lambda sid, text: self.sent.append(sid)
        self.assertEqual(self.post({"sessionId": LISTED, "text": "hi"})[0], 200)

    def test_one_send_at_a_time_409(self):
        started, release = threading.Event(), threading.Event()

        def slow(sid, text):
            started.set()
            release.wait(5)
        self.httpd.reply_sender = slow
        first = []
        t = threading.Thread(target=lambda: first.append(self.post({"sessionId": LISTED, "text": "one"})[0]))
        t.start()
        self.assertTrue(started.wait(5))
        self.assertEqual(self.post({"sessionId": LISTED, "text": "two"})[0], 409)
        release.set()
        t.join(5)
        self.assertEqual(first, [200])


class SenderTests(unittest.TestCase):
    """type_into_claude with subprocess replaced: what it runs, and that the text only goes in as argv."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="reply-sessions-")
        self.addCleanup(shutil.rmtree, self.dir)
        os.makedirs(os.path.join(self.dir, "acct", "org"))
        self.calls = []
        self.focus = {}
        self.write("local_other", 2000)
        self.write("local_target", 1000)
        real_run, real_sleep = server.subprocess.run, server.time.sleep
        server.subprocess.run = self.fake_run
        server.time.sleep = lambda s: None
        self.addCleanup(setattr, server.subprocess, "run", real_run)
        self.addCleanup(setattr, server.time, "sleep", real_sleep)
        self.typed_rc, self.typed_err, self.switches = 0, "", True
        self.prepared = "com.example.browser\nfalse\n"

    def write(self, sid, focused):
        with open(os.path.join(self.dir, "acct", "org", sid + ".json"), "w", encoding="utf-8") as f:
            json.dump({"sessionId": sid, "title": "made-up", "lastFocusedAt": focused}, f)

    def fake_run(self, args, **kw):
        self.calls.append((args, kw))

        class R:
            returncode, stdout, stderr = 0, "", ""
        r = R()
        if args[:2] == ["/usr/bin/osascript", "-e"] and args[2] == server.PREPARE_SCRIPT:
            r.stdout = self.prepared
        elif args[0] == "/usr/bin/open" and self.switches:
            self.write("local_target", 3000)            # the app switched: lastFocusedAt moves on
        elif args[:2] == ["/usr/bin/osascript", "-"]:
            r.returncode, r.stderr = self.typed_rc, self.typed_err
        return r

    def test_opens_waits_then_types_with_text_as_argv(self):
        server.type_into_claude("local_target", "hello \"quoted\" & done", self.dir)
        programs = [c[0][0] for c in self.calls]
        self.assertEqual(programs, ["/usr/bin/osascript", "/usr/bin/open", "/usr/bin/osascript"])
        self.assertEqual(self.calls[1][0], ["/usr/bin/open", "claude://claude.ai/epitaxy/local_target"])
        args, kw = self.calls[2]
        self.assertEqual(args, ["/usr/bin/osascript", "-", "hello \"quoted\" & done", "com.example.browser", "false"])
        self.assertEqual(kw["input"], server.TYPE_SCRIPT)
        self.assertNotIn("quoted", kw["input"])

    def test_already_shown_session_does_not_wait(self):
        self.write("local_target", 5000)              # focused last of all: the app already shows it
        self.switches = False
        server.type_into_claude("local_target", "hi", self.dir)
        self.assertEqual(self.calls[-1][0][1], "-")

    def test_no_switch_times_out_without_typing(self):
        self.switches = False
        clock = iter(range(0, 1000, 5))
        real = server.time.monotonic
        server.time.monotonic = lambda: next(clock)
        self.addCleanup(setattr, server.time, "monotonic", real)
        with self.assertRaises(server.ReplyError) as e:
            server.type_into_claude("local_target", "hi", self.dir)
        self.assertIn("Nothing was typed", str(e.exception))
        self.assertNotIn("-", [c[0][1] for c in self.calls if len(c[0]) > 1])

    def stalled_switch(self):
        self.switches = False
        clock = iter(range(0, 1000, 5))
        real = server.time.monotonic
        server.time.monotonic = lambda: next(clock)
        self.addCleanup(setattr, server.time, "monotonic", real)
        with self.assertRaises(server.ReplyError):
            server.type_into_claude("local_target", "hi", self.dir)

    def test_accessibility_setting_put_back_when_the_send_stops_early(self):
        self.stalled_switch()
        self.assertEqual(self.calls[0][0], ["/usr/bin/osascript", "-e", server.PREPARE_SCRIPT])
        self.assertEqual(self.calls[-1][0], ["/usr/bin/osascript", "-e", server.PUT_BACK_SCRIPT])

    def test_accessibility_setting_left_on_when_it_was_on(self):
        self.prepared = "com.example.browser\ntrue\n"
        self.stalled_switch()
        self.assertNotIn(["/usr/bin/osascript", "-e", server.PUT_BACK_SCRIPT], [c[0] for c in self.calls])

    def test_missing_session_file(self):
        with self.assertRaises(server.ReplyError):
            server.type_into_claude("local_gone", "hi", self.dir)
        self.assertEqual(self.calls, [])

    def test_osascript_failure_becomes_a_sentence(self):
        self.typed_rc = 1
        self.typed_err = "12:34: execution error: System Events got an error: osascript is not allowed assistive access. (-1719)"
        with self.assertRaises(server.ReplyError) as e:
            server.type_into_claude("local_target", "hi", self.dir)
        self.assertIn("Device Control and Data Access", str(e.exception))

    def test_script_types_only_into_a_focused_text_area_of_a_frontmost_claude(self):
        s = server.TYPE_SCRIPT
        self.assertIn('if focusRole is not "AXTextArea" then', s)
        # Electron shows its page to accessibility only after AXManualAccessibility; it's put back after.
        self.assertLess(s.index('to true'), s.index('"AXFocusedUIElement"'))
        self.assertEqual(s.count("my putBackAccessibility(manualBefore)"), 2)
        self.assertIn("repeat with i from 1 to 60", s)            # Claude needs ~2.5 s to show its page
        self.assertIn("if not (frontmost of claudeProc) then error", s)
        self.assertLess(s.index('"AXTextArea"'), s.index('keystroke "v" using command down'))
        self.assertIn("org.nspasteboard.TransientType", s)
        self.assertIn("my restoreClipboard(pb, saved)", s)


if __name__ == "__main__":
    unittest.main()
