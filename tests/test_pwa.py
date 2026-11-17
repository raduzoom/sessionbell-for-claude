"""The installed app's files in pwa/: a valid manifest, real icons of the stated sizes, and a service worker
that caches only the page shell, never session data."""
from __future__ import annotations

import json
import os
import re
import struct
import sys
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import server  # noqa: E402

PWA = os.path.join(HERE, "pwa")


def read(name, mode="r"):
    with open(os.path.join(PWA, name), mode, **({} if "b" in mode else {"encoding": "utf-8"})) as f:
        return f.read()


class PwaTests(unittest.TestCase):
    def test_every_static_file_exists(self):
        for path, (name, _) in server.STATIC.items():
            self.assertTrue(os.path.isfile(os.path.join(PWA, name)), path)

    def test_manifest(self):
        m = json.loads(read("manifest.webmanifest"))
        self.assertEqual((m["start_url"], m["scope"], m["display"]), ("/", "/", "standalone"))
        self.assertEqual(m["name"], "Sessionbell")
        for icon in m["icons"]:
            self.assertIn(icon["src"], server.STATIC, icon["src"])
            if icon["type"] == "image/png":
                w, h = map(int, icon["sizes"].split("x"))
                self.assertEqual(png_size(icon["src"].lstrip("/")), (w, h), icon["src"])
        sizes = {i["sizes"] for i in m["icons"] if i["type"] == "image/png" and i["purpose"] == "any"}
        self.assertTrue({"192x192", "512x512"} <= sizes)   # what Chrome needs to offer Install

    def test_apple_touch_icon(self):
        self.assertEqual(png_size("apple-touch-icon.png"), (180, 180))

    def test_service_worker_caches_only_the_shell(self):
        code = re.sub(r"//[^\n]*", "", read("sw.js"))          # comments may name the files it leaves alone
        self.assertNotIn("status", code)
        self.assertNotIn("state", code)
        self.assertIn("var SHELL = '/';", code)
        self.assertEqual(re.findall(r"\.put\(([^,]+),", code), ["SHELL"])
        self.assertEqual(re.findall(r"\.add\(([^)]+)\)", code), ["SHELL"])
        self.assertIn("req.mode !== 'navigate'", code)


def png_size(name):
    data = read(name, "rb")
    assert data[:8] == b"\x89PNG\r\n\x1a\n", name
    return struct.unpack(">II", data[16:24])


if __name__ == "__main__":
    unittest.main()
