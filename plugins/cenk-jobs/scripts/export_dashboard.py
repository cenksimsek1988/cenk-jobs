"""Export the job search as the dashboard's tree of small JSON files, each fact in one file only.

Usage: python -I export_dashboard.py <out dir> [--env <job-search.env>]   write the files, then say what to upload
       python -I export_dashboard.py --check                               only the check lines; writes nothing
       python -I export_dashboard.py --uploaded <out dir> <file> ...       record the files really uploaded as the ones
                                                                           on the page; the others keep their earlier
                                                                           record. "all" in place of the names: every
                                                                           file.
Every run ends with one "check:" line per mismatch between the records and the page, then "check: <n> mismatches";
the exit code stays 0. Example: "check: to-do on an ended job: J3 (rejected 2026-11-10), 2 to-do(s) -> track.py
todo J3 done all". The lines: a folder not counted (two for one job, or of a job that ended); a to-do on an ended
job, set before its job was sent, without "since", or naming a session the record does not hold; a past due date; a
job whose site is signed in and that nobody started; a found or pending job with no owner; a job waiting on a
sign-in with no row; sign-ins not checked for days; a session that is over, whose title differs from its state or
names an employer whose jobs ended; a sessions record not synced for a day; PIPELINE and a folder with different
steps; an excluded employer without a source; a job recorded rejected whose reason says the role closed or was filled;
a folder in another stage than the records give; the same employer and role sent twice; a status the plugin does not
know; a session whose title names an employer with a running job and that has no jobs; two login rows for one site
(merged into one row on the page); a reminder that is not a date, or on an ended job; Moving forward with nothing for
7 days; a job waiting on the person with no to-do; a job waiting on an account at a site the records do not name;
a sign-in to-do that names a job board for an application on the employer's own site. --check also says when the
page is behind the records (against dashboard-uploads.json), and when the Questions page is (questions.py build
--check), so one check covers both pages.
--calendar <file> (with either form): the Google Calendar list_events answer for today to 60 days ahead, saved as
JSON; adds "calendar:" lines: a job-search event of a job that ended, a coming PIPELINE step with no event of its
job on its date, or one at another time. Example: "calendar: 2026-11-19 "Job search · Acme: reply due" is for J3
Acme, which ended (rejected 2026-11-16) -> after the person's yes, delete the event".
--page <file> (with either form): the dashboard store's files/index.html as saved (ArtifactData list with out_dir);
a first check line when it is not the plugin's templates/dashboard/index.html.
After the files it prints "upload:" (the files that differ from the ones on the page) and "unchanged:" (no new
upload needed), against the record --uploaded keeps beside the tracker (dashboard-uploads.json). The export time
alone (meta:generated) is no change: index.json is listed for upload only when its other rows differ.
Writes, in <out dir>:
  index.json         the root: one row per headline count (stages, actions by kind, logins needing action) and the
                     export time. The page's tiles read only this, so it opens fast.
  applications.json  one row per application, keyed by the tracker's job id: company, role, stage, applied, where,
                     CV, folder, reminder (a date, running jobs only), again ("re-application of <id>"), ended. Read from APPLICATIONS_DIR/<stage>/<folder>/overview.md, one folder per job: a
                     not-applied folder counts only while the job is neither sent nor ended, and of two folders the
                     one in the stage the records give. Example: a sent job whose old not-applied folder is kept
                     for its notes.md is one row, under Waiting for reply.
  steps.json         one row per hiring step: its job id (app), name, date, due, details and state (upcoming, proposed:
                     offered or with no date yet, done, past, cancelled, ended: a step left open on a job that is
                     over) - no company or role, which the page takes from applications.json by the id. A job whose
                     folder lists no step takes them from PIPELINE. The page turns upcoming into past after its day.
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
                     it was done) or queued (Claude's next: a signed-in site's jobs, one row per site with their ids
                     in apps); a found or pending job nobody owns is a to-do row of its own ("Waits on you: unknown, ask
                     Claude"); each points at a job id (app) and/or a login id (login) instead of repeating them. A
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
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jsenv  # noqa: E402
import sessions as sl  # noqa: E402
from reposts import title_key  # noqa: E402
from trackerlib import (BOARD_NAME, ENDED_STAGE, ENDED_STATUS, ISO_DATE, STATUSES, employer_link, ended,  # noqa: E402
                        flat_jobs, login_of, no_pay, pipeline_entry, step_done, waits_on_person)
from trackerlib import ON_BOARD, SYNC_NOTE, site_key  # noqa: E402

# "Closed": the position closed or was filled (not a rejection); "Declined": the person said no.
STAGES = {"approved": "Moving forward", "pending": "Waiting for reply", "rejected": "Rejected", "closed": "Closed",
          "declined": "Declined", "not-applied": "Not sent"}
FIELD = re.compile(r"^- \*\*(.+?):\*\*\s*(.*)$")
STEP = re.compile(r"^\d+\.\s+\*\*(.+?)\*\*\s*-\s*(.+)$")
# A markdown link; a target in <...> may hold spaces and parentheses (step folders such as "01 ... (45 min)").
LINK = re.compile(r"\[([^\]]*)\]\((?:<[^>]*>|[^)]*)\)")
# Whole words: "Platform architecture interview" is no form, "Performance chat" no task.
TASKLIKE = re.compile(r"(?i)\b(?:tasks?|tests?|assessments?|assignments?|questionnaires?|ai interview|video interview"
                      r"|forms?|challenges?)\b")
DONE_NOTE = re.compile(r"\bdone \d{4}-\d{2}-\d{2}")  # the overview's "done <date>" is not the step's own date
OK_LOGIN = ("connected", "signed-in")
# An excluded employer (by the person's rules) needs no sign-in, so it is never in Do now.
NO_ACTION = OK_LOGIN + ("excluded",)
LOGIN_CHECK_DAYS = 3  # a sign-in older than this is a check line; with no run recorded it also reads "not checked since"
IDLE_DAYS = 7  # Moving forward with nothing done, coming or awaited for this long is a check line
RUN_HOURS = 6  # a run started this long ago with no end row did not finish
# Do now's kinds, in their order: (group, rank in the group). Urgent (it expires), the sessions to answer, working
# (the person waits), everything else by deadline and age, then Claude's own queue. Every kind is counted.
KINDS = {"urgent": (0, 0), "session": (1, 0), "working": (2, 0), "late": (3, 0), "task": (3, 1), "click": (3, 2),
         "todo": (3, 3), "info": (3, 4), "queued": (4, 0)}
# A to-do that is Claude's own work ("Claude: score the fit"), not the person's: Claude's next, never To do.
CLAUDES = re.compile(r"(?i)^\s*claude\b\s*[:,-]")
# A rejection's reason that says the role itself ended: "closed" (RULES/hiring-steps.md, Outcomes), not "rejected".
CLOSED_WORDS = re.compile(r"(?i)\b(?:filled|no longer (?:open|available|hiring)|(?:position|role|posting|vacancy|job)"
                          r" (?:has been |was |is )?(?:closed|cancell?ed|withdrawn|put on hold|on hold|paused))\b")
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "dashboard", "index.html")
JOB_TAG = re.compile(r"\[job-search: ([^\s\]]+)")


def open_job(status):
    # Jobs that wait on the person (account-needed, needs-person, needs-captcha, an older "needs-<name>"), or are
    # ready to send.
    return waits_on_person(status) or status == "to-apply"


def plain(text):
    return re.sub(r"\s+", " ", LINK.sub(r"\1", text or "")).strip()


def short(text, n=220):
    text = no_pay(plain(text))
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + "…"


def kind_by_due(kind, due, today):
    """A due date that passed is "late", never Urgent: the person says whether it was done. A task due today or
    tomorrow is Urgent (RULES.md, "Urgent steps"), whether a hiring step or a job's own to-do."""
    if due and due < today and kind != "working":
        return "late"
    if due and kind == "todo":
        kind = "task"  # a to-do with a due date is a task on a deadline (seen: three dated to-dos counted as none)
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


def run_line(env, now=None):
    """Whether a run is going, from the usage log's "run" rows, and the next one. The latest row decides: an end is
    paired only with the start right before it (an end with none reads "no start recorded"; an end on another day
    keeps its date), and a start with no end row for more than RUN_HOURS hours reads "no end recorded", never
    "Running now". Example: started 16 Nov 22:25, ok 22:57, then an "ok" on 18 Nov 01:34 alone: "Last run ended
    2026-11-18 01:34: finished; no start recorded"."""
    rows = run_rows(env)
    # SEARCH_DAYS is what /cenk-jobs:schedule wrote from the task's real schedule: this script cannot read the task.
    days = (env.get("SEARCH_DAYS") or "weekdays").strip()
    if days.lower() == "none":
        nxt = "No run scheduled."
    else:
        nxt = f"Next: {'every day' if days.lower() == 'daily' else days} at {env.get('SEARCH_TIME') or '19:00'}."
    when = lambda r: r["time"][:16].replace("T", " ")
    rows = sorted(rows, key=lambda r: r.get("time", ""))
    if not rows:
        return "No run recorded yet. " + nxt
    last = rows[-1]
    if last.get("result") != "started":
        # The latest row ends a run: its own start is the latest start with no other end between them.
        before = rows[:-1]
        start = before[-1] if before and before[-1].get("result") == "started" else None
        word = "finished" if last.get("result") == "ok" else (last.get("result") or "ended")
        if start is None:
            return f"Last run ended {when(last)}: {word}; no start recorded. " + nxt
        end = last["time"][11:16] if last["time"][:10] == start["time"][:10] else when(last)
        return f"Last run {when(start)} to {end}: {word}. " + nxt
    try:
        began = datetime.datetime.fromisoformat(last["time"][:19])
    except ValueError:
        began = None
    if began and now and now - began > datetime.timedelta(hours=RUN_HOURS):
        return f"Last run started {when(last)}: no end recorded. " + nxt
    return f"Running now, since {when(last)}. " + nxt


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
            # A part left empty ("date , who") leaves no ", " at either end.
            out["steps"].append({"name": m.group(1).strip(),
                                 "detail": plain(LINK.sub("", m.group(2))).strip(" .,;·-")})
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
    and not confirmed yet; a step with no date at all is proposed too, never past. A job whose folder lists no step
    (one outside approved/) takes its steps from PIPELINE, so they are never invisible."""
    lines = overview["steps"]
    p_steps = pipeline_entry(pipeline, job_id).get("steps") or []
    own = (pipeline.get(job_id) or {}).get("steps") if isinstance(pipeline.get(job_id), dict) else None
    if not lines and own:  # its own steps only: a shared process's steps stay on the job that owns them
        lines = [{"name": str(p.get("name") or "Step"), "detail": plain(str(p.get("note") or ""))} for p in own]
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
                 "proposed" if (ps.get("proposed") and coming) or not last else "upcoming" if coming else "past")
        rows.append({"key": f"{job_id}#{i}", "app": job_id, "n": i, "step": no_pay(s["name"]), "date": date,
                     "due": due, "detail": short(s["detail"], 160), "state": state, "done": done if ISO_DATE.fullmatch(done) else "", "awaits": "", "since": "",
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
                # No jobs recorded, and the title names an employer with a running job: the session is not linked.
                running = [j["id"] for j in theirs if not ended(j, pipeline)[0]]
                if not mine and running and any(len(k) > 3 and f" {k} " in words for k in keys(company)):
                    out.append(f"session {name}: the title names {company} and it has no jobs "
                               f"-> sessions.py set {name} jobs={','.join(running[:3])}")
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


def outcome_checks(jobs, pipeline):
    """A sent job recorded rejected whose reason says the role closed or was filled: that is "closed"."""
    out = []
    for job in jobs:
        entry = pipeline_entry(pipeline, job["id"])
        # Two shapes: "reason" beside the stage, or the older {"rejected": {"date", "reason"}}.
        older = entry.get("rejected") if isinstance(entry.get("rejected"), dict) else {}
        reason = str(entry.get("reason") or older.get("reason") or "")
        if entry.get("stage") == "rejected" and CLOSED_WORDS.search(reason):
            out.append(f"recorded rejected, its reason reads closed: {job['id']} {job.get('company', '')} "
                       f"(\"{short(reason, 80)}\") -> PIPELINE stage closed (RULES/hiring-steps.md, Outcomes)")
    return out


def merge_logins(rows):
    """(rows, {merged id: kept id}, check lines): the job-site rows of one site (site_key) as one row, so a site is
    never twice in the tab or in Do now. The row checked last gives the status, of the rows someone checked: a row
    logins.py sync made only says a job waits, so it gives its jobs, never its state. Jobs and fixes are summed.
    Each merge is a check line, so LOGINS gets one row too. Example: "LinkedIn" signed-in (checked) and "linkedin"
    made by sync later: one row, signed-in, with the jobs of both."""
    groups, order = {}, []
    for r in rows:
        k = ("site", site_key(r)) if r.get("kind", "site") == "site" else ("own", r["id"])
        if k not in groups:
            order.append(k)
        groups.setdefault(k, []).append(r)
    out, alias, checks = [], {}, []
    # A site that is no job board, linked to a board's page: its Open link leads to the wrong site.
    odd = [r["id"] for r in rows if r.get("kind", "site") == "site" and not BOARD_NAME.search(f"{r.get('name', '')} {r['id']}")
           and BOARD_NAME.search(re.sub(r"^https?://", "", str(r.get("link") or "")).split("/")[0])]
    if odd:
        checks.append(f"a site's link is a job board's page: {', '.join(odd)} -> logins.py set <id> <status> "
                      "\"<note>\" link=<its own sign-in page>")
    for k in order:
        same = groups[k]
        if len(same) == 1:
            out.append(same[0])
            continue
        # The row kept is the plainest name ("LinkedIn", the first of equals); its state is the latest check's.
        name_row = min(same, key=lambda r: len(str(r.get("name") or r["id"])))
        checked = [r for r in same if not str(r.get("note") or "").startswith(SYNC_NOTE)] or same
        last = max(checked, key=lambda r: str(r.get("checked") or ""))
        keep = dict(name_row, **{k: last.get(k) for k in ("status", "checked", "note", "fix", "link") if last.get(k)})
        keep["jobs"] = [j for r in same for j in r.get("jobs", [])]
        keep["fix"] = keep.get("fix") or next((r["fix"] for r in same if r.get("fix")), "")
        out.append(keep)
        for r in same:
            alias[r["id"]] = keep["id"]
        checks.append(f"one site, {len(same)} login rows: {', '.join(r['id'] for r in same)} -> keep {keep['id']} "
                      f"in LOGINS with the latest check ({keep.get('status')}, {str(keep.get('checked'))[:16]}) and "
                      "the jobs of all, and remove the others")
    return out, alias, checks


def repeat_checks(jobs, pipeline):
    """({job id: "re-application of <id>"}, check lines): the same employer and role sent twice (employer keys and
    title words as reposts.py matches them). Both are facts: flagged, never hidden. The check line is for a pair
    nobody has recorded: once the later job says repeat_of=<the earlier id>, only the flag stays."""
    import employerlib as el
    seen, again, out = {}, {}, []
    sent = [j for j in jobs if j.get("status") == "submitted" or j["id"] in pipeline]
    for j in sorted(sent, key=lambda j: (str(j.get("applied") or "")[:10], j["id"])):
        keys = sorted(el.keys(j.get("company") or ""))
        k = (keys[0] if keys else "", title_key(j.get("title", "")))
        if k[0] and k[1] and k in seen:
            first = seen[k]
            again[j["id"]] = f"re-application of {first}"
            if j.get("repeat_of") != first:
                out.append(f"the same employer and role twice: {first} and {j['id']} {j.get('company', '')} "
                           f"\"{short(j.get('title', ''), 60)}\" -> track.py set {j['id']} {j.get('status') or 'submitted'} "
                           f"\"\" repeat_of={first}")
        else:
            seen.setdefault(k, j["id"])
    return again, out


def status_checks(jobs):
    """A tracker status the plugin does not know (STATUSES): it passes every list silently otherwise."""
    odd = {}
    for j in jobs:
        if j.get("status") and j["status"] not in STATUSES:
            odd.setdefault(j["status"], []).append(j["id"])
    return [f"status not known to the plugin: {s} ({len(ids)}: {', '.join(ids[:8])}{' ...' if len(ids) > 8 else ''}) "
            f"-> track.py set <id> needs-person (or the status meant)" for s, ids in sorted(odd.items())]


def idle_checks(apps, steps, today):
    """Moving forward with nothing done, coming or awaited for IDLE_DAYS days."""
    out = []
    limit = (datetime.date.fromisoformat(today) - datetime.timedelta(days=IDLE_DAYS)).isoformat()
    for a in apps:
        if a["stage"] != "Moving forward":
            continue
        mine = [s for s in steps if s["app"] == a["id"]]
        if any(s["state"] in ("upcoming", "proposed", "waiting") or s.get("awaits") for s in mine):
            continue
        last = max([s["done"] or s["date"] for s in mine] + [a["applied"][:10]], default="")
        if last and last < limit:
            out.append(f"moving forward, nothing since {last}: {a['id']} {a['company']} -> a waiting to-do "
                       "(track.py todo <id> add waiting ...) or the outcome")
    return out


def event_rows(answer):
    """[{id, title, day, at, job, colour}] from a saved Google Calendar list_events answer (or its events list): day
    is the local date, at the local HH:MM ("" all day), job the id in "[job-search: <id> ...]" of the description."""
    events = answer.get("events", []) if isinstance(answer, dict) else answer
    rows = []
    for e in events or []:
        start = e.get("start") or {}
        if start.get("dateTime"):
            when = datetime.datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
            when = when.astimezone() if when.tzinfo else when
            day, at = when.date().isoformat(), when.strftime("%H:%M")
        else:
            day, at = str(start.get("date") or "")[:10], ""
        tag = JOB_TAG.search(e.get("description") or "")
        rows.append({"id": e.get("id", ""), "title": e.get("summary") or "", "day": day, "at": at,
                     "job": tag.group(1) if tag else "", "colour": str(e.get("colorId") or "")})
    return rows


def calendar_checks(env, answer, jobs, pipeline, today, days=60):
    """The calendar against the records: an event of a job that ended; a coming step with no event of its job on its
    date, or one at another time. An event belongs to a job by its "[job-search: <id>" tag, else by the company's
    name in its title; only job-search events count (the colour, the title prefix or the tag)."""
    import employerlib as el
    colour = str(env.get("CALENDAR_COLOR") or "3")
    prefix = env.get("CALENDAR_PREFIX") or "Job search · "
    until = (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()
    by_id = {j["id"]: j for j in jobs}
    events = [e for e in event_rows(answer)
              if e["colour"] == colour or e["title"].startswith(prefix.strip()) or e["job"]]

    def owner(e, among):
        if e["job"] in by_id:
            return [by_id[e["job"]]]
        title = " " + re.sub(r"[^a-z0-9]+", " ", e["title"].lower()) + " "
        return [j for j in among if any(f" {k} " in title for k in el.keys(j.get("company") or ""))]

    out = []
    for e in events:
        if e["day"] < today:
            continue
        mine = owner(e, jobs)
        if mine and all(ended(j, pipeline)[0] for j in mine):
            j = mine[0]
            how, end = ended(j, pipeline)
            out.append(f"calendar: {e['day']} \"{short(e['title'], 70)}\" is for {j['id']} {j.get('company', '')}, "
                       f"which ended ({how}{' ' + end if end else ''}) -> after the person's yes, delete the event "
                       "(an invitation: remove its colour)")
    for job in jobs:
        if ended(job, pipeline)[0]:
            continue
        mine = [e for e in events if job in owner(e, [job])]
        for n, step in enumerate(pipeline_entry(pipeline, job["id"]).get("steps") or [], 1):
            day = str(step.get("date") or "")[:10]
            if not ISO_DATE.fullmatch(day) or not today <= day <= until or step.get("cancelled") or step_done(step):
                continue
            name = f"{job['id']} {job.get('company', '')} step {n} \"{short(step.get('name') or 'Step', 50)}\""
            same = [e for e in mine if e["day"] == day]
            hit = re.match(r"\d{1,2}:\d{2}", str(step.get("time") or ""))
            at = hit.group(0).zfill(5) if hit else ""  # no time in PIPELINE: any event that day counts
            if not same:
                other = sorted({e["day"] for e in mine if e["day"] >= today})
                out.append(f"calendar: no event for {name} on {day}"
                           + (f"; its job's events are on {', '.join(other)}" if other else "")
                           + " -> create it or correct the date (RULES/hiring-steps.md, Calendar)")
            elif at != "00:00" and at and not any(e["at"] in ("", at) for e in same):
                out.append(f"calendar: {name} is at {at} in PIPELINE, its event at "
                           f"{', '.join(sorted(e['at'] for e in same))} -> correct the one that is wrong")
    return out


def page_check(saved):
    """The dashboard's page code (its store's files/index.html, saved as JSON with "text", or as HTML) against the
    plugin's templates/dashboard/index.html: an older copy reads fields the export no longer writes."""
    if isinstance(saved, dict) and not isinstance(saved.get("text"), str):
        return ["the saved dashboard page has no \"text\" field: save the store's files/index.html again "
                "(ArtifactData list with out_dir)"]
    text = saved["text"] if isinstance(saved, dict) else str(saved)
    with open(TEMPLATE, encoding="utf-8") as fh:
        want = fh.read()
    same = text.replace("\r\n", "\n").strip() == want.replace("\r\n", "\n").strip()
    return [] if same else ["the dashboard page is not the plugin's template: write files/index.html from "
                            "templates/dashboard/index.html (RULES/run.md, Dashboard)"]


def build(env, now, calendar=None, page=None):
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
    # The stage folder against the records: the page shows a row's stage from its folder.
    for job_id, stage_dir, name, _ in chosen:
        job = by_id.get(job_id)
        want = stage_dir_of(job, pipeline) if job else stage_dir
        if want != stage_dir:
            said = want or f"{job.get('status')} (no folder)"
            checks.append(f"folder stage: {job_id} is in {stage_dir}/, the records say {said} -> build_app_folders.py")
    again, repeat_lines = repeat_checks(jobs, pipeline)
    checks += repeat_lines + status_checks(jobs)
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
        # The reminder is a date to follow up, and only while the job runs: free text or an ended job's is a check.
        reminder = f.get("reminder", "").strip()
        running = stage_dir in ("approved", "pending")
        if reminder and not (running and ISO_DATE.fullmatch(reminder[:10])):
            checks.append(f"reminder: {job_id} \"{short(reminder, 50)}\" "
                          + ("is not a date" if running else f"on a job that is {STAGES[stage_dir]}")
                          + " -> move the words to its notes and clear the reminder")
        apps.append({"id": job_id, "stage": STAGES[stage_dir], "company": company.strip(), "role": role.strip(),
                     "applied": f.get("applied", ""), "where": no_pay(f.get("where", "")),
                     "cv": re.sub(r"^.*?-CV-", "", f.get("cv sent", "")).replace(".pdf", "").replace("-", " "),
                     "status": short(f.get("status", ""), 160),
                     "reminder": reminder[:10] if running and ISO_DATE.fullmatch(reminder[:10]) else "",
                     "again": again.get(job_id, ""), "ended": "" if running or stage_dir == "not-applied" else "yes",
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
    logins, login_alias, merged = merge_logins(logins)
    checks += merged
    login_by_id = {r["id"]: r for r in logins}
    login_by_id.update({old: login_by_id[new] for old, new in login_alias.items()})
    site_of = lambda job: login_alias.get(login_of(job), login_of(job))  # noqa: E731
    # "needs": the person has something to do there (a connector, or a site a job waits on); the page groups by it.
    # A site no job waits on is "Not signed in", whatever its fix says (seen: a Workday sign-in for jobs sent).
    needs = lambda r: r.get("status") not in NO_ACTION and bool(  # noqa: E731
        r.get("kind") == "connector" or r.get("jobs"))
    login_rows = [{"id": r["id"], "name": r.get("name", r["id"]), "kind": r.get("kind", "site"),
                   "status": r.get("status", "unknown"), "checked": (r.get("checked") or "")[:16].replace("T", " "),
                   "note": short(r.get("note", ""), 160), "fix": short(r.get("fix", ""), 200), "link": r.get("link", ""),
                   "account": r.get("account", ""), "jobs": len(r.get("jobs", [])), "needs": "yes" if needs(r) else "",
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
    nosite = []  # account-needed jobs whose site the records do not name
    boarded = []  # sign-in to-dos that name a job board for a job applied on the employer's own site
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
            if kind == "click" and BOARD_NAME.search(t.get("login") or "") and not ON_BOARD.search(t.get("login") or "") \
                    and not login_of(job):
                boarded.append(f"{job['id']} ({t['login']})")
            shown = kind_by_due(kind, t.get("due", ""), today)
            if t.get("session") in live and shown not in ("urgent", "late"):
                # It names its session by id: one row per session, not one per to-do. Urgent and late stay rows.
                folded.setdefault(t["session"], []).append((job["id"], short(t.get("text", ""), 120)))
                continue
            row_job[f"{job['id']}:{i}"] = job["id"]
            if shown == "late":
                checks.append(f'past due: {job["id"]} "{short(t.get("text", ""), 60)}", due {t["due"]}')
            if CLAUDES.match(t.get("text", "")) and shown not in ("urgent", "late"):
                shown = "queued"  # Claude's own work, written as a to-do: Claude's next, not the person's
            actions.append({"key": f"{job['id']}:{i}", "app": app,
                            "login": login_alias.get(t.get("login", ""), t.get("login", "")),
                            "kind": shown,
                            "where": t.get("where", ""), "text": short(t.get("text", ""), 240),
                            "link": t.get("link") or job_links.get(job["id"], ""), "due": t.get("due", ""),
                            "since": t.get("since", "")})
        if todo or how or not open_job(job.get("status")):
            continue
        if job["status"] == "account-needed":
            site = site_of(job)
            if not site:
                # A job board that only forwards is never the login (trackerlib.login_of): the site is Claude's to
                # find on the posting, then `track.py wait ... login=<site>`.
                owned.add(job["id"])
                nosite.append(job["id"])
                continue
            if site in sites:
                # One action per login, not per job: the login's row says how many jobs wait on it. A site that is
                # signed in needs nothing from the person: the job is Claude's next (below).
                continue
            # The site's name, even with no row in LOGINS yet: the dashboard labels it a sign-in, not a plain click.
            owned.add(job["id"])
            row_job[f"{job['id']}:signin"] = job["id"]
            actions.append({"key": f"{job['id']}:signin", "app": app, "login": site,
                            "kind": "click",
                            "text": f"Sign in (or create the account) on {site}, leave the profile empty, then tell Claude",
                            "link": job_links.get(job["id"], ""), "due": "", "since": ""})
        elif waits_on_person(job["status"]) and job["id"] not in asked_jobs and job["id"] not in in_session:
            # A job waiting on the person with no to-do: its note says what, as "Waits on you: ...", and a check
            # line asks for a real to-do. A note on any other job (a hand score, a site's quirk) is Claude's, never
            # the person's to-do; a job ready to send (to-apply) is Claude's next, below.
            owned.add(job["id"])
            row_job[f"{job['id']}:todo"] = job["id"]
            note = short(job.get("outcome") or (job.get("needs") or [""])[0] or job.get("note", ""), 220)
            checks.append(f"{job['status']} with no to-do: {job['id']} -> track.py wait {job['id']} needs-person "
                          "\"<what>\"")
            actions.append({"key": f"{job['id']}:todo", "app": app, "login": "", "kind": "todo",
                            "text": "Waits on you: " + (note or "unknown, ask Claude"),
                            "link": job_links.get(job["id"], ""), "due": "", "since": ""})
    # Without questions.py's file (no Questions page yet): an employer the person's rules leave to them ("discuss")
    # gets a Question row here once it has answered (a job of it in PIPELINE that has not ended), as questions.py
    # build asks; with the file, build already put that employer on the page.
    asked = set()
    for job in [] if os.path.exists(qpath) else jobs:
        company = job.get("company", "")
        entry = pipeline_entry(pipeline, job["id"]) if job["id"] in pipeline else {}
        if company in asked or not entry or entry.get("stage") in ENDED_STAGE or job.get("status") in ENDED_STATUS:
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
    # A job's own to-do with a due date already stands for its step with that due: one row, never two.
    todo_dues = {(a.get("app") or row_job.get(a["key"], ""), a["due"]) for a in actions if a["due"]}
    for s in steps:
        late = s["state"] == "past" and bool(s["due"])  # a deadline that passed with no "done": the person says
        if not late and not (s["state"] == "upcoming" and (s["due"] or TASKLIKE.search(s["step"]))):
            continue
        if s["due"] and (s["app"], s["due"]) in todo_dues:
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
        if needs(r):
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
                             "waits": waits_on, "apps": ids, "since": s.get("since", ""), "why": s["why"],
                             "link": s.get("link", "")})
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
                        "link": s.get("link", ""), "due": "", "since": s.get("since", "")})

    # A wait on the employer: on the job's last done step ("Done ... awaiting feedback since ..."), else its own row.
    for job_id, items in waits.items():
        text = "; ".join(t for t, _ in items)
        since = min((s for _, s in items if s), default="")
        done_rows = [s for s in steps if s["app"] == job_id and s["state"] == "done"]
        if done_rows:
            done_rows[-1].update(awaits=text, since=since)
        else:
            steps.append({"key": f"{job_id}#wait", "app": job_id if job_id in known else "", "n": 0,
                          "step": "Waiting: " + text, "date": since, "due": "", "detail": "", "state": "waiting", "done": "", "awaits": text, "since": since, "also": []})

    # Claude's next: open jobs nobody owns, one row per reason, so every open job has an owner on the page. A job
    # whose site is signed in but still "account-needed"; one ready to send (to-apply, a long-shot held for a later
    # day among them); an unread posting the next fit check reads again; a found or pending job with no to-do.
    ready, new, rowless, to_send, unread, long_shots = {}, [], [], [], [], 0
    login_action = {r["id"] for r in logins if needs(r)}
    for job in jobs:
        if job["id"] in owned or ended(job, pipeline)[0]:
            continue
        if job.get("status") == "account-needed":
            site = site_of(job)
            if job["id"] in known and (login_by_id.get(site) or {}).get("status") in OK_LOGIN:
                ready.setdefault(site, []).append(job["id"])
            elif site not in login_action:
                rowless.append(job["id"])  # its site's row says nothing waits on it, or is an excluded employer's
        elif job.get("status") == "to-apply":
            to_send.append(job["id"])
            long_shots += (job.get("grade") or (job.get("prep") or {}).get("grade")) == "long-shot"
        elif job.get("status") == "found" and job.get("unread"):
            unread.append(job["id"])
        elif job.get("status") in ("found", "pending"):
            new.append(job["id"])
    plural = lambda n: "s" if n > 1 else ""  # noqa: E731
    queued = [(f"queued:ready:{site}", ids, f"{len(ids)} application{plural(len(ids))} ready to send: "
               f"{login_by_id[site].get('name', site)} is signed in") for site, ids in sorted(ready.items())]
    if to_send:
        queued.append(("queued:send", to_send, f"{len(to_send)} application{plural(len(to_send))} prepared, "
                       "to send" + (f" ({long_shots} long-shot{plural(long_shots)} wait for a later day: "
                                    "LONG_SHOTS_PER_DAY)" if long_shots else "")))
    if nosite:
        queued.append(("queued:nosite", nosite, f"{len(nosite)} application{plural(len(nosite))} wait{'s' if len(nosite) == 1 else ''} on "
                       "an account at a site not named yet: Claude finds it on the posting"))
    if unread:
        queued.append(("queued:unread", unread, f"{len(unread)} posting{plural(len(unread))} not read in full: the "
                       "next fit check reads the saved text"))
    # A found or pending job nobody owns is a gap in the records: a Do now row of its own, so it is never silent.
    # Seen: 16 jobs waiting on sign-ins and answers stayed "found" with no to-do for two days.
    for job_id in new:
        row_job[f"{job_id}:noowner"] = job_id
        actions.append({"key": f"{job_id}:noowner", "app": job_id if job_id in known else "", "login": "",
                        "kind": "todo",
                        "text": "Waits on you: unknown, ask Claude (found or pending; no to-do, question or session)",
                        "link": job_links.get(job_id, ""), "due": "", "since": ""})
    for key, ids, text in queued:
        shown = [j for j in ids if j in known]
        actions.append({"key": key, "app": shown[0] if shown else "", "apps": shown, "login": "", "kind": "queued",
                        "text": text, "link": "", "due": "", "since": ""})
    # A row whose job has no folder yet still names it: company and role from the tracker (the page's For column).
    for a in actions:
        job = by_id.get(row_job.get(a["key"], ""))
        if not a.get("app") and job:
            a["for"] = f"{job.get('company', '')} – {job.get('title', '')}"

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
    if nosite:
        checks.append(f"account-needed with no site named: {', '.join(nosite)} -> track.py wait <id> account-needed "
                      "\"<what>\" login=\"<platform> · <employer>\"")
    if boarded:
        checks.append(f"a sign-in to-do names a job board, but the application is on the employer's site: "
                      f"{', '.join(boarded)} -> track.py wait <id> account-needed \"<what>\" login=<the employer's site>")
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
    checks += outcome_checks(jobs, pipeline)
    checks += idle_checks(apps, steps, today)
    if calendar is not None:
        checks += calendar_checks(env, calendar, jobs, pipeline, today)
    if page is not None:
        checks = page_check(page) + checks
    bare = [x["employer"] for x in excluded if not x.get("source")]
    if bare:
        checks.append(f"excluded employers without a source: {', '.join(bare)}")

    # Urgent first (it expires), then the sessions to answer, in their order, then "working" (Claude or a session is
    # on it: the person waits), then by deadline (a past one on top), then the rows of a session's jobs in the
    # session order, then by age: the older "since" first, rows without one last in the tracker's order.
    actions.sort(key=lambda a: (KINDS.get(a["kind"], (3, 5))[0], a.get("rank", 0), a["due"] == "", a["due"],
                                job_rank.get(row_job.get(a["key"]), 999), a["since"] == "", a["since"],
                                KINDS.get(a["kind"], (3, 5))[1]))

    # The page works each row's kind out again from its due date and the viewer's own day (a page opened on Monday
    # after a Friday export), and counts Do now from the rows; these counts are the export's, for a first paint.
    index = [{"key": f"stage:{s}", "group": "stage", "label": s, "n": sum(1 for a in apps if a["stage"] == s)}
             for s in STAGES.values()]
    index += [{"key": f"actions:{k}", "group": "actions", "label": k, "n": sum(1 for a in actions if a["kind"] == k)}
              for k in KINDS]
    index += [{"key": "actions:waiting", "group": "actions", "label": "waiting", "n": len(waits)},
              {"key": "logins:action", "group": "logins", "label": "need action",
               "n": sum(1 for r in login_rows if r["needs"])},
              {"key": "meta:generated", "group": "meta", "label": now.strftime("%Y-%m-%d %H:%M"), "n": 0},
              {"key": "meta:run", "group": "meta", "label": run_line(env, now), "n": 0},
              # The person's own Questions page (QUESTIONS_PAGE), linked from Do now.
              {"key": "meta:questions", "group": "meta", "label": env.get("QUESTIONS_PAGE") or "", "n": 0},
              # The page's Calendar tab keeps the events in the person's job-search colour or with this prefix.
              {"key": "meta:calendar_color", "group": "meta", "label": str(env.get("CALENDAR_COLOR") or "3"), "n": 0},
              {"key": "meta:calendar_prefix", "group": "meta",
               "label": (env.get("CALENDAR_PREFIX") or "Job search · ").strip(), "n": 0}]

    files = list(zip(FILES, (index, apps, steps, actions, login_rows, excluded, session_rows)))
    return files, checks, (f"{len(apps)} applications, {len(steps)} steps, {len(actions)} actions, "
                           f"{len(login_rows)} logins, {len(excluded)} excluded employers, {len(session_rows)} sessions")


FILES = ("index.json", "applications.json", "steps.json", "actions.json", "logins.json", "excluded.json",
         "sessions.json")


def uploads_path(env):
    """Beside the tracker: which export of each file is on the page now ({"at", "files": {name: sha256}})."""
    return os.path.join(os.path.dirname(env.path("TRACKER")), "dashboard-uploads.json")


def digest(name, rows):
    """The sha256 of a file's rows as the page has them, without the export time (meta:generated): the same records
    give the same digest at any minute. Example: two exports a minute apart with no new record have one digest for
    index.json."""
    if name == "index.json":
        rows = [r for r in rows if not (isinstance(r, dict) and r.get("key") == "meta:generated")]
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, indent=1).encode("utf-8")).hexdigest()


def digest_file(path):
    with open(path, encoding="utf-8") as fh:
        return digest(os.path.basename(path), json.load(fh))


def questions_check(env):
    """The Questions page's line for --check: "" when it is up to date or the person has no questions file yet."""
    qpath = env.path("QUESTIONS") if env.get("QUESTIONS") else os.path.join(env.home, "apply", "questions.json")
    if not os.path.isfile(qpath):
        return ""
    res = subprocess.run([sys.executable, "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "questions.py"),
                          "build", "--check", "--env", env.file], capture_output=True, text=True, encoding="utf-8")
    out = (res.stdout or "").strip().splitlines()
    if res.returncode or not out:
        return f"questions.py build --check failed: {((res.stderr or '').strip().splitlines() or ['no output'])[-1]}"
    return "" if out[-1] == "the Questions page is up to date" else out[-1]


def main():
    args = sys.argv[1:]
    env_arg = None
    if "--env" in args:
        i = args.index("--env")
        env_arg = args[i + 1]
        del args[i:i + 2]
    given = {}
    for opt in ("--calendar", "--page"):
        if opt in args:
            i = args.index(opt)
            if i + 1 >= len(args):
                sys.exit(f"{opt} takes a saved file: " + ("a Google Calendar list_events answer (JSON)"
                         if opt == "--calendar" else "the dashboard store's files/index.html (JSON or HTML)"))
            try:
                with open(args[i + 1], encoding="utf-8") as fh:
                    raw = fh.read()
                given[opt] = raw if opt == "--page" and not raw.lstrip().startswith("{") else json.loads(raw)
            except (OSError, ValueError) as e:
                sys.exit(f"{opt}: {args[i + 1]} is not readable ({e})")
            del args[i:i + 2]
    calendar = given.get("--calendar")
    flags, rest = {a for a in args if a.startswith("--")}, [a for a in args if not a.startswith("--")]
    if flags - {"--check", "--uploaded"} or len(flags) > 1:
        sys.exit(__doc__)
    if "--uploaded" in flags and len(rest) < 2:
        sys.exit("--uploaded <out dir> <file> ...: name the files you uploaded (the export's \"upload:\" line), or "
                 "\"all\"; the others keep their earlier record")
    if "--uploaded" not in flags and len(rest) != (0 if "--check" in flags else 1):
        sys.exit(__doc__)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # a check line may name an employer the console cannot print
    env = jsenv.load(env_arg, __file__)
    now = datetime.datetime.now()
    if "--uploaded" in flags:
        # Only what was really uploaded is on the page: a file the export wrote and nobody uploaded is not.
        if "all" in rest[1:] and rest[1:] != ["all"]:
            sys.exit('"all" stands alone, without file names')
        names = list(FILES) if rest[1:] == ["all"] else list(dict.fromkeys(rest[1:]))
        unknown = [n for n in names if n not in FILES]
        missing = [n for n in names if n in FILES and not os.path.isfile(os.path.join(rest[0], n))]
        if unknown or missing:
            sys.exit((f"not a file of the export: {', '.join(unknown)}. " if unknown else "")
                     + (f"not in {rest[0]}: {', '.join(missing)}. " if missing else "") + "Nothing recorded.")
        have = {}
        if os.path.isfile(uploads_path(env)):
            try:
                with open(uploads_path(env), encoding="utf-8") as fh:
                    have = dict(json.load(fh).get("files") or {})
            except (OSError, ValueError, AttributeError, TypeError) as e:
                sys.exit(f"{uploads_path(env)} is not readable ({e}): delete it, then run --uploaded <out dir> all "
                         "after uploading every file")
        try:
            have.update({name: digest_file(os.path.join(rest[0], name)) for name in names})
        except (OSError, ValueError) as e:
            sys.exit(f"an exported file is not readable ({e}): export again, then --uploaded. Nothing recorded.")
        have = {name: have[name] for name in FILES if name in have}
        with open(uploads_path(env), "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"at": now.replace(microsecond=0).isoformat(), "files": have}, fh, indent=1)
        print(f"recorded as on the page: {' '.join(names)}")
        kept = [name for name in have if name not in names]
        print(f"earlier record kept: {' '.join(kept) or 'none'}")
        never = [name for name in FILES if name not in have]
        if never:
            print(f"never recorded as uploaded: {' '.join(never)}")
        return
    files, checks, summary = build(env, now, calendar, given.get("--page"))
    behind = []
    if "--check" in flags and os.path.isfile(uploads_path(env)):
        # The records against what is on the page, without writing: each file as the export would write it.
        with open(uploads_path(env), encoding="utf-8") as fh:
            on_page = json.load(fh).get("files", {})
        behind = [name for name, rows in files if digest(name, rows) != on_page.get(name)]
        if behind:
            checks.insert(0, f"the page is behind the records: {' '.join(behind)} -> export, upload them, then "
                             "--uploaded")
    if "--check" in flags:
        line = questions_check(env)
        if line:
            checks.insert(1 if behind else 0, line)
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
        changed = [name for name in FILES if digest_file(os.path.join(out_dir, name)) != on_page.get(name)]
        print("upload:", " ".join(changed) or "none")
        print("unchanged:", " ".join(name for name in FILES if name not in changed) or "none")
    for line in checks:
        print("check:", line)
    print(f"check: {len(checks)} mismatches")


if __name__ == "__main__":
    main()
