"""Export the job search as the dashboard's tree of small JSON files, each fact in one file only.

Usage: python -I export_dashboard.py <out dir> [--env <job-search.env>]   write the files, then say what to upload
       python -I export_dashboard.py --check                               only the check lines; writes nothing
       python -I export_dashboard.py --uploaded <out dir>                  record these files as the ones on the page
Every run ends with one "check:" line per mismatch between the records and the page, then "check: <n> mismatches";
the exit code stays 0. Example: "check: to-do on an ended job: J3 (rejected 2026-11-10), 2 to-do(s) -> track.py
todo J3 done all". The lines: a folder not counted (two for one job, or of a job that ended); a to-do on an ended
job, set before its job was sent, without "since", or naming a session the record does not hold; a past due date; a
job whose site is signed in and that nobody started; a found or pending job with no owner; a job waiting on a
sign-in with no row; sign-ins not checked for days; a session that is over, whose title differs from its state or
names an employer whose jobs ended; a sessions record not synced for a day; PIPELINE and a folder with different
steps; an excluded employer without a source.
After the files it prints "upload:" (the files that differ from the ones on the page) and "unchanged:" (no new
upload needed), against the record --uploaded keeps beside the tracker (dashboard-uploads.json).
Writes, in <out dir>:
  index.json         the root: one row per headline count (stages, actions by kind, logins needing action) and the
                     export time. The page's tiles read only this, so it opens fast.
  applications.json  one row per application, keyed by the tracker's job id: company, role, stage, applied, where,
                     CV, folder. Read from APPLICATIONS_DIR/<stage>/<folder>/overview.md, one folder per job: a
                     not-applied folder counts only while the job is neither sent nor ended, and of two folders the
                     one in the stage the records give. Example: a sent job whose old not-applied folder is kept
                     for its notes.md is one row, under Waiting for reply.
  steps.json         one row per hiring step: its job id (app), name, date, due, details and state (upcoming, proposed,
                     done, past, cancelled, ended: a step left open on a job that is over) - no company or role, which the page takes from applications.json by the id.
                     The words come from the overview; date, due, done and cancelled from PIPELINE, the same
                     position. also: the applications that share the process (PIPELINE "same_as"). A wait on the
                     employer (a "waiting" to-do) is on the job's last done step (awaits, since), else a row of its
                     own (state waiting).
  actions.json       one row per thing the person can do now: kind click (sign in, open a page), info (an open
                     question on the Questions page, from QUESTIONS), todo (anything else a job waits on the person
                     for, from its note), task (a test, online tasks, an AI interview, a deadline), urgent (a step only the
                     person can do that expires: an emailed code, a filled form's CAPTCHA, a task due within 24
                     hours; first in the list), working (Claude or a
                     session with the person is on it: wait), late (a due date that passed: the person says whether
                     it was done) or queued (Claude's next: jobs nobody owns, one row per reason with their ids in
                     apps); each points at a job id (app) and/or a login id (login) instead of repeating them. A
                     "waiting" to-do is never here. An ended job's to-dos are not listed: none for a job ended by
                     its tracker status, and for one ended in PIPELINE only those set on or after that date.
                     Order: urgent, working, rows with a date (the earliest first), rows without one (the older
                     "since" first), queued.
  logins.json        one row per connector and job site (from LOGINS): status, when checked, how to fix it, and
                     how many jobs wait on it; stale "yes" for a connected or signed-in row last checked before the
                     last run started (no run recorded: more than LOGIN_CHECK_DAYS days ago). The site of an excluded employer is left out, whatever its last state: it needs no
                     sign-in.
  excluded.json      the person's one list of excluded employers (employerlib.excluded_list): employer, Excluded or
                     Withdrawn, by what (their decision or their rules), why (the category), the finding in words,
                     its source, since when, and the jobs it stopped.
  sessions.json      one row per session in SESSIONS (sessions.py; this script cannot call the app, so it only
                     reads that record): rank (1.. in the order to answer them, 0 when it does not wait on the
                     person), state (you, ready, done), title without its state prefix, what it waits on, its job
                     ids (apps), date, since, and why it stands there. Empty without a record.
Sessions in actions.json: a session that waits on the person is one row of kind session ("Answer first"), right
after the urgent rows, in rank order; one that works alone is one working row. A to-do that names a session
("session": <id>) is on that row, not a row of its own, unless it is urgent or late. Other rows of a session's jobs
come in the session order before age. A job in a session is never queued.
The calendar is not exported: the dashboard reads Google Calendar live (job-search events carry their own color).
Sources: the folders, TRACKER, PIPELINE, LOGINS and SESSIONS. Pay figures and street addresses never go into these files,
since anyone who can open the dashboard can read them.
"""
import datetime
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jsenv  # noqa: E402
import sessions as sl  # noqa: E402
from trackerlib import (ENDED_STATUS, ISO_DATE, employer_link, ended, flat_jobs, login_of, no_pay,  # noqa: E402
                        pipeline_entry, step_done, waits_on_person)

# "Closed": the position closed or was filled (not a rejection); "Declined": the person said no.
STAGES = {"approved": "Moving forward", "pending": "Waiting for reply", "rejected": "Rejected", "closed": "Closed",
          "declined": "Declined", "not-applied": "Not sent"}
FIELD = re.compile(r"^- \*\*(.+?):\*\*\s*(.*)$")
STEP = re.compile(r"^\d+\.\s+\*\*(.+?)\*\*\s*-\s*(.+)$")
# A markdown link; a target in <...> may hold spaces and parentheses (step folders such as "01 ... (45 min)").
LINK = re.compile(r"\[([^\]]*)\]\((?:<[^>]*>|[^)]*)\)")
TASKLIKE = re.compile(r"(?i)task|test|assessment|assignment|questionnaire|ai interview|video interview|form|challenge")
DONE_NOTE = re.compile(r"\bdone \d{4}-\d{2}-\d{2}")  # the overview's "done <date>" is not the step's own date
OK_LOGIN = ("connected", "signed-in")
# An excluded employer (by the person's rules) needs no sign-in, so it is never in Do now.
NO_ACTION = OK_LOGIN + ("excluded",)
LOGIN_CHECK_DAYS = 3  # a sign-in older than this is a check line; with no run recorded it also reads "not checked since"
# Do now's order: urgent (it expires), the sessions to answer, working (the person waits), everything else, then
# Claude's own queue.
GROUP = {"urgent": 0, "session": 1, "working": 2, "queued": 4}
KIND_RANK = {"late": 0, "task": 1, "click": 2, "todo": 3, "info": 4}
COUNTED = ("urgent", "session", "working", "task", "click", "todo", "info", "late", "queued")


def open_job(status):
    # Jobs that wait on the person (account-needed, needs-person, needs-captcha, an older "needs-<name>"), or are
    # ready to send.
    return waits_on_person(status) or status == "to-apply"


def plain(text):
    return re.sub(r"\s+", " ", LINK.sub(r"\1", text or "")).strip()


def short(text, n=220):
    text = no_pay(plain(text))
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + "…"


DONE = ("submitted", "excluded", "skipped", "closed", "declined", "failed")


def kind_by_due(kind, due, today):
    """A due date that passed is "late", never Urgent: the person says whether it was done. A task due today or
    tomorrow is Urgent (RULES.md, "Urgent steps"), whether a hiring step or a job's own to-do."""
    if due and due < today and kind != "working":
        return "late"
    tomorrow = (datetime.date.fromisoformat(today) + datetime.timedelta(days=1)).isoformat()
    return "urgent" if kind == "task" and due and due <= tomorrow else kind


def open_questions(path):
    """The Questions page's open questions from QUESTIONS ({} when the file is missing or unreadable)."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            questions = json.load(f).get("questions", {})
    except ValueError as e:
        print(f"warning: {path} is not valid JSON ({e}); Do now shows no questions", file=sys.stderr)
        return {}
    return {k: q for k, q in questions.items() if q.get("status") == "open"}


def employer_view(env):
    """A function: company -> (verdict, asks, warns), each finding {label, level, fact, src}, from the person's rules,
    their own checks and the shared blacklist (read once)."""
    import employerlib as el
    rule_set = el.rules(env)
    shared, own = el.blacklist(), el.checks_file(env)
    el.blacklist, el.checks_file = (lambda: shared), (lambda e: own)
    memo = {}

    def view(company):
        if company not in memo:
            checks = el.lookup(env, company, facts="flagged")
            verdict, _ = el.decide(env, company, checks, rule_set)
            asks, warns = [], []
            for cat, k in checks.items():
                s = rule_set["categories"].get(cat)
                if k.get("status") != "flagged" or s is None:
                    continue
                level = k.get("level", "direct")
                act = el.act_for(s, level)  # "ask" for an undecided level: neither a wait nor a warning here
                item = {"label": s.get("label", cat), "level": level, "fact": k.get("fact", ""),
                        "src": k.get("source_url", "")}
                (asks if act == "discuss" else warns if act == "warn" else []).append(item)
            memo[company] = (verdict, asks, warns)
        return memo[company]
    return view


def run_rows(env):
    """The usage log's "run" rows (started, then ok|failed|stopped), oldest first."""
    path = env.path("USAGE_LOG") if env.get("USAGE_LOG") else os.path.join(env.home, "apply", "usage-log.jsonl")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [r for r in (json.loads(line) for line in f if line.strip()) if r.get("step") == "run"]


def last_run_start(env):
    """When the last run started, or None: a login state older than that was not looked at in this run."""
    starts = [r["time"] for r in run_rows(env) if r.get("result") == "started"]
    try:
        return datetime.datetime.fromisoformat(starts[-1][:19]) if starts else None
    except ValueError:
        return None


def run_line(env):
    """Whether a run is going, from the usage log's "run" rows, and the next one."""
    rows = run_rows(env)
    # SEARCH_DAYS is what /cenk-jobs:schedule wrote from the task's real schedule: this script cannot read the task.
    days = (env.get("SEARCH_DAYS") or "weekdays").strip()
    if days.lower() == "none":
        nxt = "No run scheduled."
    else:
        nxt = f"Next: {'every day' if days.lower() == 'daily' else days} at {env.get('SEARCH_TIME') or '19:00'}."
    when = lambda r: r["time"][:16].replace("T", " ")
    starts = [r for r in rows if r.get("result") == "started"]
    if not starts:
        return "No run recorded yet. " + nxt
    start = starts[-1]
    ends = [r for r in rows if r.get("result") != "started" and r["time"] >= start["time"]]
    if not ends:
        return f"Running now, since {when(start)}. " + nxt
    end = ends[-1]
    return f"Last run {when(start)} to {end['time'][11:16]}: {'finished' if end['result'] == 'ok' else end['result']}. " + nxt


def dates(text):
    return re.findall(r"\d{4}-\d{2}-\d{2}", text or "")


def parse(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    out = {"title": lines[0].lstrip("# ").strip() if lines else "", "fields": {}, "steps": []}
    section = None
    for line in lines[1:]:
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        m = FIELD.match(line)
        if m and section is None:
            out["fields"][m.group(1).strip().lower()] = plain(m.group(2))
            continue
        m = STEP.match(line)
        if m and section == "hiring steps":
            # The step's links (prep, cheat-sheet, feedback) are files, not details: drop them whole.
            out["steps"].append({"name": m.group(1).strip(), "detail": plain(LINK.sub("", m.group(2))).rstrip(" .·")})
    return out


def stage_dir_of(job, pipeline):
    """The stage folder the records give a job: a sent one by its PIPELINE stage (pending without one), an open one
    not-applied, and "" for one that ended before it was sent (it has no folder)."""
    if job.get("status") == "submitted":
        stage = pipeline_entry(pipeline, job["id"]).get("stage")
        return stage if stage in STAGES and stage != "not-applied" else "pending"
    return "" if job.get("status") in ENDED_STATUS else "not-applied"


def application_folders(root, by_id, pipeline):
    """([(job id, stage folder, folder, parsed overview)], [(job id, stage folder, folder) not counted]): one folder
    per job id. A not-applied folder counts only while the job is neither sent nor ended; of two folders, the one in
    the stage the records give. A folder without a job id, or of a job the tracker does not know, counts as it is."""
    found, order = {}, []
    for stage_dir in STAGES:
        base = os.path.join(root, stage_dir)
        for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
            ov = os.path.join(base, name, "overview.md")
            if not os.path.isfile(ov):
                continue
            o = parse(ov)
            job_id = o["fields"].get("job id") or f"{stage_dir}/{name}"
            if job_id not in found:
                order.append(job_id)
            found.setdefault(job_id, []).append((stage_dir, name, o))
    chosen, extra = [], []
    for job_id in order:
        folders, job = found[job_id], by_id.get(job_id)
        if job is not None:
            want = stage_dir_of(job, pipeline)
            extra += [(job_id, s, n) for s, n, _ in folders if s == "not-applied" and want != "not-applied"]
            folders = sorted((f for f in folders if f[0] != "not-applied" or want == "not-applied"),
                             key=lambda f: f[0] != want)  # stable: the stage the records give first
        if folders:
            chosen.append((job_id, *folders[0]))
            extra += [(job_id, s, n) for s, n, _ in folders[1:]]
    stage_order = list(STAGES)
    chosen.sort(key=lambda c: (stage_order.index(c[1]), c[2]))
    return chosen, extra


def step_rows(job_id, overview, pipeline, also, today, over=""):
    """(rows, a check line or ""): one row per hiring step of an application. The overview's step lines give the
    words; PIPELINE's steps, when there are as many, give each one's date, due, done, cancelled and proposed (else
    the dates in the words, and a line that says the two differ). over: how the job ended ("rejected"), or "": a
    step of an ended job that was not done is "ended", never upcoming or past due. A proposed step is a date offered
    and not confirmed yet."""
    lines = overview["steps"]
    p_steps = pipeline_entry(pipeline, job_id).get("steps") or []
    aligned = len(p_steps) == len(lines)
    differ = "" if aligned or not lines else (f"{job_id}: {len(p_steps)} steps in PIPELINE, {len(lines)} in its "
                                              "folder -> build_app_folders.py")
    rows = []
    for i, s in enumerate(lines, 1):
        ps = p_steps[i - 1] if aligned else {}
        found = dates(DONE_NOTE.sub("", s["detail"]))
        date = str(ps.get("date") or "")[:10] or (found[0] if found else "")
        due = str(ps.get("due") or "")[:10] if aligned else (max(found) if len(found) > 1 else "")
        done = step_done(ps)
        last = max(date, due)
        coming = bool(last) and last >= today
        state = ("cancelled" if ps.get("cancelled") else "done" if done else "ended" if over else
                 "proposed" if ps.get("proposed") and (coming or not last) else "upcoming" if coming else "past")
        rows.append({"key": f"{job_id}#{i}", "app": job_id, "n": i, "step": no_pay(s["name"]), "date": date,
                     "due": due, "detail": short(s["detail"], 160), "upcoming": "yes" if state == "upcoming" else "no",
                     "state": state, "done": done if ISO_DATE.fullmatch(done) else "", "awaits": "", "since": "",
                     "also": also})
    return rows, differ


def checked_at(row):
    try:
        return datetime.datetime.fromisoformat((row.get("checked") or "").replace(" ", "T")[:19])
    except ValueError:
        return None


def stale_login(row, now, run_start=None):
    """A "connected" or "signed in" is what the last check found. One from before the last run started was not
    looked at in this run, so nobody knows whether it still holds; with no run recorded, one older than
    LOGIN_CHECK_DAYS days."""
    checked = checked_at(row)
    if row.get("status") not in OK_LOGIN or checked is None:
        return False
    if run_start is not None:
        return checked < run_start
    return now - checked > datetime.timedelta(days=LOGIN_CHECK_DAYS)


# A note that asks the person to sign in or to make an account contradicts a row that reads connected or signed in.
ASKS_SIGN_IN = re.compile(r"(?i)\b(sign[ -]?in|log[ -]?in|sign[ -]?up|register|(create|make|open)\b.{0,20}\baccount)\b")
NOT_ASKING = re.compile(r"(?i)\b(signed[ -]in|logged[ -]in|no (sign[ -]?in|account|login))\b")


def asks_sign_in(note):
    return bool(ASKS_SIGN_IN.search(NOT_ASKING.sub("", note or "")))


def session_checks(record, ranked, jobs, pipeline, today, now, keys):
    """The check lines about sessions: one whose date is past or whose jobs are all sent or ended and that is not
    done; a title whose prefix differs from the state; a title that names an employer whose jobs there have ended;
    a record not synced for more than a day. keys: employerlib.keys, an employer's names without its legal form."""
    out = []
    by_id = {j["id"]: j for j in jobs}
    at = {}  # employer -> its jobs
    for j in jobs:
        at.setdefault(j.get("company", ""), []).append(j)
    over = lambda j: j.get("status") == "submitted" or bool(ended(j, pipeline)[0])  # noqa: E731
    for s in ranked:
        name = s.get("name") or s["id"]
        if s["state"] != "done":
            mine = [by_id[j] for j in s.get("jobs") or [] if j in by_id]
            fix = f"-> sessions.py set {name} state=done, then rename it"
            if s.get("due") and s["due"] < today:
                out.append(f"session {name}: its date {s['due']} is past {fix}")
            elif not s["date"] and mine and all(over(j) for j in mine):
                out.append(f"session {name}: its jobs are all sent or ended {fix}")
            # Its title names an employer: over when the session's jobs there (else all the tracker's) have ended.
            words = " " + re.sub(r"[^a-z0-9]+", " ", sl.split_title(s.get("title", ""))[1].lower()).strip() + " "
            for company, theirs in at.items():
                there = [j for j in mine if j.get("company", "") == company] or theirs
                gone = [j for j in there if ended(j, pipeline)[0]]
                if gone and len(gone) == len(there) and any(len(k) > 3 and f" {k} " in words for k in keys(company)):
                    out.append(f"session {name}: the title names {company}, whose job {gone[0]['id']} is "
                               f"{ended(gone[0], pipeline)[0]}")
        said = sl.split_title(s.get("title", ""))[0]
        if s.get("title") and said != s["state"]:
            out.append(f"session {name}: its title says {said or 'no state'}, its state is {s['state']} "
                       f"-> rename it (sessions.py show)")
    if ranked:
        try:
            age = (now - datetime.datetime.fromisoformat(record.get("synced") or "")).days
        except ValueError:
            age = None
        if age is None or age >= 1:
            out.append("the sessions record was " + ("never synced" if age is None else f"synced {age} days ago")
                       + " -> sessions.py sync <list.json>")
    return out


def build(env, now):
    """([(file name, rows)], [check lines], the one-line summary): the seven files and what in the records disagrees
    with them. Writes nothing."""
    checks = []
    root = env.path("APPLICATIONS_DIR")
    today = now.date().isoformat()
    run_start = last_run_start(env)

    tracker = json.load(open(env.path("TRACKER"), encoding="utf-8"))
    pipeline_path = env.path("PIPELINE") if env.get("PIPELINE") else ""
    pipeline = json.load(open(pipeline_path, encoding="utf-8")) if pipeline_path and os.path.isfile(pipeline_path) else {}
    jobs = flat_jobs(tracker)
    by_id = {j["id"]: j for j in jobs}

    chosen, extra = application_folders(root, by_id, pipeline)
    known = {c[0] for c in chosen}
    counted = {c[0]: c[1] for c in chosen}
    for job_id, stage_dir, _ in extra:
        checks.append(f"duplicate folder: {job_id} in {counted[job_id]} and {stage_dir} (the second is not counted)"
                      if job_id in counted else
                      f"stale folder: {job_id} in {stage_dir}, the job is {by_id[job_id].get('status')} (not counted)")
    shared_by = {}  # the job whose steps are shared -> the applications that share them (PIPELINE "same_as")
    for job_id in sorted(known):
        own = pipeline.get(job_id)
        if isinstance(own, dict) and own.get("same_as"):
            shared_by.setdefault(own["same_as"], []).append(job_id)
    apps, steps = [], []
    for job_id, stage_dir, name, o in chosen:
        f = o["fields"]
        # Titles and folder names can carry a posted rate ("Java Engineer - EUR 400 a day"): mask them too.
        company, _, role = no_pay(o["title"]).partition(" - ")
        apps.append({"id": job_id, "stage": STAGES[stage_dir], "company": company.strip(), "role": role.strip(),
                     "applied": f.get("applied", ""), "where": no_pay(f.get("where", "")),
                     "cv": re.sub(r"^.*?-CV-", "", f.get("cv sent", "")).replace(".pdf", "").replace("-", " "),
                     "letter": "yes" if f.get("cover letter") and "none" not in f.get("cover letter", "").lower() else "no",
                     "status": short(f.get("status", ""), 160), "reminder": short(f.get("reminder", ""), 160),
                     "folder": no_pay(f"{os.path.basename(root)}/{stage_dir}/{name}")})
        rows, differ = step_rows(job_id, o, pipeline, shared_by.get(job_id, []), today,
                                 ended(by_id[job_id], pipeline)[0] if job_id in by_id else "")
        steps += rows
        checks += [differ] if differ else []

    view = employer_view(env)
    import employerlib as el
    excluded_rows = el.excluded_list(env, jobs, pipeline)
    # Findings are public facts about the employer, never the person's pay: plain text, not pay-masked.
    excluded = [{k: (re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else v) for k, v in x.items() if k != "names"}
                for x in excluded_rows]

    logins_path = env.path("LOGINS") if env.get("LOGINS") else ""
    all_logins = []
    if logins_path and os.path.exists(logins_path):
        all_logins = json.load(open(logins_path, encoding="utf-8")).get("logins", [])
    on_site = {}  # login id -> the employers of the tracker's jobs on it
    for job in jobs:
        on_site.setdefault(login_of(job), set()).add(job.get("company", ""))
    # An excluded employer's site needs no sign-in, whatever its last state: not in the tab, in Do now or in a count.
    logins = [r for r in all_logins if r.get("status") != "excluded" and r.get("kind") != "employer"
              and not (r.get("kind", "site") == "site" and el.excluded_site(r, excluded_rows, on_site.get(r["id"], ())))]
    login_by_id = {r["id"]: r for r in logins}
    login_rows = [{"id": r["id"], "name": r.get("name", r["id"]), "kind": r.get("kind", "site"),
                   "status": r.get("status", "unknown"), "checked": (r.get("checked") or "")[:16].replace("T", " "),
                   "note": short(r.get("note", ""), 160), "fix": short(r.get("fix", ""), 200), "link": r.get("link", ""),
                   "account": r.get("account", ""), "jobs": len(r.get("jobs", [])),
                   "stale": "yes" if stale_login(r, now, run_start) else ""}
                  for r in logins]
    sites = {r["id"] for r in all_logins}

    # The sessions, from the coordinator's record: the ones not done take the to-dos that name them.
    record = sl.load(env)
    ranked = sl.ranked(record, jobs, pipeline, today)
    live = {s["id"]: s for s in ranked if s["state"] != "done"}
    session_ids = {s["id"] for s in ranked}
    in_session = {j for s in live.values() for j in s.get("jobs") or []}
    folded = {}  # session id -> [(job id, to-do text)]

    actions = []
    waits = {}  # job id -> [(what the employer owes, since)], from its "waiting" to-dos
    owned = set()  # jobs with a row, a wait, a question or a session of their own
    row_job = {}  # action key -> job id, for the session order
    undated = []  # "<job id> (<n>)": open jobs with to-dos that have no "since" (older records)
    # Every row gets a link: its own, else the job's application page off the job boards.
    job_links = {j["id"]: employer_link(j, login_of(j)) or j.get("apply_url", "") for j in jobs}
    # The Questions page's open questions (QUESTIONS): Do now's Question rows, one each, so the two never differ; a
    # job with an open question there shows no other row from its note.
    qpath = env.path("QUESTIONS") if env.get("QUESTIONS") else os.path.join(env.home, "apply", "questions.json")
    qs_open = open_questions(qpath)
    asked_jobs = {j for q in qs_open.values() for j in q.get("jobs", [])}
    owned |= asked_jobs
    for qid, q in qs_open.items():
        first = (q.get("jobs") or [""])[0]
        actions.append({"key": f"q:{qid}", "app": first if first in known else "", "login": "", "kind": "info",
                        "text": short(q.get("text", ""), 240),
                        "link": env.get("QUESTIONS_PAGE") or job_links.get(first, ""), "due": "",
                        "since": q.get("asked", "")})
    for job in jobs:
        app = job["id"] if job["id"] in known else ""
        how, end = ended(job, pipeline)
        every = job.get("todo") or []
        todo = list(enumerate(every, 1))
        if how:
            # An ended job needs nothing it needed before: no to-do of a job ended by its tracker status, and of one
            # ended in PIPELINE only those set on or after that date (a withdrawal email still to send).
            # "closed" and "declined" name a tracker status and a PIPELINE stage alike: the status tells them apart.
            sent = job.get("status") not in ENDED_STATUS
            todo = [(i, t) for i, t in todo if sent and end and (t.get("since") or "") >= end]
            if len(todo) < len(every):
                checks.append(f"to-do on an ended job: {job['id']} ({how}{' ' + end if end else ''}), "
                              f"{len(every) - len(todo)} to-do(s) -> track.py todo {job['id']} "
                              + ("done <n> (list numbers them)" if todo else "done all"))
        else:
            applied = (job.get("applied") or "")[:10] if job.get("status") == "submitted" else ""
            before = [t for t in every if applied and t.get("since") and t["since"] < applied]
            if before:
                checks.append(f"to-do set before {job['id']} was sent: "
                              + "; ".join(f'"{short(t.get("text", ""), 60)}"' for t in before))
            undated += [f"{job['id']} ({sum(1 for t in every if not t.get('since'))})"] if any(
                not t.get("since") for t in every) else []
        for t in every:
            if t.get("session") and t["session"] not in live:
                checks.append(f"to-do of {job['id']} names session {t['session']}, "
                              + ("which is done" if t["session"] in session_ids else "not in the record"))
        # The tracker's own list of what the person must do for this job wins, whatever the job's status: a sent job
        # still has its interview reminders, and a posting being screened is "found".
        for i, t in todo:
            owned.add(job["id"])
            # A to-do is never a Question (those are the page's): no kind, or "info", is To do.
            kind = "todo" if t.get("kind", "info") == "info" else t["kind"]
            if kind == "waiting":  # the employer's move: Hiring steps, never Do now
                waits.setdefault(job["id"], []).append((short(t.get("text", ""), 200), t.get("since", "")))
                continue
            shown = kind_by_due(kind, t.get("due", ""), today)
            if t.get("session") in live and shown not in ("urgent", "late"):
                # It names its session by id: one row per session, not one per to-do. Urgent and late stay rows.
                folded.setdefault(t["session"], []).append((job["id"], short(t.get("text", ""), 120)))
                continue
            row_job[f"{job['id']}:{i}"] = job["id"]
            if shown == "late":
                checks.append(f'past due: {job["id"]} "{short(t.get("text", ""), 60)}", due {t["due"]}')
            actions.append({"key": f"{job['id']}:{i}", "app": app, "login": t.get("login", ""),
                            "kind": shown,
                            "where": t.get("where", ""), "text": short(t.get("text", ""), 240),
                            "link": t.get("link") or job_links.get(job["id"], ""), "due": t.get("due", ""),
                            "since": t.get("since", "")})
        if todo or how or not open_job(job.get("status")):
            continue
        if job["status"] == "account-needed":
            site = login_of(job)
            if site in sites:
                # One action per login, not per job: the login's row says how many jobs wait on it. A site that is
                # signed in needs nothing from the person: the job is Claude's next (below).
                continue
            # The site's name, even with no row in LOGINS yet: the dashboard labels it a sign-in, not a plain click.
            owned.add(job["id"])
            actions.append({"key": f"{job['id']}:signin", "app": app, "login": site,
                            "kind": "click",
                            "text": f"Sign in (or create the account) on {site}, leave the profile empty, then tell Claude",
                            "link": job_links.get(job["id"], ""), "due": "", "since": ""})
        elif job["id"] not in asked_jobs and job["id"] not in in_session:
            # What the job waits on, from its note: a To do, not a Question (questions live on the Questions page).
            # A job in a session has that session's row instead.
            owned.add(job["id"])
            actions.append({"key": f"{job['id']}:todo", "app": app, "login": "", "kind": "todo",
                            "text": short(job.get("outcome") or (job.get("needs") or [""])[0] or job.get("note", ""), 240),
                            "link": job_links.get(job["id"], ""), "due": "", "since": ""})
    # Without questions.py's file (no Questions page yet): an employer the person's rules leave to them ("discuss")
    # gets a Question row here; with it, build already put that employer on the page.
    asked = set()
    for job in [] if os.path.exists(qpath) else jobs:
        company = job.get("company", "")
        if job.get("status") in DONE or company in asked or job["id"] in pipeline:
            continue
        verdict, asks, _ = view(company)
        if verdict != "discuss" or not asks:
            continue
        asked.add(company)
        owned |= {j["id"] for j in jobs if j.get("company", "") == company}
        a = asks[0]
        more = f" (and {len(asks) - 1} more finding{'s' if len(asks) > 2 else ''})" if len(asks) > 1 else ""
        actions.append({"key": f"ask:{company}", "app": "", "login": "", "kind": "info",
                        "text": short(f"{company}, {job.get('title', '')}: {a['label']} ({a['level']}): {a['fact']}", 230)
                                + more + (". Allow, or exclude? Answer on your Questions page." if env.get("QUESTIONS_PAGE")
                                          else ". Allow, or exclude? Tell Claude."),
                        "link": env.get("QUESTIONS_PAGE") or a["src"] or job_links.get(job["id"], ""), "due": "",
                        "since": ""})
    for a in apps:
        _, _, warns = view(a["company"])
        a["warn"] = "; ".join(short(f"{w['label']} ({w['level']}): {w['fact']}", 150) for w in warns[:2])
    for s in steps:
        late = s["state"] == "past" and bool(s["due"])  # a deadline that passed with no "done": the person says
        if not late and not (s["state"] == "upcoming" and (s["due"] or TASKLIKE.search(s["step"]))):
            continue
        # A step's email link (PIPELINE "mail"), never its own page: that may be a personal access link.
        p_steps = pipeline_entry(pipeline, s["app"]).get("steps") or []
        mail = p_steps[s["n"] - 1].get("mail", "") if len(p_steps) >= s["n"] else ""
        if late:
            checks.append(f'past due: {s["app"]} step "{s["step"]}", due {s["due"]} -> its "done" in PIPELINE, '
                          "or tell the person")
        actions.append({"key": f"{s['key']}:do", "app": s["app"], "login": "",
                        "kind": "late" if late else kind_by_due("task", s["due"], today),
                        "text": s["step"] + (f" - {'was due' if late else 'due'} {s['due']}" if s["due"] else ""),
                        "link": mail or job_links.get(s["app"], ""), "due": s["due"] or s["date"], "since": ""})
    for r in logins:
        if r.get("status") not in NO_ACTION and (r.get("kind") == "connector" or r.get("jobs") or r.get("fix")):
            verb = {"needs-reconnect": "Reconnect", "blocked": "Clear the check on", "needs-sign-up": "Create an account on",
                    "expired": "Sign in again to"}.get(r.get("status"), "Sign in to")
            waiting = len(r.get("jobs", []))
            actions.append({"key": f"login:{r['id']}", "app": "", "login": r["id"], "kind": "click",
                            "text": f"{verb} {r.get('name', r['id'])}"
                                    + (f" ({waiting} application{'s wait' if waiting > 1 else ' waits'} on it), then tell Claude" if waiting else "")
                                    + (f": {short(r.get('fix', ''), 160)}" if r.get("fix") else ""),
                            "link": r.get("link", ""), "due": "", "since": (r.get("checked") or "")[:10]})

    # One row per session that is not done: "Answer first" when it waits on the person, in progress when it works
    # alone, with its jobs (the job in hand first) and the to-dos that name it.
    session_rows, job_rank = [], {}
    for s in ranked:
        named = folded.get(s["id"], [])
        ids = list(dict.fromkeys(list(s.get("jobs") or []) + [j for j, _ in named]))
        waits_on = short(s.get("waits") or "; ".join(dict.fromkeys(t for _, t in named)), 200)
        title = no_pay(sl.split_title(s.get("title") or s.get("name") or s["id"])[1])
        session_rows.append({"id": s["id"], "rank": s["rank"], "state": s["state"], "title": title,
                             "name": s.get("name", ""), "waits": waits_on, "apps": ids, "due": s["date"],
                             "since": s.get("since", ""), "why": s["why"], "link": s.get("link", "")})
        if s["state"] == "done":
            continue
        owned |= set(ids)
        waiting = s["state"] == "you"
        if waiting:
            for job_id in ids:
                job_rank.setdefault(job_id, s["rank"])
        shown = [j for j in ids if j in known]
        actions.append({"key": f"s:{s['id']}", "app": shown[0] if shown else "", "apps": shown, "login": "",
                        "kind": "session" if waiting else "working", "rank": s["rank"],
                        "text": title + (f" · {waits_on}" if waits_on else "")
                                + (f" · by {s['date']}" if waiting and s["date"] else ""),
                        "link": "", "due": "", "since": s.get("since", "")})

    # A wait on the employer: on the job's last done step ("Done ... awaiting feedback since ..."), else its own row.
    for job_id, items in waits.items():
        text = "; ".join(t for t, _ in items)
        since = min((s for _, s in items if s), default="")
        done_rows = [s for s in steps if s["app"] == job_id and s["state"] == "done"]
        if done_rows:
            done_rows[-1].update(awaits=text, since=since)
        else:
            steps.append({"key": f"{job_id}#wait", "app": job_id if job_id in known else "", "n": 0,
                          "step": "Waiting: " + text, "date": since, "due": "", "detail": "", "upcoming": "no",
                          "state": "waiting", "done": "", "awaits": text, "since": since, "also": []})

    # Claude's next: open jobs nobody owns, one row per reason, so every open job has an owner on the page. A job
    # whose site is signed in but still "account-needed", and a found or pending job with no to-do or question.
    ready, new, rowless = {}, [], []
    login_action = {r["id"] for r in logins if r.get("status") not in NO_ACTION
                    and (r.get("kind") == "connector" or r.get("jobs") or r.get("fix"))}
    for job in jobs:
        if job["id"] in owned or ended(job, pipeline)[0]:
            continue
        if job.get("status") == "account-needed":
            site = login_of(job)
            if job["id"] in known and (login_by_id.get(site) or {}).get("status") in OK_LOGIN:
                ready.setdefault(site, []).append(job["id"])
            elif site not in login_action:
                rowless.append(job["id"])  # its site's row says nothing waits on it, or is an excluded employer's
        elif job["id"] in known and job.get("status") in ("found", "pending"):
            new.append(job["id"])
    queued = [(f"queued:ready:{site}", ids, f"{len(ids)} application{'s' if len(ids) > 1 else ''} ready to send: "
               f"{login_by_id[site].get('name', site)} is signed in") for site, ids in sorted(ready.items())]
    if new:
        queued.append(("queued:new", new, f"{len(new)} job{'s' if len(new) > 1 else ''} found or cleared, not started yet"))
    for key, ids, text in queued:
        actions.append({"key": key, "app": ids[0], "apps": ids, "login": "", "kind": "queued", "text": text,
                        "link": "", "due": "", "since": ""})

    # The rest of the cross-check: what the records say and no row shows, or shows as something it is not.
    if undated:
        checks.append(f"to-dos without since: {', '.join(undated)} -> track.py todo <id> done <n>, then add it "
                      "again with since=<date>")
    for site, ids in sorted(ready.items()):
        checks.append(f"ready, not started: {', '.join(ids)} ({login_by_id[site].get('name', site)} is signed in)")
    if new:
        checks.append(f"no owner: {', '.join(new)} (found or pending; no to-do, question or session)")
    if rowless:
        checks.append(f"waits on a sign-in with no row: {', '.join(rowless)} -> logins.py sync")
    age = lambda r: (now - checked_at(r)).days  # noqa: E731
    old = [f"{r['name']} ({age(r)} days)" for r in login_rows
           if r["stale"] and r["kind"] != "connector" and age(r) > LOGIN_CHECK_DAYS]
    if old:
        checks.append(f"sign-ins not checked for more than {LOGIN_CHECK_DAYS} days: {', '.join(old)}")
    cold = [f"{r['name']} (last {r['checked']})" for r in login_rows if r["stale"] and r["kind"] == "connector"]
    if cold:
        checks.append(f"connectors not checked in this run: {', '.join(cold)} -> one cheap call each, then logins.py set")
    odd = [r["name"] for r in login_rows if r["status"] in OK_LOGIN and asks_sign_in(login_by_id[r["id"]].get("note", ""))]
    if odd:
        checks.append(f"reads signed in or connected, but its note asks for a sign-in or an account: {', '.join(odd)} "
                      "-> logins.py set <id> needs-sign-in or needs-sign-up")
    checks += session_checks(record, ranked, jobs, pipeline, today, now, el.keys)
    bare = [x["employer"] for x in excluded if not x.get("source")]
    if bare:
        checks.append(f"excluded employers without a source: {', '.join(bare)}")

    # Urgent first (it expires), then the sessions to answer, in their order, then "working" (Claude or a session is
    # on it: the person waits), then by deadline (a past one on top), then the rows of a session's jobs in the
    # session order, then by age: the older "since" first, rows without one last in the tracker's order.
    actions.sort(key=lambda a: (GROUP.get(a["kind"], 3), a.get("rank", 0), a["due"] == "", a["due"],
                                job_rank.get(row_job.get(a["key"]), 999), a["since"] == "", a["since"],
                                KIND_RANK.get(a["kind"], 5)))

    index = [{"key": f"stage:{s}", "group": "stage", "label": s, "n": sum(1 for a in apps if a["stage"] == s)}
             for s in STAGES.values()]
    index += [{"key": f"actions:{k}", "group": "actions", "label": k, "n": sum(1 for a in actions if a["kind"] == k)}
              for k in COUNTED]
    index += [{"key": f"sessions:{state}", "group": "sessions", "label": state,
               "n": sum(1 for s in session_rows if s["state"] == state)} for state in sl.STATES]
    index += [{"key": "actions:waiting", "group": "actions", "label": "waiting", "n": sum(len(v) for v in waits.values())},
              {"key": "logins:ok", "group": "logins", "label": "working",
               "n": sum(1 for r in login_rows if r["status"] in OK_LOGIN and not r["stale"])},
              {"key": "logins:action", "group": "logins", "label": "need action",
               "n": sum(1 for r in login_rows if r["status"] not in NO_ACTION and (r["kind"] == "connector" or r["jobs"] or r["fix"]))},
              {"key": "excluded:n", "group": "excluded", "label": "excluded employers", "n": len(excluded)},
              {"key": "meta:generated", "group": "meta", "label": now.strftime("%Y-%m-%d %H:%M"),
               "n": len(apps)},
              {"key": "meta:run", "group": "meta", "label": run_line(env), "n": 0},
              # The person's own Questions page (QUESTIONS_PAGE), linked from Do now.
              {"key": "meta:questions", "group": "meta", "label": env.get("QUESTIONS_PAGE") or "", "n": 0}]

    files = list(zip(FILES, (index, apps, steps, actions, login_rows, excluded, session_rows)))
    return files, checks, (f"{len(apps)} applications, {len(steps)} steps, {len(actions)} actions, "
                           f"{len(login_rows)} logins, {len(excluded)} excluded employers, {len(session_rows)} sessions")


FILES = ("index.json", "applications.json", "steps.json", "actions.json", "logins.json", "excluded.json",
         "sessions.json")


def uploads_path(env):
    """Beside the tracker: which export of each file is on the page now ({"at", "files": {name: sha256}})."""
    return os.path.join(os.path.dirname(env.path("TRACKER")), "dashboard-uploads.json")


def digest(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main():
    args = sys.argv[1:]
    env_arg = None
    if "--env" in args:
        i = args.index("--env")
        env_arg = args[i + 1]
        del args[i:i + 2]
    flags, rest = {a for a in args if a.startswith("--")}, [a for a in args if not a.startswith("--")]
    if flags - {"--check", "--uploaded"} or len(flags) > 1 or len(rest) != (0 if "--check" in flags else 1):
        sys.exit(__doc__)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # a check line may name an employer the console cannot print
    env = jsenv.load(env_arg, __file__)
    now = datetime.datetime.now()
    if "--uploaded" in flags:
        have = {name: digest(os.path.join(rest[0], name)) for name in FILES if os.path.isfile(os.path.join(rest[0], name))}
        with open(uploads_path(env), "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"at": now.replace(microsecond=0).isoformat(), "files": have}, fh, indent=1)
        print(f"recorded as on the page: {' '.join(have) or 'no file found in ' + rest[0]}")
        return
    files, checks, summary = build(env, now)
    if "--check" not in flags:
        out_dir = rest[0]
        os.makedirs(out_dir, exist_ok=True)
        for name, rows in files:
            with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="\n") as fh:
                json.dump(rows, fh, ensure_ascii=False, indent=1)
        print(f"{summary} -> {out_dir}")
        # Only a file that differs from the one on the page needs a new upload (--uploaded records what is there).
        on_page = {}
        if os.path.isfile(uploads_path(env)):
            with open(uploads_path(env), encoding="utf-8") as fh:
                on_page = json.load(fh).get("files", {})
        changed = [name for name in FILES if digest(os.path.join(out_dir, name)) != on_page.get(name)]
        print("upload:", " ".join(changed) or "none")
        print("unchanged:", " ".join(name for name in FILES if name not in changed) or "none")
    for line in checks:
        print("check:", line)
    print(f"check: {len(checks)} mismatches")


if __name__ == "__main__":
    main()
