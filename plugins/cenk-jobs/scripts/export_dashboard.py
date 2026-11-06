"""Export the job search as the dashboard's tree of small JSON files, each fact in one file only.

Usage: python -I export_dashboard.py <out dir> [--env <job-search.env>]
Writes, in <out dir>:
  index.json         the root: one row per headline count (stages, actions by kind, logins needing action) and the
                     export time. The page's tiles read only this, so it opens fast.
  applications.json  one row per application folder (APPLICATIONS_DIR/<stage>/<folder>/overview.md), keyed by
                     the tracker's job id: company, role, stage, applied, where, CV, folder.
  steps.json         one row per hiring step: its job id (app), name, date and details - no company or role, which
                     the page takes from applications.json by the id.
  actions.json       one row per thing the person can do now: kind click (sign in, open a page), info (answer a
                     question), task (a test, online tasks, an AI interview, a deadline), or working (Claude or a
                     session with the person is on it: wait); each points at a job id (app) and/or a login id
                     (login) instead of repeating them.
  logins.json        one row per connector and job site (from LOGINS): status, when checked, how to fix it, and
                     how many jobs wait on it.
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


def open_job(status):
    # Jobs that wait on the person (account-needed, needs-person, needs-captcha, an older "needs-<name>"), or are
    # ready to send.
    return waits_on_person(status) or status == "to-apply"


def plain(text):
    return re.sub(r"\s+", " ", LINK.sub(r"\1", text or "")).strip()


def short(text, n=220):
    text = no_pay(plain(text))
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + "…"


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
                   "account": r.get("account", ""), "jobs": len(r.get("jobs", []))} for r in logins]
    sites = {r["id"] for r in logins}

    actions = []
    tracker = json.load(open(env.path("TRACKER"), encoding="utf-8"))
    pipeline_path = env.path("PIPELINE") if env.get("PIPELINE") else ""
    pipeline = json.load(open(pipeline_path, encoding="utf-8")) if pipeline_path and os.path.isfile(pipeline_path) else {}
    # Every row gets a link: its own, else the job's application page off the job boards.
    job_links = {j["id"]: employer_link(j, login_of(j)) or j.get("apply_url", "") for j in flat_jobs(tracker)}
    for job in flat_jobs(tracker):
        app = job["id"] if job["id"] in known else ""
        if not open_job(job.get("status")):
            # In progress shows whatever the job's status: a posting still being screened is "found".
            for i, t in enumerate(t for t in job.get("todo") or [] if t.get("kind") == "working"):
                actions.append({"key": f"{job['id']}:w{i}", "app": app, "login": "", "kind": "working",
                                "text": short(t.get("text", ""), 240),
                                "link": t.get("link") or job_links.get(job["id"], ""), "due": t.get("due", "")})
            continue
        if job.get("todo"):  # the tracker's own list of what the person must do for this job wins
            for i, t in enumerate(job["todo"], 1):
                actions.append({"key": f"{job['id']}:{i}", "app": app, "login": t.get("login", ""),
                                "kind": t.get("kind", "info"), "text": short(t.get("text", ""), 240),
                                "link": t.get("link") or job_links.get(job["id"], ""), "due": t.get("due", "")})
            continue
        if job["status"] == "account-needed":
            site = login_of(job)
            if site in sites:
                continue  # one action per login, not per job: the login's row says how many jobs wait on it
            actions.append({"key": f"{job['id']}:signin", "app": app, "login": site if site in sites else "",
                            "kind": "click",
                            "text": f"Sign in (or create the account) on {site}, leave the profile empty, then tell Claude",
                            "link": job_links.get(job["id"], ""), "due": ""})
        else:
            actions.append({"key": f"{job['id']}:answer", "app": app, "login": "", "kind": "info",
                            "text": short(job.get("outcome") or (job.get("needs") or [""])[0] or job.get("note", ""), 240),
                            "link": job_links.get(job["id"], ""), "due": ""})
    for s in steps:
        if s["upcoming"] == "yes" and (s["due"] or TASKLIKE.search(s["step"])):
            # A step's email link (PIPELINE "mail"), never its own page: that may be a personal access link.
            p = pipeline.get(s["app"]) or {}
            p = (pipeline.get(p["same_as"]) or p) if p.get("same_as") else p
            p_steps = p.get("steps") or []
            mail = p_steps[s["n"] - 1].get("mail", "") if len(p_steps) >= s["n"] else ""
            actions.append({"key": f"{s['key']}:do", "app": s["app"], "login": "", "kind": "task",
                            "text": s["step"] + (f" - due {s['due']}" if s["due"] else ""),
                            "link": mail or job_links.get(s["app"], ""), "due": s["due"] or s["date"]})
    for r in logins:
        if r.get("status") not in OK_LOGIN and (r.get("kind") == "connector" or r.get("jobs") or r.get("fix")):
            verb = {"needs-reconnect": "Reconnect", "blocked": "Clear the check on"}.get(r.get("status"), "Sign in to")
            waiting = len(r.get("jobs", []))
            actions.append({"key": f"login:{r['id']}", "app": "", "login": r["id"], "kind": "click",
                            "text": f"{verb} {r.get('name', r['id'])}"
                                    + (f" ({waiting} application{'s wait' if waiting > 1 else ' waits'} on it), then tell Claude" if waiting else "")
                                    + (f": {short(r.get('fix', ''), 160)}" if r.get("fix") else ""),
                            "link": r.get("link", ""), "due": ""})
    # "working": Claude or a session with the person is on it, so the person waits; those rows come first.
    actions.sort(key=lambda a: (a["kind"] != "working", a["due"] == "", a["due"],
                                {"task": 0, "click": 1, "info": 2}.get(a["kind"], 3)))

    index = [{"key": f"stage:{s}", "group": "stage", "label": s, "n": sum(1 for a in apps if a["stage"] == s)}
             for s in STAGES.values()]
    index += [{"key": f"actions:{k}", "group": "actions", "label": k, "n": sum(1 for a in actions if a["kind"] == k)}
              for k in ("working", "task", "click", "info")]
    index += [{"key": "logins:ok", "group": "logins", "label": "working",
               "n": sum(1 for r in login_rows if r["status"] in OK_LOGIN)},
              {"key": "logins:action", "group": "logins", "label": "need action",
               "n": sum(1 for r in login_rows if r["status"] not in OK_LOGIN and (r["kind"] == "connector" or r["jobs"] or r["fix"]))},
              {"key": "meta:generated", "group": "meta", "label": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
               "n": len(apps)},
              {"key": "meta:run", "group": "meta", "label": run_line(env), "n": 0}]

    os.makedirs(out_dir, exist_ok=True)
    for fname, rows in (("index.json", index), ("applications.json", apps), ("steps.json", steps),
                        ("actions.json", actions), ("logins.json", login_rows)):
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=1)
    print(f"{len(apps)} applications, {len(steps)} steps, {len(actions)} actions, {len(login_rows)} logins -> {out_dir}")


if __name__ == "__main__":
    main()
