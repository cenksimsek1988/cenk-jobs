"""The person's saved searches (SEARCHES in job-search.env, default apply/searches.json): one row per search.

A row with an email alert is read from Gmail at every run; a site without alerts is searched on every weekday
by default (every=<days> for a longer gap), never on a Saturday or Sunday: a check that falls there is due on
Monday. So a run looks only at what is new instead of searching every site again. A search never read is due at once.

python -I searches.py add "<site>" "<query>" alert=yes gmail="<Gmail query>"     a search with an email alert
python -I searches.py add "<site>" "<query>" alert=no                            a site without alerts, every weekday
python -I searches.py add "<site>" "<query>" alert=no every=7                    the same, every 7 days
python -I searches.py add "<site>" "<terms>" source=<kind> board=<name> [place="<terms>"] [mode=remote|any]
                                                                                 a search collect_postings.py reads
                                                                                 without a model (method script);
                                                                                 kinds: greenhouse, lever, ashby,
                                                                                 smartrecruiters, workable, linkedin,
                                                                                 and the remote feeds remotive,
                                                                                 remoteok, jobicy, himalayas,
                                                                                 arbeitnow, workable-search (no
                                                                                 board), remoterocketship and
                                                                                 himalayas-search (board=<country>,
                                                                                 tech=<stack> for the first). Boards
                                                                                 and workable-search: every 7 days by
                                                                                 default. mode: remote
                                                                                 (LinkedIn's remote filter, and the
                                                                                 text must say remote) or any
python -I searches.py import <profile.json>                                      rows from a profile: {"linkedin":
                                                                                 [{location, remote, queries}],
                                                                                 "boards": [{source, board, site} or a
                                                                                 file of them], "feeds": [names]}; a
                                                                                 row already saved is kept
python -I searches.py rates                                                      per row: found, screened by the
                                                                                 funnel, real fits (high or normal)
                                                                                 and the rate; then the rows with 20+
                                                                                 screened and no real fit, to ask the
                                                                                 person about
python -I searches.py list                                                       one line per search
python -I searches.py due [--json]                                               the searches due today; with none
                                                                                 saved, one line that says so; --json:
                                                                                 the due rows as one JSON list
python -I searches.py sites [--add]                                              the sites of the tracker's jobs that
                                                                                 have no saved search, most jobs first;
                                                                                 --add: a script row for each employer
                                                                                 whose job links are on a board the
                                                                                 script reads, named by the employer
python -I searches.py fail <id> <code>                                           a script search's board answered with
                                                                                 an error; two 404s in a row make it
                                                                                 "gone": no longer due, listed with it
python -I searches.py every <id|source> <days>                                   how often a row (or every row of a
                                                                                 source) is read; example: every
                                                                                 greenhouse 7
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
ASK_AFTER = 20  # screened postings with no real fit before the person is asked about the search
if not args or args[0] not in ("add", "list", "due", "done", "seen", "sites", "fail", "import", "rates", "every"):
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


FEEDS = ("remotive", "remoteok", "jobicy", "himalayas", "arbeitnow", "workable-search")  # remote feeds: no board
COUNTRY_FEEDS = ("remoterocketship", "himalayas-search")  # board=<country>
SOURCES = ("greenhouse", "lever", "ashby", "smartrecruiters", "workable", "linkedin") + FEEDS + COUNTRY_FEEDS
# Read weekly by default (19 Nov: 0 new fits from 1,091 board postings; Workable search 0 fits): a new row's every.
WEEKLY = ("greenhouse", "lever", "ashby", "smartrecruiters", "workable", "workable-search")
MODES = ("remote", "any")
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


BOARDS = (("greenhouse", r"(?:job-)?boards(?:\.eu)?\.greenhouse\.io/(?:embed/job_app\?for=)?([\w-]+)"),
          ("lever", r"jobs(?:\.eu)?\.lever\.co/([\w-]+)"), ("ashby", r"jobs\.ashbyhq\.com/([\w.-]+)"),
          ("smartrecruiters", r"jobs\.smartrecruiters\.com/([\w-]+)"), ("workable", r"apply\.workable\.com/([\w-]+)"))


def board_of(url):
    """(source, board) for a job link on a board the script reads, else None."""
    for source, pattern in BOARDS:
        m = re.search(pattern, url or "", re.I)
        if m and m.group(1).lower() not in ("api", "embed", "j", "jobs"):
            return source, m.group(1)
    return None


def is_due(row):
    if row.get("gone"):
        return False  # its board is not found: the coordinator fixes or removes the row
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
    source = extra.get("source", "")
    if source and source not in SOURCES:
        sys.exit(f"source is one of {', '.join(SOURCES)}: got {source!r}")
    if source and source != "linkedin" and source not in FEEDS and not extra.get("board"):
        sys.exit(f'a {source} search needs board=<the board name in its address>')
    if extra.get("mode") and extra["mode"] not in MODES:
        sys.exit(f"mode is one of {', '.join(MODES)}: got {extra['mode']!r}")
    if source and not args[2].strip() and not env.get("ROLE_TERMS"):
        sys.exit("a script search needs terms (a title must hold one), or ROLE_TERMS in job-search.env")
    next_id = max([r["id"] for r in rows], default=0) + 1
    rows.append({"id": next_id, "site": args[1], "query": args[2], "alert": alert, "gmail": extra.get("gmail", ""),
                 "every_days": int(extra.get("every") or (7 if source in WEEKLY else 1)), "added": today.isoformat(),
                 "last_checked": "", "last_found": None, "method": "script" if source else "agent",
                 **{k: extra[k] for k in ("note", "source", "board", "place", "employer", "mode", "tech")
                    if extra.get(k)}})
    save(data)
    print(next_id, args[1], args[2])
elif cmd == "import":
    # A profile in the search experiment's shape: {"linkedin": [{location, remote, queries}], "boards": [{source,
    # board, site|employer} or the path of a JSON list of them], "feeds": [names]}. A row already saved is kept.
    if len(args) != 2:
        sys.exit("import <profile.json>")
    with open(args[1], encoding="utf-8") as f:
        profile = json.load(f)
    have = {(r.get("source"), (r.get("board") or "").lower(), (r.get("query") or "").lower(),
             (r.get("place") or "").lower()) for r in rows}
    added = []

    def row_of(site, query, **more):
        key = (more.get("source"), (more.get("board") or "").lower(), query.lower(), (more.get("place") or "").lower())
        if key in have:
            return
        have.add(key)
        rows.append({"id": max([r["id"] for r in rows], default=0) + 1, "site": site, "query": query, "alert": False,
                     "gmail": "", "every_days": 7 if more.get("source") in WEEKLY else 1, "added": today.isoformat(),
                     "last_checked": "", "last_found": None, "method": "script", **{k: v for k, v in more.items() if v}})
        added.append(f"{rows[-1]['id']} {site} | {query or '(ROLE_TERMS)'}")

    for block in profile.get("linkedin", []):
        for q in block.get("queries", []):
            row_of(f"LinkedIn {block.get('location', '')}".strip(), q, source="linkedin",
                   place=block.get("location", ""), mode="remote" if block.get("remote") else "any")
    boards = []
    for b in profile.get("boards", []):
        if isinstance(b, str):
            path = b if os.path.isabs(b) else os.path.join(os.path.dirname(os.path.abspath(args[1])), b)
            if not os.path.isfile(path):
                print(f"boards file not found, skipped: {b}")
                continue
            with open(path, encoding="utf-8") as f:
                got = json.load(f)
            boards += got.get("searches", []) if isinstance(got, dict) else got
        else:
            boards.append(b)
    for b in boards:
        if b.get("source") in SOURCES and b.get("source") not in FEEDS and b.get("source") != "linkedin" and b.get("board"):
            name = b.get("employer") or b.get("site") or b["board"]
            row_of(name, b.get("query") or "", source=b["source"], board=b["board"], employer=name)
    for feed in profile.get("feeds", []):
        if feed in FEEDS:
            row_of(feed, "", source=feed, mode="remote")
    save(data)
    print("\n".join(added + [f"{len(added)} searches added"]))
elif cmd == "rates":
    # Real fits only (the funnel's high or normal grade), never a cheaper judge's: a row's rate is real fits per
    # posting the funnel screened. ASK_AFTER screened with no fit is a question for the person, never dropped alone.
    with open(env.path("TRACKER"), encoding="utf-8") as f:
        jobs = flat_jobs(json.load(f))
    per = {}
    for j in jobs:
        sid = str(j.get("search") or "")
        if not sid:
            continue
        p = j.get("prep") or {}
        c = per.setdefault(sid, {"found": 0, "screened": 0, "fits": 0})
        c["found"] += 1
        if p:
            c["screened"] += 1
            if p.get("grade") in ("high", "normal") or str(p.get("reason") or "").startswith("not a high fit"):
                c["fits"] += 1
    ask = []
    for r in rows:
        c = per.get(str(r["id"]), {"found": 0, "screened": 0, "fits": 0})
        rate = f"{100 * c['fits'] // c['screened']}%" if c["screened"] else "-"
        print(r["id"], r["site"], "|", r.get("query") or "(ROLE_TERMS)", "| found", c["found"], "| screened",
              c["screened"], "| real fits", c["fits"], "|", rate)
        if c["screened"] >= ASK_AFTER and not c["fits"]:
            ask.append(f"{r['id']} {r['site']} | {r.get('query') or '(ROLE_TERMS)'}: {c['screened']} screened, 0 real fits")
    print("ask the person whether to drop (questions.py add general):", "; ".join(ask) or "none")
elif cmd == "list":
    for r in rows:
        print(r["id"], r["site"], "|", r["query"], "| alert" if r["alert"] else f"| every {r['every_days']} days",
              "|", r.get("method", "agent"), "| last", r["last_checked"] or "never",
              *(["| gone since", r["gone"]] if r.get("gone") else []), *(["|", r["note"]] if r.get("note") else []))
elif cmd == "due" and "--json" in args:
    # --since <date[Thh:mm]>: a script search read since then counts as due too, so a window given by hand reaches it.
    if "--since" in args and args.index("--since") + 1 >= len(args):
        sys.exit("due --json --since <YYYY-MM-DD[THH:MM]>")
    since = args[args.index("--since") + 1] if "--since" in args else ""
    again = lambda r: (since and r.get("method") == "script" and not r.get("gone")  # noqa: E731
                       and (r.get("last_checked") or "") >= since)
    print(json.dumps([r for r in rows if is_due(r) or again(r)], ensure_ascii=False))
elif cmd == "due":
    if not rows:
        print("no saved search: add one per site and query (searches.py add; searches.py sites lists the tracker's sites)")
    for r in filter(is_due, rows):
        how = f"gmail: {r['gmail']}" if r["alert"] else f"script: {r['source']}" if r.get("method") == "script" else "no alert"
        print(r["id"], r["site"], "|", r["query"], "|", how, "| last", r["last_checked"] or "never")
elif cmd == "every":
    # every <id|source> <days>: how often a row is read; by source, every row of it (example: every greenhouse 7).
    if len(args) != 3 or not args[2].isdigit() or int(args[2]) < 1:
        sys.exit("every takes <search id or source> <days>")
    hit = [r for r in rows if str(r["id"]) == args[1] or r.get("source") == args[1]]
    if not hit:
        sys.exit(f"no search with id or source {args[1]!r}; see searches.py list")
    for r in hit:
        r["every_days"] = int(args[2])
    save(data)
    print(f"{len(hit)} searches read every {args[2]} days")
elif cmd == "done":
    row = next((r for r in rows if str(r["id"]) == args[1]), None) if len(args) > 1 else None
    if not row:
        sys.exit("no such search; see searches.py list")
    # Date and time: the next run's window starts here (collect_postings.py), not at the start of the day.
    row["last_checked"] = (f"{as_of}T12:00" if as_of else datetime.datetime.now().strftime("%Y-%m-%dT%H:%M"))
    row.pop("fails", None)
    found = pairs(args[2:]).get("found")
    row["last_found"] = int(found) if found else None
    save(data)
    print(row["id"], row["site"], "done", row["last_checked"])
elif cmd == "fail":
    row = next((r for r in rows if str(r["id"]) == args[1]), None) if len(args) > 2 else None
    if not row:
        sys.exit("searches.py fail <id> <code>; see searches.py list")
    row["fails"] = row.get("fails", 0) + 1 if args[2] == "404" else 0
    if row["fails"] >= 2:
        row["gone"] = today.isoformat()
    save(data)
    print(row["id"], row["site"], f"gone since {row['gone']}: the board is not found" if row.get("gone")
          else f"answered {args[2]}; it stays due")
elif cmd == "sites" and "--add" in args:
    if not env.get("ROLE_TERMS"):
        sys.exit("a script search needs terms (a title must hold one): set ROLE_TERMS in job-search.env first")
    with open(env.path("TRACKER"), encoding="utf-8") as f:
        tracker = json.load(f)
    have = {(r.get("source"), r.get("board", "").lower()) for r in rows}
    added, excluded = [], {}
    import employerlib as el
    rule_set = el.rules(env)
    for j in flat_jobs(tracker):
        hit = board_of(j.get("apply_url") or j.get("url") or "") or board_of(j.get("url") or "")
        if not hit or (hit[0], hit[1].lower()) in have:
            continue
        name = j.get("company", "")
        if name and name not in excluded:
            excluded[name] = el.check_view(env, name, rule_set)["verdict"] == "exclude"
        if j.get("status") == "excluded" or excluded.get(name):
            continue  # an employer the person's rules exclude gets no search
        have.add((hit[0], hit[1].lower()))
        next_id = max([r["id"] for r in rows], default=0) + 1
        rows.append({"id": next_id, "site": j.get("company", "") or hit[1], "employer": j.get("company", ""),
                     "query": env.get("ROLE_TERMS", ""),
                     "alert": False, "gmail": "", "every_days": 7 if hit[0] in WEEKLY else 1,
                     "added": today.isoformat(), "last_checked": "",
                     "last_found": None, "method": "script", "source": hit[0], "board": hit[1],
                     **({"place": env["PLACES"]} if env.get("PLACES") else {})})
        added.append(f"{next_id} {rows[-1]['site']} | {hit[0]} {hit[1]}")
    save(data)
    print("\n".join(added + [f"{len(added)} script searches added"]))
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
