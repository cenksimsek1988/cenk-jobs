"""Collect new postings without a model: every saved search with method "script" (searches.py), read from the job
board's public API or LinkedIn's guest search, filtered by its terms and places, minus what the tracker already has.

python -I collect_postings.py [--since <YYYY-MM-DD[THH:MM]>] [--out <search file>] [--add] [--from <dir>] [--rows <ids>]
    prints one line per new posting: company | title | place | date | link | found_by, then one line per search read.
    --rows <id,id>: only these due searches (a widening round's new rows); a listed one not due is named, not read.
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
"Remote, US" does not. A board's own remote flag (Ashby, Lever, Workable, SmartRecruiters) makes the place
"Remote - <place>", and a place that names only a region ("EMEA", "Europe") is checked as a remote one.
Example: searches.py add "Acme jobs" "engineer, architect" source=greenhouse board=acme place="Rome, Italy".
A board row read for the first time takes every open posting of the board, whatever its date; later reads start at
the row's last read. The posting text a board's list carries (Greenhouse, Lever, Ashby), and a LinkedIn remote
posting's text read for its remote check, is saved in POSTINGS_DIR as <id>.md for each posting that goes to the
funnel, and passed as its text_file.
A row's own place narrows the person's places, never widens them: a posting that is not remote must also be in one
of PLACES (or the scope's any_mode_places). Example: a LinkedIn row "Berlin" with PLACES=Rome, Italy passes nothing
from a Berlin office.
Feeds, 3 s apart per source; 2 refusals (429) in a row stop a source for the run, its searches stay due. New
sources: remoterocketship (board=<country slug>, a term is a title slug, optional tech=<stack>; the 20 newest per
page, so daily), himalayas-search (board=<country>; discovery only: apply_url is left empty with an apply_note, the
fit check finds the employer's own page; the himalayas feed too), workable-search (remote postings; kept only with a
place or region of the person's). Before the funnel, each posting's own page is read (LOCATION_CHECKS a run, default
60; Ashby and Greenhouse from their APIs): one whose every place is outside the person's places, that must be based
in another country, or works US hours is left out ("some overlap with US hours" is no reason). A posting whose
employer and title are already in the tracker under another link is left out, unless that job closed or was skipped
only by a setting's cut the person's settings no longer make (track.py reopen). A "team lead" title needs an
engineering word. A job the last fit check could not read ("unread" in the tracker) gets its text saved (fetch_jd.py
--posting) and passed as text_file; one whose text could not be saved (a page drawn by script) is named in a "no text
saved" line, for the session to save from Chrome. A job track.py reopen set back to found joins the funnel too, from
its "reopened" day.
Remote Rocketship: a title or stack with no page (404) is skipped with one line; the row fails only when every page
does. A posting's place is the countries it hires in (its locationCountries, else location), not the board's; one
whose required language the master record does not list is left out, counted in one line.
LinkedIn: up to 5 pages per search over the window since its start, newest first, each page from the posting after
the last one read, the row's terms (else ROLE_TERMS) joined with OR (linkedin_keywords), 4.5 s between calls and a
job text 6 s after
the last call; one refusal (429) pauses 60 s and slows to 8 s, an error or a second refusal stops LinkedIn for this
run and its remaining searches stay due. A board that answers 404 twice is marked gone (searches.py fail).
found_by is script:<source>:<board>; the run report counts script and agent finds apart.
The order, in which the funnel is filled too: company boards and remote feeds (remotive, remoteok, jobicy,
himalayas, arbeitnow, remoterocketship, himalayas-search, workable-search), then LinkedIn by city (mode=any), then
LinkedIn remote searches (mode=remote). On 19 Nov Remote Rocketship gave 12 of 14 fits.
The person's title rules (SEARCH_RULES, see templates/search-rules-example.json) apply before any text is read, to
boards and feeds too, whose postings are often sales or operations roles: another language's title form, a low
level, no level word, a word they drop, no engineering word. A feed's posting passes only with a region of the
scope in its own location field: "Remote, Europe" passes with the region Europe, "Remote, USA only" does not. A
LinkedIn remote search's posting goes on only when its own text speaks of remote work (one text read, no model,
TEXT_FETCHES a run; seen: 73 of 82 were hybrid in one city). The location check, seen 19 Nov: 32 of 40 "Europe"
postings were single-country elsewhere. A repost of a role already applied to or declined, or skipped for fit in
the last 30 days, is left out (reposts.py).
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
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import choices  # noqa: E402
import jsenv  # noqa: E402
import reposts  # noqa: E402
from trackerlib import flat_jobs, pay_for, pay_table, scope_of, terms, title_has  # noqa: E402
from fetch_jd import to_text  # noqa: E402
from variants import runs, usage_rows  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (job-search assistant)"}
# The posting texts a board's list already carries (Greenhouse with content=true, Lever, Ashby), by link: saved as
# the posting's text file when it goes to the fit check, which then reads it whole instead of fetching it (0.46.0).
TEXTS = {}
BOARDS = ("greenhouse", "lever", "ashby", "smartrecruiters", "workable")  # each lists every open posting
API = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true",
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
    # One page per term. Remote Rocketship: board = a country slug ("italy"), a term becomes a title slug; its page
    # holds the 20 newest postings (?page= is ignored), so read it daily. Himalayas search: board = a country
    # ("Italy"); discovery only: its posting pages are blocked, so the apply link is found on the employer's site.
    # Workable search: remote postings only, no board.
    "remoterocketship": "https://www.remoterocketship.com/country/{board}/jobs/{slug}",
    "himalayas-search": "https://himalayas.app/jobs/api/search?q={term}&country={board}&sort=recent",
    "workable-search": "https://jobs.workable.com/api/v1/jobs?query={term}&workplace=remote",
}
FEEDS = tuple(FEED_API)
DISCOVERY_ONLY = ("himalayas", "himalayas-search")  # the apply link is the employer's own careers page
# Every source but LinkedIn: 3 s between calls of one source; 2 refusals (429) in a row stop it for the run, its
# searches stay due (19 Nov: Himalayas and Workable refused every call after ~100 at 1.2 s).
SOURCE_GAP, SOURCE_REFUSALS = 3.0, 2
# A posting open to more than one country, or to a region: the Workable search keeps it (with remote work).
WIDE = re.compile(r"(?i)\b(EU|EMEA|Europe|European Union|worldwide|anywhere)\b")
# A place that says remote with a word of degree before it: read as plain "remote" (0.46.6). Example: "Full Remote".
FULL_REMOTE = re.compile(r"(?i)(?:\b(?:full|fully|completely|entirely)|\b100\s*%)[\s-]+remote\b")
# Hiring only in another country (18 Nov gate): the person's places decide whether it is "another" one.
ONLY_IN = re.compile(r"\b(?i:must|need to|needs to|required to|should|have to)\s+(?i:be\s+)?(?i:based|located|"
                     r"reside|residing|resident|live|living)\s+(?i:in)\s+(?:the\s+)?([A-Z][A-Za-z.]+(?: [A-Z][A-Za-z.]+)*)")
REMOTE_IN = re.compile(r"\b(?i:remote)\s*[-–(,]\s*([A-Z][A-Za-z]+(?: [A-Z][a-z]+)?)")
TIME_ZONES = re.compile(r"(?i)\b(?:US|U\.S\.|North American?|EST|PST|CST|Pacific|Eastern|Central)\s+(?:time\s*zones?|"
                        r"hours|business hours)\b")
LOCATION_CHECKS = 60  # postings whose own page is read for the location check, per run (LOCATION_CHECKS)
# LinkedIn: 4.5 s between calls, a job text 6 s after the last call; one refusal (429) pauses 60 s and slows to 8 s;
# a second one stops LinkedIn for the run. Seen on 17 Nov: 4.5 s ran into 429 after ~46 texts, 8 s ran through.
LINKEDIN_GAP, TEXT_GAP, SLOW_GAP, PAUSE = 4.5, 6.0, 8.0, 60
LINKEDIN_PAGES = 5  # calls per search, newest first: 10 postings a page since Nov 2026 (25 before)
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
    data = next_data(text) if source == "remoterocketship" else json.loads(text)
    if source in FEEDS:
        return feed_postings(source, data, board)
    name = board
    if source == "greenhouse":
        for j in data.get("jobs", []):
            keep_text(j.get("absolute_url", ""), html.unescape(j.get("content") or ""))
        return [(j.get("title", ""), name, (j.get("location") or {}).get("name", ""),
                 day(j.get("first_published") or j.get("updated_at")), j.get("absolute_url", "")) for j in data.get("jobs", [])]
    if source == "lever":
        for j in data:
            lists = "".join(f"<h3>{x.get('text')}</h3><ul>{x.get('content') or ''}</ul>" for x in j.get("lists") or [])
            keep_text(j.get("hostedUrl", ""), (j.get("description") or "") + lists + (j.get("additional") or ""))
        return [(j.get("text", ""), name, remote_flagged((j.get("categories") or {}).get("location", ""),
                                                         str(j.get("workplaceType", "")).lower() == "remote"),
                 day(j.get("createdAt")), j.get("hostedUrl", "")) for j in data]
    if source == "ashby":
        listed = [j for j in data.get("jobs", []) if j.get("isListed", True)]
        for j in listed:
            keep_text(j.get("jobUrl", ""), j.get("descriptionHtml") or j.get("descriptionPlain") or "")
        return [(j.get("title", ""), name, remote_flagged(j.get("location", ""), bool(j.get("isRemote"))
                                                          or str(j.get("workplaceType", "")).lower() == "remote"),
                 day(j.get("publishedAt")), j.get("jobUrl", "")) for j in listed]
    if source == "smartrecruiters":
        return [(j.get("name", ""), (j.get("company") or {}).get("name", name),
                 remote_flagged(", ".join(x for x in ((j.get("location") or {}).get("city"),
                                                     (j.get("location") or {}).get("country")) if x),
                                bool((j.get("location") or {}).get("remote"))),
                 day(j.get("releasedDate")), f"https://jobs.smartrecruiters.com/{board}/{j.get('id', '')}")
                for j in data.get("content", [])]
    if source == "workable":
        return [(j.get("title", ""), data.get("name") or name,
                 remote_flagged(", ".join(x for x in (j.get("city"), j.get("country")) if x),
                                bool(j.get("telecommuting"))),
                 day(j.get("published_on")), j.get("url") or j.get("shortlink", "")) for j in data.get("jobs", [])]
    return []


def remote_flagged(place, remote):
    """A board's own remote flag, in the place's words, so the place check treats the posting as remote (0.46.0;
    before, a remote job filed under a city outside the person's places was dropped). Example: "Remote - Berlin,
    Germany"."""
    if not remote or "remote" in (place or "").lower():
        return place or ("Remote" if remote else "")
    return f"Remote - {place}" if place else "Remote"


def keep_text(url, markup):
    """A board's own posting text, kept by link for the fit check (TEXTS)."""
    text = to_text(markup)
    if url and len(text) >= 300:
        TEXTS[url] = text


def next_data(text):
    """A Remote Rocketship page's postings: {"jobs": props.pageProps.initialJobOpenings} of its __NEXT_DATA__, and
    "generic": True when the page is the country's list of every remote job, not a title's (rocketship_title_page)."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', text, re.S)
    if not m:
        raise ValueError("no __NEXT_DATA__ on the page")
    data = json.loads(m.group(1))
    props = (data.get("props") or {}).get("pageProps") or {}
    return {"jobs": props.get("initialJobOpenings") or [], "generic": not rocketship_title_page(data),
            "weekly": props.get("initialWeeklyNewCount")}


def rocketship_title_page(data):
    """False when a Remote Rocketship page is the generic list a title it does not know falls back to: its
    __NEXT_DATA__ query names no title (jobsInput). Seen 21 Nov: germany/jobs/tech-lead and germany/jobs/xyz gave the
    same 20 newest remote jobs of any title, query {}; germany/jobs/engineering-manager gave query {"jobsInput":
    "entwicklungsleiter"}. A page without a query (an older saved answer) counts as a title page."""
    return "query" not in data or bool((data.get("query") or {}).get("jobsInput"))


LANGUAGES = None  # the words of the person's languages, from the master record's "languages" (read once)
LANGUAGE_LEFT = {}  # a required language the records do not list -> the postings it left out this run
# A language's own name, accents dropped, read as its English one, so the record may spell it either way.
NATIVE_NAMES = {"deutsch": "german", "turkce": "turkish", "espanol": "spanish", "castellano": "spanish",
                "francais": "french", "italiano": "italian", "portugues": "portuguese", "nederlands": "dutch",
                "polski": "polish", "svenska": "swedish", "norsk": "norwegian", "dansk": "danish", "suomi": "finnish",
                "cestina": "czech", "magyar": "hungarian", "romana": "romanian"}


def language_words(text):
    """A language entry's words in ASCII and lowercase, a native name read as its English one. Example: "Deutsch (C1)"
    -> {"german", "c"}."""
    plain = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    return {NATIVE_NAMES.get(w, w) for w in re.findall(r"[a-z]+", plain)}


def known_languages():
    """The words of the languages the master record lists (strings, or {"language": ...}); empty when it lists none."""
    global LANGUAGES
    if LANGUAGES is None:
        LANGUAGES = set()
        env = globals().get("ENV")  # set by main(); a test may call this without it
        path = env.path("MASTER_RECORD") if env is not None and env.get("MASTER_RECORD") else ""
        try:
            with open(path, encoding="utf-8") as fh:
                items = (json.load(fh) or {}).get("languages") or []
        except (OSError, ValueError, AttributeError):
            items = []
        for item in items if isinstance(items, list) else []:
            name = item.get("language") or item.get("name") if isinstance(item, dict) else item
            if name:
                LANGUAGES |= language_words(name)
    return LANGUAGES


def language_ok(job):
    """False when a Remote Rocketship posting requires a language the records do not list at all, so it never costs a
    fit check (0.46.6; seen 21 Nov: 9 hard skips for a language). A language matches by any word of its name, in its
    own spelling too ("Deutsch" is German). With no languages recorded, every posting passes."""
    need = [str(x).strip() for x in job.get("requiredLanguages") or [] if str(x).strip()]
    known = known_languages() if need else set()
    missing = [x for x in need if known and not language_words(x) & known]
    for x in missing:
        LANGUAGE_LEFT[x] = LANGUAGE_LEFT.get(x, 0) + 1
    return not missing


def feed_postings(source, data, board=""):
    """[(title, company, place, date, url)] from a remote feed's answer; the place reads "Remote, <its region>". A
    posting that names no region never reads as a bare "Remote" (which passes anywhere): often it is US-only."""
    remote = lambda where: "Remote, " + (where.strip() or "no region given")  # noqa: E731
    if source == "remoterocketship":
        country = board.replace("-", " ").title()
        out = []
        for j in data.get("jobs", []):
            if j.get("dateDeleted") or j.get("isEntryLevel") or j.get("isJunior") or not language_ok(j):
                continue
            # The posting's own countries, else the board's (0.46.6; seen 21 Nov: a posting open only in Poland read
            # "Remote, Europe" from the europe board, and 36 such hard skips cost a fit check each in one catch-up).
            own = ", ".join(str(c) for c in j.get("locationCountries") or [] if c) or str(j.get("location") or "")
            where = own or country
            kind = j.get("locationType", "remote")
            out.append((j.get("roleTitle", ""),
                        ((j.get("company") or {}) if isinstance(j.get("company"), dict) else {}).get("name", ""),
                        remote(where) if kind == "remote" else f"{kind}, {where}",
                        day(j.get("created_at")), j.get("url", "")))
        return out
    if source == "himalayas-search":
        return [(j.get("title", ""), j.get("companyName", ""),
                 remote(", ".join(j.get("locationRestrictions") or []) or "Worldwide"), day(j.get("pubDate")),
                 j.get("applicationLink") or j.get("guid") or "") for j in data.get("jobs", [])]
    if source == "workable-search":
        out = []
        for j in data.get("jobs", []):
            if j.get("workplace") != "remote":
                continue
            places = [x for x in (j.get("locations") or []) if x and x != "TELECOMMUTE"]
            where = ", ".join(places[:4]) or (j.get("location") or {}).get("countryName") or ""
            wide = dict.fromkeys(m.group(1) for m in WIDE.finditer(" ".join(str(j.get(k) or "")
                                                                            for k in ("title", "description"))))
            out.append((j.get("title", ""), (j.get("company") or {}).get("title", ""),
                        remote(", ".join([where] * bool(where) + list(wide))), day(j.get("created")), j.get("url", "")))
        return out
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
    board = urllib.parse.quote(row.get("board", ""))
    if source == "remoterocketship":
        tech = "?techStack=" + urllib.parse.quote(row["tech"]) if row.get("tech") else ""
        return [FEED_API[source].format(board=board.lower(), slug=re.sub(r"[^a-z0-9]+", "-", w.lower()).strip("-"))
                + tech for w in words]
    if source in ("himalayas-search", "workable-search"):
        return [FEED_API[source].format(board=board, term=urllib.parse.quote(w)) for w in words]
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


LAST_CALL = {}  # source -> the time of its last call (feeds only: a board is one call per run)


def paced_fetch(source, url):
    """fetch() at most once every SOURCE_GAP seconds per feed."""
    rest = SOURCE_GAP - (time.monotonic() - LAST_CALL.get(source, -SOURCE_GAP))
    if rest > 0:
        time.sleep(rest)
    LAST_CALL[source] = time.monotonic()
    return fetch(url)


def rocketship_pages(row, words, from_dir=None):
    """Remote Rocketship: one page per title (with the row's stack). A page that answers 404 is that title's, never the
    row's: it is skipped with one line, and the row fails (searches.py fail) only when every page does. Seen 20 Nov:
    italy/jobs/staff?techStack=java answered 404. A title Remote Rocketship does not know gives the country's generic
    list of every remote job (0.46.2): skipped like a 404, never read as that title's postings. With --from, the n-th
    title reads the n-th saved page (remoterocketship-<board>.json, then -p2, -p3), and a page's .status file answers
    with that code."""
    out, missing, urls = [], 0, feed_urls(row, words)
    base = os.path.join(from_dir, f"remoterocketship-{row.get('board', '')}") if from_dir else ""
    for n, url in enumerate(urls):
        try:
            if from_dir:
                page = base + ("" if n == 0 else f"-p{n + 1}")
                code = saved_status(page)
                if code:
                    raise Refused(code)
                with open(page + ".json", encoding="utf-8") as fh:
                    text = fh.read()
            else:
                text = paced_fetch("remoterocketship", url)
            try:
                generic = next_data(text)["generic"]
            except ValueError:
                generic = False  # no __NEXT_DATA__: the page's own error comes when it is read
            if generic:
                missing += 1
                print(f"no Remote Rocketship page for that title: {url} gave the generic list of every remote job: "
                      f'drop that title from search {row.get("id")} (searches.py query {row.get("id")} "<the other '
                      'titles>"; searches.py suggest names them)')
                continue
            out.append(text)
        except Refused as problem:
            if problem.code == 404:
                missing += 1
                print(f"no Remote Rocketship page: {url}: drop that title or stack from search {row.get('id')} "
                      f'(searches.py query {row.get("id")} "<the other titles>")')
                continue
            if not out:
                raise
            print(f"remoterocketship: {url} not read ({problem}); {len(out)} page(s) kept")
            break
        except (OSError, ValueError) as problem:
            if not out:
                raise
            print(f"remoterocketship: {url} not read ({problem}); {len(out)} page(s) kept")
            break
    if urls and missing == len(urls):
        raise Refused(404)
    return out


def linkedin_keywords(words):
    """The search's terms as one LinkedIn query: each term of two or more words quoted, the terms joined with OR, so a
    posting with any one of them matches (0.46.0; before, "a, b" asked LinkedIn for the words of every term, and a
    row with no terms of its own read every job in its place). Example: ["engineering manager", "CTO"] ->
    '"engineering manager" OR CTO'."""
    return " OR ".join(f'"{w}"' if " " in w else w for w in (str(w).strip() for w in words) if w)


def answers(row, from_dir, queue, start, words=()):
    """The source's answer texts for this search: one for a board, up to LINKEDIN_PAGES for LinkedIn, a feed's
    pages."""
    source, board = row["source"], row.get("board", "")
    if source == "remoterocketship":
        return rocketship_pages(row, list(words), from_dir)
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
                out.append(paced_fetch(source, url))
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
    out, offset = [], 0
    for _ in range(LINKEDIN_PAGES):
        query = urllib.parse.urlencode({"keywords": linkedin_keywords(list(words)), "location": row.get("place", ""),
                                        **filters, "f_TPR": f"r{seconds}", "sortBy": "DD", "start": offset})
        text = queue.call(lambda: fetch(LINKEDIN.format(query=query)))
        out.append(text)
        held = text.count('<div class="base-card')
        if not held:
            break
        # "start" counts postings: a page held 25 before Nov 2026 and 10 since (seen 21 Nov: steps of 25 skipped
        # postings 10-24 and 35-49), so the next page starts after the last posting read.
        offset += held
    return out


def own_page(url, from_dir, pid):
    """(places, text) from a posting's own page: Ashby's location and secondary locations and Greenhouse's location
    from their APIs, else the page's text alone. With --from: the board's saved answer (ashby-<board>.json),
    greenhouse-job-<id>.json, or page-<posting id>.html. Raises Refused, OSError or ValueError when unread."""
    def read(name, live_url):
        if from_dir:
            with open(os.path.join(from_dir, name), encoding="utf-8") as fh:
                return fh.read()
        return paced_fetch("page:" + urllib.parse.urlparse(live_url).netloc, live_url)
    m = re.search(r"jobs\.ashbyhq\.com/([^/?#]+)/([0-9a-f-]{36})", url)
    if m:
        board = json.loads(read(f"ashby-{m.group(1)}.json", API["ashby"].format(board=m.group(1))))
        job = next((j for j in board.get("jobs", []) if j.get("id") == m.group(2)), None)
        if not job:
            raise ValueError("not on the Ashby board (closed?)")
        places = [job.get("location")] + [x.get("location") for x in job.get("secondaryLocations") or []]
        remote = job.get("isRemote") or str(job.get("workplaceType", "")).lower() == "remote"
        places = [p if not remote or "remote" in p.lower() else "Remote, " + p for p in places if p]
        return places, job.get("descriptionPlain") or ""
    m = re.search(r"greenhouse\.io/([^/?#]+)/jobs/(\d+)", url)
    if m:
        d = json.loads(read(f"greenhouse-job-{m.group(2)}.json",
                            f"https://boards-api.greenhouse.io/v1/boards/{m.group(1)}/jobs/{m.group(2)}"))
        return [(d.get("location") or {}).get("name", "")], re.sub(r"<[^>]+>", " ", html.unescape(d.get("content") or ""))
    page = read(f"page-{pid}.html", url)
    page = re.sub(r"(?s)<script.*?</script>|<style.*?</style>", " ", page)
    return [], re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page)))


def location_out(p, from_dir, regions):
    """Why the posting's own page puts it outside the person's places, or "": every place it names is outside them
    (Ashby, Greenhouse, "Remote - Poland" in its text), it must be based in another country, or it works US hours.
    A page that cannot be read leaves the posting in: the fit check reads it."""
    try:
        places, text = own_page(p["url"], from_dir, p["id"])
    except (Refused, OSError, ValueError):
        return ""
    named = [x for x in places if x] + ["Remote, " + m.group(1) for m in REMOTE_IN.finditer(text)]
    if named and not any(place_ok(x, PLACES, regions) for x in named):
        return "location on its own page: " + "; ".join(dict.fromkeys(named))
    only = [m.group(1).rstrip(".") for m in ONLY_IN.finditer(text)]
    if only and not any(place_ok("Remote, " + x, PLACES, regions) for x in only):
        return "hires only in " + only[0]
    zones = TIME_ZONES.search(text)
    # "some overlap with US hours" asks for a few shared hours, not US working hours; "full overlap" asks for them.
    near = text[max(0, zones.start() - 60):zones.end() + 20] if zones else ""
    overlap = re.search(r"(?i)\boverlap", near) and not re.search(r"(?i)\b(full|fully|complete|completely|entire)\s+"
                                                                  r"overlap|\boverlap\s+(fully|completely)\b", near)
    if zones and not overlap and not place_ok("Remote, US", PLACES, regions):
        return "works " + zones.group(0)
    return ""


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
# "Team lead" counts only next to an engineering word (18 Nov: customer-success and operations team leads came in).
TEAM_LEAD = re.compile(r"(?i)\bteam[\s-]*lead(?:er)?\b")
ENGINEERING = re.compile(r"(?i)\b(engineer\w*|develop\w*|software|backend|back-end|frontend|front-end|full[- ]?stack|"
                         r"platform|devops|data|tech\w*|security|java|kotlin|cloud|infrastructure|qa|sre|it)\b")


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
    if TEAM_LEAD.search(title) and not (has("need") or ENGINEERING.search(title)):
        return "a team lead without an engineering word"
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


PLACES, NOT_PLACES = [], []  # from job-search.env in main()


def remote_gate(row, location):
    """True when a LinkedIn remote search's posting must say remote work in its text to go on. A posting in a place
    the person takes in any work mode needs no such word (0.46.6; seen 21 Nov: hybrid postings in the scope's own
    any_mode_places city were left out by a remote search). Example: "Lisbon, Portugal (Hybrid)" with any_mode_places
    Lisbon goes on."""
    if row.get("source") != "linkedin" or row.get("mode") != "remote":
        return False
    where = str(location or "").lower()
    any_mode = bool(PLACES) and "remote" not in where and title_has(where, PLACES) and not title_has(where, NOT_PLACES)
    return not any_mode


def load_places(env):
    """Set PLACES and NOT_PLACES from job-search.env, then the master record's search scope field by field (one
    missing keeps the env's); return the regions a remote posting must name."""
    global PLACES, NOT_PLACES
    regions = terms(env.get("REMOTE_REGIONS"))
    PLACES, NOT_PLACES = terms(env.get("PLACES")), terms(env.get("NOT_PLACES"))
    scope_regions, scope_places = scope_of(env)
    PLACES = scope_places if scope_places is not None else PLACES
    return scope_regions if scope_regions is not None else regions


def wanted(row, title, place, role_terms, regions):
    """A title must hold one of the search's terms (else ROLE_TERMS); the place one of its places. A remote posting
    passes only with one of its places or REMOTE_REGIONS in the same text, or as a bare "Remote".
    A row's own places narrow the person's places, never widen them: a posting that is not remote, found by a row
    that is not a remote search, must also be in one of PLACES (the scope's any_mode_places when set). A remote
    search's postings often name only a city. A place that names a hybrid or office part is not remote here. Seen 20
    Nov: LinkedIn city rows the person had dropped gave 89 of 103 postings out of scope. Example: a row "Berlin" with
    PLACES=Rome, Italy passes no "Berlin, Germany" and no "Berlin (Hybrid, remote 2 days)"."""
    words, own = terms(row.get("query")) or role_terms, terms(row.get("place"))
    if not title_has(title, words):
        return False
    if not place_ok(place, own or PLACES, regions):
        return False
    where = place.lower()
    remote_only = remote_like(where)
    return not own or row.get("mode") == "remote" or remote_only or place_ok(place, PLACES, regions)


def remote_like(where):
    """A place that is remote, or names only regions ("Europe", "EMEA; Worldwide": no city or country), with no
    hybrid or office part. 0.46.0: a region-only place was read as an office place and dropped. "Berlin, EMEA" is
    no region-only place."""
    if re.search(r"\b(hybrid|office|on-?site)\b", where):
        return False
    region_only = bool(WIDE.search(where)) and not re.sub(r"[\s,;/|()&+.\-–]+|\band\b", "", WIDE.sub("", where))
    return "remote" in where or region_only


def place_ok(place, places, regions):
    """A place the person ruled out (NOT_PLACES) never passes, even inside a place they accept ("Turin, Italy" with
    Turin ruled out); then the place must hold one of places, where a remote or region-only posting needs one of
    places or regions. "Full Remote", "Fully remote" and "100% remote" read as "Remote" (0.46.6: they were dropped)."""
    where = FULL_REMOTE.sub("remote", place.lower())
    if title_has(where, NOT_PLACES):
        return False
    if "remote" in where or remote_like(where):
        return where.strip(" ()-") == "remote" or title_has(where, places + regions)
    return not places or title_has(where, places)


def run(script, *more):
    cmd = [sys.executable, "-I", os.path.join(HERE, script), *more, "--env", ENV.file]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if res.returncode == 3:  # STALE (recordlib): another command wrote the file meanwhile; once more, on the new one
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if res.returncode:
        sys.exit(f"{script} {' '.join(more[:2])} failed: {res.stderr.strip()[-300:]}")
    return res.stdout


def tracked_keys():
    """(employer key, title key) -> job id for every job in the tracker, except a closed one (a new posting is a new
    opening) and one the fit check skipped only by a setting's cut the person's settings no longer make
    (choices.setting_cut; before 0.46.0 such a cut kept the title out for good). The new posting then comes in, and
    track.py reopen leaves the old row skipped."""
    with open(ENV.path("TRACKER"), encoding="utf-8") as fh:
        jobs = flat_jobs(json.load(fh))
    out = {}
    for j in jobs:
        note = str(j.get("note") or j.get("outcome") or "")
        if j.get("status") == "closed" or (j.get("status") == "skipped" and choices.setting_cut(note, ENV)):
            continue
        tk = reposts.title_key(j.get("title", ""))
        for k in reposts.employer_keys(ENV, j.get("company", ""), {}):
            out.setdefault((k, tk), j.get("id", ""))
    return out


def save_text(path, p, text):
    """A posting's text from a board's list, in fetch_jd.py --posting's form."""
    d = datetime.date.today()
    body = re.sub(r"\n{3,}", "\n\n", text).strip()
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"# Job description: {p['company']} - {p['title']}\n\n- **Source:** {p['url']}\n"
                 f"- **Fetched:** {d.day} {d:%b %Y} (the posting can change or close later)\n\n{body}\n")


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
    for flag in ("--env", "--out", "--from", "--since", "--rows"):
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
    role_terms, regions = terms(ENV.get("ROLE_TERMS")), load_places(ENV)
    rules = title_rules(ENV)
    since_args = ["--since", opts["--since"]] if opts.get("--since") else []
    rows = [r for r in json.loads(run("searches.py", "due", "--json", *since_args) or "[]") if r.get("method") == "script"]
    if opts.get("--rows"):
        # A widening round reads only its own new rows, not every due row again (0.46.6; seen 21 Nov: about 160
        # rows, 30-40 minutes a round). Example: --rows 181,182.
        ids = [x.strip() for x in opts["--rows"].split(",") if x.strip()]
        if not ids or not all(x.isdigit() for x in ids):
            sys.exit(f"--rows takes search ids, comma-separated: got {opts['--rows']!r}")
        wanted_ids = {int(x) for x in ids}  # numbers: "0181" is row 181
        not_due = sorted(wanted_ids - {int(r["id"]) for r in rows})
        rows = [r for r in rows if int(r["id"]) in wanted_ids]
        if not_due:
            print(f"--rows: not due, not read: {', '.join(map(str, not_due))} (searches.py list)")
    rows.sort(key=rank)  # boards and feeds first: a LinkedIn refusal never costs them
    found, read, linkedin_stopped, refusals = [], [], "", {}
    queue = LinkedInQueue(live=not opts.get("--from"))
    for row in rows:
        if not (terms(row.get("query")) or role_terms):
            read.append(f"search {row['id']} {row['site']}: no terms and no ROLE_TERMS: skipped; it stays due")
            continue
        if row["source"] == "linkedin" and linkedin_stopped:
            read.append(f"search {row['id']} {row['site']}: LinkedIn stopped this run ({linkedin_stopped}); it stays due")
            continue
        if refusals.get(row["source"], 0) >= SOURCE_REFUSALS:
            read.append(f"search {row['id']} {row['site']}: {row['source']} stopped this run ({SOURCE_REFUSALS} "
                        "refusals in a row); it stays due")
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
            if problem.code == 429:
                refusals[row["source"]] = refusals.get(row["source"], 0) + 1
            read.append(f"search {row['id']} {row['site']}: not read ({problem}); it stays due")
            continue
        except (OSError, ValueError) as problem:
            if row["source"] == "linkedin" and not opts.get("--from"):
                linkedin_stopped = str(problem)
            read.append(f"search {row['id']} {row['site']}: not read ({problem}); it stays due")
            continue
        refusals[row["source"]] = 0  # an answer ends a run of refusals
        postings = [p for text in texts for p in parse(row["source"], row.get("board", ""), text)]
        # A board lists only open postings: its first read takes them all, so the posting that led to the board is
        # never lost to the window (0.46.0); later reads start at the row's last read.
        since = "" if row["source"] in BOARDS and not last[:10] else start.date().isoformat()
        kept, dropped = [], {}
        for t, c, p, d, u in postings:
            if not u or not wanted(row, t, p, role_terms, regions) or (d and since and d < since):
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
                       rank=rank(row), gate=remote_gate(row, p))
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
                            search=j.get("search", ""), unread=j.get("unread", ""))
                       for j in flat_jobs(json.load(fh))
                       # track.py reopen: any finder, from its "reopened" day on (--per-day paces them); the
                       # field stays on the row, so a reopened job left found and unprepared comes back next run
                       if j.get("status") == "found"
                       and (str(j["reopened"]) <= datetime.date.today().isoformat() if j.get("reopened")
                            else str(j.get("found_by", "")).startswith("script:"))
                       and not j.get("prep") and j["id"] not in {p["id"] for p in new}]
        for p in backlog:
            row = rows_by_id.get(int(p["search"])) if str(p["search"]).isdigit() else None
            p["rank"] = rank(row) if row else (2 if p["found_by"].startswith("script:linkedin") else 0)
            p["gate"] = bool(row and remote_gate(row, p.get("location", "")))
        # A role applied to before, posted again (a new link, the same employer and title), never goes in again;
        # nor one the funnel skipped for fit in the last FIT_CACHE_DAYS days (the fit cache).
        with open(ENV.path("TRACKER"), encoding="utf-8") as fh:
            index = reposts.Index(ENV, json.load(fh))
        repeated = {p["id"]: index.repost_of(p["company"], p["title"]) for p in new + backlog}
        left.update({k: "repost of " + v for k, v in repeated.items() if v and k not in left})
        skipped = {p["id"]: index.fit_skip_of(p["company"], p["title"]) for p in new + backlog if p["id"] not in left}
        left.update({k: f"the same job as {v}, skipped for fit" for k, v in skipped.items() if v})
        # The same employer and title already in the tracker under another link (another source): never new again.
        tracked = tracked_keys()
        for p in new:
            if p["id"] not in left:
                tk = reposts.title_key(p["title"])
                twin = next((tracked[(k, tk)] for k in reposts.employer_keys(ENV, p["company"], {})
                             if (k, tk) in tracked), "")
                if twin and twin != p["id"]:
                    left[p["id"]] = f"the same job as {twin} (already in the tracker)"
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
        checks_raw = (ENV.get("LOCATION_CHECKS") or str(LOCATION_CHECKS)).strip()
        if not checks_raw.isdigit():
            sys.exit(f"LOCATION_CHECKS is a number: got {checks_raw!r}")
        checks = int(checks_raw)
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
                keep_text(p["url"], text)  # the guest page holds the whole posting: the fit check needs no fetch
            elif checks > 0 and not p["found_by"].startswith("script:linkedin"):
                checks -= 1  # the posting's own page, before any token is spent on it (19 Nov: 32 of 40 out)
                why = location_out(p, opts.get("--from"), regions)
                if why:
                    left[p["id"]] = why
                    print(f"left out: {p['id']} | {p['company']} | {p['title']} | {why}")
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
        # A posting the last fit check could not read: its text is saved now (fetch_jd.py --posting) for this one.
        postings = ENV.path("POSTINGS_DIR") if ENV.get("POSTINGS_DIR") else os.path.join(ENV.home, "apply", "postings")
        unread_ids = [p["id"] for p in chosen if p.get("unread")]
        if unread_ids and not opts.get("--from"):
            print(run("fetch_jd.py", *unread_ids, "--posting").strip())
        # A board's list carried the posting text (TEXTS): saved now, so the fit check reads it whole, with no fetch
        # and no "check in browser" (0.46.0).
        saved = 0
        for p in chosen:
            text_file = os.path.join(postings, p["id"] + ".md")
            if p["url"] in TEXTS and not os.path.isfile(text_file):
                os.makedirs(postings, exist_ok=True)
                save_text(text_file, p, TEXTS[p["url"]])
                saved += 1
        if saved:
            print(f"{saved} posting texts saved for the fit check (boards' lists, LinkedIn remote checks)")
        for p in chosen:
            # A page drawn by script (seen: jobs.dover.com) gives no text to a script or to the fit check.
            text_file = os.path.join(postings, p["id"] + ".md")
            if p.get("unread") and not os.path.isfile(text_file):
                print(f"no text saved for unread {p['id']} ({p['url']}): save it from Chrome as "
                      f"{text_file.replace(os.sep, '/')} (references/sites/dover.md)")
        for p in chosen:
            p["pay"] = pay_for(pays, p["location"])
            text_file = os.path.join(postings, p["id"] + ".md")
            discovery = (p["found_by"].split(":") + [""])[1] in DISCOVERY_ONLY
            companies.setdefault(p["company"], []).append({k: p[k] for k in ("id", "title", "url", "location", "date", "found_by")}
                                                          | ({"pay": p["pay"]} if p["pay"] else {})
                                                          | ({"text_file": text_file.replace(os.sep, "/")}
                                                             if os.path.isfile(text_file) else {})
                                                          | ({"apply_url": "", "apply_note": "apply on the employer's "
                                                              "own careers page (this site's posting pages are blocked)"}
                                                             if discovery else {"apply_url": p["url"]}))
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
    if LANGUAGE_LEFT:
        print("Remote Rocketship postings left out for a required language the records do not list: "
              + ", ".join(f"{k} {v}" for k, v in sorted(LANGUAGE_LEFT.items())))
    print(f"{len(new)} new postings from {sum(1 for x in read if not isinstance(x, str))} searches read by script"
          + (", added to the tracker" if add and new else "") + f"; window from {run_start:%Y-%m-%d %H:%M}")


if __name__ == "__main__":
    main()
