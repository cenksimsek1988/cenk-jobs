"""Collect new postings without a model: every saved search with method "script" (searches.py), read from the job
board's public API or LinkedIn's guest search, filtered by its terms and places, minus what the tracker already has.

python -I collect_postings.py [--since <YYYY-MM-DD[THH:MM]>] [--out <search file>] [--add] [--from <dir>]
    prints one line per new posting: company | title | place | date | link | found_by, then one line per search read.
    --since: where the window starts for a search never read; default the start of the last finished run in the
    usage log, else 7 days back. A search read before starts at its own last read. Postings dated before the start are left out.
    --out: also writes the postings for workflows/screen-and-prepare.js ({companies: [{name, jobs: [{id, title, url,
    apply_url, location, date, found_by}]}]}): at most MAX_NEW_PER_RUN (default 30) jobs, newest first, then the
    tracker's found jobs from earlier runs that were never prepared; the rest wait for the next run.
    --add: also adds every new posting to the tracker (track.py add <id> ... found_by=<source> date=<date>).
    --from <dir>: reads each source's answer from <dir>/<source>-<board>.json (.html for linkedin, -p2 and -p3 for
    its next pages; <source>-<board>.status holding an HTTP code answers with that error) instead of the web; tests.
Only searches due today are read (searches.py due), and each is marked read (searches.py done <id> found=<n>); with
--since, also a script search read since then, again over the window given (seen: a search read at 01:00 was not
read again with --since 00:00).
A search row: site, employer (for a board: the employer's name, which names every posting; without it, the site
without a trailing "jobs" or "careers"), query (terms, comma-separated: a
title must hold one; empty: ROLE_TERMS from job-search.env; neither: the search is skipped and stays due), source,
board (the name in the board's address; for linkedin: none), place (terms, comma-separated: the place must hold one;
empty: PLACES from job-search.env, else any place). A place in NOT_PLACES never passes, also inside an accepted
country ("Turin, Italy" with NOT_PLACES=Turin); carried postings pass the same places check. Each posting of the
search file gets its city's pay from PAY_TABLE (career_view.py pay) when the table has it.
A remote posting passes only when its place also holds one of the search's places or one of
REMOTE_REGIONS (job-search.env), or reads just "Remote". Example: "Remote, EU" passes with REMOTE_REGIONS=EU;
"Remote, US" does not. Example: searches.py add "Acme jobs" "engineer, architect" source=greenhouse
board=acme place="Rome, Italy".
LinkedIn: up to 3 pages per search, 4 seconds apart, over the window since its start; an error or a refusal (429)
stops LinkedIn for this run and its remaining searches stay due. A board that answers 404 twice is marked gone
(searches.py fail). found_by is script:<source>:<board>; the run report counts script and agent finds apart.
Add --env <job-search.env> anywhere to pick the env file.
"""
import datetime
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jsenv  # noqa: E402
import reposts  # noqa: E402
from trackerlib import flat_jobs, pay_for, pay_table  # noqa: E402
from variants import runs, usage_rows  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (job-search assistant)"}
API = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
    "lever": "https://api.lever.co/v0/postings/{board}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{board}",
    "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/{board}/postings",
    "workable": "https://apply.workable.com/api/v1/widget/accounts/{board}",
}
LINKEDIN = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?{query}"
LINKEDIN_JOB = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}"
# Remote job feeds: public JSON, each posting with its own location field. {term}, {geo}, {n}: filled per page.
FEED_API = {
    "remotive": "https://remotive.com/api/remote-jobs?limit=200&search={term}",
    "remoteok": "https://remoteok.com/api",
    "jobicy": "https://jobicy.com/api/v2/remote-jobs?count=100&geo={geo}&industry=dev",
    "himalayas": "https://himalayas.app/jobs/api?limit=20&offset={n}",
    "arbeitnow": "https://www.arbeitnow.com/api/job-board-api?page={n}",
}
FEEDS = tuple(FEED_API)
# LinkedIn: 4.5 s between calls, a job text 6 s after the last call; one refusal (429) pauses 60 s and slows to 8 s;
# a second one stops LinkedIn for the run. Seen on 17 Nov: 4.5 s ran into 429 after ~46 texts, 8 s ran through.
LINKEDIN_GAP, TEXT_GAP, SLOW_GAP, PAUSE = 4.5, 6.0, 8.0, 60
TEXT_FETCHES = 40  # LinkedIn job texts read per run for the remote check (TEXT_FETCHES in job-search.env)
# A remote LinkedIn search returns city hybrid jobs too (18 Nov: 73 of 82): its posting goes to the funnel only when
# its own text speaks of remote work.
REMOTE_WORDS = re.compile(r"(?i)\b(remote|remotely|fully[- ]remote|da remoto|in remoto|full remote|telelavoro|"
                          r"uzaktan|work from home|work from anywhere|distributed team)\b")


class LinkedInQueue:
    """One queue for every LinkedIn call of the run: the gap, and whether it was refused once."""

    def __init__(self, live):
        self.live, self.last, self.gap, self.refused = live, 0.0, LINKEDIN_GAP, False

    def wait(self, gap=None):
        rest = max(self.gap, gap or 0) - (time.monotonic() - self.last)
        if rest > 0 and self.live:
            time.sleep(rest)
        self.last = time.monotonic()

    def call(self, read, gap=None):
        """read() under the queue; the first 429 pauses PAUSE seconds, slows to SLOW_GAP and tries once more."""
        self.wait(gap)
        try:
            return read()
        except Refused as problem:
            if problem.code != 429 or self.refused:
                raise
            self.refused, self.gap = True, SLOW_GAP
            if self.live:
                time.sleep(PAUSE)
            self.wait(gap)
            return read()


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def day(value):
    """A date as YYYY-MM-DD from an ISO text or epoch milliseconds; "" when unknown."""
    if isinstance(value, (int, float)):
        seconds = value if value < 1e11 else value / 1000  # feeds give seconds, boards milliseconds
        return datetime.datetime.fromtimestamp(seconds, datetime.timezone.utc).date().isoformat()
    m = re.match(r"\d{4}-\d{2}-\d{2}", str(value or ""))
    return m.group(0) if m else ""


class Refused(Exception):
    """An HTTP error from a source: its code (404 for a board that is gone, 429 for LinkedIn refusing)."""

    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.code = code


def parse(source, board, text):
    """[(title, company, place, date, url)] from one source's answer."""
    if source == "linkedin":
        out = []
        for card in re.split(r'<div class="base-card', text)[1:]:
            pick = lambda pattern: html.unescape(re.sub(r"<[^>]+>", "", (re.search(pattern, card, re.S) or [None, ""])[1])).strip()  # noqa: E731
            url = (re.search(r'class="base-card__full-link[^"]*"\s+href="([^"]+)"', card) or [None, ""])[1]
            out.append((pick(r'class="base-search-card__title">(.*?)</h3>'),
                        pick(r'class="base-search-card__subtitle">(.*?)</h4>'),
                        pick(r'class="job-search-card__location">(.*?)</span>'),
                        (re.search(r'datetime="([\d-]+)"', card) or [None, ""])[1], html.unescape(url).split("?")[0]))
        return out
    data = json.loads(text)
    if source in FEEDS:
        return feed_postings(source, data)
    name = board
    if source == "greenhouse":
        return [(j.get("title", ""), name, (j.get("location") or {}).get("name", ""),
                 day(j.get("first_published") or j.get("updated_at")), j.get("absolute_url", "")) for j in data.get("jobs", [])]
    if source == "lever":
        return [(j.get("text", ""), name, (j.get("categories") or {}).get("location", ""), day(j.get("createdAt")),
                 j.get("hostedUrl", "")) for j in data]
    if source == "ashby":
        return [(j.get("title", ""), name, j.get("location", ""), day(j.get("publishedAt")), j.get("jobUrl", ""))
                for j in data.get("jobs", []) if j.get("isListed", True)]
    if source == "smartrecruiters":
        return [(j.get("name", ""), (j.get("company") or {}).get("name", name),
                 ", ".join(x for x in ((j.get("location") or {}).get("city"), (j.get("location") or {}).get("country")) if x),
                 day(j.get("releasedDate")), f"https://jobs.smartrecruiters.com/{board}/{j.get('id', '')}")
                for j in data.get("content", [])]
    if source == "workable":
        return [(j.get("title", ""), data.get("name") or name,
                 ", ".join(x for x in (j.get("city"), j.get("country")) if x), day(j.get("published_on")),
                 j.get("url") or j.get("shortlink", "")) for j in data.get("jobs", [])]
    return []


def feed_postings(source, data):
    """[(title, company, place, date, url)] from a remote feed's answer; the place reads "Remote, <its region>". A
    posting that names no region never reads as a bare "Remote" (which passes anywhere): often it is US-only."""
    remote = lambda where: "Remote, " + (where.strip() or "no region given")  # noqa: E731
    if source == "remotive":
        return [(j.get("title", ""), j.get("company_name", ""), remote(j.get("candidate_required_location", "")),
                 day(j.get("publication_date")), j.get("url", "")) for j in data.get("jobs", [])]
    if source == "remoteok":
        return [(j.get("position", ""), j.get("company", ""), remote(j.get("location", "")), day(j.get("date")),
                 j.get("url", "")) for j in (data if isinstance(data, list) else []) if j.get("position")]
    if source == "jobicy":
        return [(j.get("jobTitle", ""), j.get("companyName", ""), remote(j.get("jobGeo", "")), day(j.get("pubDate")),
                 j.get("url", "")) for j in data.get("jobs", [])]
    if source == "himalayas":
        return [(j.get("title", ""), j.get("companyName", ""),
                 remote(", ".join(j.get("locationRestrictions") or []) or "Worldwide"), day(j.get("pubDate")),
                 j.get("applicationLink") or j.get("guid") or "") for j in data.get("jobs", [])]
    if source == "arbeitnow":
        return [(j.get("title", ""), j.get("company_name", ""), remote(j.get("location", "")), day(j.get("created_at")),
                 j.get("url", "")) for j in data.get("data", []) if j.get("remote")]
    return []


def feed_urls(row, words):
    """The pages a feed is read from: one per term (remotive), per region (jobicy), or the first pages."""
    source = row["source"]
    if source == "remotive":
        return [FEED_API[source].format(term=urllib.parse.quote(w)) for w in words[:8]]
    if source == "jobicy":
        return [FEED_API[source].format(geo=urllib.parse.quote(g)) for g in (terms(row.get("place")) or ["europe", "emea", "anywhere"])]
    if source == "himalayas":
        return [FEED_API[source].format(n=n) for n in range(0, 100, 20)]
    if source == "arbeitnow":
        return [FEED_API[source].format(n=n) for n in (1, 2, 3)]
    return [FEED_API[source]]


SEEN_STATUS = {}  # a saved answer's ".status" codes used so far (tests): "429 200" answers 429, then the page


def saved_status(base):
    """The next HTTP code a saved answer stands for, or None: a .status file holds one code, or several in turn."""
    path = base + ".status"
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        codes = fh.read().split()
    n = SEEN_STATUS.get(path, 0)
    SEEN_STATUS[path] = n + 1
    code = int(codes[min(n, len(codes) - 1)])
    return code if code >= 400 else None


def fetch(url):
    try:
        return get(url)
    except urllib.error.HTTPError as problem:
        raise Refused(problem.code) from problem


def answers(row, from_dir, queue, start, words=()):
    """The source's answer texts for this search: one for a board, up to 3 pages for LinkedIn, a feed's pages."""
    source, board = row["source"], row.get("board", "")
    if from_dir:
        base = os.path.join(from_dir, f"{source}-{board or ('feed' if source in FEEDS else 'search')}")

        def saved():
            code = saved_status(base)
            if code:
                raise Refused(code)
            pages = [base + ("." if n == 1 else f"-p{n}.") + ("html" if source == "linkedin" else "json")
                     for n in (1, 2, 3)]
            out = []
            for path in pages[:1 if source not in FEEDS and source != "linkedin" else 3]:
                if os.path.isfile(path):
                    with open(path, encoding="utf-8") as fh:
                        out.append(fh.read())
            if not out:
                raise OSError(f"no saved answer {pages[0]}")
            return out
        return queue.call(saved) if source == "linkedin" else saved()
    if source in FEEDS:
        out = []
        for url in feed_urls(row, list(words)):
            try:
                out.append(fetch(url))
            except (Refused, OSError, ValueError) as problem:
                if not out:
                    raise
                print(f"{source}: {url} not read ({problem}); {len(out)} page(s) kept")
                break  # a later page that fails ends the feed; the pages read are kept
        return out
    if source != "linkedin":
        return [fetch(API[source].format(board=urllib.parse.quote(board)))]
    seconds = max(3600, int((datetime.datetime.now() - start).total_seconds()))
    filters = {"f_WT": "2"} if row.get("mode") == "remote" else {}
    out = []
    for page in range(3):
        query = urllib.parse.urlencode({"keywords": row.get("query", ""), "location": row.get("place", ""),
                                        **filters, "f_TPR": f"r{seconds}", "start": 25 * page})
        text = queue.call(lambda: fetch(LINKEDIN.format(query=query)))
        out.append(text)
        if "base-card" not in text:
            break
    return out


def job_text(url, from_dir, queue):
    """A LinkedIn job's own text (guest page), for the remote check; None when its link holds no job number (it can
    never be read); raises Refused or OSError when unread this time."""
    m = re.search(r"(\d{6,})/?(?:\?|$)", url) or re.search(r"/view/[^/]*?(\d{6,})", url)
    if not m:
        return None
    if from_dir:
        base = os.path.join(from_dir, f"linkedin-job-{m.group(1)}")

        def saved():
            code = saved_status(base)
            if code:
                raise Refused(code)
            with open(base + ".html", encoding="utf-8") as fh:
                return fh.read()
        return queue.call(saved, TEXT_GAP)
    return queue.call(lambda: fetch(LINKEDIN_JOB.format(id=m.group(1))), TEXT_GAP)


RULE_KEYS = ("forms_out", "low", "level", "senior", "senior_need", "senior_no", "no", "soft_no", "need")


def title_rules(env):
    """The person's title rules (SEARCH_RULES, default apply/search-rules.json), compiled; {} when there are none.
    Each value is a regular expression, matched case-insensitively. Example: {"no": "sales|marketing"}."""
    path = env.path("SEARCH_RULES") if env.get("SEARCH_RULES") else os.path.join(env.home, "apply", "search-rules.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        return {k: re.compile(raw[k], re.I) for k in RULE_KEYS if raw.get(k)}
    except (ValueError, TypeError, AttributeError, re.error) as problem:
        sys.exit(f"{path}: not readable as title rules (a JSON object of regular expressions): {problem}")


def title_out(title, rules):
    """Why the title rules leave a title out before any text is read, or "". In order: another language's title
    form, a level too low, no level word, a word to drop, a soft word without an engineering word, a "senior"-only
    title outside senior_need or inside senior_no, no engineering word."""
    def has(key):
        return key in rules and rules[key].search(title)
    if has("forms_out"):
        return "title in another language"
    if has("low"):
        return "level too low"
    if ("level" in rules or "senior" in rules) and not (has("level") or has("senior")):
        return "no level word"
    if has("no"):
        return "a word you drop"
    if has("soft_no") and not has("need"):
        return "a word you drop (no engineering word)"
    if has("senior") and not has("level") and (("senior_need" in rules and not has("senior_need")) or has("senior_no")):
        return "senior title outside your stack"
    if "need" in rules and not has("need"):
        return "no engineering word"
    return ""


def rank(row):
    """The order sources are read and the funnel is filled in (18 Nov real fits): boards and remote feeds first,
    then LinkedIn in any work mode (a city), then LinkedIn remote searches."""
    if row.get("source") != "linkedin":
        return 0
    return 2 if row.get("mode") == "remote" else 1


def saved_rows(env):
    """Every saved search row (SEARCHES), for the rank and remote check of postings carried from earlier runs."""
    path = env.path("SEARCHES") if env.get("SEARCHES") else os.path.join(os.path.dirname(env.path("TRACKER")),
                                                                          "searches.json")
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except ValueError as problem:
        sys.exit(f"{path}: not readable JSON ({problem})")
    rows = data.get("searches", []) if isinstance(data, dict) else data
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def scope_of(env):
    """(remote regions, places for any work mode) from the master record's preferences.locations.search_scope; each
    is None when the scope does not hold it, and then REMOTE_REGIONS or PLACES from job-search.env counts."""
    path = env.path("MASTER_RECORD") if env.get("MASTER_RECORD") else ""
    if not path or not os.path.isfile(path):
        return None, None
    try:
        with open(path, encoding="utf-8") as fh:
            record = json.load(fh)
    except ValueError as problem:
        sys.exit(f"{path}: not readable JSON ({problem})")
    prefs = record.get("preferences") if isinstance(record, dict) else None
    locations = prefs.get("locations") if isinstance(prefs, dict) else None
    # An older record keeps its locations as a list: no scope there.
    scope = locations.get("search_scope") if isinstance(locations, dict) else None
    scope = scope if isinstance(scope, dict) else {}

    def field(key):
        values = scope.get(key)
        if not isinstance(values, list) or not values:
            return None
        return [str(x).strip().lower() for x in values if str(x).strip()]
    return field("remote_regions"), field("any_mode_places")


def terms(text):
    return [t.strip().lower() for t in str(text or "").split(",") if t.strip()]


def title_has(title, words):
    """A term matches whole words of the title, a phrase as a whole: "tech lead" passes "Tech Lead, Payments" and not
    "Lead Project Manager"; "lead" does not pass "Leadership Coach"."""
    low = title.lower()
    return any(re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", low) for w in words)


PLACES, NOT_PLACES = [], []  # from job-search.env in main()


def wanted(row, title, place, role_terms, regions):
    """A title must hold one of the search's terms (else ROLE_TERMS); the place one of its places. A remote posting
    passes only with one of its places or REMOTE_REGIONS in the same text, or as a bare "Remote"."""
    words, places = terms(row.get("query")) or role_terms, terms(row.get("place")) or PLACES
    if not title_has(title, words):
        return False
    return place_ok(place, places, regions)


def place_ok(place, places, regions):
    """A place the person ruled out (NOT_PLACES) never passes, even inside a place they accept ("Turin, Italy" with
    Turin ruled out); then the place must hold one of places, where a remote posting needs one of places or regions."""
    where = place.lower()
    if title_has(where, NOT_PLACES):
        return False
    if "remote" in where:
        return where.strip(" ()-") == "remote" or title_has(where, places + regions)
    return not places or title_has(where, places)


def run(script, *more):
    res = subprocess.run([sys.executable, "-I", os.path.join(HERE, script), *more, "--env", ENV.file],
                         capture_output=True, text=True, encoding="utf-8")
    if res.returncode:
        sys.exit(f"{script} {' '.join(more[:2])} failed: {res.stderr.strip()[-300:]}")
    return res.stdout


def window_start(since, rows_of_log):
    """The window's start: --since, else the start of the last finished run, else 7 days back."""
    if since:
        return datetime.datetime.fromisoformat(since[:16])
    done = runs(rows_of_log)
    if done:
        return datetime.datetime.fromisoformat(done[-1][0][:16])
    return datetime.datetime.now() - datetime.timedelta(days=7)


def main():
    global ENV
    args = sys.argv[1:]
    opts = {}
    for flag in ("--env", "--out", "--from", "--since"):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                sys.exit(f"{flag} takes a value")
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    add = "--add" in args
    if [a for a in args if a != "--add"]:
        sys.exit(__doc__)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ENV = jsenv.load(opts.get("--env"), __file__)
    try:
        run_start = window_start(opts.get("--since"), usage_rows(ENV)[1])
    except ValueError:
        sys.exit("--since takes a date, YYYY-MM-DD or YYYY-MM-DDTHH:MM")
    role_terms, regions = terms(ENV.get("ROLE_TERMS")), terms(ENV.get("REMOTE_REGIONS"))
    global PLACES, NOT_PLACES
    PLACES, NOT_PLACES = terms(ENV.get("PLACES")), terms(ENV.get("NOT_PLACES"))
    scope_regions, scope_places = scope_of(ENV)
    regions = scope_regions if scope_regions is not None else regions  # field by field: one missing keeps the env's
    PLACES = scope_places if scope_places is not None else PLACES
    rules = title_rules(ENV)
    since_args = ["--since", opts["--since"]] if opts.get("--since") else []
    rows = [r for r in json.loads(run("searches.py", "due", "--json", *since_args) or "[]") if r.get("method") == "script"]
    rows.sort(key=rank)  # boards and feeds first: a LinkedIn refusal never costs them
    found, read, linkedin_stopped = [], [], ""
    queue = LinkedInQueue(live=not opts.get("--from"))
    for row in rows:
        if not (terms(row.get("query")) or role_terms):
            read.append(f"search {row['id']} {row['site']}: no terms and no ROLE_TERMS: skipped; it stays due")
            continue
        if row["source"] == "linkedin" and linkedin_stopped:
            read.append(f"search {row['id']} {row['site']}: LinkedIn stopped this run ({linkedin_stopped}); it stays due")
            continue
        last = row.get("last_checked") or ""
        # A search that stayed due over runs (refused, down) starts at its own last read, so nothing is skipped.
        start = datetime.datetime.fromisoformat(last[:16]) if last[:10] else run_start
        if opts.get("--since") and last[:10] and start > run_start:
            start = run_start  # read again by hand: the window given wins over the row's own last read
        try:
            texts = answers(row, opts.get("--from"), queue, start, terms(row.get("query")) or role_terms)
        except Refused as problem:
            if row["source"] == "linkedin":
                linkedin_stopped = str(problem)
                read.append(f"search {row['id']} {row['site']}: not read ({problem}): LinkedIn stops for this run; "
                            "it stays due")
                continue
            if problem.code == 404:
                print(run("searches.py", "fail", str(row["id"]), "404").strip())
            read.append(f"search {row['id']} {row['site']}: not read ({problem}); it stays due")
            continue
        except (OSError, ValueError) as problem:
            if row["source"] == "linkedin" and not opts.get("--from"):
                linkedin_stopped = str(problem)
            read.append(f"search {row['id']} {row['site']}: not read ({problem}); it stays due")
            continue
        postings = [p for text in texts for p in parse(row["source"], row.get("board", ""), text)]
        since = start.date().isoformat()
        kept, dropped = [], {}
        for t, c, p, d, u in postings:
            if not u or not wanted(row, t, p, role_terms, regions) or (d and d < since):
                continue
            why = title_out(t, rules)  # before any text is read: the person's title rules
            if why:
                dropped[why] = dropped.get(why, 0) + 1
            else:
                kept.append((t, c, p, d, u))
        if dropped:
            read.append(f"search {row['id']} {row['site']}: title rules left out "
                        + ", ".join(f"{n} ({why})" for why, n in sorted(dropped.items())))
        by = f"script:{row['source']}:{row.get('board') or ('feed' if row['source'] in FEEDS else 'search')}"
        # A board's postings carry the employer's name as the search row names it, never the board's slug.
        # A site named "Examplia (ashby)" loses its board too, or the employer check matches the board "Ashby".
        site = re.sub(r"\s*\(" + re.escape(row["source"]) + r"\)\s*$", "", row["site"], flags=re.I)
        employer = row.get("employer") or re.sub(r"(?i)[\s-]+(jobs|careers|career site|careers page)$", "", site).strip()
        own_name = row["source"] == "linkedin" or row["source"] in FEEDS  # each posting names its employer
        name = (lambda c: c or row["site"]) if own_name else (lambda c: employer)
        found += [dict(title=t, company=name(c), location=p, date=d, url=u, found_by=by, search=row["id"],
                       rank=rank(row), gate=row["source"] == "linkedin" and row.get("mode") == "remote")
                  for t, c, p, d, u in kept]
        read.append((row, len(kept), by))
    links = os.path.join(os.path.dirname(ENV.path("TRACKER")), ".collect-links.txt")
    with open(links, "w", encoding="utf-8") as fh:
        fh.write("\n".join(p["url"] for p in found))
    try:
        new_urls = {line.split(" ", 1)[1] for line in run("searches.py", "seen", "--file", links).splitlines()
                    if line.startswith("new ")} if found else set()
    finally:
        os.remove(links)
    seen, new = set(), []
    for p in sorted(found, key=lambda p: p["rank"]):  # of one job found twice, the board's or feed's link is kept
        if p["url"] in new_urls and p["url"] not in seen:
            seen.add(p["url"])
            p["id"] = "P" + hashlib.sha1(p["url"].encode("utf-8")).hexdigest()[:8]
            new.append(p)
    for p in new:
        print(" | ".join((p["company"], p["title"], p["location"], p["date"] or "-", p["url"], p["found_by"])))
    left = {}  # posting id -> why it is left out of the funnel; recorded "skipped" with --add
    # The same job from two sources in one run (the same employer and title): one screen, not two.
    # Any shared employer key counts ("Acme" and "Acme GmbH"), as for reposts; a posting with no employer name is
    # never taken for another one.
    first = {}
    for p in new:
        tk = reposts.title_key(p["title"])
        keys = [(k, tk) for k in reposts.employer_keys(ENV, p["company"], {})]
        twin = next((first[k] for k in keys if k in first), "")
        if twin:
            left[p["id"]] = f"the same job as {twin} (found twice this run)"
        else:
            first.update({k: p["id"] for k in keys})
    if opts.get("--out"):
        raw = (ENV.get("MAX_NEW_PER_RUN") or "30").strip().lower()
        if raw != "unlimited" and not raw.isdigit():
            sys.exit(f"MAX_NEW_PER_RUN is a number or unlimited: got {raw!r}")
        cap = None if raw == "unlimited" else int(raw)
        rows_by_id = {r["id"]: r for r in saved_rows(ENV)}
        with open(ENV.path("TRACKER"), encoding="utf-8") as fh:
            backlog = [dict(id=j["id"], title=j.get("title", ""), company=j.get("company", ""), url=j.get("url", ""),
                            location=j.get("location", ""), date=j.get("date", ""), found_by=j.get("found_by", ""),
                            search=j.get("search", ""))
                       for j in flat_jobs(json.load(fh))
                       if j.get("status") == "found" and str(j.get("found_by", "")).startswith("script:")
                       and not j.get("prep") and j["id"] not in {p["id"] for p in new}]
        for p in backlog:
            row = rows_by_id.get(int(p["search"])) if str(p["search"]).isdigit() else None
            p["rank"] = rank(row) if row else (2 if p["found_by"].startswith("script:linkedin") else 0)
            p["gate"] = bool(row and row.get("source") == "linkedin" and row.get("mode") == "remote")
        # A role applied to before, posted again (a new link, the same employer and title), never goes in again;
        # nor one the funnel skipped for fit in the last FIT_CACHE_DAYS days (the fit cache).
        with open(ENV.path("TRACKER"), encoding="utf-8") as fh:
            index = reposts.Index(ENV, json.load(fh))
        repeated = {p["id"]: index.repost_of(p["company"], p["title"]) for p in new + backlog}
        left.update({k: "repost of " + v for k, v in repeated.items() if v and k not in left})
        skipped = {p["id"]: index.fit_skip_of(p["company"], p["title"]) for p in new + backlog if p["id"] not in left}
        left.update({k: f"the same job as {v}, skipped for fit" for k, v in skipped.items() if v})
        # A posting carried from an earlier run passes the person's places too (seen: 19 of 263 outside them).
        left.update({p["id"]: "outside your places: " + p["location"] for p in backlog
                     if p["id"] not in left and p["location"] and not place_ok(p["location"], PLACES, regions)})
        for p in new + backlog:
            if p["id"] in left:
                print(f"left out: {p['id']} | {p['company']} | {p['title']} | {left[p['id']]}")
        fresh = [p for p in new if p["id"] not in left]
        backlog = [p for p in backlog if p["id"] not in left]
        # Filled in the sources' order (boards and feeds, LinkedIn by city, LinkedIn remote), newest first within
        # each; a LinkedIn remote posting goes in only when its own text speaks of remote work.
        order = sorted(fresh, key=lambda p: p["date"] or "", reverse=True) + \
            sorted(backlog, key=lambda p: p["date"] or "", reverse=True)
        order.sort(key=lambda p: p["rank"])
        texts_raw = (ENV.get("TEXT_FETCHES") or str(TEXT_FETCHES)).strip()
        if not texts_raw.isdigit():
            sys.exit(f"TEXT_FETCHES is a number: got {texts_raw!r}")
        budget = int(texts_raw)
        chosen, unread = [], 0
        for p in order:
            if cap is not None and len(chosen) >= cap:
                break
            if p.get("gate"):
                if budget <= 0 or linkedin_stopped:
                    unread += 1
                    continue  # waits for the next run, unread
                budget -= 1
                try:
                    text = job_text(p["url"], opts.get("--from"), queue)
                except (Refused, OSError, ValueError) as problem:
                    if isinstance(problem, Refused) and problem.code == 429:
                        linkedin_stopped = str(problem)
                    print(f"text not read: {p['id']} | {p['url']} | {problem}; it waits for the next run")
                    unread += 1
                    continue
                if text is None:  # its link holds no job number: no run can read it
                    left[p["id"]] = "location: no LinkedIn job number to check its text for remote work"
                    print(f"left out: {p['id']} | {p['company']} | {p['title']} | {left[p['id']]}")
                    continue
                if not REMOTE_WORDS.search(html.unescape(re.sub(r"<[^>]+>", " ", text))):
                    left[p["id"]] = "location: its text says nothing of remote work (LinkedIn remote search)"
                    print(f"left out: {p['id']} | {p['company']} | {p['title']} | {left[p['id']]}")
                    continue
            chosen.append(p)
        if unread:
            print(f"{unread} LinkedIn remote postings wait for the next run: their text was not read (TEXT_FETCHES, "
                  "or LinkedIn refused)")
        taken = {p["id"] for p in chosen}
        fresh = [p for p in fresh if p["id"] not in left]
        backlog = [p for p in backlog if p["id"] not in left]
        new_out = sum(1 for p in fresh if p["id"] not in taken)
        # In the tracker, a posting left out waits for the next run; without --add a new one is not there: it is lost.
        waiting = sum(1 for p in backlog if p["id"] not in taken) + (new_out if add else 0)
        later = f"{waiting} wait for the next run" + ("" if add or not new_out else
                                                       f"; {new_out} new left out (not in the tracker without --add)")
        companies = {}
        pays = pay_table(ENV)[1]
        for p in chosen:
            p["pay"] = pay_for(pays, p["location"])
            companies.setdefault(p["company"], []).append({k: p[k] for k in ("id", "title", "url", "location", "date", "found_by")}
                                                          | ({"pay": p["pay"]} if p["pay"] else {})
                                                          | {"apply_url": p["url"]})
        with open(opts["--out"], "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"companies": [{"name": n, "jobs": j} for n, j in companies.items()]}, fh, ensure_ascii=False, indent=1)
        print(f"{len(chosen)} postings for this run's funnel (MAX_NEW_PER_RUN={raw}); {later}")
    if add:
        for p in new:
            run("track.py", "add", p["id"], p["company"], p["title"], p["url"], f"found_by={p['found_by']}",
                f"search={p['search']}",
                *([f"location={p['location']}"] if p["location"] else []), *([f"date={p['date']}"] if p["date"] else []))
    if add and left:
        # One tracker write for every posting left out: it is in the tracker, so it is never "new" again.
        batch = os.path.join(os.path.dirname(ENV.path("TRACKER")), ".collect-left.tsv")
        with open(batch, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("".join(f"{k}\tskipped\t{v}\n" for k, v in left.items()))
        try:
            run("track.py", "set", "--file", batch)
        finally:
            os.remove(batch)
    # Marked read only now: a search whose postings failed to be written stays due, so none is lost to its date.
    for item in read:
        if isinstance(item, str):
            print(item)
            continue
        row, n, by = item
        run("searches.py", "done", str(row["id"]), f"found={sum(1 for p in new if p['search'] == row['id'])}")
        print(f"search {row['id']} {row['site']}: {n} matching, read")
    print(f"{len(new)} new postings from {sum(1 for x in read if not isinstance(x, str))} searches read by script"
          + (", added to the tracker" if add and new else "") + f"; window from {run_start:%Y-%m-%d %H:%M}")


if __name__ == "__main__":
    main()
