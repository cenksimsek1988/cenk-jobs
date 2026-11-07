"""The person's logins: connectors (Gmail, Google Calendar, Google Drive, Claude in Chrome, ...) and job-site sign-ins.

python -I logins.py sync                                   rebuild the job-site rows from the tracker's open jobs
python -I logins.py set <id> <status> "<note>" [key=value]  record a check (keys: name, kind, fix, link, account)
python -I logins.py show                                   one line per login
Statuses: connected (a connector that answered), signed-in (a site the person is signed in to), needs-sign-up (no
account yet: the person creates it), expired (the person was signed in and the session ended: a sign-in page where
a form was), needs-sign-in, needs-reconnect, blocked (a bot check or terms page waiting on the person), excluded (an
employer the person's rules exclude: no sign-in needed), unknown (older rows only; the dashboard shows it as "not
signed in"). sync makes new site rows needs-sign-in; Claude sets needs-sign-up, expired and excluded with `set`.
A site no job waits on keeps its last state, with the reason in its note: signed-in, or needs-sign-in (shown as
"not signed in"). Example: `set "Acme Jobs" signed-in "no open job: the offer closed, 6 Nov 2026"`.
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


def excluded_employers(tracker):
    """[(row, reason)] for each employer with a job excluded by the rules or withdrawn on ethics."""
    import employerlib as el
    rule_set = el.rules(env)
    pipeline = el.load_json(env.path("PIPELINE"), {}) if env.get("PIPELINE") else {}
    labels = {c: s.get("label", c) for c, s in rule_set["categories"].items()}
    by_company, withdrawn, notes = {}, {}, {}
    for job in flat_jobs(tracker):
        p = pipeline.get(job.get("id")) or {}
        if p.get("same_as"):
            p = pipeline.get(p["same_as"]) or p
        if p.get("stage") == "declined" and p.get("why") == "ethics":
            withdrawn.setdefault(job.get("company", ""), p)
        if job.get("status") == "excluded" or (p.get("stage") == "declined" and p.get("why") == "ethics"):
            by_company.setdefault(job.get("company", ""), []).append(job.get("title") or job["id"])
            notes.setdefault(job.get("company", ""), job.get("outcome") or "")

    def short(text, n=140):
        text = (text or "").strip()
        return text[:n].rstrip() + ("..." if len(text) > n else "")

    out = []
    for company, titles in sorted(by_company.items()):
        found = el.excluding(env, company, rule_set)
        checks = el.lookup(env, company)
        p = withdrawn.get(company, {})
        parts = []
        # On the never-apply list: the reason is the finding behind it, so the person sees what the employer does.
        if found and found[0]["origin"] == "list":
            flagged = [(c, k) for c, k in checks.items() if k.get("status") == "flagged"]
            # A group's unit ("Acme Cloud" under "Acme"): the finding may be recorded under the list's own name.
            for name in [n for n in rule_set.get("never_apply", []) if el.on_never_list(company, [n])]:
                if not flagged:
                    checks = el.lookup(env, name)
                    flagged = [(c, k) for c, k in checks.items() if k.get("status") == "flagged"]
            if flagged:
                found = [{"category": c, "origin": "finding", "level": k.get("level", "direct")} for c, k in flagged]
        for f in found:
            cat = f["category"] or p.get("category", "")
            fact = (checks.get(cat, {}).get("fact") or "") if cat else ""
            if not fact and f["origin"] == "decision" and cat:
                # A group's unit: the decision and its finding are recorded under the group's own name.
                own_name, _ = el.find_entry(el.checks_file(env).get("employers", {}), company)
                if own_name:
                    fact = el.lookup(env, own_name).get(cat, {}).get("fact") or ""
            if f["origin"] == "list":
                names = [n for n in rule_set.get("never_apply", []) if el.on_never_list(company, [n])]
                parts.append("on your never-apply list" + (f" ({', '.join(names)})" if names else "")
                             + "; no finding recorded yet: Claude checks it at the next run")
            elif f["origin"] == "decision":
                parts.append("your decision" + (f", {labels.get(cat, cat)}" if cat else "")
                             + (f": {short(fact)}" if fact else (f": {short(p.get('reason'))}" if p.get("reason") else "")))
            else:
                parts.append(f"{labels.get(cat, cat)} ({f.get('level', 'direct')})" + (f": {short(fact)}" if fact else ""))
        # No reason left in the checks (an older screen): the tracker's own note says why.
        fallback = short(notes.get(company, "").removeprefix("employer excluded: "), 160) or "by your rules when the job was screened"
        reason = ("Withdrawn" if p else "Excluded") + ": " + ("; ".join(parts) or fallback)
        reason += f". Jobs: {'; '.join(t[:60] for t in titles[:4])}" + (f" and {len(titles) - 4} more" if len(titles) > 4 else "")
        out.append(({"id": f"employer: {company}", "name": company, "kind": "employer", "status": "excluded",
                     "jobs": [], "link": "", "auto": True}, reason))
    return out


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
        if row.get("status") == "banned":  # the older name of the state
            row["status"] = "excluded"
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
    # Every employer the person turned down for their rules, so they remember it: one "excluded" row each, with the
    # reason in words. Rebuilt at each sync from the tracker, the pipeline and the person's own employer checks.
    for rid in [k for k, r in rows.items() if r.get("kind") == "employer" and r.get("auto")]:
        del rows[rid]
    import employerlib as el
    for row, reason in excluded_employers(tracker):
        site = next((r for r in rows.values() if r.get("kind") == "site"
                     and el.keys(r.get("name", "")) & el.keys(row["name"])), None)
        if site:
            site.update(status="excluded", note=reason)
        else:
            rows[row["id"]] = dict(row, note=reason, checked=now)
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
