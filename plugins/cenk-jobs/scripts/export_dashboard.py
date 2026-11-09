"""Export the job search as the dashboard's tree of small JSON files, each fact in one file only.

Usage: python -I export_dashboard.py <out dir> [--env <job-search.env>]
Writes, in <out dir>:
  index.json         the root: one row per headline count (stages, actions by kind, logins needing action) and the
                     export time. The page's tiles read only this, so it opens fast.
  applications.json  one row per application folder (APPLICATIONS_DIR/<stage>/<folder>/overview.md), keyed by
                     the tracker's job id: company, role, stage, applied, where, CV, folder.
  steps.json         one row per hiring step: its job id (app), name, date and details - no company or role, which
                     the page takes from applications.json by the id.
  actions.json       one row per thing the person can do now: kind click (sign in, open a page), info (an open
                     question on the Questions page, from QUESTIONS), todo (anything else a job waits on the person
                     for, from its note), task (a test, online tasks, an AI interview, a deadline), urgent (a step only the
                     person can do that expires: an emailed code, a filled form's CAPTCHA, a task due within 24
                     hours; first in the list), or working (Claude or a
                     session with the person is on it: wait); each points at a job id (app) and/or a login id
                     (login) instead of repeating them.
  logins.json        one row per connector and job site (from LOGINS): status, when checked, how to fix it, and
                     how many jobs wait on it. The site of an excluded employer is left out: it needs no sign-in.
  excluded.json      the person's one list of excluded employers (employerlib.excluded_list): employer, Excluded or
                     Withdrawn, by what (their decision or their rules), why (the category), the finding in words,
                     its source, since when, and the jobs it stopped.
The calendar is not exported: the dashboard reads Google Calendar live (job-search events carry their own color).
Sources: the folders, TRACKER, PIPELINE and LOGINS. Pay figures and street addresses never go into these files,
since anyone who can open the dashboard can read them.
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jsenv  # noqa: E402
from trackerlib import employer_link, flat_jobs, login_of, no_pay, waits_on_person  # noqa: E402

# "Closed": the position closed or was filled (not a rejection); "Declined": the person said no.
STAGES = {"approved": "Moving forward", "pending": "Waiting for reply", "rejected": "Rejected", "closed": "Closed",
          "declined": "Declined", "not-applied": "Not sent"}
FIELD = re.compile(r"^- \*\*(.+?):\*\*\s*(.*)$")
STEP = re.compile(r"^\d+\.\s+\*\*(.+?)\*\*\s*-\s*(.+)$")
# A markdown link; a target in <...> may hold spaces and parentheses (step folders such as "01 ... (45 min)").
LINK = re.compile(r"\[([^\]]*)\]\((?:<[^>]*>|[^)]*)\)")
TASKLIKE = re.compile(r"(?i)task|test|assessment|assignment|questionnaire|ai interview|video interview|form|challenge")
OK_LOGIN = ("connected", "signed-in")
# An excluded employer (by the person's rules) needs no sign-in, so it is never in Do now.
NO_ACTION = OK_LOGIN + ("excluded",)


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


def urgent_if_soon(kind, due):
    """A task due today or tomorrow is Urgent (RULES.md, "Urgent steps"), whether a hiring step or a job's own to-do."""
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
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
            checks = el.lookup(env, company)
            verdict, _ = el.decide(env, company, checks, rule_set)
            asks, warns = [], []
            for cat, k in checks.items():
                s = rule_set["categories"].get(cat)
                if k.get("status") != "flagged" or s is None:
                    continue
                level = k.get("level", "direct")
                act = s.get("action", "discuss") if level == "direct" else s.get("indirect", "discuss")
                item = {"label": s.get("label", cat), "level": level, "fact": k.get("fact", ""),
                        "src": k.get("source_url", "")}
                (asks if act == "discuss" else warns if act == "warn" else []).append(item)
            memo[company] = (verdict, asks, warns)
        return memo[company]
    return view


def run_line(env):
    """Whether a run is going, from the usage log's "run" rows (started, then ok|failed|stopped), and the next one."""
    path = env.path("USAGE_LOG") if env.get("USAGE_LOG") else os.path.join(env.home, "apply", "usage-log.jsonl")
    rows = []
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            rows = [r for r in (json.loads(line) for line in f if line.strip()) if r.get("step") == "run"]
    nxt = f"Next: every day at {env.get('SEARCH_TIME') or '19:00'}."
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


def main():
    args = sys.argv[1:]
    env = jsenv.load(args[args.index("--env") + 1] if "--env" in args else None, __file__)
    out_dir = [a for i, a in enumerate(args) if a != "--env" and (i == 0 or args[i - 1] != "--env")][0]
    root = env.path("APPLICATIONS_DIR")
    today = datetime.date.today().isoformat()

    apps, steps = [], []
    for stage_dir, stage in STAGES.items():
        base = os.path.join(root, stage_dir)
        for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
            ov = os.path.join(base, name, "overview.md")
            if not os.path.isfile(ov):
                continue
            o = parse(ov)
            f = o["fields"]
            job_id = f.get("job id") or f"{stage_dir}/{name}"
            # Titles and folder names can carry a posted rate ("Java Engineer - EUR 400 a day"): mask them too.
            company, _, role = no_pay(o["title"]).partition(" - ")
            apps.append({"id": job_id, "stage": stage, "company": company.strip(), "role": role.strip(),
                         "applied": f.get("applied", ""), "where": no_pay(f.get("where", "")),
                         "cv": re.sub(r"^.*?-CV-", "", f.get("cv sent", "")).replace(".pdf", "").replace("-", " "),
                         "letter": "yes" if f.get("cover letter") and "none" not in f.get("cover letter", "").lower() else "no",
                         "status": short(f.get("status", ""), 160), "reminder": short(f.get("reminder", ""), 160),
                         "folder": no_pay(f"{os.path.basename(root)}/{stage_dir}/{name}")})
            for i, s in enumerate(o["steps"], 1):
                found = dates(s["detail"])
                steps.append({"key": f"{job_id}#{i}", "app": job_id, "n": i, "step": no_pay(s["name"]),
                              "date": found[0] if found else "", "due": max(found) if len(found) > 1 else "",
                              "detail": short(s["detail"], 160),
                              "upcoming": "yes" if found and max(found) >= today else "no"})
    known = {a["id"] for a in apps}

    logins_path = env.path("LOGINS") if env.get("LOGINS") else ""
    logins = []
    if logins_path and os.path.exists(logins_path):
        logins = json.load(open(logins_path, encoding="utf-8")).get("logins", [])
    login_rows = [{"id": r["id"], "name": r.get("name", r["id"]), "kind": r.get("kind", "site"),
                   "status": r.get("status", "unknown"), "checked": (r.get("checked") or "")[:16].replace("T", " "),
                   "note": short(r.get("note", ""), 160), "fix": short(r.get("fix", ""), 200), "link": r.get("link", ""),
                   "account": r.get("account", ""), "jobs": len(r.get("jobs", []))}
                  for r in logins if r.get("status") != "excluded" and r.get("kind") != "employer"]
    sites = {r["id"] for r in logins}

    actions = []
    tracker = json.load(open(env.path("TRACKER"), encoding="utf-8"))
    pipeline_path = env.path("PIPELINE") if env.get("PIPELINE") else ""
    pipeline = json.load(open(pipeline_path, encoding="utf-8")) if pipeline_path and os.path.isfile(pipeline_path) else {}
    # Every row gets a link: its own, else the job's application page off the job boards.
    job_links = {j["id"]: employer_link(j, login_of(j)) or j.get("apply_url", "") for j in flat_jobs(tracker)}
    view = employer_view(env)
    import employerlib as el
    # Findings are public facts about the employer, never the person's pay: plain text, not pay-masked.
    excluded = [{k: (re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else v) for k, v in x.items() if k != "names"}
                for x in el.excluded_list(env, flat_jobs(tracker), pipeline)]
    # The Questions page's open questions (QUESTIONS): Do now's Question rows, one each, so the two never differ; a
    # job with an open question there shows no other row from its note.
    qpath = env.path("QUESTIONS") if env.get("QUESTIONS") else os.path.join(env.home, "apply", "questions.json")
    qs_open = open_questions(qpath)
    asked_jobs = {j for q in qs_open.values() for j in q.get("jobs", [])}
    for qid, q in qs_open.items():
        first = (q.get("jobs") or [""])[0]
        actions.append({"key": f"q:{qid}", "app": first if first in known else "", "login": "", "kind": "info",
                        "text": short(q.get("text", ""), 240),
                        "link": env.get("QUESTIONS_PAGE") or job_links.get(first, ""), "due": ""})
    for job in flat_jobs(tracker):
        app = job["id"] if job["id"] in known else ""
        # The tracker's own list of what the person must do for this job wins, whatever the job's status: a sent job
        # still has its interview reminders or a withdrawal to send, and a posting being screened is "found".
        if not open_job(job.get("status")) and not job.get("todo"):
            continue
        if job.get("todo"):
            for i, t in enumerate(job["todo"], 1):
                actions.append({"key": f"{job['id']}:{i}", "app": app, "login": t.get("login", ""),
                                # A to-do is never a Question (those are the page's): no kind, or "info", is To do.
                                "kind": urgent_if_soon("todo" if t.get("kind", "info") == "info" else t["kind"],
                                                       t.get("due", "")),
                                "where": t.get("where", ""), "text": short(t.get("text", ""), 240),
                                "link": t.get("link") or job_links.get(job["id"], ""), "due": t.get("due", "")})
            continue
        if job["status"] == "account-needed":
            site = login_of(job)
            if site in sites:
                continue  # one action per login, not per job: the login's row says how many jobs wait on it
            # The site's name, even with no row in LOGINS yet: the dashboard labels it a sign-in, not a plain click.
            actions.append({"key": f"{job['id']}:signin", "app": app, "login": site,
                            "kind": "click",
                            "text": f"Sign in (or create the account) on {site}, leave the profile empty, then tell Claude",
                            "link": job_links.get(job["id"], ""), "due": ""})
        elif job["id"] not in asked_jobs:
            # What the job waits on, from its note: a To do, not a Question (questions live on the Questions page).
            actions.append({"key": f"{job['id']}:todo", "app": app, "login": "", "kind": "todo",
                            "text": short(job.get("outcome") or (job.get("needs") or [""])[0] or job.get("note", ""), 240),
                            "link": job_links.get(job["id"], ""), "due": ""})
    # Without questions.py's file (no Questions page yet): an employer the person's rules leave to them ("discuss")
    # gets a Question row here; with it, build already put that employer on the page.
    asked = set()
    for job in [] if os.path.exists(qpath) else flat_jobs(tracker):
        company = job.get("company", "")
        if job.get("status") in DONE or company in asked or job["id"] in pipeline:
            continue
        verdict, asks, _ = view(company)
        if verdict != "discuss" or not asks:
            continue
        asked.add(company)
        a = asks[0]
        more = f" (and {len(asks) - 1} more finding{'s' if len(asks) > 2 else ''})" if len(asks) > 1 else ""
        actions.append({"key": f"ask:{company}", "app": "", "login": "", "kind": "info",
                        "text": short(f"{company}, {job.get('title', '')}: {a['label']} ({a['level']}): {a['fact']}", 230)
                                + more + (". Allow, or exclude? Answer on your Questions page." if env.get("QUESTIONS_PAGE")
                                          else ". Allow, or exclude? Tell Claude."),
                        "link": env.get("QUESTIONS_PAGE") or a["src"] or job_links.get(job["id"], ""), "due": ""})
    for a in apps:
        _, _, warns = view(a["company"])
        a["warn"] = "; ".join(short(f"{w['label']} ({w['level']}): {w['fact']}", 150) for w in warns[:2])
    for s in steps:
        if s["upcoming"] == "yes" and (s["due"] or TASKLIKE.search(s["step"])):
            # A step's email link (PIPELINE "mail"), never its own page: that may be a personal access link.
            p = pipeline.get(s["app"]) or {}
            p = (pipeline.get(p["same_as"]) or p) if p.get("same_as") else p
            p_steps = p.get("steps") or []
            mail = p_steps[s["n"] - 1].get("mail", "") if len(p_steps) >= s["n"] else ""
            actions.append({"key": f"{s['key']}:do", "app": s["app"], "login": "", "kind": urgent_if_soon("task", s["due"]),
                            "text": s["step"] + (f" - due {s['due']}" if s["due"] else ""),
                            "link": mail or job_links.get(s["app"], ""), "due": s["due"] or s["date"]})
    for r in logins:
        if r.get("status") not in NO_ACTION and (r.get("kind") == "connector" or r.get("jobs") or r.get("fix")):
            verb = {"needs-reconnect": "Reconnect", "blocked": "Clear the check on", "needs-sign-up": "Create an account on",
                    "expired": "Sign in again to"}.get(r.get("status"), "Sign in to")
            waiting = len(r.get("jobs", []))
            actions.append({"key": f"login:{r['id']}", "app": "", "login": r["id"], "kind": "click",
                            "text": f"{verb} {r.get('name', r['id'])}"
                                    + (f" ({waiting} application{'s wait' if waiting > 1 else ' waits'} on it), then tell Claude" if waiting else "")
                                    + (f": {short(r.get('fix', ''), 160)}" if r.get("fix") else ""),
                            "link": r.get("link", ""), "due": ""})
    # Urgent first (it expires), then "working" (Claude or a session is on it: the person waits), then by deadline.
    actions.sort(key=lambda a: ({"urgent": 0, "working": 1}.get(a["kind"], 2), a["due"] == "", a["due"],
                                {"task": 0, "click": 1, "todo": 2, "info": 3}.get(a["kind"], 4)))

    index = [{"key": f"stage:{s}", "group": "stage", "label": s, "n": sum(1 for a in apps if a["stage"] == s)}
             for s in STAGES.values()]
    index += [{"key": f"actions:{k}", "group": "actions", "label": k, "n": sum(1 for a in actions if a["kind"] == k)}
              for k in ("urgent", "working", "task", "click", "todo", "info")]
    index += [{"key": "logins:ok", "group": "logins", "label": "working",
               "n": sum(1 for r in login_rows if r["status"] in OK_LOGIN)},
              {"key": "logins:action", "group": "logins", "label": "need action",
               "n": sum(1 for r in login_rows if r["status"] not in NO_ACTION and (r["kind"] == "connector" or r["jobs"] or r["fix"]))},
              {"key": "excluded:n", "group": "excluded", "label": "excluded employers", "n": len(excluded)},
              {"key": "meta:generated", "group": "meta", "label": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
               "n": len(apps)},
              {"key": "meta:run", "group": "meta", "label": run_line(env), "n": 0},
              # The person's own Questions page (QUESTIONS_PAGE), linked from Do now.
              {"key": "meta:questions", "group": "meta", "label": env.get("QUESTIONS_PAGE") or "", "n": 0}]

    os.makedirs(out_dir, exist_ok=True)
    for fname, rows in (("index.json", index), ("applications.json", apps), ("steps.json", steps),
                        ("actions.json", actions), ("logins.json", login_rows), ("excluded.json", excluded)):
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=1)
    print(f"{len(apps)} applications, {len(steps)} steps, {len(actions)} actions, {len(login_rows)} logins, "
          f"{len(excluded)} excluded employers -> {out_dir}")


if __name__ == "__main__":
    main()
