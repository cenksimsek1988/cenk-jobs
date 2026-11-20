"""The person's logins: connectors (Gmail, Google Calendar, Google Drive, Claude in Chrome, ...) and job-site sign-ins.

python -I logins.py sync                                   rebuild the job-site rows from the tracker's open jobs
python -I logins.py set <id> <status> "<note>" [key=value]  record a check (keys: name, kind, fix, link, account)
python -I logins.py show                                   one line per login
Statuses: connected (a connector that answered), signed-in (a site the person is signed in to), needs-sign-up (no
account yet: the person creates it), expired (the person was signed in and the session ended: a sign-in page where
a form was), needs-sign-in, needs-reconnect, blocked (a bot check or terms page waiting on the person), excluded (the
site of an employer the person's rules exclude: no sign-in needed; sync sets it, whatever the site's last state, by
its name, the part after "·" or the employers of the jobs on it; the employers themselves are in the dashboard's
Excluded tab, not in this file), unknown (older rows only; the dashboard shows it as "not signed
in"). sync makes new site rows needs-sign-in; Claude sets needs-sign-up and expired with `set`.
sync files each job under the row of its site, one row per site (a job board by the board's name: "LinkedIn Easy
Apply" waits under "LinkedIn"); a job whose site is not named yet (a board that only forwards) gets no row.
A site no job waits on keeps its last state: signed-in with its own note, any other state with the note "no
application waits on it (since <date>)", the earlier note kept in its history.
Example: `set "Acme Jobs" signed-in "no open job: the offer closed, 6 Nov 2026"`.
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
from trackerlib import JOB_BOARD, PER_EMPLOYER, employer_link, flat_jobs, job_urls, login_of, workday_host  # noqa: E402
from trackerlib import PAGES_BEHIND, SYNC_NOTE, site_key  # noqa: E402

STATUSES = ("connected", "signed-in", "needs-sign-up", "expired", "needs-sign-in", "needs-reconnect", "blocked",
            "excluded", "unknown")
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
    # A Workday site is one row per tenant host: a row named by its host (older syncs) takes the employer's name, or
    # goes into the named row of the same host; a job matches the row on its host, whatever the employer's spelling.
    # Seen: a "Workday · <Employer>" row with 0 jobs while a job on its host waited under the host's name.
    on_host = {}
    for job in flat_jobs(tracker):
        h = workday_host(*job_urls(job))
        if h:
            on_host.setdefault(h, login_of(job))
    named = {}
    for row in [r for r in rows.values() if r.get("kind") == "site"]:
        h = workday_host(row["id"], row.get("link") or "")
        if h and row["id"].lower() != h:
            named.setdefault(h, row["id"])
    for row in [r for r in rows.values() if r.get("kind") == "site" and workday_host(r["id"]) == r["id"].lower()]:
        h = row["id"].lower()
        target = named.get(h) or (on_host.get(h) if on_host.get(h) in rows else "")
        if target:
            # The named row stays; the host row's last state goes into its history.
            del rows[row["id"]]
            rows[target].setdefault("history", []).append(
                {k: row[k] for k in ("checked", "status", "note") if k in row} | {"was": row["id"]})
            named[h] = target
        elif h in on_host:
            del rows[row["id"]]
            name = on_host[h]
            row.update(id=name, name=name, link=row.get("link") or f"https://{h}")
            rows[name] = row
            named[h] = name
    # One row per site: a job waits under the row already kept for its site, whatever its spelling, never a second
    # one (seen 20 Nov 2026: "linkedin" rows made beside a signed-in "LinkedIn" one asked for a sign-in). Of
    # several, the plainest name, as export_dashboard.merge_logins keeps.
    same_site = {}
    for row in sorted((r for r in rows.values() if r.get("kind") == "site"),
                      key=lambda r: (len(str(r.get("name") or r["id"])), r["id"])):
        same_site.setdefault(site_key(row), row["id"])
    for job in flat_jobs(tracker):
        if job.get("status") == "account-needed":
            login = named.get(workday_host(*job_urls(job))) or login_of(job)
            if not login:
                continue  # no site named yet (a job board that only forwards): export_dashboard.py --check names it
            if login not in rows:
                login = same_site.setdefault(site_key({"id": login}), login)
            waiting.setdefault(login, []).append(job["id"])
            if not links.get(login):
                links[login] = employer_link(job, login)
    for row in list(rows.values()):
        if row.get("status") == "banned":  # the older name of the state
            row["status"] = "excluded"
        if row.get("kind") == "site":
            row["jobs"] = sorted(waiting.pop(row["id"], []))
            # An employer's own site is never signed in to through a job board's page.
            if PER_EMPLOYER.search(row["id"]) and JOB_BOARD.search(row.get("link") or ""):
                row["link"] = ""
            row["link"] = row.get("link") or links.get(row["id"], "")
            # A row sync made earlier that no job waits on any more goes; a row Claude set by hand stays, and says
            # that nothing waits on it, so an old "Sign in ..." never reads as a request (seen 20 Nov 2026: a sign-in
            # done for jobs already sent).
            if not row["jobs"] and row.get("note", "").startswith(SYNC_NOTE):
                del rows[row["id"]]
            elif not row["jobs"] and row.get("status") not in OK + ("excluded",) \
                    and not row.get("note", "").startswith("no application waits"):
                row.setdefault("history", []).append({k: row[k] for k in ("checked", "status", "note") if k in row})
                row["note"] = f"no application waits on it (since {now[:10]})"
    for site, ids in waiting.items():
        rows[site] = {"id": site, "name": site, "kind": "site", "status": "needs-sign-in", "checked": now,
                      "note": SYNC_NOTE, "jobs": sorted(ids), "link": links.get(site, "")}
    # Excluded employers are listed in the dashboard's Excluded tab (employerlib.excluded_list), not here: rows of
    # kind "employer" from older versions go, and a job site of an excluded employer is marked excluded.
    for rid in [k for k, r in rows.items() if r.get("kind") == "employer"]:
        del rows[rid]
    import employerlib as el
    pipeline = el.load_json(env.path("PIPELINE"), {}) if env.get("PIPELINE") else {}
    excluded = el.excluded_list(env, flat_jobs(tracker), pipeline)
    on_site = {}  # login id -> the employers of the tracker's jobs on it
    for job in flat_jobs(tracker):
        on_site.setdefault(login_of(job), set()).add(job.get("company", ""))
    for site in [r for r in rows.values() if r.get("kind") == "site" and not r.get("jobs")]:
        # Whatever its last state: "Workday · Acme", expired, is Acme's own site (employerlib.excluded_site).
        hit = el.excluded_site(site, excluded, on_site.get(site["id"], ()))
        note = f"employer excluded: {hit['employer']}, see the Excluded tab" if hit else ""
        if hit and (site.get("status"), site.get("note")) != ("excluded", note):
            site.setdefault("history", []).append({k: site[k] for k in ("checked", "status", "note") if k in site})
            site.update(status="excluded", note=note, checked=now)
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
    print(PAGES_BEHIND)
else:
    for r in data["logins"]:
        print(f"{r['id']:32} {r.get('kind', ''):9} {r['status']:15} {len(r.get('jobs', []))} jobs  {r.get('note', '')[:60]}")
