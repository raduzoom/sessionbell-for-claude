#!/usr/bin/env python3
"""Sessionbell: the server.

Serves the page and data/status.json on http://127.0.0.1:8790 only, and stores Snooze, Dismiss and Pin in
data/state.json (it is that file's only writer). Routes: GET /, GET /status.json, GET /state.json,
GET /health, POST /state, POST /reply (types a reply into a listed Claude session, only when config.local.json or config.json has "replyEnabled": true:
see "Reply" below), and
the installed app's fixed files from pwa/ (STATIC: manifest, service worker, icons). It serves real session titles and accepts writes, so every request goes through
the guards in handoff §8: loopback only, a strict Host check (stops DNS rebinding), the page's own Origin and
a JSON content type on writes, a 2 KB limit, strict validation, no caching and no sniffing.

    python3 server.py [--port 8790]

Python 3.9+, standard library only. Run with -I by the login agent, so it imports nothing from this folder.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
HOST = "127.0.0.1"
PORT = 8790
CSP = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; "
       "img-src 'self' data:; manifest-src 'self'; worker-src 'self'; base-uri 'none'; form-action 'none'; "
       "frame-ancestors 'none'")
# The installed app (PWA): a fixed list of files from pwa/, nothing else from disk. None holds session data.
STATIC = {
    "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
    "/sw.js": ("sw.js", "text/javascript; charset=utf-8"),
    "/icon.svg": ("icon.svg", "image/svg+xml"),
    "/icon-192.png": ("icon-192.png", "image/png"),
    "/icon-512.png": ("icon-512.png", "image/png"),
    "/icon-maskable-512.png": ("icon-maskable-512.png", "image/png"),
    "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png"),
}
SECTIONS = ("main", "scheduled", "stale", "quiet", "hidden")
PAGE_REFRESH_S = 5                      # used when config.json is missing or its value is wrong

# state.json limits (handoff §8)
MAX_BODY = 2048
SESSION_ID = re.compile(r"local_[A-Za-z0-9_-]{1,80}")
DAY_MS = 24 * 60 * 60_000
SNOOZE_MAX_MS = 8 * 24 * 60 * 60 * 1000
DISMISS_KEEP_MS = 90 * 24 * 60 * 60 * 1000
MAX_ENTRIES = 1000
MAX_PINS = 200                          # pins never end by themselves; keep the newest this many
ACTIONS = ("snooze", "dismiss", "restore", "pin", "unpin")

# POST /reply limits
MAX_REPLY_CHARS = 4000
MAX_REPLY_BODY = 64 * 1024              # 4,000 characters, even when every one is JSON-escaped
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")    # keeps newline and tab
SESSIONS_DIR = os.path.expanduser("~/Library/Application Support/Claude/claude-code-sessions")
LINK_PREFIX = "claude://claude.ai/epitaxy/"
CLAUDE_APP_ID = "com.anthropic.claudefordesktop"
SWITCH_TIMEOUT_S = 10


def _json_object(path):
    """The JSON object in path, or {} when the file is missing, unreadable or not an object."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError, RecursionError):
        return {}
    return data if isinstance(data, dict) else {}


def read_config(root):
    """What the page needs from config.json: how often to re-read the status (2 to 300 s), and whether the
    reply bar is on. Replies are off unless the file says "replyEnabled": true.

    config.local.json (git-ignored, this Mac's own choices) overrides config.json key by key, so the shared,
    published file can keep replies off while this Mac turns them on."""
    config = _json_object(os.path.join(root, "config.json"))
    config.update(_json_object(os.path.join(root, "config.local.json")))
    seconds = PAGE_REFRESH_S
    value = config.get("pageRefreshSeconds")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and 2 <= value <= 300:
        seconds = value
    return {"pageRefreshSeconds": seconds, "replyEnabled": config.get("replyEnabled") is True}


def status_path(root):
    return os.path.join(root, "data", "status.json")


def state_path(root):
    return os.path.join(root, "data", "state.json")


def _now():
    return int(time.time() * 1000)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _error_status(message):
    """What the page gets when there's no usable status: a red banner, never a calm 0."""
    status = {"schema": 1, "generatedAt": None, "error": message, "projects": []}
    for key in SECTIONS + ("working", "caughtUp"):
        status[key] = []
    status["counts"] = {}
    return status


def _expected_shape(data):
    """Format drift must become a red banner, never a calm 0 (handoff §14)."""
    when = data.get("generatedAt")
    return (data.get("schema") == 1 and isinstance(when, (int, float)) and not isinstance(when, bool)
            and (data.get("error") is None or isinstance(data.get("error"), str))
            and isinstance(data.get("projects"), list) and isinstance(data.get("counts"), dict)
            and all(isinstance(data.get(key), list) for key in SECTIONS)
            # "working" was added later: optional, but a list when present.
            and isinstance(data.get("working", []), list)
            and isinstance(data.get("caughtUp", []), list))     # added 2026-11-17, optional the same way


# state.json ---------------------------------------------------------------------------------

def _valid_entry(entry):
    # "at" is only for pruning; an entry without it still hides, as in the scanner (review finding).
    if not isinstance(entry, dict) or ("at" in entry and not _number(entry.get("at"))):
        return False
    if entry.get("kind") == "snooze":
        return _number(entry.get("until"))
    if entry.get("kind") == "dismiss":
        return _number(entry.get("lastActivityAt"))
    return False


def read_state(path):
    """The stored state; a missing or broken file (or entry) hides nothing (handoff §5)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError, UnicodeDecodeError):
        data = None
    hidden = data.get("hidden") if isinstance(data, dict) else None
    if not isinstance(hidden, dict):
        hidden = {}
    clean = {sid: dict(e, at=e.get("at", 0)) for sid, e in hidden.items()
             if isinstance(sid, str) and SESSION_ID.fullmatch(sid) and _valid_entry(e)}
    # Pins (added 2026-11-15): {sessionId: {"at": ms}}. A pinned session stays listed until you unpin it.
    pinned = data.get("pinned") if isinstance(data, dict) else None
    if not isinstance(pinned, dict):
        pinned = {}
    pins = {sid: {"at": e["at"] if _number(e.get("at")) else 0} for sid, e in pinned.items()
            if isinstance(sid, str) and SESSION_ID.fullmatch(sid) and isinstance(e, dict)}
    return {"version": 1, "hidden": clean, "pinned": pins}


def prune(state, now):
    """Drop ended snoozes and dismissals older than 90 days; keep the 1,000 newest entries."""
    kept = {}
    for sid, e in state["hidden"].items():
        if e["kind"] == "snooze" and e["until"] <= now:
            continue
        if e["kind"] == "dismiss" and now - e["at"] > DISMISS_KEEP_MS:
            continue
        kept[sid] = e
    newest = sorted(kept.items(), key=lambda item: item[1]["at"], reverse=True)[:MAX_ENTRIES]
    pins = sorted(state.get("pinned", {}).items(), key=lambda item: item[1]["at"], reverse=True)[:MAX_PINS]
    return {"version": 1, "hidden": dict(newest), "pinned": dict(pins)}


def apply_action(state, body, now):
    """Return the new state, or raise ValueError with a reason for a 400."""
    if not isinstance(body, dict):
        raise ValueError("the body must be a JSON object")
    sid, action = body.get("sessionId"), body.get("action")
    if not isinstance(sid, str) or not SESSION_ID.fullmatch(sid):
        raise ValueError("sessionId must look like local_…")
    if action not in ACTIONS:
        raise ValueError("action must be snooze, dismiss, restore, pin or unpin")
    hidden = dict(state["hidden"])
    pinned = dict(state.get("pinned", {}))
    # The latest choice wins: pinning shows a hidden session again; snoozing or dismissing unpins it.
    if action == "pin":
        hidden.pop(sid, None)
        pinned[sid] = {"at": now}
        return {"version": 1, "hidden": hidden, "pinned": pinned}
    if action == "unpin":
        pinned.pop(sid, None)
        return {"version": 1, "hidden": hidden, "pinned": pinned}
    if action == "snooze":
        until = body.get("until")
        if not _number(until) or not now < until <= now + SNOOZE_MAX_MS:
            raise ValueError("until must be in the next 8 days")
        hidden[sid] = {"kind": "snooze", "until": int(until), "at": now}
        pinned.pop(sid, None)
    elif action == "dismiss":
        last = body.get("lastActivityAt")
        # Kept exactly (no rounding): the rule compares it with the session's own value.
        if not _number(last) or not 0 < last <= now + DAY_MS:
            raise ValueError("lastActivityAt must be a time up to now")
        hidden[sid] = {"kind": "dismiss", "lastActivityAt": last, "at": now}
        pinned.pop(sid, None)
    else:
        hidden.pop(sid, None)
    return {"version": 1, "hidden": hidden, "pinned": pinned}


def _ensure_data_folder(folder):
    """Create data/ if missing and mark it ignored by Dropbox (best effort). Same as the scanner's."""
    if os.path.isdir(folder):
        return
    os.makedirs(folder, mode=0o700)
    try:
        import subprocess
        subprocess.run(["/usr/bin/xattr", "-w", "com.dropbox.ignored", "1", folder],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=False)
    except (OSError, ValueError):
        pass


def write_state(state, path):
    """Atomic (temp file in the same folder, then os.replace) and private (0600)."""
    folder = os.path.dirname(os.path.abspath(path))
    _ensure_data_folder(folder)
    fd, tmp = tempfile.mkstemp(prefix=".state-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=True, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)                 # our own temp file only
        raise


# Reply: type a message into a Claude session ------------------------------------------------
# The Claude app has no way for another program to send a message, so the server opens the session with
# its claude:// link, waits until the app shows it, then pastes the text and presses Return through
# System Events. Needs Accessibility (and Automation for System Events) for whatever runs the server.

class ReplyError(Exception):
    """A send that failed; the message is shown on the page as it is."""


def clean_reply(body):
    """Return (sessionId, text), or raise ValueError with a reason for a 400."""
    if not isinstance(body, dict):
        raise ValueError("the body must be a JSON object")
    sid, text = body.get("sessionId"), body.get("text")
    if not isinstance(sid, str) or not SESSION_ID.fullmatch(sid):
        raise ValueError("sessionId must look like local_…")
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    text = CONTROL_CHARS.sub("", text.replace("\r\n", "\n").replace("\r", "\n")).strip()
    if not text:
        raise ValueError("Type a reply first.")
    if len(text) > MAX_REPLY_CHARS:
        raise ValueError("A reply can be up to %d characters." % MAX_REPLY_CHARS)
    return sid, text


def listed_sessions(path):
    """Session ids on the dashboard now: a reply only goes to a session the scanner listed."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict) or not _expected_shape(data):
        return None
    return {c.get("sessionId") for key in SECTIONS + ("working", "caughtUp") for c in data.get(key, [])
            if isinstance(c, dict)}


def _focused_at(path):
    """The session file's lastFocusedAt (the only field read), or None."""
    try:
        with open(path, encoding="utf-8") as f:
            value = json.load(f).get("lastFocusedAt")
    except (OSError, ValueError, UnicodeDecodeError, AttributeError):
        return None
    return value if _number(value) else None


# Pastes argv 1 into Claude's focused message box and presses Return, then puts the clipboard back
# (every item and type) and brings back the app that was in front (argv 2). Typing happens only when
# Claude is frontmost and a text area has focus; otherwise it stops with a message and types nothing.
TYPE_SCRIPT = r'''
use AppleScript version "2.4"
use framework "Foundation"
use framework "AppKit"
use scripting additions

on run argv
	set replyText to item 1 of argv
	set previousApp to item 2 of argv
	set manualBefore to item 3 of argv  -- AXManualAccessibility before the send: "true", "false" or "unknown"
	set pb to missing value
	set saved to missing value
	try
		tell application id "%(app)s" to activate
		tell application "System Events"
			set claudeProc to first process whose bundle identifier is "%(app)s"
			repeat 30 times
				if frontmost of claudeProc then exit repeat
				delay 0.1
			end repeat
			if not (frontmost of claudeProc) then error "Claude didn't come to the front. Nothing was typed." number 1001
			-- Claude is an Electron app: it shows its page (the message box) to accessibility clients only
			-- after one sets AXManualAccessibility, and builds that view in about 2.5 s (measured 2026-11-13).
			-- The server turned it on before opening the session; it's put back as it was at the end.
			try
				if manualBefore is "unknown" then set manualBefore to (value of attribute "AXManualAccessibility" of claudeProc) as text
				set value of attribute "AXManualAccessibility" of claudeProc to true
			end try
			set focusRole to ""
			set lastErr to ""
			repeat with i from 1 to 60
				try
					set focusedEl to value of attribute "AXFocusedUIElement" of claudeProc
					if focusedEl is not missing value then set focusRole to role of focusedEl
				on error e number n
					set lastErr to "; macOS error " & n
				end try
				if focusRole is "AXTextArea" then exit repeat
				if i is 30 then
					-- Halfway with no message box: raise Claude's window and bring the app forward again.
					try
						perform action "AXRaise" of window 1 of claudeProc
					end try
					tell application id "%(app)s" to activate
				end if
				delay 0.1
			end repeat
			if focusRole is not "AXTextArea" then
				if focusRole is "" then set focusRole to "nothing"
				set seen to ""
				try
					set seen to "; windows " & (count of windows of claudeProc)
					set seen to seen & ", minimized " & (value of attribute "AXMinimized" of window 1 of claudeProc as text)
				end try
				error "Claude's message box doesn't have focus (focused: " & focusRole & seen & lastErr & "). Nothing was typed." number 1002
			end if
		end tell
		set pb to current application's NSPasteboard's generalPasteboard()
		set saved to my saveClipboard(pb)
		pb's clearContents()
		pb's setString:replyText forType:(current application's NSPasteboardTypeString)
		pb's setString:"" forType:"org.nspasteboard.TransientType"
		tell application "System Events"
			keystroke "v" using command down
			delay 0.5
			key code 36
		end tell
		delay 0.5
	on error msg number n
		if saved is not missing value then my restoreClipboard(pb, saved)
		my putBackAccessibility(manualBefore)
		my goBack(previousApp)
		error msg number n
	end try
	my restoreClipboard(pb, saved)
	my putBackAccessibility(manualBefore)
	my goBack(previousApp)
end run

on putBackAccessibility(manualBefore)
	if manualBefore is not "false" then return
	try
		tell application "System Events" to set value of attribute "AXManualAccessibility" of (first process whose bundle identifier is "%(app)s") to false
	end try
end putBackAccessibility

on goBack(previousApp)
	if previousApp is "" or previousApp is "%(app)s" then return
	try
		tell application id previousApp to activate
	end try
end goBack

on saveClipboard(pb)
	set saved to current application's NSMutableArray's array()
	set pbItems to pb's pasteboardItems()
	if pbItems is missing value then return saved
	repeat with i from 0 to ((pbItems's |count|()) - 1)
		set itm to (pbItems's objectAtIndex:i)
		set d to current application's NSMutableDictionary's dictionary()
		set ts to itm's types()
		repeat with j from 0 to ((ts's |count|()) - 1)
			set t to (ts's objectAtIndex:j)
			set dat to (itm's dataForType:t)
			if dat is not missing value then (d's setObject:dat forKey:t)
		end repeat
		(saved's addObject:d)
	end repeat
	return saved
end saveClipboard

on restoreClipboard(pb, saved)
	pb's clearContents()
	if (saved's |count|()) is 0 then return
	set newItems to current application's NSMutableArray's array()
	repeat with i from 0 to ((saved's |count|()) - 1)
		set d to (saved's objectAtIndex:i)
		set itm to current application's NSPasteboardItem's alloc()'s init()
		set ks to d's allKeys()
		repeat with j from 0 to ((ks's |count|()) - 1)
			set k to (ks's objectAtIndex:j)
			(itm's setData:(d's objectForKey:k) forType:k)
		end repeat
		(newItems's addObject:itm)
	end repeat
	pb's writeObjects:newItems
end restoreClipboard
''' % {"app": CLAUDE_APP_ID}

# Before opening the session: which app is in front (to bring it back), and Claude's AXManualAccessibility,
# which it turns on so Claude's accessibility view builds while the app switches. Prints "<bundle id>\n<state>".
PREPARE_SCRIPT = '''
tell application "System Events"
	set frontId to bundle identifier of first process whose frontmost is true
	set manualState to "unknown"
	try
		set claudeProc to first process whose bundle identifier is "%(app)s"
		set manualState to (value of attribute "AXManualAccessibility" of claudeProc) as text
		set value of attribute "AXManualAccessibility" of claudeProc to true
	end try
	return frontId & linefeed & manualState
end tell
''' % {"app": CLAUDE_APP_ID}

PUT_BACK_SCRIPT = ('tell application "System Events" to set value of attribute "AXManualAccessibility" of '
                   '(first process whose bundle identifier is "%s") to false' % CLAUDE_APP_ID)


def osascript_message(stderr):
    """Turn osascript's stderr into a sentence for the page."""
    text = (stderr or "").strip()
    found = re.search(r"execution error: (.*) \((-?\d+)\)\s*$", text, re.S)
    message, number = (found.group(1).strip(), int(found.group(2))) if found else (text, None)
    if number in (1001, 1002):
        return message
    if number == -1743 or "Not authorized to send Apple events" in text:
        return ("macOS hasn't let the dashboard control System Events. Allow it in System Settings › "
                "Privacy & Security › Automation, then send again. Nothing was typed.")
    if number in (-1719, -25211) or "assistive access" in text or "not allowed to send keystrokes" in text:
        return ("macOS hasn't let the dashboard type. In System Settings, turn on python3 (or Terminal, if "
                "you started the server there) under Device Control and Data Access, then send again.")
    return "Couldn't type the reply: %s" % (message.splitlines()[0] if message else "osascript failed")


def type_into_claude(sid, text, sessions_dir=SESSIONS_DIR):
    """Open the session in the Claude app and type the reply. Raises ReplyError when it can't."""
    paths = glob.glob(os.path.join(glob.escape(sessions_dir), "*", "*", "local_*.json"))
    path = next((p for p in paths if os.path.basename(p) == sid + ".json"), None)
    if path is None:
        raise ReplyError("The Claude app has no file for this session any more. Nothing was typed.")
    before = _focused_at(path)
    # Already the session the app shows (focused last of all)? Then opening it won't change lastFocusedAt.
    shown = before is not None and all((_focused_at(p) or 0) <= before for p in paths)
    previous, manual = "", "unknown"
    try:
        prep = subprocess.run(["/usr/bin/osascript", "-e", PREPARE_SCRIPT], capture_output=True,
                              text=True, timeout=10)
        if prep.returncode == 0:
            lines = prep.stdout.strip().split("\n")
            previous = lines[0].strip()
            if len(lines) > 1 and lines[1].strip() in ("true", "false"):
                manual = lines[1].strip()
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        _open_and_type(sid, text, path, before, shown, previous, manual)
    except ReplyError:
        # TYPE_SCRIPT puts the setting back itself; this covers a stop before it ran (no harm if twice).
        if manual == "false":
            try:
                subprocess.run(["/usr/bin/osascript", "-e", PUT_BACK_SCRIPT], capture_output=True, timeout=10)
            except (OSError, subprocess.SubprocessError):
                pass
        raise


def _open_and_type(sid, text, path, before, shown, previous, manual):
    try:
        subprocess.run(["/usr/bin/open", LINK_PREFIX + sid], check=True, timeout=10,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        raise ReplyError("Couldn't open the session in the Claude app. Nothing was typed.")
    if not shown:
        deadline = time.monotonic() + SWITCH_TIMEOUT_S
        while True:
            now = _focused_at(path)
            if now is not None and (before is None or now > before):
                break
            if time.monotonic() > deadline:
                raise ReplyError("Claude didn't switch to the session within %d seconds. Nothing was typed."
                                 % SWITCH_TIMEOUT_S)
            time.sleep(0.25)
    time.sleep(0.6)                        # let the session's message box appear and take focus
    try:
        done = subprocess.run(["/usr/bin/osascript", "-", text, previous, manual], input=TYPE_SCRIPT,
                              capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        raise ReplyError("Couldn't type the reply: osascript didn't finish.")
    if done.returncode != 0:
        raise ReplyError(osascript_message(done.stderr))


# HTTP ---------------------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "sessionbell"
    sys_version = ""
    timeout = 10                     # a client that stops sending mid-body frees its thread (review finding)

    # Quiet logs: the page polls every few seconds, so routine 2xx answers aren't logged.
    def log_request(self, code="-", size="-"):
        if str(code).startswith("2"):
            return
        super().log_request(code, size)

    def _send(self, code, body, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", CSP)
        if code == 405:
            self.send_header("Allow", "GET, POST")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _text(self, code, message):
        self._send(code, (message + "\n").encode("utf-8"), "text/plain; charset=utf-8")

    def _json(self, data):
        self._send(200, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _host_ok(self):
        port = self.server.server_address[1]
        return self.headers.get("Host") in ("127.0.0.1:%d" % port, "localhost:%d" % port)

    def do_GET(self):
        if not self._host_ok():
            return self._text(403, "Forbidden")
        path = urlsplit(self.path).path
        root = self.server.root
        if path == "/":
            try:
                with open(os.path.join(root, "index.html"), "rb") as f:
                    body = f.read()
            except OSError:
                return self._text(500, "index.html is missing")
            return self._send(200, body, "text/html; charset=utf-8")
        if path in STATIC:
            name, content_type = STATIC[path]
            try:
                with open(os.path.join(root, "pwa", name), "rb") as f:
                    body = f.read()
            except OSError:
                return self._text(404, "Not found")
            return self._send(200, body, content_type)
        if path == "/status.json":
            return self._serve_status(status_path(root))
        if path == "/state.json":
            return self._json(read_state(state_path(root)))
        if path == "/config.json":
            return self._json(read_config(root))
        if path == "/health":
            return self._json({"ok": True})
        return self._text(404, "Not found")

    def _serve_status(self, path):
        try:
            with open(path, "rb") as f:
                body = f.read()
        except FileNotFoundError:
            return self._json(_error_status("The scanner hasn't written any status yet. Run python3 scanner.py."))
        except OSError:
            return self._json(_error_status("The status file can't be read. Run python3 scanner.py again."))
        try:
            data = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, RecursionError):
            data = None
        if not isinstance(data, dict):
            return self._json(_error_status("The status file can't be read. Run python3 scanner.py again."))
        if not _expected_shape(data):
            return self._json(_error_status("The status file has an unexpected format. "
                                            "Run python3 scanner.py again, or update the dashboard."))
        return self._send(200, body, "application/json; charset=utf-8")

    def do_POST(self):
        if not self._host_ok():
            return self._text(403, "Forbidden")
        route = urlsplit(self.path).path
        if route not in ("/state", "/reply"):
            return self._text(404, "Not found")
        # Only the page itself may write: same origin as the Host it came through.
        if self.headers.get("Origin") != "http://" + self.headers.get("Host"):
            return self._text(403, "Forbidden")
        # A JSON content type forces a CORS preflight, which is never answered: cross-site forms can't post.
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            return self._text(415, "Unsupported media type")
        length = self.headers.get("Content-Length")
        if length is None:
            return self._text(411, "Length required")
        try:
            size = int(length)
        except ValueError:
            return self._text(400, "Bad Content-Length")
        if size < 0:
            return self._text(400, "Bad Content-Length")
        if size > (MAX_REPLY_BODY if route == "/reply" else MAX_BODY):
            return self._text(413, "Body too large")
        raw = self.rfile.read(size)
        try:
            body = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, RecursionError):   # deep nesting raises on Python 3.9
            return self._text(400, "The body must be JSON")
        if route == "/reply":
            return self._reply(body)
        path = state_path(self.server.root)
        with self.server.state_lock:          # the server is the only writer; one lock is enough
            now = _now()
            try:
                state = apply_action(read_state(path), body, now)
            except ValueError as e:
                return self._text(400, str(e))
            state = prune(state, now)
            write_state(state, path)
        return self._json(state)

    def _reply(self, body):
        # Off unless config.json turns it on: typing into another app needs the user's say-so.
        if not read_config(self.server.root)["replyEnabled"]:
            return self._text(403, 'Replying from the dashboard is off. Set "replyEnabled": true in config.local.json '
                                   "and reload the page. Nothing was typed.")
        try:
            sid, text = clean_reply(body)
        except ValueError as e:
            return self._text(400, str(e))
        listed = listed_sessions(status_path(self.server.root))
        if listed is None:
            return self._text(503, "The dashboard has no current scan, so it can't check the session. "
                                   "Nothing was typed.")
        if sid not in listed:
            return self._text(404, "That session isn't on the dashboard any more. Nothing was typed.")
        # One send at a time: two at once would type into each other.
        if not self.server.reply_lock.acquire(blocking=False):
            return self._text(409, "Another reply is being typed. Try again in a moment.")
        try:
            self.server.reply_sender(sid, text)
        except ReplyError as e:
            return self._text(503, str(e))
        finally:
            self.server.reply_lock.release()
        return self._json({"ok": True})

    def _not_allowed(self):
        if not self._host_ok():
            return self._text(403, "Forbidden")
        self._text(405, "Method not allowed")

    # Every other method goes through the same guards and headers (HEAD and OPTIONS included).
    do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = _not_allowed


class Server(ThreadingHTTPServer):
    request_queue_size = 64                 # the default 5 resets connections when requests arrive together
    daemon_threads = True


def make_server(root, port):
    httpd = Server((HOST, port), Handler)
    httpd.daemon_threads = True
    httpd.root = root
    httpd.state_lock = threading.Lock()
    httpd.reply_lock = threading.Lock()
    httpd.reply_sender = type_into_claude     # tests replace it: no test ever types into the app
    return httpd


def main(argv=None):
    ap = argparse.ArgumentParser(description="Serve the dashboard on 127.0.0.1 only.")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--root", default=HERE)
    args = ap.parse_args(argv)
    httpd = make_server(args.root, args.port)
    print("Sessionbell: http://%s:%d" % (HOST, args.port), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
