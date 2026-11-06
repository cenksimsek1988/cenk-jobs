"""The person's logins: connectors (Gmail, Google Calendar, Google Drive, Claude in Chrome, ...) and job-site sign-ins.

python -I logins.py sync                                   rebuild the job-site rows from the tracker's open jobs
python -I logins.py set <id> <status> "<note>" [key=value]  record a check (keys: name, kind, fix, link, account)
python -I logins.py show                                   one line per login
Statuses: connected (a connector that answered), signed-in (a site the person is signed in to), needs-sign-in,
needs-reconnect, blocked (a bot check or terms page waiting on the person), unknown.
The file (LOGINS in job-search.env) is the one place login state lives: the dashboard's Logins tab and its "Do now"
list read it, and each job-site row points at the tracker's jobs by id instead of repeating them. Claude writes it at
every session's health check: a connector's status from one cheap call, a site's from what the person or the browser
showed. Add --env <job-search.env> anywhere to pick the env file.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jsenv  # noqa: E402
from trackerlib import JOB_BOARD, PER_EMPLOYER, employer_link, flat_jobs, login_of  # noqa: E402

STATUSES = ("connected", "signed-in", "needs-sign-in", "needs-reconnect", "blocked", "unknown")
OK = ("connected", "signed-in")
args = sys.argv[1:]
env_arg = None
if "--env" in args:
    i = args.index("--env")
    env_arg = args[i + 1]
    del args[i:i + 2]
env = jsenv.load(env_arg, __file__)
PATH = env.path("LOGINS")
now = datetime.datetime.now().replace(microsecond=0).isoformat()


def load():
    if not os.path.exists(PATH):
        return {"_about": "Login state: connectors and job-site sign-ins. Written by Claude at each health check.",
                "logins": []}
    with open(PATH, encoding="utf-8") as f:
        return json.load(f)


def save(data):
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PATH)


if not args or args[0] not in ("sync", "set", "show"):
    sys.exit(__doc__)
data = load()
rows = {r["id"]: r for r in data["logins"]}
if args[0] == "sync":
    tracker = json.load(open(env.path("TRACKER"), encoding="utf-8"))
    waiting, links = {}, {}
    for job in flat_jobs(tracker):
        if job.get("status") == "account-needed":
            login = login_of(job)
            waiting.setdefault(login, []).append(job["id"])
            if not links.get(login):
                links[login] = employer_link(job, login)
    for row in list(rows.values()):
        if row.get("kind") == "site":
            row["jobs"] = sorted(waiting.pop(row["id"], []))
            # An employer's own site is never signed in to through a job board's page.
            if PER_EMPLOYER.search(row["id"]) and JOB_BOARD.search(row.get("link") or ""):
                row["link"] = ""
            row["link"] = row.get("link") or links.get(row["id"], "")
            # A row sync made earlier that no job waits on any more goes; a row Claude set by hand stays.
            if not row["jobs"] and row.get("note", "").startswith("an application waits"):
                del rows[row["id"]]
    for site, ids in waiting.items():
        rows[site] = {"id": site, "name": site, "kind": "site", "status": "needs-sign-in", "checked": now,
                      "note": "an application waits on this site's sign-in or account", "jobs": sorted(ids),
                      "link": links.get(site, "")}
    data["logins"] = sorted(rows.values(), key=lambda r: (r.get("kind") != "connector", r["id"]))
    save(data)
    print(f"{sum(1 for r in data['logins'] if r.get('kind') == 'site')} sites, "
          f"{sum(1 for r in data['logins'] if r.get('kind') == 'connector')} connectors -> {PATH}")
elif args[0] == "set":
    login_id, status, note = args[1], args[2], args[3] if len(args) > 3 else ""
    if status not in STATUSES:
        sys.exit(f"status must be one of {', '.join(STATUSES)}")
    row = rows.setdefault(login_id, {"id": login_id, "name": login_id, "kind": "site", "jobs": []})
    for pair in args[4:]:
        key, _, value = pair.partition("=")
        row[key] = value
    # Keep the earlier state: the old note is often the only record of what was seen and when.
    if "status" in row and (row["status"], row.get("note", "")) != (status, note):
        row.setdefault("history", []).append({k: row[k] for k in ("checked", "status", "note") if k in row})
    row.update(status=status, note=note, checked=now)
    data["logins"] = sorted(rows.values(), key=lambda r: (r.get("kind") != "connector", r["id"]))
    save(data)
    print(login_id, "->", status)
else:
    for r in data["logins"]:
        print(f"{r['id']:32} {r.get('kind', ''):9} {r['status']:15} {len(r.get('jobs', []))} jobs  {r.get('note', '')[:60]}")
