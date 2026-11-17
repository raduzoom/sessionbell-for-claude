"""POST /state and state.json (handoff §5, §8, §13). Made-up data only; the server runs on a free port."""
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

DAY = 24 * 60 * 60 * 1000


def now_ms():
    return int(time.time() * 1000)


class StateTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="state-test-")
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, "data"))
        with open(os.path.join(self.root, "index.html"), "w", encoding="utf-8") as f:
            f.write("page")
        self.start()

    def start(self):
        self.httpd = server.make_server(self.root, 0)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    @property
    def origin(self):
        return "http://127.0.0.1:%d" % self.port

    def request(self, method, path, body=None, host=None, headers=None, length=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.putrequest(method, path, skip_host=True)
        conn.putheader("Host", host or "127.0.0.1:%d" % self.port)
        for k, v in (headers or {}).items():
            conn.putheader(k, v)
        data = body.encode("utf-8") if isinstance(body, str) else body
        if data is not None and length:
            conn.putheader("Content-Length", str(len(data)))
        conn.endheaders(data)
        resp = conn.getresponse()
        out = resp.read()
        conn.close()
        return resp.status, out

    def post(self, payload, **kw):
        headers = {"Origin": self.origin, "Content-Type": "application/json"}
        headers.update(kw.pop("headers", {}))
        body = payload if isinstance(payload, (str, bytes)) else json.dumps(payload)
        return self.request("POST", "/state", body, headers=headers, **kw)

    def state(self):
        code, body = self.request("GET", "/state.json")
        self.assertEqual(code, 200)
        return json.loads(body)

    def state_file(self):
        return os.path.join(self.root, "data", "state.json")

    # Round trips ----------------------------------------------------------------------------

    def test_snooze_round_trip(self):
        until = now_ms() + 3600_000
        code, body = self.post({"action": "snooze", "sessionId": "local_abc", "until": until})
        self.assertEqual(code, 200)
        entry = json.loads(body)["hidden"]["local_abc"]
        self.assertEqual((entry["kind"], entry["until"]), ("snooze", until))
        self.assertEqual(self.state()["hidden"]["local_abc"]["until"], until)

    def test_dismiss_round_trip(self):
        code, _ = self.post({"action": "dismiss", "sessionId": "local_d-1", "lastActivityAt": 1794490000000})
        self.assertEqual(code, 200)
        entry = self.state()["hidden"]["local_d-1"]
        self.assertEqual((entry["kind"], entry["lastActivityAt"]), ("dismiss", 1794490000000))
        self.assertIsInstance(entry["at"], int)

    def test_restore(self):
        self.post({"action": "snooze", "sessionId": "local_abc", "until": now_ms() + 3600_000})
        code, _ = self.post({"action": "restore", "sessionId": "local_abc"})
        self.assertEqual(code, 200)
        self.assertEqual(self.state()["hidden"], {})
        self.assertEqual(self.post({"action": "restore", "sessionId": "local_never"})[0], 200)

    def test_pin_and_unpin(self):
        code, state = self.post({"action": "pin", "sessionId": "local_abc"})
        self.assertEqual(code, 200)
        self.assertEqual(list(self.state()["pinned"]), ["local_abc"])
        self.assertEqual(self.post({"action": "unpin", "sessionId": "local_abc"})[0], 200)
        self.assertEqual(self.state()["pinned"], {})
        self.assertEqual(self.post({"action": "unpin", "sessionId": "local_never"})[0], 200)

    def test_pin_shows_a_hidden_session_and_hiding_unpins(self):
        self.post({"action": "snooze", "sessionId": "local_abc", "until": now_ms() + 3600_000})
        self.post({"action": "pin", "sessionId": "local_abc"})
        self.assertEqual((self.state()["hidden"], list(self.state()["pinned"])), ({}, ["local_abc"]))
        self.post({"action": "dismiss", "sessionId": "local_abc", "lastActivityAt": 1})
        self.assertEqual((list(self.state()["hidden"]), self.state()["pinned"]), (["local_abc"], {}))
        # Restore only ends a hide; it never touches a pin.
        self.post({"action": "pin", "sessionId": "local_abc"})
        self.post({"action": "restore", "sessionId": "local_abc"})
        self.assertEqual(list(self.state()["pinned"]), ["local_abc"])

    def test_pin_rejects_a_bad_session_id(self):
        self.assertEqual(self.post({"action": "pin", "sessionId": "../x"})[0], 400)

    def test_pins_never_expire_but_keep_newest_200(self):
        t = now_ms()
        many = {"version": 1, "hidden": {}, "pinned": {"local_%03d" % i: {"at": t - i * 365 * DAY} for i in range(205)}}
        many["pinned"]["bad id"] = {"at": t}
        many["pinned"]["local_noat"] = "x"
        with open(self.state_file(), "w", encoding="utf-8") as f:
            json.dump(many, f)
        self.post({"action": "restore", "sessionId": "local_none"})
        pinned = self.state()["pinned"]
        self.assertEqual(len(pinned), 200)
        self.assertIn("local_150", pinned)                 # 150 years old: still pinned
        self.assertNotIn("local_204", pinned)
        self.assertNotIn("bad id", pinned)

    def test_get_state_missing_is_empty(self):
        self.assertEqual(self.state(), {"version": 1, "hidden": {}, "pinned": {}})

    def test_broken_state_reads_empty(self):
        for text in ("{ half", "[1]", '{"version": 1, "hidden": [1]}'):
            with open(self.state_file(), "w", encoding="utf-8") as f:
                f.write(text)
            self.assertEqual(self.state(), {"version": 1, "hidden": {}, "pinned": {}})
        # A POST over a broken file starts clean instead of failing.
        self.assertEqual(self.post({"action": "restore", "sessionId": "local_x"})[0], 200)

    def test_survives_a_server_restart(self):
        until = now_ms() + 3600_000
        self.post({"action": "snooze", "sessionId": "local_abc", "until": until})
        self.httpd.shutdown()
        self.httpd.server_close()
        self.start()
        self.assertEqual(self.state()["hidden"]["local_abc"]["until"], until)

    # Guards ---------------------------------------------------------------------------------

    def test_foreign_host_403(self):
        code, _ = self.post({"action": "restore", "sessionId": "local_x"}, host="evil.example:%d" % self.port)
        self.assertEqual(code, 403)
        self.assertFalse(os.path.exists(self.state_file()))

    def test_missing_origin_403(self):
        code, _ = self.request("POST", "/state", json.dumps({"action": "restore", "sessionId": "local_x"}),
                               headers={"Content-Type": "application/json"})
        self.assertEqual(code, 403)

    def test_foreign_origin_403(self):
        for origin in ("http://evil.example", "null", "http://127.0.0.1:1", "https://127.0.0.1:%d" % self.port,
                       "http://localhost:%d" % self.port):       # Origin must match the Host it came through
            code, _ = self.post({"action": "restore", "sessionId": "local_x"}, headers={"Origin": origin})
            self.assertEqual(code, 403, origin)
        self.assertFalse(os.path.exists(self.state_file()))

    def test_localhost_origin_through_localhost_host_ok(self):
        code, _ = self.post({"action": "restore", "sessionId": "local_x"}, host="localhost:%d" % self.port,
                            headers={"Origin": "http://localhost:%d" % self.port})
        self.assertEqual(code, 200)

    def test_wrong_content_type_415(self):
        for ctype in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data; boundary=x"):
            code, _ = self.post({"action": "restore", "sessionId": "local_x"}, headers={"Content-Type": ctype})
            self.assertEqual(code, 415, ctype)
        code, _ = self.post({"action": "restore", "sessionId": "local_x"},
                            headers={"Content-Type": "application/json; charset=utf-8"})
        self.assertEqual(code, 200)

    def test_missing_length_411(self):
        code, _ = self.post({"action": "restore", "sessionId": "local_x"}, length=False)
        self.assertEqual(code, 411)

    def test_body_over_2kb_413(self):
        code, _ = self.post({"action": "restore", "sessionId": "local_x", "pad": "x" * 2100})
        self.assertEqual(code, 413)

    def test_bad_json_400(self):
        for body in ("{ half", "[1, 2]", '"text"', b"\xff\xfe"):
            self.assertEqual(self.post(body)[0], 400, body)

    def test_bad_session_id_400(self):
        for sid in ("abc", "local_", "local_" + "a" * 81, "local_a b", "local_../x", 7, None):
            code, _ = self.post({"action": "restore", "sessionId": sid})
            self.assertEqual(code, 400, sid)

    def test_unknown_action_400(self):
        for action in ("delete", "", None, "archive"):
            self.assertEqual(self.post({"action": action, "sessionId": "local_x"})[0], 400, action)

    def test_until_in_the_past_400(self):
        self.assertEqual(self.post({"action": "snooze", "sessionId": "local_x", "until": now_ms() - 1})[0], 400)

    def test_until_beyond_8_days_400(self):
        for until in (now_ms() + 8 * DAY + 60_000, float("inf"), "tomorrow", True, None):
            body = json.dumps({"action": "snooze", "sessionId": "local_x", "until": until})
            self.assertEqual(self.post(body)[0], 400, until)
        self.assertEqual(self.post({"action": "snooze", "sessionId": "local_x", "until": now_ms() + 7 * DAY})[0], 200)

    def test_dismiss_needs_last_activity_400(self):
        for value in (None, "x", True, float("nan")):
            body = json.dumps({"action": "dismiss", "sessionId": "local_x", "lastActivityAt": value})
            self.assertEqual(self.post(body)[0], 400, value)

    def test_dismiss_time_must_be_plausible_400(self):
        # Review finding: 1e308 or a negative time would hide a session for 90 days.
        for value in (1e308, -5, 0, now_ms() + 2 * DAY):
            body = json.dumps({"action": "dismiss", "sessionId": "local_x", "lastActivityAt": value})
            self.assertEqual(self.post(body)[0], 400, value)

    def test_dismiss_keeps_a_fractional_time_exactly(self):
        # Review finding: rounding down would make the session look newer than the dismissal.
        self.post({"action": "dismiss", "sessionId": "local_f", "lastActivityAt": 1794490000000.75})
        self.assertEqual(self.state()["hidden"]["local_f"]["lastActivityAt"], 1794490000000.75)

    def test_deeply_nested_body_400(self):
        # Review finding: Python 3.9 raised RecursionError and dropped the connection.
        self.assertEqual(self.post("[" * 1500)[0], 400)

    def test_entry_without_at_still_hides(self):
        # Same as the scanner, which never needed "at".
        with open(self.state_file(), "w", encoding="utf-8") as f:
            json.dump({"version": 1, "hidden": {"local_old": {"kind": "dismiss", "lastActivityAt": 5}}}, f)
        self.assertEqual(self.state()["hidden"]["local_old"]["kind"], "dismiss")

    def test_stalled_body_times_out(self):
        # Review finding: a client that never sends its body held a thread forever.
        self.assertLessEqual(server.Handler.timeout, 30)
        import socket
        old, server.Handler.timeout = server.Handler.timeout, 1
        self.addCleanup(setattr, server.Handler, "timeout", old)
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=40)
        self.addCleanup(sock.close)
        sock.sendall(("POST /state HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nOrigin: %s\r\n"
                      "Content-Type: application/json\r\nContent-Length: 100\r\n\r\n{}" % (self.port, self.origin)).encode())
        started = time.time()
        sock.recv(4096)                 # returns once the server gives up on the body
        self.assertLess(time.time() - started, 20)

    # Storage --------------------------------------------------------------------------------

    def test_state_file_private_and_atomic(self):
        self.post({"action": "snooze", "sessionId": "local_abc", "until": now_ms() + 3600_000})
        self.assertEqual(os.stat(self.state_file()).st_mode & 0o077, 0)
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, "data"))), ["state.json"])

    def test_prune_ended_snoozes(self):
        old = {"version": 1, "hidden": {"local_old": {"kind": "snooze", "until": now_ms() - 1000, "at": now_ms() - DAY}}}
        with open(self.state_file(), "w", encoding="utf-8") as f:
            json.dump(old, f)
        self.post({"action": "dismiss", "sessionId": "local_new", "lastActivityAt": 1})
        self.assertEqual(sorted(self.state()["hidden"]), ["local_new"])

    def test_prune_old_dismissals(self):
        old = {"version": 1, "hidden": {
            "local_old": {"kind": "dismiss", "lastActivityAt": 1, "at": now_ms() - 91 * DAY},
            "local_keep": {"kind": "dismiss", "lastActivityAt": 1, "at": now_ms() - 89 * DAY}}}
        with open(self.state_file(), "w", encoding="utf-8") as f:
            json.dump(old, f)
        self.post({"action": "restore", "sessionId": "local_none"})
        self.assertEqual(sorted(self.state()["hidden"]), ["local_keep"])

    def test_keep_newest_1000(self):
        t = now_ms()
        many = {"version": 1, "hidden": {"local_%04d" % i: {"kind": "dismiss", "lastActivityAt": 1, "at": t - i}
                                         for i in range(1005)}}
        with open(self.state_file(), "w", encoding="utf-8") as f:
            json.dump(many, f)
        self.post({"action": "restore", "sessionId": "local_none"})
        hidden = self.state()["hidden"]
        self.assertEqual(len(hidden), 1000)
        self.assertIn("local_0000", hidden)
        self.assertNotIn("local_1004", hidden)

    def test_concurrent_posts_keep_every_entry(self):
        until = now_ms() + 3600_000
        threads = [threading.Thread(target=self.post,
                                    args=({"action": "snooze", "sessionId": "local_t%02d" % i, "until": until},))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(self.state()["hidden"]), 20)

    def test_post_writes_only_under_data(self):
        before = sorted(os.listdir(self.root))
        self.post({"action": "snooze", "sessionId": "local_abc", "until": now_ms() + 3600_000})
        self.assertEqual(sorted(os.listdir(self.root)), before)

    def test_post_to_other_paths_404(self):
        code, _ = self.request("POST", "/status.json", "{}",
                               headers={"Origin": self.origin, "Content-Type": "application/json"})
        self.assertEqual(code, 404)


if __name__ == "__main__":
    unittest.main()
