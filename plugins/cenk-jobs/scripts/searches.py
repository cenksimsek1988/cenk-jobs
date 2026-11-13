"""The person's saved searches (SEARCHES in job-search.env, default apply/searches.json): one row per search.

A row with an email alert is read from Gmail at every run; a site without alerts is searched on every weekday
by default (every=<days> for a longer gap), never on a Saturday or Sunday: a check that falls there is due on
Monday. So a run looks only at what is new instead of searching every site again. A search never read is due at once.

python -I searches.py add "<site>" "<query>" alert=yes gmail="<Gmail query>"     a search with an email alert
python -I searches.py add "<site>" "<query>" alert=no                            a site without alerts, every weekday
python -I searches.py add "<site>" "<query>" alert=no every=7                    the same, every 7 days
python -I searches.py list                                                       one line per search
python -I searches.py due                                                        the searches due today; with none
                                                                                 saved, one line that says so
python -I searches.py sites                                                      the sites of the tracker's jobs that
                                                                                 have no saved search, most jobs first
python -I searches.py done <id> found=<n>                                        record that a search was read
python -I searches.py seen <url> [<url> ...]                                     says "new" or "known" per link
python -I searches.py seen --file <links file>                                   the same, one link per line in a file
Add --env <job-search.env> anywhere to pick the env file; --today <YYYY-MM-DD> reads "due" as of that day.
add also takes note="<text>". Example: searches.py add "Acme careers" "engineering" alert=no note="no alert offered, 2026-11-13"
Example: searches.py add LinkedIn "Backend engineer, remote" alert=yes gmail="from:jobalerts-noreply@linkedin.com newer_than:2d"
"""
import datetime
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jsenv  # noqa: E402
from trackerlib import flat_jobs  # noqa: E402

args = sys.argv[1:]
env_arg = None
if "--env" in args:
    i = args.index("--env")
    env_arg = args[i + 1]
    del args[i:i + 2]
as_of = None
if "--today" in args:
    i = args.index("--today")
    as_of = args[i + 1] if i + 1 < len(args) else ""
    del args[i:i + 2]
    try:
        datetime.date.fromisoformat(as_of)
    except ValueError:
        sys.exit("--today takes a date, YYYY-MM-DD")
if not args or args[0] not in ("add", "list", "due", "done", "seen", "sites"):
    sys.exit(__doc__)
env = jsenv.load(env_arg, __file__)
PATH = env.path("SEARCHES") if env.get("SEARCHES") else env.path("TRACKER") + "/../searches.json"
PATH = os.path.normpath(PATH)
today = datetime.date.fromisoformat(as_of) if as_of else datetime.date.today()


def load():
    if not os.path.exists(PATH):
        return {"_about": "Saved searches: read from alert emails, or checked on a schedule (searches.py).", "searches": []}
    with open(PATH, encoding="utf-8") as f:
        return json.load(f)


def save(data):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(PATH + ".tmp", PATH)


def pairs(items):
    return dict(item.split("=", 1) for item in items if "=" in item)


TRACKING = re.compile(r"(?i)^(utm_\w+|trk\w*|tracking\w*|ref|refid|referrer|src|source|gh_src|mc_\w+|fbclid|gclid|lever-\w+)$")


def key_of(url):
    """One job, one key: a board's links differ per email, the job's number does not. Elsewhere the query stays, without
    what only tracks the click: a false "new" costs a screen, a false "known" loses the job."""
    url = url.strip()
    parts = urllib.parse.urlparse(url)
    host = parts.netloc.lower().removeprefix("www.")
    query = urllib.parse.parse_qs(parts.query)
    if "linkedin." in host:
        found = re.findall(r"\d{6,}", parts.path) or query.get("currentJobId")
        if found:
            return "linkedin:" + found[-1]
    if "indeed." in host:
        found = query.get("jk") or query.get("vjk")
        if found:
            return "indeed:" + found[0]
    kept = sorted((k, v) for k, v in urllib.parse.parse_qsl(parts.query) if not TRACKING.match(k))
    return host + parts.path.rstrip("/").lower() + ("?" + urllib.parse.urlencode(kept) if kept else "")


def is_due(row):
    last = row.get("last_checked")
    if not last:
        return True
    if row.get("alert"):
        return (today - datetime.date.fromisoformat(last[:10])).days >= 1
    if today.weekday() >= 5:  # a site search waits for Monday; an alert's emails are read at any run
        return False
    return (today - datetime.date.fromisoformat(last[:10])).days >= int(row.get("every_days") or 1)


def host_of(url):
    return urllib.parse.urlparse(url.strip()).netloc.lower().removeprefix("www.")


def covers(row, host):
    """A saved search covers a host when its site's name is in it ("LinkedIn" in linkedin.com) or it names the host."""
    name = re.sub(r"[^a-z0-9]", "", row.get("site", "").lower())
    words = " ".join((row.get("site", ""), row.get("query", ""), row.get("gmail", ""), row.get("note", ""))).lower()
    return (len(name) >= 3 and name in re.sub(r"[^a-z0-9]", "", host)) or host in words


data = load()
rows = data["searches"]
cmd = args[0]
if cmd == "add":
    if len(args) < 4:
        sys.exit(__doc__)
    extra = pairs(args[3:])
    alert = extra.get("alert", "").lower() == "yes"
    if alert and not extra.get("gmail"):
        sys.exit('an alert needs gmail="<Gmail query>"')
    next_id = max([r["id"] for r in rows], default=0) + 1
    rows.append({"id": next_id, "site": args[1], "query": args[2], "alert": alert, "gmail": extra.get("gmail", ""),
                 "every_days": int(extra.get("every") or 1), "added": today.isoformat(),
                 "last_checked": "", "last_found": None, **({"note": extra["note"]} if extra.get("note") else {})})
    save(data)
    print(next_id, args[1], args[2])
elif cmd == "list":
    for r in rows:
        print(r["id"], r["site"], "|", r["query"], "| alert" if r["alert"] else f"| every {r['every_days']} days",
              "| last", r["last_checked"] or "never", *(["|", r["note"]] if r.get("note") else []))
elif cmd == "due":
    if not rows:
        print("no saved search: add one per site and query (searches.py add; searches.py sites lists the tracker's sites)")
    for r in filter(is_due, rows):
        how = f"gmail: {r['gmail']}" if r["alert"] else "no alert"
        print(r["id"], r["site"], "|", r["query"], "|", how, "| last", r["last_checked"] or "never")
elif cmd == "done":
    row = next((r for r in rows if str(r["id"]) == args[1]), None) if len(args) > 1 else None
    if not row:
        sys.exit("no such search; see searches.py list")
    row["last_checked"] = today.isoformat()
    found = pairs(args[2:]).get("found")
    row["last_found"] = int(found) if found else None
    save(data)
    print(row["id"], row["site"], "done", row["last_checked"])
elif cmd == "sites":
    with open(env.path("TRACKER"), encoding="utf-8") as f:
        tracker = json.load(f)
    count = {}
    for j in flat_jobs(tracker):
        host = host_of(j.get("url") or "")
        if host and not any(covers(r, host) for r in rows):
            count[host] = count.get(host, 0) + 1
    for host, n in sorted(count.items(), key=lambda kv: (-kv[1], kv[0])):
        print(host, "|", n, "job" if n == 1 else "jobs", "| no saved search")
elif cmd == "seen":
    with open(env.path("TRACKER"), encoding="utf-8") as f:
        tracker = json.load(f)
    known = {key_of(u) for j in flat_jobs(tracker) for u in (j.get("url"), j.get("apply_url")) if u}
    links = args[1:]
    if links[:1] == ["--file"] and len(links) == 2:  # links from an email or a page come in a file, never through a shell
        with open(links[1], encoding="utf-8") as f:
            links = [line.strip() for line in f if line.strip()]
    for url in links:
        print("known" if key_of(url) in known else "new", url)
