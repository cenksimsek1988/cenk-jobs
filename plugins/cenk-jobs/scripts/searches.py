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
                                                                                 remoteok, jobicy (tag=<tags>: by
                                                                                 tag), himalayas, arbeitnow,
                                                                                 workable-search (no board),
                                                                                 weworkremotely (board=<category>, or
                                                                                 none: the whole feed),
                                                                                 remoterocketship and
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
                                                                                 the due rows as one JSON list. A
                                                                                 script row outside the scope (below)
                                                                                 is left out: "outside the scope: ..."
python -I searches.py scope-ok <id>                                              keep a row outside the scope: the
                                                                                 person said so
python -I searches.py query <id> "<terms>"                                       a row's terms, replaced; example: a
                                                                                 Remote Rocketship title with no page
                                                                                 left out
python -I searches.py sites [--add]                                              the sites of the tracker's jobs that
                                                                                 have no saved search, most jobs first;
                                                                                 --add: a script row for each employer
                                                                                 whose job links are on a board the
                                                                                 script reads, named by the employer
python -I searches.py fail <id> <code>                                           a script search's board answered with
                                                                                 an error; two 404s in a row make it
                                                                                 "gone": no longer due, listed with it
python -I searches.py every <id|source> <days|off>                               how often a row (or every row of a
                                                                                 source) is read; example: every
                                                                                 greenhouse 7; off: never due again
                                                                                 (a number turns it back on)
python -I searches.py discover --file <links file>                               board discovery: one link per line
                                                                                 (web search results); prints each
                                                                                 board a script reads that has no
                                                                                 row yet: "new <kind> <board> <link>"
python -I searches.py suggest [--days <n>] [--from <dir>]                        Remote Rocketship, checked one page
                                                                                 each: the rows' titles with no title
                                                                                 page (the generic list comes back),
                                                                                 the titles of the last n days' fits
                                                                                 (default 30) and the countries of the
                                                                                 scope's remote regions the rows lack;
                                                                                 prints the query and add commands,
                                                                                 changes nothing (the person's yes
                                                                                 first); --from: saved pages
                                                                                 (rocketship-<country>-<title>.html)
python -I searches.py rules [--write]                                            the title rules in use (SEARCH_RULES,
                                                                                 default apply/search-rules.json),
                                                                                 checked: their keys, or why they
                                                                                 cannot be read; --write: the default
                                                                                 (templates/search-rules-example.json)
                                                                                 when there is no file yet
python -I searches.py done <id> found=<n>                                        record that a search was read
python -I searches.py seen <url> [<url> ...]                                     says "new" or "known" per link
python -I searches.py seen --file <links file>                                   the same, one link per line in a file
Outside the scope: a script row of office or hybrid postings (mode not remote) whose every place is in NOT_PLACES, or,
once the person has set the scope's any_mode_places (career_view.py scope), names none of them and is named by none,
as whole words. Example: a LinkedIn row "Berlin" with any_mode_places Springfield. Seen 20 Nov: city rows the person
had dropped gave 89 of 103 postings out of scope. Words only: a city inside an accepted country is named outside
when neither names the other ("Milan" with any_mode_places Italy); the person keeps it with scope-ok.
Add --env <job-search.env> anywhere to pick the env file; --today <YYYY-MM-DD> reads "due" as of that day. The file is
SEARCHES, else searches.json beside TRACKER; every write goes through recordlib.py (STALE, exit 3: run it again).
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
import recordlib  # noqa: E402
from trackerlib import flat_jobs, scope_of, terms, title_has  # noqa: E402

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
if not args or args[0] not in ("add", "list", "due", "done", "seen", "sites", "fail", "import", "rates", "every",
                               "discover", "scope-ok", "query", "suggest", "rules"):
    sys.exit(__doc__)
env = jsenv.load(env_arg, __file__)
if args[0] == "rules":
    # The person's title rules (0.48.0), checked as collect_postings.py reads them; --write puts the default in place
    # once (seen 23 Nov: no rules file existed, so no title rule ran and every row's terms filtered its titles).
    import shutil
    import collect_postings as cp
    rules_path = env.path("SEARCH_RULES") if env.get("SEARCH_RULES") else os.path.join(env.home, "apply",
                                                                                       "search-rules.json")
    if "--write" in args[1:]:
        template = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates",
                                                 "search-rules-example.json"))
        if os.path.isfile(rules_path):
            print(f"{rules_path} exists: left as it is")
        elif not os.path.isfile(template):
            sys.exit(f"the default title rules are missing from the plugin ({template}): reinstall it")
        else:
            os.makedirs(os.path.dirname(rules_path), exist_ok=True)
            shutil.copyfile(template, rules_path)
            print(f"wrote {rules_path}: the default title rules (templates/search-rules-example.json)")
    if not os.path.isfile(rules_path):
        sys.exit(f"no title rules at {rules_path}: every row's terms filter its titles (searches.py rules --write)")
    have = cp.title_rules(env)  # exits naming the problem when a value is no regular expression
    keep = (env.get("ROW_TERMS") or "").strip().lower() == "filter"
    print(f"{rules_path}: {', '.join(k for k in cp.RULE_KEYS if k in have) or 'no rule'}; "
          + ("ROW_TERMS=filter: every row's terms filter its titles" if keep
             else "need is set: a searching row's terms only search" if "need" in have
             else "no need: every row's terms filter its titles"))
    sys.exit(0)
PATH = env.path("SEARCHES") if env.get("SEARCHES") else env.path("TRACKER") + "/../searches.json"
PATH = os.path.normpath(PATH)
today = datetime.date.fromisoformat(as_of) if as_of else datetime.date.today()


BASE = ""


def load():
    global BASE
    data, BASE = recordlib.load(env, "searches", {
        "_about": "Saved searches: read from alert emails, or checked on a schedule (searches.py).", "searches": []})
    return data


def save(data):
    global BASE
    BASE = recordlib.save(env, "searches", data, BASE, "searches.py", indent=1)


def pairs(items):
    return dict(item.split("=", 1) for item in items if "=" in item)


# Remote feeds: no board needed (weworkremotely: board=<category> picks one, none reads the whole feed).
FEEDS = ("remotive", "remoteok", "jobicy", "himalayas", "arbeitnow", "workable-search", "weworkremotely")
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
    if row.get("gone") or row.get("off"):
        return False  # its board is not found (the coordinator fixes or removes the row), or it was turned off
    last = row.get("last_checked")
    if not last:
        return True
    if row.get("alert"):
        return (today - datetime.date.fromisoformat(last[:10])).days >= 1
    if today.weekday() >= 5:  # a site search waits for Monday; an alert's emails are read at any run
        return False
    return (today - datetime.date.fromisoformat(last[:10])).days >= int(row.get("every_days") or 1)


def outside_scope(row, not_places, scope_places):
    """A script row of office or hybrid postings whose every place is outside the scope (the docstring says when). A
    row the person kept (scope_ok) never is."""
    if row.get("method") != "script" or row.get("mode") == "remote" or row.get("scope_ok"):
        return False
    own = terms(row.get("place"))

    def out(place):
        if title_has(place, not_places):
            return True
        return scope_places is not None and not (title_has(place, scope_places)
                                                 or any(title_has(s, [place]) for s in scope_places))
    return bool(own) and all(out(p) for p in own)


def scope_check():
    """outside_scope with the person's NOT_PLACES and the scope's any_mode_places (None when not set)."""
    not_places, scope_places = terms(env.get("NOT_PLACES")), scope_of(env)[1]
    return lambda row: outside_scope(row, not_places, scope_places)


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
    if extra.get("tag") and source != "jobicy":
        sys.exit("tag=<tags> is Jobicy's: its pages by tag")
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
                 **{k: extra[k] for k in ("note", "source", "board", "place", "employer", "mode", "tech", "tag")
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
              *(["| gone since", r["gone"]] if r.get("gone") else []), *(["| off since", r["off"]] if r.get("off") else []),
              *(["|", r["note"]] if r.get("note") else []))
elif cmd == "due" and "--json" in args:
    # --since <date[Thh:mm]>: a script search read since then counts as due too, so a window given by hand reaches it.
    if "--since" in args and args.index("--since") + 1 >= len(args):
        sys.exit("due --json --since <YYYY-MM-DD[THH:MM]>")
    since = args[args.index("--since") + 1] if "--since" in args else ""
    again = lambda r: (since and r.get("method") == "script" and not r.get("gone") and not r.get("off")  # noqa: E731
                       and (r.get("last_checked") or "") >= since)
    outside = scope_check()
    print(json.dumps([r for r in rows if (is_due(r) or again(r)) and not outside(r)], ensure_ascii=False))
elif cmd == "due":
    if not rows:
        print("no saved search: add one per site and query (searches.py add; searches.py sites lists the tracker's sites)")
    outside = scope_check()
    for r in filter(is_due, rows):
        if outside(r):
            print(f"outside the scope: {r['id']} {r['site']} ({r.get('place', '')}): ask the person to turn it off "
                  f"(searches.py every {r['id']} off) or keep it (searches.py scope-ok {r['id']})")
            continue
        how = f"gmail: {r['gmail']}" if r["alert"] else f"script: {r['source']}" if r.get("method") == "script" else "no alert"
        print(r["id"], r["site"], "|", r["query"], "|", how, "| last", r["last_checked"] or "never")
elif cmd == "every":
    # every <id|source> <days|off>: how often a row is read; by source, every row of it (example: every greenhouse 7).
    # off: never due again, kept for its history; a number turns it back on.
    if len(args) != 3 or not (args[2] == "off" or args[2].isdigit() and int(args[2]) >= 1):
        sys.exit("every takes <search id or source> <days|off>")
    hit = [r for r in rows if str(r["id"]) == args[1] or r.get("source") == args[1]]
    if not hit:
        sys.exit(f"no search with id or source {args[1]!r}; see searches.py list")
    for r in hit:
        if args[2] == "off":
            r["off"] = today.isoformat()
        else:
            r["every_days"] = int(args[2])
            r.pop("off", None)
    save(data)
    print(f"{len(hit)} searches off" if args[2] == "off" else f"{len(hit)} searches read every {args[2]} days")
elif cmd == "scope-ok":
    # scope-ok <id>: the person keeps a row outside the scope; it is due again and never named outside it.
    hit = [r for r in rows if len(args) == 2 and str(r["id"]) == args[1]]
    if not hit:
        sys.exit("scope-ok takes a search id; see searches.py list")
    hit[0]["scope_ok"] = today.isoformat()
    save(data)
    print(f"{hit[0]['id']} {hit[0]['site']}: kept outside the scope")
elif cmd == "query":
    # query <id> "<terms>": the row's terms, replaced (comma-separated; a script row needs at least one, or ROLE_TERMS).
    hit = [r for r in rows if len(args) == 3 and str(r["id"]) == args[1]]
    if not hit:
        sys.exit('query takes a search id and its new terms: query <id> "<terms>"; see searches.py list')
    hit[0]["query"] = ", ".join(t.strip() for t in args[2].split(",") if t.strip())
    save(data)
    print(f"{hit[0]['id']} {hit[0]['site']}: {hit[0]['query'] or '(ROLE_TERMS)'}")
elif cmd == "suggest":
    # Remote Rocketship gave 12 of 14 fits on 19 Nov, from 2 country rows: it finds more with more countries and
    # titles. A title it does not know gives the country's generic list (collect_postings.rocketship_title_page), so
    # each row's titles are checked on its own country's page, each fit title and new country on one page,
    # SOURCE_GAP apart, at most SUGGEST_PAGES pages (about 3 minutes).
    import time
    import collect_postings as cp
    opts = dict(zip(args[1::2], args[2::2]))
    if len(args) % 2 == 0 or set(opts) - {"--days", "--from"} or not str(opts.get("--days", "30")).isdigit():
        sys.exit("suggest [--days <n>] [--from <dir>]")
    days, from_dir, SUGGEST_PAGES = int(opts.get("--days", "30")), opts.get("--from"), 60
    REGION_BOARDS = {"eu": "european-union", "european union": "european-union", "emea": "europe",
                     "anywhere": "worldwide", "global": "worldwide", "uk": "united-kingdom", "us": "united-states",
                     "usa": "united-states"}  # each page checked 21 Nov; emea and anywhere have none

    def slug(text):  # a title's page, as collect_postings.feed_urls makes it
        return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")

    def safe(text):
        """A title as a printed command holds it: letters, digits, spaces and & + . # - only, so a posting's quote,
        $ or backtick never reaches a shell. Example: 'Lead "Core" Engineer' -> "lead core engineer"."""
        return " ".join(re.sub(r"[^a-z0-9 &+.#-]", " ", str(text).lower()).split())

    def title_words(title):
        """A posting title as a search term: the part before a dash, bar, comma or bracket, without seniority and
        work-mode words. Example: "Senior Engineering Manager, Payments (Remote)" -> "engineering manager"."""
        core = re.split(r"\s[-–|/]\s|,|\(|\[", str(title))[0]
        return safe(re.sub(r"(?i)\b(senior|sr|junior|jr|remote|hybrid|i{1,3}|iv)\b\.?", " ", core))

    pages = {}

    def page(board, title):
        """(state, weekly new) of one page, checked once: "title", "generic" (the list of every remote job), "none"
        (404 or no saved page), "error ..." or "unchecked" (over SUGGEST_PAGES)."""
        key = (board, slug(title))
        if key not in pages:
            text, state = None, "none"
            if from_dir:
                path = os.path.join(from_dir, f"rocketship-{key[0]}-{key[1]}.html")
                if os.path.isfile(path):
                    with open(path, encoding="utf-8") as fh:
                        text = fh.read()
            elif sum(1 for s, _ in pages.values() if s != "unchecked") >= SUGGEST_PAGES:
                state = "unchecked"
            else:
                if pages:
                    time.sleep(cp.SOURCE_GAP)
                try:
                    text = cp.fetch(cp.FEED_API["remoterocketship"].format(board=key[0], slug=key[1]))
                except cp.Refused as problem:
                    state = "none" if problem.code == 404 else f"error {problem.code}"
                except OSError as problem:
                    state = f"error {type(problem).__name__}"
            weekly = None
            if text is not None:
                try:
                    data = cp.next_data(text)
                    state, weekly = ("generic" if data["generic"] else "title"), data.get("weekly")
                except ValueError:
                    state = "error: no page data"
            pages[key] = (state, weekly)
        return pages[key]

    rr = [r for r in rows if r.get("source") == "remoterocketship" and not r.get("off") and not r.get("gone")]
    boards = list(dict.fromkeys(str(r.get("board") or "").lower() for r in rr if r.get("board")))
    regions = scope_of(env)[0]
    regions = regions if regions is not None else terms(env.get("REMOTE_REGIONS"))
    countries = list(dict.fromkeys(boards + [REGION_BOARDS.get(x.lower(), slug(x)) for x in regions if slug(x)]))
    since = (today - datetime.timedelta(days=days)).isoformat()
    with open(env.path("TRACKER"), encoding="utf-8") as f:
        jobs = flat_jobs(json.load(f))
    first = lambda j: min((str(h.get("date", ""))[:10] for h in j.get("history") or []),  # noqa: E731
                          default=str(j.get("date") or ""))
    fits = [j for j in jobs if (j.get("prep") or {}).get("grade") in ("high", "normal") and first(j) >= since]
    known, words = {}, {}  # a title's page -> the rows that search it, and the title as a row spells it
    for r in rr:
        for t in terms(r.get("query")):
            known.setdefault(slug(t), []).append(r)
            words.setdefault(slug(t), t)
    counts = {}
    for j in fits:
        t = title_words(j.get("title", ""))
        if t and slug(t) not in known:
            counts[t] = counts.get(t, 0) + 1
    wanted = sorted(counts, key=lambda t: -counts[t])
    probe = (boards or countries or ["europe"])[0]
    board_of = lambda r: str(r.get("board") or probe).lower()  # noqa: E731
    # Each row's titles on its own country's page: a title one country does not know may have a page in another.
    drops = {r["id"]: [t for t in terms(r.get("query")) if page(board_of(r), t)[0] in ("generic", "none")] for r in rr}
    kept = [s for s in known if any(page(board_of(r), s)[0] == "title" for r in known[s])]
    add_titles = [t for t in wanted[:10] if page(probe, t)[0] == "title"]
    base = (kept + [slug(t) for t in add_titles])[:1]
    add_countries = [(c, page(c, base[0])[1]) for c in countries if c not in boards and base
                     and page(c, base[0])[0] == "title"]
    tech = {r.get("tech") or "" for r in rr}
    tech = tech.pop() if len(tech) == 1 else ""
    shown = lambda n: "?" if n is None else n  # noqa: E731  (a page without its weekly count)
    print(f"Remote Rocketship: {len(rr)} rows, {len(known)} titles; {len(fits)} fits in the last {days} days, "
          f"{len(wanted)} of their titles not searched; {len(pages)} pages checked")
    for r in rr:
        for t in drops[r["id"]]:
            print(f'drop: "{safe(t)}" in search {r["id"]}: no title page on {board_of(r)} '
                  f"({page(board_of(r), t)[0]}: the generic list of every remote job, or none)")
    for t in add_titles:
        print(f'add title: "{t}" ({counts[t]} fit{"" if counts[t] == 1 else "s"}; {shown(page(probe, t)[1])} new a '
              f"week on {probe})")
    for c, weekly in add_countries:
        print(f'add country: {c} ({shown(weekly)} new a week for "{safe(words.get(base[0], base[0]))}")')
    titles = [safe(words[t]) for t in kept] + add_titles
    commands = []
    for r in rr:
        mine = [safe(t) for t in terms(r.get("query")) if t not in drops[r["id"]]]
        new = [t for t in add_titles if slug(t) not in {slug(x) for x in mine}]
        if not mine + new:
            print(f"off: search {r['id']}: none of its titles has a page")
            commands.append(f"searches.py every {r['id']} off")
        elif new or drops[r["id"]]:
            commands.append(f'searches.py query {r["id"]} "{", ".join(mine + new)}"')
    for c, _ in add_countries:
        commands.append(f'searches.py add "Remote Rocketship {c.replace("-", " ").title()}" "{", ".join(titles)}" '
                        f"source=remoterocketship board={c} mode=remote" + (f" tech={tech}" if tech else ""))
    for line in commands:
        print(line)
    unchecked = sum(1 for s, _ in pages.values() if s == "unchecked" or s.startswith("error"))
    print(f"{len(commands)} commands; nothing was changed: each waits for the person's yes"
          + (f"; {unchecked} pages not checked (run it again later)" if unchecked else ""))
elif cmd == "discover":
    # Board discovery: links from web searches, one per line in a file (never typed into a command). A board the
    # script reads that has no row (gone or off rows included) is printed once; any other link is left out.
    if len(args) != 3 or args[1] != "--file":
        sys.exit("discover --file <links file>")
    try:
        with open(args[2], encoding="utf-8") as f:
            links = [line.strip() for line in f if line.strip()]
    except OSError as e:
        sys.exit(f"discover: cannot read {args[2]}: {e}")
    have = {(r.get("source"), (r.get("board") or "").lower()) for r in rows}
    new = saved = other = 0
    for url in links:
        hit = board_of(url)
        if not hit:
            other += 1
        elif (hit[0], hit[1].lower()) in have:
            saved += 1
        else:
            have.add((hit[0], hit[1].lower()))
            new += 1
            print("new", hit[0], hit[1], url)
    print(f"new boards: {new}; links to saved boards: {saved}; links not on a board: {other}")
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
