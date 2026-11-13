"""The person's open sessions and the order to answer them (SESSIONS in job-search.env, default apply/sessions.json).

python -I sessions.py sync <list.json>                  take in the app's session list, saved as a file
python -I sessions.py set <id|name> [key=value ...]     keys: state=you|ready|done, waits="<what it waits on>",
                                                        jobs=J1,J2 (the job in hand first; empty clears),
                                                        due=<date>|none, tab=yes|no (it holds a filled form open
                                                        in a browser tab), steps=<n>|none (the person's steps
                                                        left to finish it), name=<short name>
python -I sessions.py order <id|name> ... | auto        these first, in this order; the rule orders the rest.
                                                        auto: the rule alone
python -I sessions.py show                              the order, one line per session, and each title to set
The coordinator keeps this record; the dashboard only reads it (export_dashboard.py cannot call the app).
A session: {id, name, title, state, waits, jobs, due, tab, steps, since, active, running, link}. state: you (it waits on
the person), ready (it works alone), done (its report is recorded): the three title prefixes "You · ", "Ready · ",
"Done · ". The record's state is the source and the title follows: show prints "rename <id> to: Done · Acme open
questions" where a title's prefix differs.
sync reads the list as the app's session tool returns it: an array of {sessionId, title, cwd, isArchived,
isRunning, lastActivityAt, name, link}. Ask for 200 sessions, archived included: the tool lists 20 by default. A new
session in the main folder is added with the state of its title's prefix (none: ready); a known one gets its
title, running and last activity, and keeps its state; one the list marks archived is dropped and named; one
missing from the list stays and is named. The main session ("Job search coordinator") is no row.
The order of the sessions that wait on the person: the ones named by `order`; then urgent (an Urgent to-do, or a
task due today or tomorrow, on one of its jobs); then a fixed date, the nearest first (due, else the earliest
coming step or to-do date of its jobs); then a form held open in a browser tab (tab=yes); then the fewest steps left
(steps=<n>); then the rest, the longest wait first. The coordinator's list of questions and the dashboard's Do now
use this one order. Example: 1 apply-acme (urgent), 2 study-beta (by 2026-11-16), 3 apply-gamma (form open in a tab),
4 answers-delta (1 step left). An older record's "quick": true reads as one step left.
Add --env <job-search.env> anywhere to pick the env file.
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jsenv  # noqa: E402
from trackerlib import ISO_DATE, ended, flat_jobs, pipeline_entry, step_done  # noqa: E402

STATES = ("you", "ready", "done")
PREFIX = {"you": "You", "ready": "Ready", "done": "Done"}
TITLE = re.compile(r"^(You|Ready|Done) · ")
MAIN_TITLE = "Job search coordinator"


def record_path(env):
    return env.path("SESSIONS") if env.get("SESSIONS") else os.path.join(env.home, "apply", "sessions.json")


def load(env):
    path = record_path(env)
    if not os.path.exists(path):
        return {"_about": "The person's open sessions and the order to answer them. Written by the coordinator "
                          "through sessions.py; the dashboard reads it.", "synced": "", "order": [], "sessions": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(env, data):
    path = record_path(env)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(path + ".tmp", path)


def split_title(title):
    """(state, the title without its prefix): ("you", "Acme open questions") for "You · Acme open questions"."""
    found = TITLE.match(title or "")
    return (found.group(1).lower(), title[found.end():]) if found else ("", title or "")


def title_for(session):
    return f"{PREFIX[session['state']]} · {split_title(session.get('title', ''))[1]}"


def facts(session, by_id, pipeline, today):
    """(urgent, date, sends) of a session, from its jobs: an Urgent to-do or a task due today or tomorrow; its own
    due, else the earliest coming to-do or step date; how many of its jobs are not sent yet."""
    tomorrow = (datetime.date.fromisoformat(today) + datetime.timedelta(days=1)).isoformat()
    jobs = [by_id[j] for j in session.get("jobs", []) if j in by_id]
    open_jobs = [j for j in jobs if not ended(j, pipeline)[0]]
    urgent, coming = False, []
    for job in open_jobs:
        for t in job.get("todo") or []:
            due = t.get("due") or ""
            urgent = urgent or t.get("kind") == "urgent" or (t.get("kind") == "task" and today <= due <= tomorrow)
            coming += [due] if due >= today else []
        for step in pipeline_entry(pipeline, job["id"]).get("steps") or []:
            if not step.get("cancelled") and not step_done(step):
                coming += [d for d in (str(step.get(k) or "")[:10] for k in ("date", "due")) if d >= today]
    sends = sum(1 for j in open_jobs if j.get("status") != "submitted")
    return urgent, session.get("due") or (min(coming) if coming else ""), sends


def steps_left(session):
    """The person's steps left to finish the session's work, or 0 when nobody said; an older "quick" is one step."""
    return int(session.get("steps") or 0) or (1 if session.get("quick") else 0)


def ranked(data, jobs, pipeline, today):
    """Every session as a row with its rank (1.. for the ones that wait on the person, 0 for the others), date and
    why it stands there: the waiting ones in the order to answer them, then the ones that work alone, then done."""
    by_id = {j["id"]: j for j in jobs}
    explicit = {sid: n for n, sid in enumerate(data.get("order") or [])}
    rows = []
    for s in data.get("sessions") or []:
        urgent, date, sends = facts(s, by_id, pipeline, today)
        since = s.get("since") or ""
        if s["id"] in explicit:
            key, why = (0, explicit[s["id"]], "", ""), "set by Claude"
        elif urgent:
            key, why = (1, 0, date or "9999", since), "urgent"
        elif date:
            key, why = (2, 0, date, since), f"by {date}"
        elif s.get("tab"):
            key, why = (3, 0, "", since), "form open in a tab"
        elif steps_left(s):
            n = steps_left(s)
            key, why = (4, n, "", since), f"{n} step{'' if n == 1 else 's'} left"
        else:
            key, why = (5, 0, "", since), f"waiting since {since}" if since else "waiting"
        rows.append((STATES.index(s.get("state", "ready")), key if s.get("state") == "you" else (9, 0, "", since),
                     dict(s, date=date, sends=sends, why=why if s.get("state") == "you" else "")))
    rows.sort(key=lambda r: (r[0], r[1]))
    out, n = [], 0
    for state, _, row in rows:
        n += 1 if state == 0 else 0
        out.append(dict(row, rank=n if state == 0 else 0))
    return out


def find(data, word):
    rows = data.get("sessions") or []
    hit = [s for s in rows if s["id"] == word] or [s for s in rows if s.get("name") == word]
    if len(hit) != 1:
        sys.exit(f"{'no' if not hit else 'more than one'} session {word!r} in the record: `sessions.py show` lists "
                 "them; a new one comes in with `sessions.py sync <list.json>`")
    return hit[0]


def same_folder(a, b):
    norm = lambda p: os.path.normcase(os.path.normpath(p or "")).replace("\\", "/").rstrip("/")  # noqa: E731
    return bool(a) and norm(a) == norm(b)


def sync(env, data, path, today):
    with open(path, encoding="utf-8") as f:
        listed = json.load(f)
    listed = listed.get("sessions", []) if isinstance(listed, dict) else listed
    known = {s["id"]: s for s in data.get("sessions") or []}
    seen, added, dropped = set(), [], []
    for row in listed:
        sid = row.get("sessionId") or row.get("id")
        if not sid or (sid not in known and not same_folder(row.get("cwd"), env.home)):
            continue  # another project's session
        if row.get("title") == MAIN_TITLE:
            known.pop(sid, None)  # the main session: the person is in it, so it is no row
            continue
        seen.add(sid)
        if row.get("isArchived"):
            if sid in known:
                dropped.append(known.pop(sid))
            continue
        s = known.get(sid)
        if s is None:
            s = known[sid] = {"id": sid, "name": row.get("name") or "",
                              "state": split_title(row.get("title"))[0] or "ready", "waits": "", "jobs": [],
                              "since": today}
            added.append(s)
        s.update(title=row.get("title") or "", running=bool(row.get("isRunning")),
                 active=(row.get("lastActivityAt") or "")[:16], link=row.get("link") or "")
        if row.get("name"):
            s["name"] = row["name"]
    data["sessions"] = list(known.values())
    data["order"] = [sid for sid in data.get("order") or [] if sid in known]
    data["synced"] = datetime.datetime.now().replace(microsecond=0).isoformat()
    label = lambda s: s.get("name") or s["id"]  # noqa: E731
    missing = [s for sid, s in known.items() if sid not in seen]
    print(f"{len(known)} sessions: {len(added)} added, {len(dropped)} archived and dropped, "
          f"{len(missing)} not in the list")
    for word, rows in (("added", added), ("dropped", dropped), ("not in the list (it stays; list 200, archived "
                                                                   "included)", missing)):
        if rows:
            print(f"{word}: " + ", ".join(f"{label(s)} ({s['state']})" for s in rows))


def set_fields(env, data, word, pairs, today):
    s = find(data, word)
    for pair in pairs:
        key, eq, value = pair.partition("=")
        if key == "quick":
            sys.exit("quick is gone: steps=1 says one step is left, tab=yes that a filled form is open in a tab")
        if not eq or key not in ("state", "waits", "jobs", "due", "tab", "steps", "name"):
            sys.exit(f"expected state=, waits=, jobs=, due=, tab=, steps= or name=, got {pair!r}")
        if key == "state":
            if value not in STATES:
                sys.exit(f"state is one of {', '.join(STATES)}")
            if value != s.get("state"):
                s["since"] = today
            s["state"] = value
        elif key == "jobs":
            ids = [j for j in value.split(",") if j]
            with open(env.path("TRACKER"), encoding="utf-8") as f:
                tracked = {j["id"] for j in flat_jobs(json.load(f))}
            unknown = [j for j in ids if j not in tracked]
            if unknown:
                sys.exit(f"not in the tracker: {', '.join(unknown)}")
            s["jobs"] = ids
        elif key == "due":
            if value not in ("", "none") and not ISO_DATE.fullmatch(value):
                sys.exit(f"due is a date, YYYY-MM-DD, or none: got {value!r}")
            s["due"] = "" if value == "none" else value
        elif key == "tab":
            if value not in ("yes", "no"):
                sys.exit("tab is yes or no")
            s["tab"] = value == "yes"
        elif key == "steps":
            if value not in ("", "none") and not value.isdigit():
                sys.exit(f"steps is a number, or none: got {value!r}")
            s["steps"] = 0 if value in ("", "none") else int(value)
            s.pop("quick", None)
        else:
            s[key] = value
    print(s.get("name") or s["id"], "->", ", ".join(f"{k}={s.get(k)}" for k in ("state", "waits", "jobs", "due", "tab", "steps")
                                                   if s.get(k) not in (None, "", [], False, 0)))


def show(env, data, today):
    with open(env.path("TRACKER"), encoding="utf-8") as f:
        jobs = flat_jobs(json.load(f))
    pipeline_path = env.path("PIPELINE") if env.get("PIPELINE") else ""
    pipeline = {}
    if pipeline_path and os.path.isfile(pipeline_path):
        with open(pipeline_path, encoding="utf-8") as f:
            pipeline = json.load(f)
    rows = ranked(data, jobs, pipeline, today)
    for s in rows:
        print(f"{s['rank'] or '-':>2} {s['state']:5} {(s.get('name') or s['id']):24} {s['why']:22} "
              f"{s.get('waits', '')}" + (f"  [{', '.join(s['jobs'])}]" if s.get("jobs") else ""))
    for s in rows:
        if s.get("title") and s["title"] != title_for(s):
            print(f"rename {s['id']} to: {title_for(s)}")
    print(f"{len(rows)} sessions; synced {data.get('synced') or 'never'}")


def main():
    args = sys.argv[1:]
    env_arg = None
    if "--env" in args:
        i = args.index("--env")
        env_arg = args[i + 1]
        del args[i:i + 2]
    if not args or args[0] not in ("sync", "set", "order", "show"):
        sys.exit(__doc__)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # a title may hold a character the console cannot print
    env = jsenv.load(env_arg, __file__)
    data = load(env)
    today = datetime.date.today().isoformat()
    if args[0] == "show":
        show(env, data, today)
        return
    if args[0] == "sync":
        if len(args) < 2:
            sys.exit("sessions.py sync <list.json>")
        sync(env, data, args[1], today)
    elif args[0] == "set":
        if len(args) < 3:
            sys.exit("sessions.py set <id|name> key=value ...")
        set_fields(env, data, args[1], args[2:], today)
    else:
        data["order"] = [] if args[1:] in ([], ["auto"]) else [find(data, word)["id"] for word in args[1:]]
        print("order:", ", ".join(data["order"]) or "auto (the rule alone)")
    save(env, data)


if __name__ == "__main__":
    main()
