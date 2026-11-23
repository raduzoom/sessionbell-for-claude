"""Server tests (handoff §8). Made-up data only; the server runs on a free port in a thread."""
from __future__ import annotations

import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402

PAGE = "<!doctype html><title>Sessionbell</title>"
STATUS = {"schema": 1, "generatedAt": 1, "error": None, "projects": [], "main": [], "scheduled": [],
          "stale": [], "quiet": [], "hidden": [], "counts": {"main": 0, "scanned": 3}}


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="server-test-")
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, "data"))
        with open(os.path.join(self.root, "index.html"), "w", encoding="utf-8") as f:
            f.write(PAGE)
        self.write_status(json.dumps(STATUS))
        self.httpd = server.make_server(self.root, 0)
        self.port = self.httpd.server_address[1]
        t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        t.start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def write_status(self, text):
        with open(os.path.join(self.root, "data", "status.json"), "w", encoding="utf-8") as f:
            f.write(text)

    def request(self, path, method="GET", host=None, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.putrequest(method, path, skip_host=True)
        if host is not False:
            conn.putheader("Host", host or "127.0.0.1:%d" % self.port)
        for k, v in (headers or {}).items():
            conn.putheader(k, v)
        if body is not None:
            conn.putheader("Content-Length", str(len(body)))
        conn.endheaders(body)
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        return resp.status, dict((k.lower(), v) for k, v in resp.getheaders()), data

    def test_page_served(self):
        code, headers, body = self.request("/")
        self.assertEqual(code, 200)
        self.assertTrue(headers["content-type"].startswith("text/html"))
        self.assertEqual(body.decode(), PAGE)

    def test_page_read_from_disk_each_time(self):
        with open(os.path.join(self.root, "index.html"), "w", encoding="utf-8") as f:
            f.write("changed")
        self.assertEqual(self.request("/")[2], b"changed")

    def test_status_served(self):
        code, headers, body = self.request("/status.json")
        self.assertEqual(code, 200)
        self.assertTrue(headers["content-type"].startswith("application/json"))
        self.assertEqual(json.loads(body), STATUS)

    def test_status_with_query_string(self):
        self.assertEqual(self.request("/status.json?t=123")[0], 200)

    def test_missing_status_is_an_error_object(self):
        os.replace(os.path.join(self.root, "data", "status.json"), os.path.join(self.root, "moved.json"))
        code, _, body = self.request("/status.json")
        data = json.loads(body)
        self.assertEqual(code, 200)
        self.assertIn("hasn't", data["error"])
        self.assertEqual((data["main"], data["counts"]), ([], {}))

    def test_broken_status_is_an_error_object(self):
        for text in ("{ half", "[1, 2]"):
            self.write_status(text)
            data = json.loads(self.request("/status.json")[2])
            self.assertIn("can't be read", data["error"])
            self.assertEqual(data["main"], [])

    def test_unexpected_format_is_an_error_object(self):
        # Review finding: format drift must be a red banner, never a calm 0.
        drifted = [{"schema": 2, "error": None, "sessions": []},
                   dict(STATUS, generatedAt=None),
                   dict(STATUS, main=None),
                   {k: v for k, v in STATUS.items() if k != "quiet"}]
        for data in drifted:
            self.write_status(json.dumps(data))
            got = json.loads(self.request("/status.json")[2])
            self.assertIn("unexpected format", got["error"] or "", data)
            self.assertEqual(got["main"], [])

    def test_working_list_is_optional(self):
        # A status written before the Working section existed still shows (the next scan adds the list).
        self.write_status(json.dumps(STATUS))
        self.assertEqual(json.loads(self.request("/status.json")[2]), STATUS)
        self.write_status(json.dumps(dict(STATUS, working=[])))
        self.assertEqual(json.loads(self.request("/status.json")[2])["working"], [])
        self.write_status(json.dumps(dict(STATUS, working="nope")))
        self.assertIn("unexpected format", json.loads(self.request("/status.json")[2])["error"])

    def test_scanner_error_status_passes_through(self):
        err = {"schema": 1, "generatedAt": 5, "error": "projects.json: x", "projects": [], "main": [],
               "scheduled": [], "stale": [], "quiet": [], "hidden": [], "counts": {"scanned": 3}}
        self.write_status(json.dumps(err))
        self.assertEqual(json.loads(self.request("/status.json")[2]), err)

    def test_head_and_options_go_through_the_guards(self):
        for method in ("HEAD", "OPTIONS"):
            code, headers, _ = self.request("/status.json", method=method, host="evil.example:%d" % self.port)
            self.assertEqual(code, 403, method)
            self.assertEqual(headers["cache-control"], "no-store")
            code, headers, _ = self.request("/status.json", method=method)
            self.assertEqual(code, 405, method)
            self.assertIn("content-security-policy", headers)

    def test_config_default_when_missing_or_wrong(self):
        path = os.path.join(self.root, "config.json")
        for text in (None, "not json", "[]", '{"pageRefreshSeconds": 1}', '{"pageRefreshSeconds": "5"}',
                     '{"pageRefreshSeconds": true}', '{"pageRefreshSeconds": 9999}'):
            if text is not None:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
            code, _, body = self.request("/config.json")
            self.assertEqual((code, json.loads(body)), (200, {"pageRefreshSeconds": 5, "replyEnabled": False}), text)

    def test_config_serves_only_the_page_setting(self):
        with open(os.path.join(self.root, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"scanEverySeconds": 10, "pageRefreshSeconds": 20, "replyEnabled": True, "other": "x"}, f)
        code, _, body = self.request("/config.json")
        self.assertEqual((code, json.loads(body)), (200, {"pageRefreshSeconds": 20, "replyEnabled": True}))

    def test_config_local_overrides_shared(self):
        # config.json ships with replies off; this Mac's git-ignored config.local.json can turn them on.
        with open(os.path.join(self.root, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"pageRefreshSeconds": 20, "replyEnabled": False}, f)
        local = os.path.join(self.root, "config.local.json")
        with open(local, "w", encoding="utf-8") as f:
            json.dump({"replyEnabled": True}, f)
        code, _, body = self.request("/config.json")
        self.assertEqual((code, json.loads(body)), (200, {"pageRefreshSeconds": 20, "replyEnabled": True}))
        for text in ("not json", "[]", '{"replyEnabled": "true"}'):   # a bad local file never turns replies on
            with open(local, "w", encoding="utf-8") as f:
                f.write(text)
            code, _, body = self.request("/config.json")
            self.assertEqual((code, json.loads(body)), (200, {"pageRefreshSeconds": 20, "replyEnabled": False}), text)

    def test_health(self):
        code, _, body = self.request("/health")
        self.assertEqual((code, json.loads(body)), (200, {"ok": True}))

    def test_foreign_host_403(self):
        for host in ("evil.example:%d" % self.port, "127.0.0.1", "127.0.0.1:1", "localhost.evil.example:%d" % self.port):
            code, _, body = self.request("/status.json", host=host)
            self.assertEqual(code, 403, host)
            self.assertNotIn(b"generatedAt", body)

    def test_missing_host_403(self):
        self.assertEqual(self.request("/status.json", host=False)[0], 403)

    def test_localhost_host_ok(self):
        self.assertEqual(self.request("/status.json", host="localhost:%d" % self.port)[0], 200)

    def test_security_headers(self):
        for path in ("/", "/status.json", "/config.json", "/health", "/nope"):
            _, headers, _ = self.request(path)
            self.assertEqual(headers["cache-control"], "no-store", path)
            self.assertEqual(headers["x-content-type-options"], "nosniff")
            self.assertEqual(headers["referrer-policy"], "no-referrer")
            self.assertEqual(headers["x-frame-options"], "DENY")
            csp = headers["content-security-policy"]
            for part in ("default-src 'none'", "connect-src 'self'", "frame-ancestors 'none'", "form-action 'none'"):
                self.assertIn(part, csp)
        self.assertEqual(self.request("/", host="evil:1")[1]["cache-control"], "no-store")

    def test_pwa_files_served(self):
        os.makedirs(os.path.join(self.root, "pwa"))
        for path, (name, _) in server.STATIC.items():
            with open(os.path.join(self.root, "pwa", name), "wb") as f:
                f.write(b"made-up " + name.encode())
        for path, (name, content_type) in server.STATIC.items():
            code, headers, body = self.request(path)
            self.assertEqual((code, body), (200, b"made-up " + name.encode()), path)
            self.assertEqual(headers["content-type"], content_type, path)
            self.assertEqual(headers["cache-control"], "no-store", path)
            self.assertEqual(headers["x-content-type-options"], "nosniff", path)
            self.assertEqual(self.request(path, host="evil:1")[0], 403, path)
        csp = self.request("/")[1]["content-security-policy"]
        self.assertIn("manifest-src 'self'", csp)
        self.assertIn("worker-src 'self'", csp)

    def test_pwa_files_missing_404(self):
        self.assertEqual(self.request("/sw.js")[0], 404)

    def test_only_listed_pwa_files(self):
        os.makedirs(os.path.join(self.root, "pwa"))
        with open(os.path.join(self.root, "pwa", "other.txt"), "w") as f:
            f.write("x")
        for path in ("/pwa/sw.js", "/other.txt", "/pwa/other.txt", "/sw.js/../status.json"):
            self.assertEqual(self.request(path)[0], 404, path)

    def test_unknown_path_404(self):
        for path in ("/nope", "/index.html.bak", "/data/status.json", "/scanner.py", "/projects.json"):
            self.assertEqual(self.request(path)[0], 404, path)

    def test_path_traversal_404(self):
        for path in ("/../data/status.json", "/%2e%2e/data/status.json", "//etc/passwd", "/status.json/../projects.json"):
            self.assertEqual(self.request(path)[0], 404, path)

    def test_other_methods_405(self):
        # POST /state exists since Phase 4 (tests/test_state.py): an empty object is a bad request.
        code, _, _ = self.request("/state", method="POST", body=b"{}",
                                  headers={"Content-Type": "application/json", "Origin": "http://127.0.0.1:%d" % self.port})
        self.assertEqual(code, 400)
        self.assertEqual(self.request("/", method="PUT", body=b"x")[0], 405)
        self.assertEqual(self.request("/state", method="DELETE")[0], 405)

    def test_binds_loopback_only(self):
        self.assertEqual(self.httpd.server_address[0], "127.0.0.1")

    def test_default_port_and_paths(self):
        here = os.path.dirname(os.path.abspath(server.__file__))
        self.assertEqual(server.PORT, 8790)
        self.assertEqual(server.status_path(here), os.path.join(here, "data", "status.json"))


if __name__ == "__main__":
    unittest.main()
