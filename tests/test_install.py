"""install.sh and uninstall.sh (handoff §10), dry runs only: nothing is loaded and ~/Library is untouched."""
from __future__ import annotations

import json
import os
import plistlib
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABELS = ("local.sessionbell.scanner", "local.sessionbell.server")


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp(prefix="install-test-")
        self.addCleanup(shutil.rmtree, self.out)
        result = subprocess.run(["/bin/bash", os.path.join(HERE, "install.sh"), "--dry-run", self.out],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.plists = {}
        for label in LABELS:
            with open(os.path.join(self.out, label + ".plist"), "rb") as f:
                self.plists[label] = plistlib.load(f)

    def test_both_plists_pass_plutil(self):
        for label in LABELS:
            r = subprocess.run(["/usr/bin/plutil", "-lint", os.path.join(self.out, label + ".plist")],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(sorted(os.listdir(self.out)), sorted(label + ".plist" for label in LABELS))

    def test_absolute_python_and_paths(self):
        for label, script in zip(LABELS, ("scanner.py", "server.py")):
            p = self.plists[label]
            self.assertEqual(p["Label"], label)
            self.assertEqual(p["ProgramArguments"], ["/usr/bin/python3", "-I", os.path.join(HERE, script)])
            self.assertEqual(p["WorkingDirectory"], HERE)
            self.assertTrue(p["RunAtLoad"])
            self.assertEqual(p["LimitLoadToSessionType"], "Aqua")      # a GUI login: banners can show

    def test_scanner_interval_comes_from_config(self):
        p = self.plists[LABELS[0]]
        with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
            every = json.load(f)["scanEverySeconds"]
        self.assertTrue(5 <= every <= 120)
        self.assertEqual(p["StartInterval"], every)
        self.assertNotIn("KeepAlive", p)

    def test_server_kept_alive(self):
        p = self.plists[LABELS[1]]
        self.assertTrue(p["KeepAlive"])
        self.assertNotIn("StartInterval", p)

    def test_logs_under_data(self):
        for label, name in zip(LABELS, ("scanner", "server")):
            p = self.plists[label]
            log = os.path.join(HERE, "data", "logs", name + ".log")
            self.assertEqual((p["StandardOutPath"], p["StandardErrorPath"]), (log, log))

    def test_dry_run_loads_nothing(self):
        for script in ("install.sh", "uninstall.sh"):
            with open(os.path.join(HERE, script), encoding="utf-8") as f:
                text = f.read()
            self.assertIn("--dry-run", text)
        r = subprocess.run(["/bin/bash", os.path.join(HERE, "uninstall.sh"), "--dry-run"],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        for label in LABELS:
            self.assertIn("bootout gui/", r.stdout)
            self.assertIn(label, r.stdout)

    def test_scripts_parse_and_never_rm(self):
        for script in ("install.sh", "uninstall.sh"):
            path = os.path.join(HERE, script)
            self.assertEqual(subprocess.run(["/bin/bash", "-n", path]).returncode, 0, script)
            with open(path, encoding="utf-8") as f:
                code = "\n".join(line for line in f if not line.lstrip().startswith("#"))
            self.assertNotRegex(code, r"(^|[\s;&|])rm(\s|$)", script)   # plists go to the Trash
            self.assertTrue(os.access(path, os.X_OK), script + " is executable")


if __name__ == "__main__":
    unittest.main()
