"""Checks the shared records against their schemas and against each other: one line per kind of fault.

python -I records.py check [--env <job-search.env>]
  prints "check: <id>: ..." for each fault, then "check: <n> record faults"; exit 0. export_dashboard.py --check
  prints the same lines among its own. It reads every record file and writes none: safe on a copy of a folder.

Ids (one owner each; examples use made-up jobs). Rows with one fault share one line, which names up to 8 of them
and counts the rest, so a large tracker gives a few lines:
  shape     a key with spaces around it, a value of the wrong type or outside its vocabulary
            (templates/schemas/<kind>.schema.json), a PIPELINE key no reader knows. Example: "shape: tracker J7
            status: 'needs-jane' is not one of found, ..."
  sent      a submitted job with no applied date, or naming no CV (the redesign's rule: a sent job names both). A
            split row's CV is in its detail file, which this check does not open: split rows are left out of it.
  waits     a waiting job with no waits_on; a needs-* job with no to-do, open question or live session; an
            account-needed job with no site named; a wait or sign-in to-do naming a job board while the application
            is on the employer's own site (a board is the login only for its own form: Easy Apply, Indeed Apply).
  links     a question, session or PIPELINE entry naming a job the tracker does not have; a same_as or repeat_of
            naming nothing.
  dupes     one id on two tracker or LOGINS rows; the same employer and role sent twice with no repeat_of (one line
            per pair, with its command, up to 8 pairs).
  steps     a running process's step whose due date, else its date, passed with neither done nor cancelled (a
            take-home given on Monday and due Friday is not late on Tuesday); an older step whose done is only the
            word in its how. An ended process is left out: its past steps are history.
  employer  a job not sent yet of an employer the records exclude.
A line ends with the command that fixes it, where one does. Not here, by design: "pages behind" (export_dashboard.py
and questions.py compare what each page shows, so a write that changes no page row asks for no upload), and the
export's lines that read its merged logins or the page's rows (a sign-in with no LOGINS row, two rows for one site,
the to-do lines).
"""
import collections
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jsenv  # noqa: E402
import recordlib as rl  # noqa: E402
from reposts import repeat_pairs  # noqa: E402
from trackerlib import (BOARD_NAME, ENDED_STAGE, ENDED_STATUS, ON_BOARD, flat_jobs, login_of, step_done,  # noqa: E402
                        waits_on_person)

SHOWN = 8  # rows named on one line; the rest are counted


def listed(items, sep=", "):
    items = list(items)
    return sep.join(items[:SHOWN]) + (f" and {len(items) - SHOWN} more" if len(items) > SHOWN else "")


def load_all(env, loaded=None):
    """{kind: data} of every record file; {} for a kind whose key is unset or whose file is missing."""
    out = dict(loaded or {})
    for kind, (key, default) in rl.KINDS.items():
        if kind == "changes" or kind in out:
            continue
        out[kind] = rl.load(env, kind)[0] if env.get(key) or default is not None or kind == "tracker" else {}
    return out


def shape(records):
    # (kind, where with [n] as [], the message with its value taken out) -> [(row id, where, message, value)]
    groups = collections.defaultdict(list)
    for kind, data in records.items():
        sch = rl.schema(kind)
        for rid, row in rl.rows(kind, data).items():
            node = sch["$defs"]["company" if kind == "tracker" and rid.startswith("company:") else rl.ROW_DEF[kind]]
            for where, message in rl.faults(row, node, sch, ""):
                where = where.strip()
                value = re.search(r"'([^']*)'", message)
                bare = re.sub(r"'[^']*'", "<value>", message, count=1)
                groups[(kind, re.sub(r"\[\d+\]", "[]", where), bare)].append(
                    (rid, where, message, value.group(1) if value else None))
    out = []
    for (kind, where, bare), hits in sorted(groups.items()):
        fix = " -> track.py set <id> <the status meant>" if (kind, where) == ("tracker", "status") else ""
        if len(hits) == 1:
            rid, real, message, _ = hits[0]
            out.append(f"shape: {kind} {rid} {real + ': ' if real else ''}{message}{fix}")
            continue
        values = sorted({v for *_, v in hits if v is not None})
        named = f"; values {listed(repr(v) for v in values)}" if values else ""
        out.append(f"shape: {kind} {where + ': ' if where else ''}{bare}: {len(hits)} rows "
                   f"({listed(rid for rid, *_ in hits)}){named}{fix}")
    return out


def sent(jobs):
    out = []
    submitted = [j for j in jobs if j.get("status") == "submitted"]
    no_date = [j["id"] for j in submitted if not j.get("applied")]
    no_cv = [j["id"] for j in submitted if not j.get("details")  # a split row: its CV is in the detail file
             and not (j.get("cv") or (j.get("prep") or {}).get("cv_pdf"))]
    if no_date:
        out.append(f"sent: {len(no_date)} submitted with no applied date: {listed(no_date)} -> track.py set <id> "
                   "submitted \"\" applied=<date>")
    if no_cv:
        out.append(f"sent: {len(no_cv)} submitted naming no CV: {listed(no_cv)} -> track.py set <id> submitted \"\" "
                   "cv=<the CV sent>")
    return out


def waits(jobs, records):
    asked = {j for q in rl.rows("questions", records["questions"]).values() if isinstance(q, dict)
             and q.get("status") == "open" for j in q.get("jobs") or []}
    live = {j for s in rl.rows("sessions", records["sessions"]).values() if isinstance(s, dict)
            and s.get("state") != "done" for j in s.get("jobs") or []}
    gaps, nosite, boards = collections.defaultdict(list), [], []
    for job in jobs:
        status = job.get("status") or ""
        if not waits_on_person(status):
            continue
        held = job.get("waits_on") if isinstance(job.get("waits_on"), dict) else {}
        gap = ([] if held else ["no waits_on"]) + \
              (["no to-do"] if status != "account-needed" and not job.get("todo") and job["id"] not in asked
               and job["id"] not in live else [])
        if gap:
            gaps[(status, " and ".join(gap))].append(job["id"])
        named = [held.get("login") or ""] + [t.get("login") or "" for t in job.get("todo") or []
                                             if isinstance(t, dict) and t.get("kind") == "click"]
        board = next((n for n in named if BOARD_NAME.search(n) and not ON_BOARD.search(n)), "")
        if board and not ON_BOARD.search(job.get("platform") or ""):
            boards.append(f"{job['id']} ({board})")  # one line per job: the board line names its missing site
        elif status == "account-needed" and not login_of(job):
            nosite.append(job["id"])
    out = [f"waits: {status} with {gap}: {listed(ids)} -> track.py wait <id> "
           f"{status if status in ('account-needed', 'needs-captcha') else 'needs-person'} \"<what>\""
           for (status, gap), ids in sorted(gaps.items())]
    if nosite:
        out.append(f"waits: account-needed with no site named: {listed(nosite)} -> track.py wait <id> account-needed "
                   "\"<what>\" login=\"<platform> · <employer>\"")
    if boards:
        out.append(f"waits: a wait or sign-in to-do names a job board, but the application is on the employer's site: "
                   f"{listed(boards)} -> track.py wait <id> account-needed \"<what>\" login=<the employer's site>")
    return out


def links(jobs, records):
    ids, out = {j["id"] for j in jobs}, []
    for kind, fix in (("questions", ""), ("sessions", " -> sessions.py set <id> jobs=<ids>")):
        bad = []
        for rid, row in sorted(rl.rows(kind, records[kind]).items()):
            missing = [j for j in (row.get("jobs") or [] if isinstance(row, dict) else []) if j not in ids]
            if missing:
                bad.append(f"{rid} ({', '.join(missing)})")
        if bad:
            out.append(f"links: {len(bad)} {kind[:-1]}(s) naming jobs not in the tracker: {listed(bad, '; ')}{fix}")
    entries = rl.rows("pipeline", records["pipeline"])
    strays = sorted(p for p in entries if p not in ids)
    if strays:
        out.append(f"links: PIPELINE entries of no tracker job: {listed(strays)}")
    shared = [f"{pid} ({entry['same_as']})" for pid, entry in sorted(entries.items())
              if isinstance(entry, dict) and entry.get("same_as") and entry["same_as"] not in entries]
    if shared:
        out.append(f"links: same_as naming no PIPELINE entry: {listed(shared)}")
    repeats = [f"{j['id']} ({j['repeat_of']})" for j in jobs if j.get("repeat_of") and j["repeat_of"] not in ids]
    if repeats:
        out.append(f"links: repeat_of naming no tracker job: {listed(repeats)}")
    return out


def dupes(jobs, records):
    out = []
    twice = sorted(i for i, n in collections.Counter(j["id"] for j in jobs).items() if n > 1)
    if twice:
        out.append(f"dupes: one id on two tracker rows: {listed(twice)}")
    rows = records["logins"].get("logins") if isinstance(records["logins"], dict) else None
    logins = collections.Counter(r.get("id") for r in rows or [] if isinstance(r, dict))
    again = sorted(str(i) for i, n in logins.items() if n > 1)
    if again:
        out.append(f"dupes: one id on two LOGINS rows: {listed(again)} -> keep one with the latest check")
    pairs = [(first, job) for first, job in repeat_pairs(jobs, records["pipeline"]) if job.get("repeat_of") != first]
    for first, job in pairs[:SHOWN]:
        out.append(f"dupes: the same employer and role twice: {first} and {job['id']} {job.get('company') or ''} "
                   f"\"{(job.get('title') or '')[:60]}\" -> track.py set {job['id']} {job.get('status') or 'submitted'} "
                   f"\"\" repeat_of={first}")
    if len(pairs) > SHOWN:
        rest = [f"{job['id']} (of {first})" for first, job in pairs[SHOWN:]]
        out.append(f"dupes: {len(rest)} more of the same employer and role: {listed(rest)} -> track.py set <id> "
                   "<its status> \"\" repeat_of=<the earlier id>")
    return out


def steps(pipeline, today):
    late, worded = [], []
    for pid, entry in sorted(rl.rows("pipeline", pipeline).items()):
        if not isinstance(entry, dict) or entry.get("stage") in ENDED_STAGE:
            continue  # an ended process: its past steps are history
        for n, step in enumerate(entry.get("steps") or [], 1):
            if not isinstance(step, dict) or step.get("cancelled"):
                continue
            if step_done(step):
                if not step.get("done"):
                    worded.append(f"{pid} step {n}")
                continue
            # The due date first: a take-home given on Monday and due Friday is not late on Tuesday.
            due, day = str(step.get("due") or "")[:10], str(step.get("date") or "")[:10]
            when = due or day
            if when and when < today:
                late.append(f"{pid} step {n} \"{step.get('name') or ''}\" {'due' if due else 'on'} {when}")
    out = []
    if late:
        out.append(f"steps: {len(late)} past step(s) not done: {listed(late, '; ')} -> track.py step <id> done <n> "
                   "<date>, or cancel <n>")
    if worded:
        out.append(f"steps: {len(worded)} step(s) done only in its how text: {listed(worded)} -> track.py step <id> "
                   "done <n> <date>")
    return out


def employer(env, jobs, pipeline):
    import employerlib as el
    try:
        excluded = el.excluded_list(env, jobs, pipeline)
    except SystemExit:  # no employer rules readable: nothing to compare with
        return []
    out, open_jobs = [], [j for j in jobs if (j.get("status") or "") not in ("submitted",) + ENDED_STATUS]
    for row in excluded:
        names = row.get("names") or [row["id"]]
        keys = set().union(*(el.keys(n) for n in names))
        group = row["employer"].endswith(" and its group")
        hits = [j["id"] for j in open_jobs if el.keys(j.get("company") or "") & keys
                or (group and el.covered_by(j.get("company") or "", names))]
        if hits:
            since = f", since {row['since']}" if row.get("since") else ""
            out.append(f"employer: {row['id']} is excluded ({row['by']}{since}), not sent yet: {listed(hits)} "
                       f"-> track.py set <id> excluded \"employer excluded: {row['id']}\"")
    return out


def check(env, today=None, loaded=None):
    """The fault lines, each "<id>: ...". loaded: {kind: data} already read by the caller."""
    today = today or datetime.date.today().isoformat()
    records = load_all(env, loaded)
    jobs = flat_jobs(records["tracker"])
    return (shape(records) + sent(jobs) + waits(jobs, records) + links(jobs, records) + dupes(jobs, records)
            + steps(records["pipeline"], today) + employer(env, jobs, records["pipeline"]))


def main(argv):
    args, env_arg = argv[1:], None
    if "--env" in args:
        i = args.index("--env")
        env_arg = args[i + 1]
        del args[i:i + 2]
    if args != ["check"]:
        sys.exit(__doc__)
    lines = check(jsenv.load(env_arg, __file__))
    for line in lines:
        print("check:", line)
    print(f"check: {len(lines)} record faults")


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")  # a cp1252 console and a site named "Workday · Acme"
    main(sys.argv)
