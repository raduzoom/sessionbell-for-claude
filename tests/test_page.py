"""Static safety checks on index.html (handoff §9, §15). The page's behaviour is checked in a browser on
made-up snapshots; these tests guard the rules that must never regress."""
from __future__ import annotations

import os
import re
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def page():
    with open(os.path.join(HERE, "index.html"), encoding="utf-8") as f:
        return f.read()


def script_and_markup():
    """The page without its CSS, so a CSS comment can't hide or fake a finding."""
    return re.sub(r"<style>.*?</style>", "", page(), flags=re.S)


class PageTests(unittest.TestCase):
    def test_no_html_injection_sinks(self):
        text = script_and_markup()
        for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function",
                     "setTimeout('", 'setTimeout("', "srcdoc"):
            self.assertNotIn(sink, text, sink)

    def test_no_outside_urls(self):
        urls = re.findall(r"(?:https?:)?//[A-Za-z0-9.-]+\.[A-Za-z]{2,}[^\s'\"<>)]*", page())
        # The SVG namespace is an identifier, not a request.
        self.assertEqual([u for u in urls if u != "http://www.w3.org/2000/svg"], [])
        for tag in ("<script src", "@import", "url(http", "<iframe", "<img src=\"http"):
            self.assertNotIn(tag, page(), tag)
        # The only <link>s are the installed app's own files, served by server.py from pwa/.
        links = re.findall(r"<link\b[^>]*>", page())
        self.assertEqual(sorted(re.search(r'href="([^"]*)"', l).group(1) for l in links),
                         ["/apple-touch-icon.png", "/icon.svg", "/manifest.webmanifest"])

    def test_pwa_hooks(self):
        text = script_and_markup()
        self.assertIn("navigator.serviceWorker.register('/sw.js')", text)
        self.assertIn("navigator.setAppBadge", text)
        # Snapshots (made-up data) must never register the worker or set the Dock badge.
        self.assertIn("var live = typeof window.__STATUS_SOURCE__ !== 'function';", text)

    def test_snapshot_hook_present(self):
        self.assertIn("window.__STATUS_SOURCE__", page())

    def test_link_pattern_present(self):
        self.assertIn(r"/^claude:\/\/claude\.ai\/epitaxy\/local_[A-Za-z0-9_-]{1,80}$/", page())

    def test_new_session_link(self):
        # Added 2026-11-16: the picker's links open the Claude app's new-session screen, the folder URL-encoded.
        text = script_and_markup()
        self.assertIn("var NEW_LINK = 'claude://code/new';", text)
        self.assertIn("NEW_LINK + '?folder=' + encodeURIComponent(folder)", text)
        self.assertIn("folders: list(d.folders).filter(goodFolder)", text)

    def test_status_fetched_same_origin(self):
        self.assertIn("fetch('/status.json'", page())

    def test_approved_copy_present(self):
        text = page()
        for copy in ("Sessionbell", "Needs you", "Stale: archive or revive?", "Quieter", "Hidden",
                     "Open session", "Opening…", "Show all projects", "more need you in other projects",
                     "Scanned ", " session files", "Scanner hasn't run for ", "Last scan ",
                     "Turn started but never finished: may be a permission prompt or a slow tool.",
                     "waiting ", "Nothing needs you right now", "Checked ", "Can't show sessions right now",
                     "All projects", "coming soon", "General", "No sessions to show",
                     "No counts while the scan is failing", "The session asked", "Needs from you", "Summary",
                     "Send reply", "Sending…", "Reply to Claude…", "Reply sent to the session",
                     "Enter sends, Shift+Enter adds a line. Claude comes to the front for a moment to type it. To type, python3 must be turned on in System Settings under Device Control and Data Access.",
                     "Dismissed until it changes", "Snoozed until ",
                     "Working", "In progress", "Quiet for ", ": may be a permission prompt or a slow tool."):
            self.assertIn(copy, text, copy)

    def test_phase4_actions_present(self):
        text = script_and_markup()
        for label in ("More actions", "Show again", "Undo", "'Snooze 1 hour (back at '", "'Snooze until tomorrow 9:00'",
                      "'Dismiss'", "'Dismissed until it changes'", "'Snoozed until '", "Couldn't save. Try again."):
            self.assertIn(label, text, label)

    def test_writes_are_same_origin_json_posts(self):
        text = script_and_markup()
        self.assertIn("fetch(path, {", text)
        self.assertIn("postJSON('/state', body)", text)
        self.assertIn("postJSON('/reply', body)", text)
        self.assertIn("method: 'POST'", text)
        self.assertIn("'Content-Type': 'application/json'", text)
        self.assertIn("credentials: 'same-origin'", text)
        self.assertEqual(text.count("method: 'POST'"), 1)          # one place writes

    def test_reads_state_and_applies_the_scanner_rule(self):
        text = script_and_markup()
        self.assertIn("fetch('/state.json'", text)
        self.assertIn("SNOOZE_MAX_MS = 8 * 24 * 60 * 60 * 1000", text)
        self.assertIn("function hiddenBy(", text)

    def test_state_hook_present(self):
        self.assertIn("window.__STATE_SINK__", script_and_markup())

    def test_polls_in_the_background(self):
        # Review finding (critical): the tab title must keep updating while the tab is hidden.
        text = script_and_markup()
        timer = re.search(r"setInterval\((.*?)POLL_MS\)", text, re.S)
        self.assertIsNotNone(timer)
        self.assertNotIn("document.hidden", timer.group(1))

    def test_late_and_error_titles_are_alarms(self):
        text = script_and_markup()
        self.assertRegex(text, r"err \|\| late\) \? '\(!\) Sessionbell'")

    def test_status_shape_is_checked(self):
        text = script_and_markup()
        self.assertIn("d.schema !== 1", text)
        self.assertIn("unexpected format", text)

    def test_hash_decoding_cannot_throw(self):
        text = script_and_markup()
        self.assertEqual(text.count("decodeURIComponent("), 1)    # only inside the safe wrapper
        self.assertRegex(text, r"function decode\(s\) \{ try \{ return decodeURIComponent\(s\);")

    def test_stale_answers_are_ignored(self):
        self.assertIn("seq !== loadSeq", script_and_markup())

    def test_reduced_motion_and_transparency(self):
        text = page()
        self.assertIn("prefers-reduced-motion", text)
        self.assertIn("prefers-reduced-transparency", text)
        self.assertIn("backdrop-filter", text)


    def test_reply_bar(self):
        text = script_and_markup()
        # Open session moved into the header, outlined: Send reply is the one filled button.
        self.assertIn("var openCls = 'btn ' + (S.replyOn ? 'btn-secondary' : 'btn-primary') + ' btn-sm d-open';", text)
        # Off by default: the live page shows it only when /config.json says replyEnabled is true.
        self.assertIn("replyOn: typeof window.__STATUS_SOURCE__ === 'function' && opts.reply !== false", text)
        self.assertIn("if (c && c.replyEnabled === true && !S.replyOn)", text)
        self.assertIn("!S.replyOn ? null : h('div', { class: 'reply' }", text)
        self.assertEqual(text.count("class: 'btn btn-primary"), 2)        # Send reply and its loading state
        self.assertIn("maxlength: 4000", text)                          # server.MAX_REPLY_CHARS
        self.assertIn("if (e.key !== 'Enter' || e.shiftKey || e.isComposing", text)
        self.assertIn("if (S.composing) { S.renderLater = true; return; }", text)
        # The draft lives in page state, so the 30 s re-render can't lose it.
        self.assertIn("S.drafts[card.sessionId] = el.value;", text)

if __name__ == "__main__":
    unittest.main()
