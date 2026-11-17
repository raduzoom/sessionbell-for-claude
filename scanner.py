#!/usr/bin/env python3
"""Sessionbell: the scanner.

Reads the Claude desktop app's Code-tab session files (read-only) and writes status.json, the one file
every display reads. Behaviour follows handoff/handoff.html §3, §5 and §6.

    python3 scanner.py              write data/status.json; exit 1 if the status is an error
    python3 scanner.py --print      also print the grouped list with titles (for your own terminal)
    python3 scanner.py --summary    also print counts only, no titles or folders (safe to share)

    python3 scanner.py --no-notify  no banners for new questions
    python3 scanner.py --notify-test  send one made-up banner and exit

Python 3.9+, standard library only. It never writes to the app's folder. It shows a banner (title only)
when a session asks a new question (handoff §7).
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.expanduser("~/Library/Application Support/Claude/claude-code-sessions")
# The app no longer saves the next-step question (turnWrapUp.needsUser); only the CLI transcript has it.
TRANSCRIPTS_DIR = os.path.expanduser("~/.claude/projects")
TRANSCRIPT_TAIL = 1_000_000             # bytes; the latest wrap-up sits within ~50 KB of the end
CLI_ID = re.compile(r"[0-9A-Za-z-]{1,64}")
WRAP_UP_TOOL = "mcp__ccd_turn__wrap_up"
PLAN_TOOL = "mcp__ccd_turn__update_plan"
DOING_MAX = 100                         # characters of the "what it's doing" line
# The plan list can sit far back: image reads and long tool output fill the tail, and later calls only say
# "advance" (found 2026-11-15: 2 to 6 MB back). So the "doing" line reads further back, step by step.
DOING_TAILS = (TRANSCRIPT_TAIL, 4_000_000, 16_000_000)
# Most of those bytes are a few huge lines (images in tool results). Past the first step, a line this long
# is parsed only if it names a plan tool: that keeps a scan every 10 s cheap.
BIG_LINE = 50_000
PLAN_MARKS = (b"update_plan", b"TodoWrite")
# Real session data (titles) lives in data/, the one folder marked ignored by Dropbox so it never syncs.
DATA_DIR = os.path.join(HERE, "data")
STATUS_PATH = os.path.join(DATA_DIR, "status.json")
STATE_PATH = os.path.join(DATA_DIR, "state.json")

# A started turn with this much quiet counts as stuck; before that it is "working". The handoff said 5 minutes,
# but a long tool call can be quiet for 15 (changed 2026-11-12 at the user's request, with the Working section).
STUCK_QUIET_MS = 30 * 60_000
STALE_MS = 7 * 24 * 60 * 60_000        # needs-you items older than this go to Stale
# A background subagent started longer ago than this is taken as dead, whatever its transcript's file time says:
# old transcripts from before the app wrote "finished" get their file time bumped by other tools (seen 2026-11-16).
SUBAGENT_MAX_AGE_MS = 72 * 60 * 60_000      # 72 hours (the user's choice, 2026-11-16)
SNOOZE_MAX_MS = 8 * 24 * 60 * 60_000   # the longest snooze the server accepts
UNREADABLE_LIMIT = 0.10                # more unreadable files than this is an error
WORKTREE_MARK = "/.claude/worktrees/"
LINK_PREFIX = "claude://claude.ai/epitaxy/"

NEEDS_YOU = ("asked", "stuck", "blocked")
# "read" is only for a pinned session you've read: unpinned it would leave the list; pinned it stays in Quieter.
RANK = {"asked": 0, "stuck": 1, "blocked": 2, "review_ready": 3, "unread": 4, "working": 5, "read": 6}
SECTIONS = ("main", "scheduled", "stale", "quiet")


# projects.json ------------------------------------------------------------------------------

def load_projects(path):
    """Return (config, None) or (None, error). Rule folders come back with ~ expanded."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None, "projects.json: file not found."
    except (OSError, UnicodeDecodeError) as e:
        return None, "projects.json: can't read it (%s)." % e.__class__.__name__
    except ValueError as e:
        return None, "projects.json: not valid JSON (line %s)." % getattr(e, "lineno", "?")

    if not isinstance(data, dict):
        return None, "projects.json: the top level must be an object."
    menu, default, rules = data.get("projects"), data.get("default"), data.get("rules")
    if not isinstance(menu, list):
        return None, 'projects.json: "projects" must be a list.'
    if not isinstance(default, str):
        return None, 'projects.json: "default" must be a project id.'
    if not isinstance(rules, list):
        return None, 'projects.json: "rules" must be a list.'

    parents = {}                       # project id -> set of its sub-project ids
    owner = {}                         # sub-project id -> its project id
    for p in menu:
        if not (isinstance(p, dict) and isinstance(p.get("id"), str) and isinstance(p.get("name"), str)):
            return None, 'projects.json: every project needs a text "id" and "name".'
        children = p.get("children", [])
        if not isinstance(children, list):
            return None, 'projects.json: "children" of "%s" must be a list.' % p["id"]
        kids = set()
        for c in children:
            if not (isinstance(c, dict) and isinstance(c.get("id"), str) and isinstance(c.get("name"), str)):
                return None, 'projects.json: every sub-project of "%s" needs a text "id" and "name".' % p["id"]
            kids.add(c["id"])
            owner[c["id"]] = p["id"]
        parents[p["id"]] = kids

    if default not in parents:
        return None, 'projects.json: the default project "%s" isn\'t in the menu.' % default

    clean, seen = [], set()
    for r in rules:
        if not (isinstance(r, dict) and isinstance(r.get("folder"), str) and r["folder"].strip()):
            return None, 'projects.json: every rule needs a text "folder".'
        folder, project, sub = r["folder"], r.get("project"), r.get("subproject")
        if not isinstance(project, str):
            return None, 'projects.json: the rule for %s needs a text "project".' % folder
        if sub is not None and not isinstance(sub, str):
            return None, 'projects.json: the rule for %s needs a text "subproject" or null.' % folder
        expanded = os.path.expanduser(folder).rstrip("/") or "/"
        if expanded in seen:
            return None, "projects.json: two rules name the same folder, %s." % folder
        seen.add(expanded)
        if project not in parents:
            return None, 'projects.json: the rule for %s names an unknown project "%s".' % (folder, project)
        if sub is not None:
            if sub not in owner:
                return None, 'projects.json: the rule for %s names an unknown sub-project "%s".' % (folder, sub)
            if owner[sub] != project:
                return None, ('projects.json: the rule for %s puts sub-project "%s" under "%s", '
                              'but it belongs to "%s".' % (folder, sub, project, owner[sub]))
        clean.append({"folder": expanded, "project": project, "subproject": sub})
    return {"projects": menu, "default": default, "rules": clean}, None


# Folder to project --------------------------------------------------------------------------

def _folder(cwd):
    """The session's folder with any worktree part cut off, and whether it was a worktree."""
    folder = cwd if isinstance(cwd, str) else ""
    i = folder.find(WORKTREE_MARK)
    worktree = i >= 0
    if worktree:
        folder = folder[:i]
    return (folder.rstrip("/") or "/") if folder else "", worktree


def _rule_for(folder, rules):
    """The longest rule whose folder is this folder or one of its parents."""
    best = None
    for r in rules:
        f = r["folder"]
        if folder == f or folder.startswith(f.rstrip("/") + "/"):
            if best is None or len(f) > len(best["folder"]):
                best = r
    return best


def project_for(cwd, rules, default):
    """Return (project, subproject, repo) for a session's working folder."""
    folder, worktree = _folder(cwd)
    repo = os.path.basename(folder) or folder
    if worktree:
        repo += " (worktree)"
    rule = _rule_for(folder, rules) if folder else None
    if rule:
        return rule["project"], rule["subproject"], repo
    return default, None, repo


# Folders you can start a new session in (added 2026-11-16): the page's New session picker opens
# claude://code/new?folder=<folder>. Every folder a session ran in (worktrees cut back to their repo, newest
# use first), then the projects.json rule folders never used. Temporary folders and missing ones are left out.
MAX_FOLDERS = 200
TEMP_PREFIXES = ("/tmp/", "/private/", "/var/folders/")


def _display(folder, home):
    return "~" + folder[len(home):] if home and (folder == home or folder.startswith(home + "/")) else folder


def folder_list(sessions, cfg, exists=os.path.isdir, home=None):
    home = (os.path.expanduser("~") if home is None else home).rstrip("/")
    used = {}
    for s in sessions:
        folder, _ = _folder(s.get("cwd"))
        when = s.get("lastActivityAt")
        if folder and _number(when) and when > used.get(folder, -1):
            used[folder] = when
    for r in cfg["rules"]:
        used.setdefault(r["folder"], None)
    order = sorted(used, key=lambda f: (used[f] is None, -(used[f] or 0), f.lower()))
    out = []
    for folder in order:
        if (not folder.startswith("/") or folder == "/" or (folder + "/").startswith(TEMP_PREFIXES)
                or not exists(folder)):
            continue
        project, sub, name = project_for(folder, cfg["rules"], cfg["default"])
        out.append({"folder": folder, "name": name, "path": _display(folder, home), "project": project,
                    "subproject": sub, "lastUsedAt": used[folder]})
        if len(out) >= MAX_FOLDERS:
            break
    return out


# Reading session files ----------------------------------------------------------------------

def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _usable(s):
    """A file we can trust: the required fields have the right types (format drift counts as a problem)."""
    if not isinstance(s, dict):
        return False
    task = s.get("scheduledTaskId")
    return (isinstance(s.get("sessionId"), str) and isinstance(s.get("title"), str)
            and _number(s.get("lastActivityAt")) and (task is None or isinstance(task, str)))


def read_sessions(sessions_dir):
    """Return (sessions, problems, total) for every <account>/<org>/local_*.json file."""
    paths = sorted(glob.glob(os.path.join(glob.escape(sessions_dir), "*", "*", "local_*.json")))
    sessions, problems = [], 0
    for p in paths:
        try:
            with open(p, encoding="utf-8") as f:
                s = json.load(f)
        except (OSError, ValueError, UnicodeDecodeError):
            problems += 1
            continue
        if _usable(s):
            sessions.append(s)
        else:
            problems += 1
    return sessions, problems, len(paths)


def health_error(sessions, problems, total):
    """Say loudly when the data can't be trusted, instead of showing a calm 0."""
    if total == 0:
        return "No session files found. The Claude app may have moved its sessions folder."
    if problems > total * UNREADABLE_LIMIT:
        return ("Can't read session status, format may have changed (%d of %d files unreadable)."
                % (problems, total))
    if not any(s.get("postTurnSummary") or s.get("turnWrapUp") for s in sessions):
        return "Can't read session status, format may have changed (no file has a status field)."
    return None


# Classification -----------------------------------------------------------------------------

def _dict(value):
    return value if isinstance(value, dict) else {}


def classify(s, now):
    """asked | stuck | blocked | review_ready | unread | working | None (handoff §6, plus Working)."""
    summary = _dict(s.get("postTurnSummary"))
    wrap = _dict(s.get("turnWrapUp"))
    # lastTurnEdgeAt marks a turn's START; the app clears summary and wrap-up then.
    # Older sessions have no lastTurnEdgeAt at all: never call those stuck or working.
    if s.get("lastTurnEdgeAt") is not None and not summary and not wrap:
        return "stuck" if now - s["lastActivityAt"] > STUCK_QUIET_MS else "working"
    if wrap.get("needsUser") or s.get("askFromTranscript"):
        return "asked"
    if summary.get("status_category") == "blocked" and not _is_btw(s):
        return "blocked"
    # The turn ended but a subagent it started still runs (multi-agent plans). Once it has been quiet
    # this long it may have died with the app, so the turn's own result counts again.
    active = s.get("subagentActiveAt")
    if _number(active) and now - active <= STUCK_QUIET_MS:
        return "working"
    if summary.get("status_category") in ("review_ready", "blocked"):
        return "review_ready"
    focused = s.get("lastFocusedAt")
    if s["lastActivityAt"] > (focused if isinstance(focused, (int, float)) else 0):
        return "unread"
    return None


def _is_btw(s):
    """A btw side question turned into a session. It is a fork, so its transcript starts with the parent's
    history, and the app's summary can report the parent's blocked request as this session's (seen
    2026-11-12). The btw turn only answers your question, so never call it blocked."""
    return bool(s.get("btwLoweredFrom"))


def needs_text(s):
    summary = _dict(s.get("postTurnSummary"))
    wrap = _dict(s.get("turnWrapUp"))
    action = None if _is_btw(s) else summary.get("needs_action")
    for value in (wrap.get("needsUser"), s.get("askFromTranscript"), action,
                  summary.get("status_detail"), wrap.get("description")):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


# The question from the transcript -----------------------------------------------------------

def _is_reply(entry, content):
    """A message you typed (or a button you clicked): it answers any question before it."""
    if entry.get("type") != "user" or entry.get("isMeta"):
        return False
    return isinstance(content, str) or (isinstance(content, list) and any(
        isinstance(b, dict) and b.get("type") == "text" for b in content))


def _transcript_entries(cli_id, transcripts_dir, tail=None, whole=None, plan_only_big=False):
    """The CLI transcript's last `tail` bytes (TRANSCRIPT_TAIL when None) as (entry, content) pairs, main
    thread only. `whole`, a list, gets True appended when those bytes were the whole file. With
    `plan_only_big`, lines over BIG_LINE are skipped unless they name a plan tool."""
    tail = TRANSCRIPT_TAIL if tail is None else tail
    if not isinstance(cli_id, str) or not CLI_ID.fullmatch(cli_id):
        return
    paths = glob.glob(os.path.join(glob.escape(transcripts_dir), "*", cli_id + ".jsonl"))
    if not paths:
        return
    try:
        path = max(paths, key=os.path.getmtime)
        with open(path, "rb") as f:
            size = f.seek(0, os.SEEK_END)
            f.seek(max(0, size - tail))
            lines = f.read().split(b"\n")
    except OSError:
        return
    if size > tail:
        lines = lines[1:]                  # the first line is cut
    elif whole is not None:
        whole.append(True)
    for line in lines:
        if plan_only_big and len(line) > BIG_LINE and not any(mark in line for mark in PLAN_MARKS):
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("isSidechain"):
            continue
        yield entry, _dict(entry.get("message")).get("content")


def transcript_ask(cli_id, transcripts_dir):
    """The question in the latest wrap-up, if nothing was typed since; else "". Reads only the file's tail."""
    ask = ""
    for entry, content in _transcript_entries(cli_id, transcripts_dir):
        if _is_reply(entry, content):
            ask = ""
        elif entry.get("type") == "assistant" and isinstance(content, list):
            for block in content:
                if (isinstance(block, dict) and block.get("type") == "tool_use"
                        and block.get("name") == WRAP_UP_TOOL):
                    value = _dict(block.get("input")).get("ask")
                    ask = value.strip() if isinstance(value, str) else ""
    return ask


def attach_asks(sessions, transcripts_dir):
    """Set askFromTranscript on finished, unarchived sessions whose latest wrap-up asks you something."""
    for s in sessions:
        wrap = _dict(s.get("turnWrapUp"))
        if not wrap or wrap.get("needsUser") or s.get("isArchived") is True:
            continue
        ask = transcript_ask(s.get("cliSessionId"), transcripts_dir)
        if ask:
            s["askFromTranscript"] = ask


# What a working session is doing (added 2026-11-13) -------------------------------------------
# No model is needed: the session already writes its own one-line plan. The step marked in progress is the
# summary; with no plan, the first line of the latest message you typed. Everything stays on this Mac.

def _one_line(text):
    text = " ".join(text.split())
    return text if len(text) <= DOING_MAX else text[:DOING_MAX - 1].rstrip() + "…"


def _apply_plan(plan, call):
    """Replay one update_plan call (a whole list, advance, or done/start by 1-based number) on plan."""
    if isinstance(call.get("items"), list):
        return [[str(_dict(i).get("content", "")), _dict(i).get("status")] for i in call["items"] if isinstance(i, dict)]
    plan = [list(i) for i in plan]
    current = next((n for n, i in enumerate(plan) if i[1] == "in_progress"), None)
    if call.get("advance") is True:
        if current is not None:
            plan[current][1] = "completed"
        nxt = next((i for i in plan if i[1] == "pending"), None)
        if nxt:
            nxt[1] = "in_progress"
    for n in call.get("done") if isinstance(call.get("done"), list) else []:
        if isinstance(n, int) and 1 <= n <= len(plan):
            plan[n - 1][1] = "completed"
    start = call.get("start")
    if isinstance(start, int) and 1 <= start <= len(plan):
        plan[start - 1][1] = "in_progress"
    return plan


def _typed_text(content):
    """The words of a message you typed; "" for injected reminders and command wrappers (they start with <)."""
    if isinstance(content, list):
        content = " ".join(b.get("text", "") for b in content
                           if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str))
    if not isinstance(content, str):
        return ""
    content = content.strip()
    return "" if content.startswith("<") else content


def transcript_doing(cli_id, transcripts_dir):
    """One line on what a running turn is doing, or "". Reads the file's tail, further back (DOING_TAILS)
    until it holds a whole plan list: "advance" alone says nothing without the list it moves through."""
    plan, typed = [], ""
    for n, tail in enumerate(DOING_TAILS):
        plan, prompt_text, listed, whole = [], "", False, []
        for entry, content in _transcript_entries(cli_id, transcripts_dir, tail, whole, plan_only_big=n > 0):
            if _is_reply(entry, content):
                prompt_text = _typed_text(content) or prompt_text
            elif entry.get("type") == "assistant" and isinstance(content, list):
                for block in content:
                    if not (isinstance(block, dict) and block.get("type") == "tool_use"):
                        continue
                    call = _dict(block.get("input"))
                    if block.get("name") == PLAN_TOOL:
                        listed = listed or isinstance(call.get("items"), list)
                        plan = _apply_plan(plan, call)
                    elif block.get("name") == "TodoWrite" and isinstance(call.get("todos"), list):
                        listed = True
                        plan = [[str(_dict(t).get("activeForm") or _dict(t).get("content") or ""), _dict(t).get("status")]
                                for t in call["todos"] if isinstance(t, dict)]
        typed = prompt_text or typed       # a wider step skips big lines, so keep what a narrower one found
        if listed or whole:
            break
    step = next((i[0] for i in plan if i[1] == "in_progress" and i[0].strip()), "")
    return _one_line(step or typed.strip().split("\n")[0])


def attach_doing(sessions, transcripts_dir, now):
    """Set doingFromTranscript on the sessions that count as working."""
    for s in sessions:
        if s.get("isArchived") is True or classify(s, now) != "working":
            continue
        doing = transcript_doing(s.get("cliSessionId"), transcripts_dir)
        if doing:
            s["doingFromTranscript"] = doing


def subagent_activity(cli_id, transcripts_dir, now):
    """When an unfinished subagent of this session last wrote its transcript (ms), or None.

    A turn can end while the subagents it started keep running in the background; the session file then
    looks finished. The app writes subagents/agent-*.meta.json with finished: true once one ends (seen
    2026-11-13). Reads only that flag and file times, never the transcripts' text. The meta file's time is
    when the agent started (it is written again only when it finishes); one started over SUBAGENT_MAX_AGE_MS
    ago is ignored, because the transcript's file time alone can be bumped long after the agent died."""
    if not isinstance(cli_id, str) or not CLI_ID.fullmatch(cli_id):
        return None
    pattern = os.path.join(glob.escape(transcripts_dir), "*", cli_id, "subagents", "agent-*.meta.json")
    latest = None
    for meta in glob.glob(pattern):
        try:
            with open(meta, encoding="utf-8") as f:
                finished = _dict(json.load(f)).get("finished") is True
            started = os.path.getmtime(meta) * 1000
            written = os.path.getmtime(meta[:-len(".meta.json")] + ".jsonl") * 1000
        except (OSError, ValueError, UnicodeDecodeError):
            continue
        if finished or now - started > SUBAGENT_MAX_AGE_MS:
            continue
        if latest is None or written > latest:
            latest = written
    return latest


def attach_subagents(sessions, transcripts_dir, now):
    """Set subagentActiveAt on finished, unarchived sessions with a subagent still running."""
    for s in sessions:
        if s.get("isArchived") is True or (not s.get("postTurnSummary") and not s.get("turnWrapUp")):
            continue
        at = subagent_activity(s.get("cliSessionId"), transcripts_dir, now)
        if at is not None:
            s["subagentActiveAt"] = int(at)


def collapse_scheduled(sessions):
    """Return (regular sessions, the latest run of each scheduled task)."""
    regular, latest = [], {}
    for s in sessions:
        task = s.get("scheduledTaskId")
        if not task:
            regular.append(s)
        elif task not in latest or s["lastActivityAt"] > latest[task]["lastActivityAt"]:
            latest[task] = s
    return regular, list(latest.values())


# state.json (read-only here; the server is its only writer) ---------------------------------

def load_state(path):
    """A missing or broken state.json hides nothing."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def hidden_by(card, state, now):
    """{"kind": "snooze", "until": ms} or {"kind": "dismiss"} when the card is hidden, else None."""
    hidden = state.get("hidden") if isinstance(state, dict) else None
    entry = hidden.get(card["sessionId"]) if isinstance(hidden, dict) else None
    if not isinstance(entry, dict):
        return None
    # A snooze ends at "until", and never lasts more than 8 days (the server's limit), even if hand-edited.
    if (entry.get("kind") == "snooze" and _number(entry.get("until"))
            and now < entry["until"] <= now + SNOOZE_MAX_MS):
        return {"kind": "snooze", "until": entry["until"]}
    if (entry.get("kind") == "dismiss" and _number(entry.get("lastActivityAt"))
            and card["lastActivityAt"] <= entry["lastActivityAt"]):
        return {"kind": "dismiss"}
    return None


def pinned_ids(state):
    """The sessions you pinned (added 2026-11-15). A pin never ends by itself: only Unpin, Snooze or Dismiss."""
    pinned = state.get("pinned") if isinstance(state, dict) else None
    if not isinstance(pinned, dict):
        return set()
    return {sid for sid, e in pinned.items() if isinstance(sid, str) and isinstance(e, dict)}


# status.json --------------------------------------------------------------------------------

def _card(s, state_name, cfg, now):
    project, sub, repo = project_for(s.get("cwd"), cfg["rules"], cfg["default"])
    card = {
        "sessionId": s["sessionId"],
        "title": s["title"],
        "state": state_name,
        "project": project,
        "subproject": sub,
        "repo": repo,
        # The page shows fixed notes for stuck and working sessions.
        "needs": "" if state_name in ("stuck", "working") else needs_text(s),
        "lastActivityAt": s["lastActivityAt"],
        "waitingMs": max(0, now - s["lastActivityAt"]),
        "link": LINK_PREFIX + s["sessionId"],
    }
    if state_name == "working" and _number(s.get("lastTurnEdgeAt")):
        card["startedAt"] = s["lastTurnEdgeAt"]          # "for 27m" counts from the turn's start
    if state_name == "working" and s.get("doingFromTranscript"):
        card["doing"] = s["doingFromTranscript"]         # the plan step in progress, shown instead of a fixed note
    return card


def _sort(cards):
    cards.sort(key=lambda c: (RANK[c["state"]], -c["lastActivityAt"]))
    return cards


def error_status(error, scanned, now, menu=None):
    status = {"schema": 1, "generatedAt": now, "error": error, "projects": menu or []}
    for key in SECTIONS + ("working", "hidden"):
        status[key] = []
    status["counts"] = {"scanned": scanned}
    return status


def build_status(sessions, problems, total, projects, state, now):
    error = health_error(sessions, problems, total)
    if error:
        return error_status(error, total, now, projects["projects"])

    lists = {key: [] for key in SECTIONS}
    working = []
    # A pinned session stays where it would be anyway, in the same order, with "pinned": true. Once you've
    # read it (it would drop off), it stays in Quieter as "read" until you unpin it. A pin beats any hide.
    pins = pinned_ids(state)
    live = [s for s in sessions if s.get("isArchived") is not True]
    regular, latest = collapse_scheduled([s for s in live if s["sessionId"] not in pins])
    for s in regular + [s for s in live if s["sessionId"] in pins]:
        state_name = classify(s, now)
        pinned = s["sessionId"] in pins
        if state_name is None and not pinned:
            continue
        card = _card(s, state_name or "read", projects, now)
        if pinned:
            card["pinned"] = True
        if state_name == "working":            # doesn't need you yet: its own list, never hidden or counted
            working.append(card)
            continue
        if state_name in NEEDS_YOU:
            if s.get("scheduledTaskId"):       # only a pinned run gets here; runs are never Stale
                section = "scheduled"
            else:
                section = "stale" if now - s["lastActivityAt"] > STALE_MS else "main"
        else:
            section = "quiet"
        lists[section].append(card)
    for s in latest:
        state_name = classify(s, now)
        if state_name in NEEDS_YOU:            # a recurring task's latest run is never Stale
            lists["scheduled"].append(_card(s, state_name, projects, now))

    hidden = []
    for section in SECTIONS:
        visible = []
        for card in lists[section]:
            by = None if card.get("pinned") else hidden_by(card, state, now)
            if by:
                hidden.append(dict(card, section=section, hiddenBy=by))
            else:
                visible.append(card)
        lists[section] = _sort(visible)

    needs_you = lists["main"] + lists["scheduled"]
    status = {"schema": 1, "generatedAt": now, "error": None, "projects": projects["projects"]}
    status.update(lists)
    status["working"] = _sort(working)
    status["hidden"] = _sort(hidden)
    status["folders"] = folder_list(sessions, projects)
    status["counts"] = {
        "main": len(needs_you),
        "asked": sum(1 for c in needs_you if c["state"] == "asked"),
        "working": len(working),
        "pinned": len(pins & {s["sessionId"] for s in live}),
        "stale": len(lists["stale"]),
        "quiet": len(lists["quiet"]),
        "hidden": len(hidden),
        "scanned": total,
    }
    return status


def _ensure_private_folder(folder):
    """Create the data folder if it's missing, and mark it ignored by Dropbox (best effort, macOS)."""
    if os.path.isdir(folder):
        return
    os.makedirs(folder, mode=0o700)
    try:
        import subprocess
        subprocess.run(["/usr/bin/xattr", "-w", "com.dropbox.ignored", "1", folder],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


def write_status(status, path):
    """Write atomically (temp file in the same folder, then os.replace). The file is private (0600)."""
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".status-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            # ASCII escapes: a title cut mid-emoji (a lone surrogate) can't break the write.
            json.dump(status, f, ensure_ascii=True, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)                 # our own temp file only
        raise


# Notifications (handoff §7) -----------------------------------------------------------------

NOTIFY_TITLE = "Sessionbell"
# The text arrives as argv, never inside the script, so a title can't change what the script does.
NOTIFY_SCRIPT = "on run argv\ndisplay notification (item 2 of argv) with title (item 1 of argv)\nend run"
TEST_BODY = "Test: a session asked you something"
GROUP_AT = 3                           # this many new questions at once become one banner


def load_previous(path):
    """The last status.json, or None when there isn't a usable one (then nothing notifies)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _seen_pairs(status):
    pairs = set()
    for key in ("main", "scheduled", "stale", "hidden"):     # hidden counts as seen: a snooze ending is silent
        cards = status.get(key)
        for c in cards if isinstance(cards, list) else []:
            if isinstance(c, dict):
                pairs.add((c.get("sessionId"), c.get("needs")))
    return pairs


def new_questions(previous, current):
    """Asked cards whose (session, question) pair wasn't in the previous status. No baseline: none."""
    if not isinstance(previous, dict) or previous.get("error") or current.get("error"):
        return []
    seen = _seen_pairs(previous)
    return [c for c in current["main"] + current["scheduled"]
            if c["state"] == "asked" and (c["sessionId"], c["needs"]) not in seen]


def _osascript_with(title, body, run=None):
    import subprocess
    (run or subprocess.run)(["/usr/bin/osascript", "-e", NOTIFY_SCRIPT, title, body],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)


def _osascript(title, body):
    _osascript_with(title, body)


def notify(cards):
    """Titles only: questions can hold phone numbers or customer details, and banners show on the lock screen."""
    if len(cards) >= GROUP_AT:
        _osascript(NOTIFY_TITLE, "%d sessions asked you something" % len(cards))
    else:
        for c in cards:
            _osascript(NOTIFY_TITLE, c["title"])


# Command line -------------------------------------------------------------------------------

def _ago(ms):
    minutes = ms // 60_000
    if minutes < 60:
        return "%dm" % minutes
    if minutes < 24 * 60:
        return "%dh" % (minutes // 60)
    return "%dd" % (minutes // (24 * 60))


def _print_list(status, sessions, cfg):
    if status["error"]:
        print("ERROR: " + status["error"])
        return
    names = {p["id"]: p["name"] for p in status["projects"]}
    for p in status["projects"]:
        for c in p.get("children", []):
            names[c["id"]] = c["name"]

    def show(title, cards, extra=None):
        print("\n%s (%d)" % (title, len(cards)))
        for c in cards:
            where = names.get(c["subproject"] or c["project"], c["project"])
            line = "  %-12s %-6s %-22s %s" % (c["state"], _ago(c["waitingMs"]), where[:22], c["title"])
            if extra:
                line += "  [%s]" % extra(c)
            print(line)
            if c["needs"]:
                print("  %s %s" % (" " * 42, c["needs"][:160]))

    show("Needs you", status["main"])
    show("Scheduled tasks", status["scheduled"])
    show("Working", status["working"])
    show("Stale: archive or revive?", status["stale"])
    show("Quieter", status["quiet"])
    show("Hidden", status["hidden"], lambda c: c["hiddenBy"]["kind"] + " from " + c["section"])

    unmatched = {}
    for s in sessions:
        if s.get("isArchived") is True:
            continue
        folder, _ = _folder(s.get("cwd"))
        if not folder:
            folder = "(no folder)"
        elif _rule_for(folder, cfg["rules"]):
            continue
        unmatched[folder] = unmatched.get(folder, 0) + 1
    print("\nFolders with no rule in projects.json (they go to \"%s\"): %d" % (cfg["default"], len(unmatched)))
    for folder in sorted(unmatched):
        print("  %3d  %s" % (unmatched[folder], folder))


def _error_kind(error):
    """The error's category, without the folder or project names a projects.json error can carry."""
    if error.startswith("projects.json"):
        return "projects.json problem"
    if error.startswith("No session files"):
        return "no session files"
    if error.startswith("Can't read session status"):
        return "format may have changed"
    return "scanner failed"


def _print_summary(status, sessions, cfg):
    """Counts only: no titles, no folders, no project names. Projects are shown by menu position."""
    if status["error"]:
        print("error: " + _error_kind(status["error"]))
        print("scanned: %d" % status["counts"]["scanned"])
        return
    counts = status["counts"]
    print("scanned: %d" % counts["scanned"])
    print("needs you: %d (asked %d)" % (counts["main"], counts["asked"]))
    for key in ("main", "scheduled", "working", "stale", "quiet", "hidden"):
        by_state = {}
        for c in status[key]:
            by_state[c["state"]] = by_state.get(c["state"], 0) + 1
        detail = ", ".join("%s %d" % (k, by_state[k]) for k in sorted(by_state, key=RANK.get))
        print("%s: %d%s" % (key, len(status[key]), " (" + detail + ")" if detail else ""))
    order = [p["id"] for p in status["projects"]]
    for i, pid in enumerate(order, 1):
        cards = [c for c in status["main"] + status["scheduled"] if c["project"] == pid]
        asked = sum(1 for c in cards if c["state"] == "asked")
        print("project #%d: needs you %d (asked %d)" % (i, len(cards), asked))
    unmatched = {_folder(s.get("cwd"))[0] for s in sessions if s.get("isArchived") is not True}
    unmatched = {f for f in unmatched if f and not _rule_for(f, cfg["rules"])}
    print("folders with no rule: %d" % len(unmatched))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write status.json from the Claude app's session files.")
    ap.add_argument("--sessions-dir", default=SESSIONS_DIR)
    ap.add_argument("--transcripts-dir", default=TRANSCRIPTS_DIR)
    ap.add_argument("--projects", default=os.path.join(HERE, "projects.json"))
    ap.add_argument("--state", default=STATE_PATH)
    ap.add_argument("--out", default=STATUS_PATH)
    show = ap.add_mutually_exclusive_group()
    show.add_argument("--print", action="store_true", help="print the grouped list with titles")
    show.add_argument("--summary", action="store_true", help="print counts only, no titles or folders")
    ap.add_argument("--no-notify", action="store_true", help="don't send banners for new questions")
    ap.add_argument("--notify-test", action="store_true", help="send one made-up banner and exit")
    args = ap.parse_args(argv)

    if args.notify_test:
        _osascript(NOTIFY_TITLE, TEST_BODY)
        return 0

    now = int(time.time() * 1000)
    previous = load_previous(args.out)
    sessions, total, cfg = [], 0, None
    try:
        sessions, problems, total = read_sessions(args.sessions_dir)
        attach_asks(sessions, args.transcripts_dir)
        attach_subagents(sessions, args.transcripts_dir, now)
        attach_doing(sessions, args.transcripts_dir, now)
        cfg, error = load_projects(args.projects)
        if error:
            status = error_status(error, total, now)
        else:
            status = build_status(sessions, problems, total, cfg, load_state(args.state), now)
    except Exception as e:  # never leave an old calm status.json behind after a crash
        status = error_status("The scanner failed (%s). Run python3 scanner.py by hand to see why."
                              % e.__class__.__name__, total, now)
        if not args.summary:
            import traceback
            traceback.print_exc()
    _ensure_private_folder(os.path.dirname(os.path.abspath(args.out)))
    write_status(status, args.out)
    if not args.no_notify:
        try:
            notify(new_questions(previous, status))
        except Exception:  # a banner failing must never stop the scan
            pass

    shown = cfg or {"default": "?", "rules": []}
    if args.print:
        _print_list(status, sessions, shown)
    elif args.summary:
        _print_summary(status, sessions, shown)
    if status["error"]:
        # --summary is the agent-safe mode: say the kind of error, never the folder or project names.
        detail = _error_kind(status["error"]) if args.summary else status["error"]
        print("scanner: error: " + detail, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
