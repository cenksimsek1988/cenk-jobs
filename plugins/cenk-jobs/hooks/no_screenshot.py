"""PreToolUse guard: no screenshot and no zoom in any browser in a job-search session (RULES.md, "Claude in Chrome").
Matched on the `computer` and `browser_batch` tools only (hooks.json), under the names Claude Code and the desktop
app give them: Claude in Chrome (`mcp__claude-in-chrome__*`, as agents/applier.md lists them) and the app's
built-in browser (`mcp__Claude_Browser__*`).

A job-search session works in the main folder, which holds job-search.env; a session anywhere else is not a
job-search session, and the hook lets its calls through: the plugin's rules do not reach other work.
Input: the hook's JSON on stdin (tool_name, tool_input, cwd). Output: nothing (allow), or the deny JSON.
A guardrail for a cooperating session, not an adversary control. It fails closed: a call whose input names a
screenshot or a zoom and cannot be read is denied. A python that cannot start is a hook error, which Claude Code lets
through: hooks.json sets no "onFailure": "block", since the matcher takes every click and keystroke of the computer
tool too, and one broken interpreter would then stop every form. check_setup.py checks python.
Example: {"tool_name": "mcp__claude-in-chrome__computer", "tool_input": {"action": "screenshot"}, "cwd": "<main
folder>"} is denied; the same with "left_click" is allowed.
"""
import json
import os
import sys

BLOCKED = ("screenshot", "zoom")
READ_INSTEAD = ("read the page with find, read_page (filter: interactive, max_chars 5000) or javascript_tool "
                "returning JSON (RULES.md, \"Claude in Chrome\").")


def asks_image(node):
    """True when an "action" anywhere in the call's input is a screenshot or a zoom (browser_batch nests them)."""
    if isinstance(node, dict):
        if str(node.get("action", "")).strip().lower() in BLOCKED:
            return True
        return any(asks_image(value) for value in node.values())
    if isinstance(node, list):
        return any(asks_image(value) for value in node)
    return False


def in_main_folder(cwd):
    """The session's folder, or one above it, holds job-search.env."""
    folder = os.path.abspath(cwd or os.getcwd())
    while True:
        if os.path.isfile(os.path.join(folder, "job-search.env")):
            return True
        parent = os.path.dirname(folder)
        if parent == folder:
            return False
        folder = parent


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))


def main():
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    if not any(word in raw.lower() for word in BLOCKED):
        return  # most calls are clicks and typing: no parse
    try:
        data = json.loads(raw)
        if asks_image(data.get("tool_input")) and in_main_folder(data.get("cwd")):
            deny("No screenshot or zoom in a job-search session: " + READ_INSTEAD)
    except Exception:  # noqa: BLE001 - fails closed: an unreadable call that names a screenshot or zoom is denied
        deny("This Chrome call names a screenshot or zoom and could not be read, so it is denied: " + READ_INSTEAD)


if __name__ == "__main__":
    main()
