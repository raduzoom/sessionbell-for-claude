"""Tests for scanner.py. All data is made up; no real session file is ever copied here.

Run from the project folder:  python3 -B -m unittest -v
"""
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

def setUpModule():
    # No test may ever show a real banner: replace the sender for this whole module.
    global _real_sender
    _real_sender = getattr(scanner, "_osascript", None)
    scanner._osascript = lambda title, body: None


def tearDownModule():
    if _real_sender is not None:
        scanner._osascript = _real_sender


NOW = 1_800_000_000_000
MIN = 60_000
HOUR = 60 * MIN
DAY = 24 * HOUR

MENU = [
    {"id": "client-a", "name": "Client A", "children": [
        {"id": "client-a/us", "name": "Client A US"},
        {"id": "client-a/canada", "name": "Client A Canada"}]},
    {"id": "client-b", "name": "Client B", "comingSoon": True, "children": []},
    {"id": "tools", "name": "Internal Tools", "children": []},
    {"id": "other", "name": "Other", "children": []},
]
RULES = [
    {"folder": "/work/client-a-bot", "project": "client-a", "subproject": "client-a/us"},
    {"folder": "/work/client-a-bot-canada", "project": "client-a", "subproject": "client-a/canada"},
    {"folder": "/work/tools", "project": "tools", "subproject": None},
    {"folder": "/work/tools/deep", "project": "client-a", "subproject": None},
]


def config(rules=None):
    return {"projects": MENU, "default": "other", "rules": RULES if rules is None else rules}


def session(sid="local_a", title="A session", last=NOW - 10 * MIN, focused=None, cwd="/work/tools",
            **extra):
    s = {"sessionId": sid, "title": title, "lastActivityAt": last,
         "lastFocusedAt": last if focused is None else focused, "cwd": cwd, "isArchived": False}
    s.update(extra)
    return s


def asked(sid="local_asked", question="Ship it?", **kw):
    return session(sid, turnWrapUp={"needsUser": question, "description": "d"},
                   postTurnSummary={"status_category": "completed", "needs_action": "", "status_detail": ""},
                   **kw)


def blocked(sid="local_blocked", needs="Sign in again", **kw):
    return session(sid, postTurnSummary={"status_category": "blocked", "needs_action": needs,
                                         "status_detail": "detail"}, **kw)


def summary(category, sid, **kw):
    return session(sid, postTurnSummary={"status_category": category, "needs_action": "",
                                         "status_detail": "Done"}, **kw)


class TempDir(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="scanner-test-")
        self.addCleanup(shutil.rmtree, self.dir)

    def path(self, *parts):
        return os.path.join(self.dir, *parts)

    def write(self, rel, content):
        p = self.path(rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content if isinstance(content, str) else json.dumps(content))
        return p

    def write_session(self, s, acct="acct", org="org"):
        return self.write(os.path.join("sessions", acct, org, s["sessionId"] + ".json"), s)


# 1. projects.json ---------------------------------------------------------------------------

class ProjectsTests(TempDir):
    def projects_file(self, data):
        return self.write("projects.json", data)

    def test_valid_file(self):
        p = self.projects_file({"projects": MENU, "default": "other", "rules": [
            {"folder": "~/work/client-a-bot", "project": "client-a", "subproject": "client-a/us"}]})
        cfg, err = scanner.load_projects(p)
        self.assertIsNone(err)
        self.assertEqual(cfg["default"], "other")
        self.assertEqual(cfg["projects"], MENU)
        self.assertEqual(cfg["rules"][0]["folder"], os.path.expanduser("~/work/client-a-bot"))

    def test_missing_file(self):
        cfg, err = scanner.load_projects(self.path("nope.json"))
        self.assertIsNone(cfg)
        self.assertTrue(err.startswith("projects.json: "))

    def test_bad_json(self):
        cfg, err = scanner.load_projects(self.projects_file("{ not json"))
        self.assertIsNone(cfg)
        self.assertTrue(err.startswith("projects.json: "))

    def test_rule_names_unknown_project(self):
        p = self.projects_file({"projects": MENU, "default": "other", "rules": [
            {"folder": "~/work/client-d-bot", "project": "client-d", "subproject": None}]})
        cfg, err = scanner.load_projects(p)
        self.assertIsNone(cfg)
        self.assertEqual(err, 'projects.json: the rule for ~/work/client-d-bot names an unknown project "client-d".')

    def test_subproject_under_wrong_parent(self):
        p = self.projects_file({"projects": MENU, "default": "other", "rules": [
            {"folder": "~/work/x", "project": "tools", "subproject": "client-a/us"}]})
        cfg, err = scanner.load_projects(p)
        self.assertIsNone(cfg)
        self.assertTrue(err.startswith("projects.json: the rule for ~/work/x "))
        self.assertIn('"client-a/us"', err)

    def test_default_names_unknown_project(self):
        cfg, err = scanner.load_projects(self.projects_file({"projects": MENU, "default": "nobody", "rules": []}))
        self.assertIsNone(cfg)
        self.assertIn('"nobody"', err)

    def test_wrong_shape(self):
        cfg, err = scanner.load_projects(self.projects_file({"projects": "x", "default": "other", "rules": []}))
        self.assertIsNone(cfg)
        self.assertTrue(err.startswith("projects.json: "))

    def test_non_text_project_or_subproject_is_an_error_not_a_crash(self):
        # Review finding Important 1: these used to raise TypeError and leave the old calm status.
        for rule in ({"folder": "~/w", "project": ["tools"], "subproject": None},
                     {"folder": "~/w", "project": "client-a", "subproject": {"id": "client-a/us"}}):
            cfg, err = scanner.load_projects(self.projects_file({"projects": MENU, "default": "other",
                                                                 "rules": [rule]}))
            self.assertIsNone(cfg)
            self.assertTrue(err.startswith("projects.json: the rule for ~/w "), err)

    def test_two_rules_for_the_same_folder(self):
        p = self.projects_file({"projects": MENU, "default": "other", "rules": [
            {"folder": "/w/a", "project": "tools", "subproject": None},
            {"folder": "/w/a/", "project": "other", "subproject": None}]})
        cfg, err = scanner.load_projects(p)
        self.assertIsNone(cfg)
        self.assertIn("/w/a", err)


# 2. Folder to project -----------------------------------------------------------------------

class FolderTests(unittest.TestCase):
    def test_exact_folder(self):
        self.assertEqual(scanner.project_for("/work/tools", RULES, "other"), ("tools", None, "tools"))

    def test_subfolder(self):
        self.assertEqual(scanner.project_for("/work/client-a-bot/src", RULES, "other"),
                         ("client-a", "client-a/us", "src"))

    def test_worktree_inherits_repo(self):
        got = scanner.project_for("/work/client-a-bot/.claude/worktrees/fix-123", RULES, "other")
        self.assertEqual(got, ("client-a", "client-a/us", "client-a-bot (worktree)"))

    def test_lookalike_prefix_does_not_match(self):
        self.assertEqual(scanner.project_for("/work/tools-old", RULES, "other"), ("other", None, "tools-old"))

    def test_longest_rule_wins(self):
        self.assertEqual(scanner.project_for("/work/tools/deep/x", RULES, "other")[:2], ("client-a", None))
        self.assertEqual(scanner.project_for("/work/client-a-bot-canada", RULES, "other")[:2],
                         ("client-a", "client-a/canada"))

    def test_no_match_goes_to_default(self):
        self.assertEqual(scanner.project_for("/elsewhere/repo", RULES, "other"), ("other", None, "repo"))

    def test_missing_cwd_goes_to_default(self):
        self.assertEqual(scanner.project_for("", RULES, "other")[:2], ("other", None))


# 3. Reading and health ----------------------------------------------------------------------

class HealthTests(TempDir):
    def read(self):
        return scanner.read_sessions(self.path("sessions"))

    def test_empty_folder(self):
        os.makedirs(self.path("sessions"))
        sessions, problems, total = self.read()
        self.assertEqual((sessions, problems, total), ([], 0, 0))
        self.assertIn("No session files found", scanner.health_error(sessions, problems, total))

    def test_missing_folder_reads_as_empty(self):
        self.assertEqual(self.read(), ([], 0, 0))

    def test_all_unreadable(self):
        for i in range(3):
            self.write("sessions/acct/org/local_%d.json" % i, "garbage")
        sessions, problems, total = self.read()
        self.assertEqual((len(sessions), problems, total), (0, 3, 3))
        self.assertEqual(scanner.health_error(sessions, problems, total),
                         "Can't read session status, format may have changed (3 of 3 files unreadable).")

    def test_ten_percent_is_ok(self):
        for i in range(9):
            self.write_session(blocked("local_%d" % i))
        self.write("sessions/acct/org/local_bad.json", "garbage")
        self.assertIsNone(scanner.health_error(*self.read()))

    def test_over_ten_percent_fails(self):
        for i in range(8):
            self.write_session(blocked("local_%d" % i))
        self.write("sessions/acct/org/local_bad1.json", "garbage")
        self.write("sessions/acct/org/local_bad2.json", "garbage")
        self.assertIn("2 of 10 files unreadable", scanner.health_error(*self.read()))

    def test_missing_required_field_counts_as_problem(self):
        s = blocked("local_x")
        del s["title"]
        self.write_session(s)
        t = blocked("local_y")
        t["lastActivityAt"] = "yesterday"
        self.write_session(t)
        self.write_session(blocked("local_z"))
        sessions, problems, total = self.read()
        self.assertEqual((len(sessions), problems, total), (1, 2, 3))

    def test_non_text_scheduled_task_id_is_a_problem(self):
        # Review finding Important 2: a dict id used to crash collapse_scheduled.
        self.write_session(blocked("local_x", scheduledTaskId={"id": "task-1"}))
        self.write_session(blocked("local_y", scheduledTaskId="task-2"))
        self.write_session(blocked("local_z"))
        sessions, problems, total = self.read()
        self.assertEqual((sorted(s["sessionId"] for s in sessions), problems, total),
                         (["local_y", "local_z"], 1, 3))

    def test_no_status_fields(self):
        for i in range(3):
            self.write_session(session("local_%d" % i))
        self.assertEqual(scanner.health_error(*self.read()),
                         "Can't read session status, format may have changed (no file has a status field).")

    def test_scans_every_account_and_org(self):
        self.write_session(blocked("local_1"), "acct1", "org1")
        self.write_session(blocked("local_2"), "acct1", "org2")
        self.write_session(blocked("local_3"), "acct2", "org1")
        self.write("sessions/acct1/org1/notes.json", "{}")
        sessions, problems, total = self.read()
        self.assertEqual(sorted(s["sessionId"] for s in sessions), ["local_1", "local_2", "local_3"])
        self.assertEqual((problems, total), (0, 3))


# 4. Classify --------------------------------------------------------------------------------

class FolderListTests(unittest.TestCase):
    """The New session picker's folders (added 2026-11-16)."""

    def folders(self, sessions, exists=lambda f: True, home="/Users/you"):
        return scanner.folder_list(sessions, config(), exists=exists, home=home)

    def test_newest_use_first_then_unused_rule_folders(self):
        got = self.folders([session("local_1", cwd="/work/tools", last=NOW - HOUR),
                            session("local_2", cwd="/work/client-a-bot/.claude/worktrees/fix", last=NOW - MIN),
                            session("local_3", cwd="/work/tools", last=NOW - DAY)])
        self.assertEqual([f["folder"] for f in got],
                         ["/work/client-a-bot", "/work/tools", "/work/client-a-bot-canada", "/work/tools/deep"])
        self.assertEqual(got[0], {"folder": "/work/client-a-bot", "name": "client-a-bot", "path": "/work/client-a-bot",
                                  "project": "client-a", "subproject": "client-a/us", "lastUsedAt": NOW - MIN})
        self.assertEqual(got[1]["lastUsedAt"], NOW - HOUR)      # a folder's newest session counts
        self.assertIsNone(got[2]["lastUsedAt"])

    def test_archived_sessions_count(self):
        got = self.folders([session("local_1", cwd="/work/old-thing", isArchived=True)])
        self.assertEqual(got[0]["folder"], "/work/old-thing")
        self.assertEqual(got[0]["project"], "other")

    def test_home_is_shortened(self):
        got = self.folders([session("local_1", cwd="/Users/you/code/app")])
        self.assertEqual(got[0]["path"], "~/code/app")
        self.assertEqual(self.folders([session("local_1", cwd="/Users/younger/app")])[0]["path"], "/Users/younger/app")

    def test_missing_temporary_and_odd_folders_left_out(self):
        sessions = [session("local_%d" % i, cwd=c) for i, c in enumerate(
            ["/private/tmp/x", "/tmp", "/var/folders/ab/T/x", "relative/path", "/", "", None, 42, "/work/gone"])]
        got = self.folders(sessions, exists=lambda f: f != "/work/gone")
        self.assertEqual([f["folder"] for f in got], [r["folder"] for r in RULES])

    def test_capped(self):
        sessions = [session("local_%d" % i, cwd="/work/f%d" % i, last=NOW - i) for i in range(250)]
        got = self.folders(sessions)
        self.assertEqual(len(got), scanner.MAX_FOLDERS)
        self.assertEqual(got[0]["folder"], "/work/f0")

    def test_status_has_folders(self):
        status = scanner.build_status([asked(), blocked()], 0, 2, config(), {}, NOW)
        self.assertIsInstance(status["folders"], list)


class ClassifyTests(unittest.TestCase):
    def test_asked(self):
        self.assertEqual(scanner.classify(asked(), NOW), "asked")

    def test_blocked(self):
        self.assertEqual(scanner.classify(blocked(), NOW), "blocked")

    def test_review_ready(self):
        self.assertEqual(scanner.classify(summary("review_ready", "local_r"), NOW), "review_ready")

    def test_btw_session_is_never_blocked(self):
        # A btw fork carries its parent's history; the app's summary can pick up the parent's blocked
        # request although the btw turn only answered your question (seen 2026-11-12).
        s = blocked("local_btw", needs="Stop the parent's server", btwLoweredFrom="local_parent")
        self.assertEqual(scanner.classify(s, NOW), "review_ready")
        self.assertEqual(scanner.needs_text(s), "detail")

    def test_btw_session_can_still_ask(self):
        s = asked("local_btw", btwLoweredFrom="local_parent")
        self.assertEqual(scanner.classify(s, NOW), "asked")

    def test_unread(self):
        s = summary("completed", "local_u", last=NOW - HOUR, focused=NOW - 2 * HOUR)
        self.assertEqual(scanner.classify(s, NOW), "unread")

    def test_finished_and_seen_is_none(self):
        self.assertIsNone(scanner.classify(summary("completed", "local_c"), NOW))

    def test_stuck_after_thirty_quiet_minutes(self):
        s = session("local_s", last=NOW - 31 * MIN, lastTurnEdgeAt=NOW - 40 * MIN)
        self.assertEqual(scanner.classify(s, NOW), "stuck")

    def test_running_now_is_working(self):
        s = session("local_s", last=NOW - 2 * MIN, lastTurnEdgeAt=NOW - 3 * MIN)
        self.assertEqual(scanner.classify(s, NOW), "working")

    def test_long_tool_call_is_still_working(self):
        # Your example: a session quiet for 15 minutes during a long tool call was flagged stuck.
        s = session("local_s", last=NOW - 15 * MIN, lastTurnEdgeAt=NOW - 27 * MIN)
        self.assertEqual(scanner.classify(s, NOW), "working")

    def test_old_session_without_edge_is_never_stuck(self):
        s = session("local_old", last=NOW - 30 * DAY, focused=NOW - 30 * DAY, latestUserFrameAt=NOW - 30 * DAY)
        self.assertIsNone(scanner.classify(s, NOW))

    def test_edge_with_summary_is_finished(self):
        s = summary("completed", "local_f", last=NOW - DAY, lastTurnEdgeAt=NOW - DAY - MIN)
        self.assertIsNone(scanner.classify(s, NOW))

    def test_needs_text_order(self):
        self.assertEqual(scanner.needs_text(asked(question="Q?")), "Q?")
        self.assertEqual(scanner.needs_text(blocked(needs="Do X")), "Do X")
        s = blocked(needs="")
        self.assertEqual(scanner.needs_text(s), "detail")
        s = session("local_d", turnWrapUp={"description": "Desc"})
        self.assertEqual(scanner.needs_text(s), "Desc")
        self.assertEqual(scanner.needs_text(session("local_e")), "")


# 4b. The question from the transcript (the app no longer saves turnWrapUp.needsUser) ------------

CLI_ID = "0f0e0d0c-0b0a-4908-8706-050403020100"


def wrap_entry(ask=None, sidechain=False, kind="assistant", name="mcp__ccd_turn__wrap_up"):
    inp = {"recap": "Made-up recap."}
    if ask is not None:
        inp["ask"] = ask
    return {"type": kind, "isSidechain": sidechain,
            "message": {"role": "assistant", "content": [{"type": "tool_use", "name": name, "input": inp}]}}


def tool_result():
    return {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]}}


def prompt(text="Made-up reply", meta=False):
    e = {"type": "user", "message": {"role": "user", "content": text}}
    if meta:
        e["isMeta"] = True
    return e


def closing():
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Done."}]}}


def asked_in_transcript(sid="local_t", **kw):
    """A finished turn as the app saves it today: wrap-up with a description only."""
    return session(sid, cliSessionId=CLI_ID, turnWrapUp={"description": "Made-up recap."},
                   postTurnSummary={"status_category": "completed", "needs_action": "", "status_detail": ""},
                   lastTurnEdgeAt=NOW - 20 * MIN, **kw)


class TranscriptAskTests(TempDir):
    def transcript(self, entries, folder="-work-tools", cli_id=CLI_ID, prefix=""):
        lines = [json.dumps(e) for e in entries]
        return self.write(os.path.join("projects", folder, cli_id + ".jsonl"), prefix + "\n".join(lines) + "\n")

    def ask(self, cli_id=CLI_ID):
        return scanner.transcript_ask(cli_id, self.path("projects"))

    def test_latest_wrap_up_question(self):
        self.transcript([prompt(), wrap_entry(ask="  Ship it?  "), tool_result(), closing()])
        self.assertEqual(self.ask(), "Ship it?")

    def test_answered_question_is_gone(self):
        self.transcript([wrap_entry(ask="Ship it?"), tool_result(), closing(), prompt("Yes")])
        self.assertEqual(self.ask(), "")

    def test_later_wrap_up_without_question_wins(self):
        self.transcript([wrap_entry(ask="Ship it?"), tool_result(), prompt("Yes"), wrap_entry(), tool_result()])
        self.assertEqual(self.ask(), "")

    def test_meta_and_tool_results_are_not_replies(self):
        self.transcript([wrap_entry(ask="Ship it?"), tool_result(), prompt("reminder", meta=True), closing()])
        self.assertEqual(self.ask(), "Ship it?")

    def test_subagent_and_replayed_entries_are_ignored(self):
        self.transcript([wrap_entry(ask="Old?"), tool_result(), prompt("Yes"), wrap_entry(),
                         wrap_entry(ask="Subagent?", sidechain=True), wrap_entry(ask="Replay?", kind="api-request-blob"),
                         wrap_entry(ask="Other tool?", name="mcp__other__ask")])
        self.assertEqual(self.ask(), "")

    def test_finds_the_transcript_in_any_project_folder(self):
        self.transcript([wrap_entry(ask="Ship it?")], folder="-some-other-folder")
        self.assertEqual(self.ask(), "Ship it?")

    def test_reads_only_the_tail(self):
        # An old unanswered question beyond the tail must not count; a broken first line is skipped.
        self.transcript([wrap_entry(ask="Old?")] + [closing()] * 10, prefix="x" * 50 + "\n")
        size = os.path.getsize(self.path("projects", "-work-tools", CLI_ID + ".jsonl"))
        old_tail = scanner.TRANSCRIPT_TAIL
        scanner.TRANSCRIPT_TAIL = size - 60            # cuts inside the first wrap-up line
        try:
            self.assertEqual(self.ask(), "")
        finally:
            scanner.TRANSCRIPT_TAIL = old_tail

    def test_bad_lines_and_shapes_are_skipped(self):
        self.write(os.path.join("projects", "-work-tools", CLI_ID + ".jsonl"),
                   "not json\n[1]\n" + json.dumps({"type": "assistant", "message": {"content": "text"}}) + "\n"
                   + json.dumps(wrap_entry(ask=5)) + "\n" + json.dumps(wrap_entry(ask="Ship it?")) + "\n")
        self.assertEqual(self.ask(), "Ship it?")

    def test_missing_or_unsafe_id_reads_nothing(self):
        self.transcript([wrap_entry(ask="Ship it?")])
        for bad in (None, 5, "", "../" + CLI_ID, "*", "a/b"):
            self.assertEqual(self.ask(bad), "")
        self.assertEqual(scanner.transcript_ask(CLI_ID, self.path("nowhere")), "")

    def test_attach_marks_only_finished_turns_with_a_wrap_up(self):
        self.transcript([wrap_entry(ask="Ship it?")])
        done = asked_in_transcript("local_done")
        running = session("local_run", cliSessionId=CLI_ID, lastTurnEdgeAt=NOW - MIN)
        archived = asked_in_transcript("local_arch", isArchived=True)
        scanner.attach_asks([done, running, archived], self.path("projects"))
        self.assertEqual(done.get("askFromTranscript"), "Ship it?")
        self.assertNotIn("askFromTranscript", running)
        self.assertNotIn("askFromTranscript", archived)

    def test_question_from_transcript_is_asked_and_is_the_needs_line(self):
        s = asked_in_transcript(askFromTranscript="Ship it?")
        self.assertEqual(scanner.classify(s, NOW), "asked")
        self.assertEqual(scanner.needs_text(s), "Ship it?")
        self.assertIsNone(scanner.classify(asked_in_transcript(), NOW))



def plan_entry(**call):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "name": "mcp__ccd_turn__update_plan", "input": call}]}}


class TranscriptDoingTests(TempDir):
    def doing(self, entries):
        lines = "\n".join(json.dumps(e) for e in entries) + "\n"
        self.write(os.path.join("projects", "-work-tools", CLI_ID + ".jsonl"), lines)
        return scanner.transcript_doing(CLI_ID, self.path("projects"))

    def plan(self, *statuses):
        return plan_entry(items=[{"content": "Step %d" % (n + 1), "status": st} for n, st in enumerate(statuses)])

    def test_step_in_progress(self):
        self.assertEqual(self.doing([prompt("Fix the thing"), self.plan("completed", "in_progress", "pending")]), "Step 2")

    def test_advance_and_done_replay(self):
        entries = [prompt(), self.plan("in_progress", "pending", "pending"), plan_entry(advance=True)]
        self.assertEqual(self.doing(entries), "Step 2")
        self.assertEqual(self.doing(entries + [plan_entry(done=[2], start=3)]), "Step 3")

    def test_todowrite_uses_active_form(self):
        todo = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "TodoWrite", "input": {
            "todos": [{"content": "Run tests", "activeForm": "Running tests", "status": "in_progress"}]}}]}}
        self.assertEqual(self.doing([prompt(), todo]), "Running tests")

    def test_falls_back_to_the_typed_message(self):
        self.assertEqual(self.doing([prompt("Fix the thing\nwith more words"), prompt("<system-reminder>x", meta=False),
                                     self.plan("completed", "completed")]), "Fix the thing")

    def test_long_text_is_cut_and_subagent_ignored(self):
        side = dict(plan_entry(items=[{"content": "Sub step", "status": "in_progress"}]), isSidechain=True)
        out = self.doing([prompt("w " * 200), side])
        self.assertEqual(len(out), scanner.DOING_MAX)
        self.assertTrue(out.endswith("…"))

    def test_plan_list_beyond_the_first_tail_is_found(self):
        # Found 2026-11-15: image reads push the plan list megabytes back; only "advance" is near the end.
        filler = dict(closing(), pad="x" * 300)
        entries = [prompt("Fix the thing"), self.plan("in_progress", "pending", "pending")] + [filler] * 10 + [plan_entry(advance=True)]
        old = scanner.DOING_TAILS
        scanner.DOING_TAILS = (200, 2000, 1_000_000)
        try:
            self.assertEqual(self.doing(entries), "Step 2")
        finally:
            scanner.DOING_TAILS = old

    def test_plan_list_beyond_the_last_tail_is_not_read(self):
        filler = dict(closing(), pad="x" * 300)
        entries = [self.plan("in_progress", "pending")] + [filler] * 10 + [prompt("Now this"), plan_entry(advance=True)]
        old = scanner.DOING_TAILS
        scanner.DOING_TAILS = (200, 1000)
        try:
            self.assertEqual(self.doing(entries), "Now this")
        finally:
            scanner.DOING_TAILS = old

    def test_big_lines_are_skipped_only_past_the_first_tail(self):
        # A huge typed message (a pasted image) still counts in the first step; further back only plan lines do.
        big = prompt("Big message " + "x" * 400)
        old = (scanner.DOING_TAILS, scanner.BIG_LINE)
        scanner.BIG_LINE = 300
        try:
            scanner.DOING_TAILS = (1_000_000,)
            self.assertTrue(self.doing([big]).startswith("Big message"))
            scanner.DOING_TAILS = (100, 1_000_000)
            self.assertEqual(self.doing([big, closing(), closing()]), "")
            plan = plan_entry(items=[{"content": "Long step " + "y" * 400, "status": "in_progress"}])
            self.assertTrue(self.doing([plan, closing(), closing()]).startswith("Long step"))
        finally:
            scanner.DOING_TAILS, scanner.BIG_LINE = old

    def test_nothing_to_show(self):
        self.assertEqual(self.doing([closing()]), "")
        self.assertEqual(scanner.transcript_doing(None, self.path("projects")), "")


class SubagentTests(TempDir):
    """A turn that ended while its background subagents keep running is still working (seen 2026-11-13)."""

    def agent(self, name, finished, written, cli_id=CLI_ID, folder="-work-tools", started=None, lines="{}\n"):
        base = os.path.join("projects", folder, cli_id, "subagents", "agent-" + name)
        meta = {"agentType": "general-purpose", "finished": True} if finished else {"agentType": "general-purpose"}
        started = written if started is None else started
        meta_path = self.write(base + ".meta.json", json.dumps(meta))
        os.utime(meta_path, (started / 1000, started / 1000))
        jsonl = self.write(base + ".jsonl", lines)
        os.utime(jsonl, (written / 1000, written / 1000))

    def activity(self, cli_id=CLI_ID):
        return scanner.subagent_activity(cli_id, self.path("projects"), NOW)

    def test_old_agent_with_a_freshly_touched_transcript_is_ignored(self):
        # Seen 2026-11-16: 39-day-old subagent transcripts, never marked finished, had their file time bumped
        # by something else, which made two long-done sessions show as Working.
        self.agent("old", finished=False, written=NOW - MIN, started=NOW - 39 * DAY)
        self.assertIsNone(self.activity())
        self.agent("new", finished=False, written=NOW - 2 * MIN, started=NOW - 3 * HOUR)
        self.assertAlmostEqual(self.activity(), NOW - 2 * MIN, delta=1000)

    def test_stopped_agent_is_ignored(self):
        # Seen 2026-11-21: TaskStop ends a subagent without writing finished: true; its transcript ends with
        # the interrupt marker, and the session showed as Working for 30 minutes after its turn ended.
        work = json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "WebSearch"}]}})
        for i, content in enumerate(("[Request interrupted by user]",
                                     [{"type": "text", "text": "[Request interrupted by user for tool use]"}])):
            stop = json.dumps({"type": "user", "message": {"role": "user", "content": content}})
            self.agent("s%d" % i, finished=False, written=NOW - MIN, lines=work + "\n" + stop + "\n")
        self.assertIsNone(self.activity())
        # An agent that's still going (last entry is its own work, or a plain user message) still counts.
        self.agent("live", finished=False, written=NOW - 2 * MIN, lines=work + "\n")
        self.assertAlmostEqual(self.activity(), NOW - 2 * MIN, delta=1000)

    def test_latest_unfinished_agent_counts(self):
        self.agent("a1", finished=True, written=NOW - MIN)
        self.agent("a2", finished=False, written=NOW - 5 * MIN)
        self.agent("a3", finished=False, written=NOW - 3 * MIN)
        self.assertAlmostEqual(self.activity(), NOW - 3 * MIN, delta=1000)

    def test_all_finished_or_none_is_none(self):
        self.assertIsNone(self.activity())
        self.agent("a1", finished=True, written=NOW - MIN)
        self.assertIsNone(self.activity())

    def test_bad_meta_missing_transcript_and_unsafe_id(self):
        self.write(os.path.join("projects", "-work-tools", CLI_ID, "subagents", "agent-x.meta.json"), "not json")
        self.write(os.path.join("projects", "-work-tools", CLI_ID, "subagents", "agent-y.meta.json"), "{}")
        self.assertIsNone(self.activity())
        for bad in (None, 5, "", "../" + CLI_ID, "*"):
            self.assertIsNone(self.activity(bad))

    def test_attach_only_finished_unarchived_turns(self):
        self.agent("a1", finished=False, written=NOW - MIN)
        done = summary("review_ready", "local_done", cliSessionId=CLI_ID)
        running = session("local_run", cliSessionId=CLI_ID, lastTurnEdgeAt=NOW - MIN)
        archived = summary("review_ready", "local_arch", cliSessionId=CLI_ID, isArchived=True)
        scanner.attach_subagents([done, running, archived], self.path("projects"), NOW)
        self.assertIn("subagentActiveAt", done)
        self.assertNotIn("subagentActiveAt", running)
        self.assertNotIn("subagentActiveAt", archived)

    def test_finished_turn_with_running_subagent_is_working(self):
        s = summary("review_ready", "local_multi", lastTurnEdgeAt=NOW - 20 * MIN, subagentActiveAt=NOW - MIN)
        self.assertEqual(scanner.classify(s, NOW), "working")

    def test_quiet_subagent_falls_back_to_the_turn_result(self):
        s = summary("review_ready", "local_multi", subagentActiveAt=NOW - 31 * MIN)
        self.assertEqual(scanner.classify(s, NOW), "review_ready")

    def test_a_question_still_wins(self):
        self.assertEqual(scanner.classify(asked(subagentActiveAt=NOW - MIN), NOW), "asked")
        self.assertEqual(scanner.classify(blocked(subagentActiveAt=NOW - MIN), NOW), "blocked")


# 5. Scheduled tasks -------------------------------------------------------------------------

class ScheduledTests(unittest.TestCase):
    def test_keeps_only_latest_run(self):
        runs = [blocked("local_r%d" % i, last=NOW - i * HOUR, scheduledTaskId="task-1") for i in range(3)]
        regular, latest = scanner.collapse_scheduled(runs + [asked()])
        self.assertEqual([s["sessionId"] for s in regular], ["local_asked"])
        self.assertEqual([s["sessionId"] for s in latest], ["local_r0"])

    def test_latest_run_finished_hides_task(self):
        runs = [summary("completed", "local_new", last=NOW - MIN, scheduledTaskId="task-1"),
                blocked("local_old", last=NOW - HOUR, scheduledTaskId="task-1")]
        status = scanner.build_status(runs, 0, 2, config(), {}, NOW)
        self.assertEqual(status["scheduled"], [])
        self.assertEqual(status["main"], [])

    def test_older_run_asked_does_not_show(self):
        runs = [blocked("local_new", last=NOW - MIN, scheduledTaskId="task-1"),
                asked("local_old", last=NOW - HOUR, scheduledTaskId="task-1")]
        status = scanner.build_status(runs, 0, 2, config(), {}, NOW)
        self.assertEqual([c["sessionId"] for c in status["scheduled"]], ["local_new"])

    def test_old_latest_run_stays_scheduled_not_stale(self):
        runs = [blocked("local_r", last=NOW - 30 * DAY, scheduledTaskId="task-1")]
        status = scanner.build_status(runs, 0, 1, config(), {}, NOW)
        self.assertEqual([c["sessionId"] for c in status["scheduled"]], ["local_r"])
        self.assertEqual(status["stale"], [])


# 6. Hidden ----------------------------------------------------------------------------------

class HiddenTests(TempDir):
    card = {"sessionId": "local_a", "lastActivityAt": NOW - HOUR}

    def test_snooze_active(self):
        state = {"hidden": {"local_a": {"kind": "snooze", "until": NOW + HOUR, "at": NOW}}}
        self.assertEqual(scanner.hidden_by(self.card, state, NOW), {"kind": "snooze", "until": NOW + HOUR})

    def test_snooze_expired(self):
        state = {"hidden": {"local_a": {"kind": "snooze", "until": NOW - 1, "at": NOW - HOUR}}}
        self.assertIsNone(scanner.hidden_by(self.card, state, NOW))

    def test_snooze_beyond_8_days_hides_nothing(self):
        # The server never writes one; a hand-edited state.json can't hide a session for longer.
        far = {"hidden": {"local_a": {"kind": "snooze", "until": NOW + 8 * DAY + MIN, "at": NOW}}}
        self.assertIsNone(scanner.hidden_by(self.card, far, NOW))
        edge = {"hidden": {"local_a": {"kind": "snooze", "until": NOW + 8 * DAY, "at": NOW}}}
        self.assertIsNotNone(scanner.hidden_by(self.card, edge, NOW))

    def test_dismiss_until_new_activity(self):
        state = {"hidden": {"local_a": {"kind": "dismiss", "lastActivityAt": NOW - HOUR, "at": NOW}}}
        self.assertEqual(scanner.hidden_by(self.card, state, NOW), {"kind": "dismiss"})
        newer = dict(self.card, lastActivityAt=NOW - MIN)
        self.assertIsNone(scanner.hidden_by(newer, state, NOW))

    def test_missing_state_hides_nothing(self):
        self.assertEqual(scanner.load_state(self.path("state.json")), {})
        self.assertIsNone(scanner.hidden_by(self.card, {}, NOW))

    def test_broken_state_hides_nothing(self):
        self.assertEqual(scanner.load_state(self.write("state.json", "{ broken")), {})
        self.assertEqual(scanner.load_state(self.write("state2.json", "[1, 2]")), {})
        odd = {"hidden": {"local_a": {"kind": "snooze", "until": "tomorrow"}}}
        self.assertIsNone(scanner.hidden_by(self.card, odd, NOW))
        self.assertIsNone(scanner.hidden_by(self.card, {"hidden": ["local_a"]}, NOW))

    def test_non_finite_values_hide_nothing(self):
        # Review finding Minor 5: json.load reads Infinity, which would hide a card forever.
        inf = float("inf")
        self.assertIsNone(scanner.hidden_by(self.card, {"hidden": {"local_a": {"kind": "snooze", "until": inf}}}, NOW))
        self.assertIsNone(scanner.hidden_by(
            self.card, {"hidden": {"local_a": {"kind": "dismiss", "lastActivityAt": inf}}}, NOW))


# 7. Building status.json --------------------------------------------------------------------

class StatusTests(unittest.TestCase):
    def build(self, sessions, state=None, cfg=None):
        return scanner.build_status(sessions, 0, len(sessions), cfg or config(), state or {}, NOW)

    def ids(self, cards):
        return [c["sessionId"] for c in cards]

    def test_archived_skipped(self):
        status = self.build([asked(isArchived=True), blocked()])
        self.assertEqual(self.ids(status["main"]), ["local_blocked"])

    def test_stale_after_seven_days(self):
        status = self.build([blocked("local_old", last=NOW - 8 * DAY), blocked("local_new", last=NOW - 6 * DAY),
                             summary("review_ready", "local_rr", last=NOW - 30 * DAY)])
        self.assertEqual(self.ids(status["stale"]), ["local_old"])
        self.assertEqual(self.ids(status["main"]), ["local_new"])
        self.assertEqual(self.ids(status["quiet"]), ["local_rr"])

    def test_sort_order(self):
        sessions = [
            summary("completed", "local_unread", last=NOW - MIN, focused=NOW - HOUR),
            summary("review_ready", "local_review", last=NOW - HOUR),
            blocked("local_blocked", last=NOW - MIN),
            session("local_stuck", last=NOW - HOUR, lastTurnEdgeAt=NOW - 2 * HOUR),
            asked("local_asked_old", last=NOW - 2 * HOUR),
            asked("local_asked_new", last=NOW - MIN),
        ]
        status = self.build(sessions)
        self.assertEqual(self.ids(status["main"]),
                         ["local_asked_new", "local_asked_old", "local_stuck", "local_blocked"])
        self.assertEqual(self.ids(status["quiet"]), ["local_review", "local_unread"])

    def test_card_fields(self):
        status = self.build([asked("local_q", question="Run the check?", title="TICKET-1 Thing",
                                   cwd="/work/client-a-bot/.claude/worktrees/w", last=NOW - 25 * MIN)])
        self.assertEqual(status["main"][0], {
            "sessionId": "local_q", "title": "TICKET-1 Thing", "state": "asked",
            "project": "client-a", "subproject": "client-a/us", "repo": "client-a-bot (worktree)",
            "needs": "Run the check?", "lastActivityAt": NOW - 25 * MIN, "waitingMs": 25 * MIN,
            "link": "claude://claude.ai/epitaxy/local_q"})

    def test_stuck_card_has_empty_needs(self):
        s = session("local_s", last=NOW - HOUR, lastTurnEdgeAt=NOW - 2 * HOUR, turnWrapUp=None)
        # A second, finished session: a scan where no file has a status field is an error (HealthTests).
        main = self.build([s, summary("completed", "local_done")])["main"]
        self.assertEqual([(c["sessionId"], c["needs"]) for c in main], [("local_s", "")])

    def test_counts_include_scheduled(self):
        status = self.build([asked(), blocked(), blocked("local_old", last=NOW - 9 * DAY),
                             summary("review_ready", "local_rr"),
                             asked("local_task", scheduledTaskId="task-1")])
        self.assertEqual(status["counts"], {"main": 3, "asked": 2, "working": 0, "pinned": 0, "stale": 1,
                                            "quiet": 1, "hidden": 0, "caughtUp": 0, "scanned": 5})

    def test_error_status_has_empty_lists(self):
        status = scanner.build_status([], 3, 3, config(), {}, NOW)
        self.assertTrue(status["error"].startswith("Can't read session status"))
        for key in ("main", "scheduled", "stale", "quiet", "hidden"):
            self.assertEqual(status[key], [])
        self.assertEqual(status["counts"], {"scanned": 3})
        err = scanner.error_status("projects.json: x", 5, NOW)
        self.assertEqual((err["error"], err["projects"], err["main"], err["counts"]),
                         ("projects.json: x", [], [], {"scanned": 5}))

    def test_hidden_cards_move_to_hidden_with_section(self):
        state = {"hidden": {
            "local_asked": {"kind": "snooze", "until": NOW + HOUR, "at": NOW},
            "local_rr": {"kind": "dismiss", "lastActivityAt": NOW, "at": NOW}}}
        status = self.build([asked(), blocked(), summary("review_ready", "local_rr")], state)
        self.assertEqual(self.ids(status["main"]), ["local_blocked"])
        self.assertEqual(status["quiet"], [])
        hidden = {c["sessionId"]: (c["section"], c["hiddenBy"]["kind"]) for c in status["hidden"]}
        self.assertEqual(hidden, {"local_asked": ("main", "snooze"), "local_rr": ("quiet", "dismiss")})
        self.assertEqual(status["counts"]["hidden"], 2)
        self.assertEqual(status["counts"]["main"], 1)

    def test_working_sessions_get_their_own_list(self):
        sessions = [asked(),
                    session("local_w_old", last=NOW - 10 * MIN, lastTurnEdgeAt=NOW - 50 * MIN),
                    session("local_w_new", last=NOW - MIN, lastTurnEdgeAt=NOW - 3 * MIN),
                    session("local_stuck", last=NOW - HOUR, lastTurnEdgeAt=NOW - 2 * HOUR)]
        status = self.build(sessions)
        self.assertEqual(self.ids(status["working"]), ["local_w_new", "local_w_old"])
        self.assertEqual(self.ids(status["main"]), ["local_asked", "local_stuck"])
        self.assertEqual(status["counts"]["working"], 2)
        self.assertEqual(status["counts"]["main"], 2)            # working doesn't need you: not in the total
        card = status["working"][0]
        self.assertEqual((card["state"], card["needs"], card["startedAt"]), ("working", "", NOW - 3 * MIN))
        self.assertNotIn("doing", card)

    def test_dismissed_working_session_is_hidden_until_it_changes(self):
        # Added 2026-11-21: a manual override for a session that only looks busy.
        sessions = [asked(),
                    session("local_w1", last=NOW - MIN, lastTurnEdgeAt=NOW - 3 * MIN),
                    session("local_w2", last=NOW - MIN, lastTurnEdgeAt=NOW - 3 * MIN),
                    session("local_w3", last=NOW - MIN, lastTurnEdgeAt=NOW - 3 * MIN)]
        state = {"hidden": {"local_w1": {"kind": "dismiss", "lastActivityAt": NOW - MIN},
                            "local_w2": {"kind": "dismiss", "lastActivityAt": NOW - 2 * MIN},   # active since
                            "local_w3": {"kind": "dismiss", "lastActivityAt": NOW - MIN}},
                 "pinned": {"local_w3": {"at": NOW}}}                                          # a pin wins
        status = self.build(sessions, state=state)
        self.assertEqual(sorted(self.ids(status["working"])), ["local_w2", "local_w3"])
        self.assertEqual([(c["sessionId"], c["section"]) for c in status["hidden"]], [("local_w1", "working")])
        self.assertEqual((status["counts"]["working"], status["counts"]["hidden"]), (2, 1))

    def test_working_card_carries_what_it_is_doing(self):
        w = session("local_w", last=NOW - MIN, lastTurnEdgeAt=NOW - 3 * MIN, doingFromTranscript="Step 2")
        self.assertEqual(self.build([asked(), w])["working"][0]["doing"], "Step 2")

    def test_working_scheduled_run_is_not_listed(self):
        s = session("local_t", last=NOW - MIN, lastTurnEdgeAt=NOW - 2 * MIN, scheduledTaskId="task-1")
        status = self.build([s, asked()])
        self.assertEqual((status["working"], status["scheduled"]), ([], []))

    def test_error_status_has_an_empty_working_list(self):
        self.assertEqual(scanner.error_status("x", 1, NOW)["working"], [])

    def test_projects_menu_copied(self):
        status = self.build([blocked()])
        self.assertEqual(status["projects"], MENU)
        self.assertEqual((status["schema"], status["generatedAt"], status["error"]), (1, NOW, None))



class PinnedTests(unittest.TestCase):
    """Pinned sessions (added 2026-11-15): they stay in their own section, in the same order, with
    "pinned": true; once read they stay in Quieter as "read" until you unpin them."""

    def build(self, sessions, pins, hidden=None):
        state = {"hidden": hidden or {}, "pinned": {sid: {"at": NOW} for sid in pins}}
        return scanner.build_status(sessions, 0, len(sessions), config(), state, NOW)

    def test_read_session_stays_in_quieter(self):
        read = session("local_read")                       # focused after its last activity: nothing shows it
        status = self.build([read, summary("review_ready", "local_rr")], ["local_read"])
        self.assertEqual([(c["sessionId"], c["state"], c.get("pinned")) for c in status["quiet"]],
                         [("local_rr", "review_ready", None), ("local_read", "read", True)])
        self.assertEqual(self.build([read], [])["quiet"], [])
        self.assertEqual(status["counts"]["pinned"], 1)

    def test_pinned_cards_keep_their_section_and_order(self):
        work = session("local_w", last=NOW - MIN, lastTurnEdgeAt=NOW - 2 * MIN)
        sessions = [asked(), asked("local_new", last=NOW - MIN), summary("review_ready", "local_rr"), work,
                    blocked("local_old", last=NOW - 9 * DAY)]
        plain = self.build(sessions, [])
        status = self.build(sessions, ["local_asked", "local_rr", "local_w", "local_old"])
        for key in ("main", "quiet", "working", "stale"):
            self.assertEqual([c["sessionId"] for c in status[key]], [c["sessionId"] for c in plain[key]], key)
        self.assertEqual([c.get("pinned") for c in status["main"]], [None, True])
        self.assertTrue(status["working"][0]["pinned"] and status["stale"][0]["pinned"])
        self.assertNotIn("pinned", status)
        # Counts and banners don't change: a pinned card is still where it was.
        self.assertEqual({k: v for k, v in status["counts"].items() if k != "pinned"},
                         {k: v for k, v in plain["counts"].items() if k != "pinned"})

    def test_pin_beats_a_hide_entry(self):
        status = self.build([asked()], ["local_asked"], {"local_asked": {"kind": "dismiss", "lastActivityAt": NOW, "at": NOW}})
        self.assertEqual(([c["sessionId"] for c in status["main"]], status["hidden"]), (["local_asked"], []))

    def test_archived_pinned_session_is_dropped(self):
        status = self.build([asked(isArchived=True)], ["local_asked"])
        self.assertEqual((status["main"], status["counts"]["pinned"]), ([], 0))

    def test_pinned_scheduled_run(self):
        status = self.build([asked("local_run", scheduledTaskId="task-1", last=NOW - 9 * DAY),
                             session("local_done", scheduledTaskId="task-2")], ["local_run", "local_done"])
        self.assertEqual([c["sessionId"] for c in status["scheduled"]], ["local_run"])
        self.assertEqual([(c["sessionId"], c["state"]) for c in status["quiet"]], [("local_done", "read")])

    def test_broken_pin_entries_ignored(self):
        for pinned in ([1], "x", {"local_asked": True}, None):
            status = scanner.build_status([asked()], 0, 1, config(), {"pinned": pinned}, NOW)
            self.assertNotIn("pinned", status["main"][0], pinned)


class CaughtUpTests(unittest.TestCase):
    """Caught up (added 2026-11-17): finished sessions you've read stay listed for a week, newest first."""

    def build(self, sessions, state=None):
        return scanner.build_status(sessions, 0, len(sessions), config(), state or {}, NOW)

    def test_read_sessions_newest_first(self):
        sessions = [session("local_old", last=NOW - 2 * DAY), session("local_new", last=NOW - HOUR), asked(),
                    summary("review_ready", "local_rr")]
        status = self.build(sessions)
        self.assertEqual([(c["sessionId"], c["state"]) for c in status["caughtUp"]],
                         [("local_new", "read"), ("local_old", "read")])
        self.assertEqual(status["caughtUp"][0]["link"], scanner.LINK_PREFIX + "local_new")
        self.assertEqual((status["counts"]["caughtUp"], status["counts"]["main"], status["counts"]["quiet"]), (2, 1, 1))

    def test_older_than_a_week_archived_or_pinned_left_out(self):
        sessions = [session("local_week", last=NOW - scanner.CAUGHT_UP_MS),
                    session("local_older", last=NOW - scanner.CAUGHT_UP_MS - 1),
                    session("local_arch", isArchived=True), session("local_pin"), asked()]
        status = self.build(sessions, {"pinned": {"local_pin": {"at": NOW}}})
        self.assertEqual([c["sessionId"] for c in status["caughtUp"]], ["local_week"])
        self.assertEqual([c["sessionId"] for c in status["quiet"]], ["local_pin"])     # pinned: Quieter, as before

    def test_capped(self):
        sessions = [session("local_%d" % i, last=NOW - i * MIN) for i in range(scanner.CAUGHT_UP_MAX + 5)] + [asked()]
        got = self.build(sessions)["caughtUp"]
        self.assertEqual(len(got), scanner.CAUGHT_UP_MAX)
        self.assertEqual(got[-1]["sessionId"], "local_%d" % (scanner.CAUGHT_UP_MAX - 1))

    def test_dismissed_goes_to_hidden_until_new_activity(self):
        # Added 2026-11-18: a caught-up card can be dismissed; it sits in Hidden ("Show again") until it changes.
        sessions = [session("local_a", last=NOW - HOUR), session("local_b", last=NOW - 2 * HOUR), asked()]
        state = {"hidden": {sid: {"kind": "dismiss", "lastActivityAt": NOW - 2 * HOUR, "at": NOW}
                            for sid in ("local_a", "local_b")}}
        status = self.build(sessions, state)
        self.assertEqual([c["sessionId"] for c in status["caughtUp"]], ["local_a"])     # newer than the dismissal
        self.assertEqual([(c["sessionId"], c["section"], c["state"], c["hiddenBy"]) for c in status["hidden"]],
                         [("local_b", "caughtUp", "read", {"kind": "dismiss"})])
        self.assertEqual((status["counts"]["caughtUp"], status["counts"]["hidden"], status["counts"]["main"]), (1, 1, 1))

    def test_dismissed_older_than_a_week_left_out_and_error_status_has_the_list(self):
        old = NOW - scanner.CAUGHT_UP_MS - 1
        state = {"hidden": {"local_a": {"kind": "dismiss", "lastActivityAt": old, "at": NOW}}}
        status = self.build([session("local_a", last=old), asked()], state)
        self.assertEqual((status["caughtUp"], status["hidden"]), ([], []))
        self.assertEqual(scanner.error_status("x", 1, NOW)["caughtUp"], [])


# 8. Writing ---------------------------------------------------------------------------------

class WriteTests(TempDir):
    def test_replaces_file(self):
        out = self.write("status.json", "old")
        scanner.write_status({"schema": 1}, out)
        with open(out, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"schema": 1})

    def test_no_temp_file_left(self):
        scanner.write_status({"schema": 1}, self.path("status.json"))
        self.assertEqual(os.listdir(self.dir), ["status.json"])

    def test_lone_surrogate_in_a_title_still_writes(self):
        # Review finding: a title cut mid-emoji used to crash the write and leave the old status in place.
        out = self.path("status.json")
        scanner.write_status({"title": "Made-up \ud800 title"}, out)
        with open(out, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["title"], "Made-up \ud800 title")

    def test_output_is_valid_json_and_private(self):
        out = self.path("status.json")
        scanner.write_status({"title": "Café ✓"}, out)
        with open(out, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"title": "Café ✓"})
        self.assertEqual(os.stat(out).st_mode & 0o077, 0)


# 9. Command line ----------------------------------------------------------------------------

class CliTests(TempDir):
    def setUp(self):
        super().setUp()
        self.projects = self.write("projects.json", {
            "projects": MENU, "default": "other",
            "rules": [{"folder": "/work/tools", "project": "tools", "subproject": None}]})
        self.out = self.path("status.json")

    def run_cli(self, *extra, projects=None):
        args = ["--sessions-dir", self.path("sessions"), "--projects", projects or self.projects,
                "--state", self.path("state.json"), "--out", self.out,
                "--transcripts-dir", self.path("projects")] + list(extra)
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = scanner.main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_writes_status_to_out(self):
        self.write_session(asked(title="Secret title"))
        code, _, _ = self.run_cli()
        self.assertEqual(code, 0)
        with open(self.out, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["counts"]["main"], 1)

    def test_question_in_transcript_is_asked_and_notifies(self):
        self.write_session(asked_in_transcript(title="Made-up title"))
        self.write(os.path.join("projects", "-work-tools", CLI_ID + ".jsonl"),
                   json.dumps(wrap_entry(ask="Ship it?")) + "\n")
        self.write("status.json", {"schema": 1, "error": None, "main": [], "scheduled": [], "stale": [],
                                   "hidden": []})
        sent = []
        old = scanner._osascript
        scanner._osascript = lambda title, body: sent.append(body)
        try:
            code, _, _ = self.run_cli()
        finally:
            scanner._osascript = old
        self.assertEqual(code, 0)
        with open(self.out, encoding="utf-8") as f:
            status = json.load(f)
        self.assertEqual(status["counts"]["asked"], 1)
        self.assertEqual(status["main"][0]["needs"], "Ship it?")
        self.assertEqual(sent, ["Made-up title"])

    def test_exit_code_on_error(self):
        code, _, err = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("No session files found", err)
        code, _, err = self.run_cli(projects=self.path("missing.json"))
        self.assertEqual(code, 1)
        self.assertIn("projects.json", err)
        with open(self.out, encoding="utf-8") as f:
            self.assertTrue(json.load(f)["error"].startswith("projects.json"))

    def test_summary_has_no_titles(self):
        self.write_session(asked(title="Secret title", question="Secret question", cwd="/secret/folder"))
        self.write_session(blocked(title="Other secret", cwd="/work/tools"))
        code, out, _ = self.run_cli("--summary")
        self.assertEqual(code, 0)
        for secret in ("Secret", "secret", "Internal Tools", "Client"):
            self.assertNotIn(secret, out)
        self.assertIn("2", out)

    def test_summary_stderr_has_no_names_or_folders(self):
        # Review finding Important 3: the error line on stderr used to repeat the folder and project id.
        bad = self.write("bad-projects.json", {"projects": MENU, "default": "other", "rules": [
            {"folder": "~/work/acmecorp-bot", "project": "acmecorp", "subproject": None}]})
        self.write_session(asked())
        code, out, err = self.run_cli("--summary", projects=bad)
        self.assertEqual(code, 1)
        self.assertNotIn("acme", out + err)
        self.assertIn("projects.json", err)

    def test_every_projects_error_writes_an_error_status(self):
        self.write_session(asked())
        cases = ["{ bad json",
                 {"projects": MENU, "default": "other", "rules": [{"folder": "/x", "project": "nope"}]},
                 {"projects": MENU, "default": "other",
                  "rules": [{"folder": "/x", "project": "tools", "subproject": "client-a/us"}]},
                 {"projects": MENU, "default": "other", "rules": [{"folder": "/x", "project": ["tools"]}]}]
        for i, data in enumerate(cases):
            code, _, _ = self.run_cli(projects=self.write("p%d.json" % i, data))
            self.assertEqual(code, 1)
            with open(self.out, encoding="utf-8") as f:
                status = json.load(f)
            self.assertTrue(status["error"].startswith("projects.json: "), status["error"])
            self.assertEqual(status["main"], [])

    def test_crash_still_writes_an_error_status(self):
        # Safety net: any unexpected exception replaces the old status with an error, never leaves a calm 0.
        self.write_session(asked())
        self.run_cli()
        original = scanner.build_status
        scanner.build_status = lambda *a, **k: 1 / 0
        self.addCleanup(setattr, scanner, "build_status", original)
        code, _, err = self.run_cli("--summary")
        self.assertEqual(code, 1)
        with open(self.out, encoding="utf-8") as f:
            status = json.load(f)
        self.assertIn("ZeroDivisionError", status["error"])
        self.assertEqual(status["main"], [])
        self.assertNotIn("Traceback", err)

    def test_real_data_lives_in_the_data_folder(self):
        # status.json and state.json live in data/, the one folder kept off Dropbox.
        here = os.path.dirname(os.path.abspath(scanner.__file__))
        self.assertEqual(scanner.DATA_DIR, os.path.join(here, "data"))
        self.assertEqual(scanner.STATUS_PATH, os.path.join(here, "data", "status.json"))
        self.assertEqual(scanner.STATE_PATH, os.path.join(here, "data", "state.json"))

    def test_creates_a_missing_out_folder(self):
        self.write_session(asked())
        self.out = self.path("new-data", "status.json")
        code, _, _ = self.run_cli()
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isfile(self.out))

    def test_print_counts_sessions_without_a_folder(self):
        s = asked()
        del s["cwd"]
        self.write_session(s)
        _, out, _ = self.run_cli("--print")
        self.assertIn("(no folder)", out.split("no rule")[-1])

    def test_print_lists_unmatched_folders(self):
        self.write_session(asked(title="Visible title", cwd="/elsewhere/repo-x"))
        self.write_session(blocked(cwd="/work/tools/sub"))
        code, out, _ = self.run_cli("--print")
        self.assertEqual(code, 0)
        self.assertIn("Visible title", out)
        self.assertIn("/elsewhere/repo-x", out)
        self.assertNotIn("/work/tools/sub", out.split("no rule")[-1])


if __name__ == "__main__":
    unittest.main()
