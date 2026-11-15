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
Only searches due today are read (searches.py due), and each is marked read (searches.py done <id> found=<n>).
A search row: site, employer (for a board: the employer's name, which names every posting; without it, the site
without a trailing "jobs" or "careers"), query (terms, comma-separated: a
title must hold one; empty: ROLE_TERMS from job-search.env; neither: the search is skipped and stays due), source,
board (the name in the board's address; for linkedin: none), place (terms, comma-separated: the place must hold one;
empty: any place). A remote posting passes only when its place also holds one of the search's places or one of
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
from trackerlib import flat_jobs  # noqa: E402
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


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def day(value):
    """A date as YYYY-MM-DD from an ISO text or epoch milliseconds; "" when unknown."""
    if isinstance(value, (int, float)):
        return datetime.datetime.fromtimestamp(value / 1000, datetime.timezone.utc).date().isoformat()
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


def fetch(url):
    try:
        return get(url)
    except urllib.error.HTTPError as problem:
        raise Refused(problem.code) from problem


def answers(row, from_dir, last_request, start):
    """The source's answer texts for this search: one for a board, up to 3 pages for LinkedIn."""
    source, board = row["source"], row.get("board", "")
    if from_dir:
        base = os.path.join(from_dir, f"{source}-{board or 'search'}")
        if os.path.isfile(base + ".status"):
            with open(base + ".status", encoding="utf-8") as fh:
                raise Refused(int(fh.read().strip()))
        pages = [base + ("." if n == 1 else f"-p{n}.") + ("html" if source == "linkedin" else "json") for n in (1, 2, 3)]
        out = []
        for path in pages[:3 if source == "linkedin" else 1]:
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as fh:
                    out.append(fh.read())
        if not out:
            raise OSError(f"no saved answer {pages[0]}")
        return out
    if source != "linkedin":
        return [fetch(API[source].format(board=urllib.parse.quote(board)))]
    seconds = max(3600, int((datetime.datetime.now() - start).total_seconds()))
    out = []
    for page in range(3):
        wait = 4 - (time.monotonic() - last_request[0])
        if wait > 0:
            time.sleep(wait)
        last_request[0] = time.monotonic()
        query = urllib.parse.urlencode({"keywords": row.get("query", ""), "location": row.get("place", ""),
                                        "f_TPR": f"r{seconds}", "start": 25 * page})
        text = fetch(LINKEDIN.format(query=query))
        out.append(text)
        if "base-card" not in text:
            break
    return out


def terms(text):
    return [t.strip().lower() for t in str(text or "").split(",") if t.strip()]


def wanted(row, title, place, role_terms, regions):
    """A title must hold one of the search's terms (else ROLE_TERMS); the place one of its places. A remote posting
    passes only with one of its places or REMOTE_REGIONS in the same text, or as a bare "Remote"."""
    words, places = terms(row.get("query")) or role_terms, terms(row.get("place"))
    if not any(w in title.lower() for w in words):
        return False
    where = place.lower()
    if "remote" in where:
        return where.strip(" ()-") == "remote" or any(p in where for p in places + regions)
    return not places or any(p in where for p in places)


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
    rows = [r for r in json.loads(run("searches.py", "due", "--json") or "[]") if r.get("method") == "script"]
    found, read, last_request, linkedin_stopped = [], [], [0.0], ""
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
        try:
            texts = answers(row, opts.get("--from"), last_request, start)
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
        kept = [(t, c, p, d, u) for t, c, p, d, u in postings
                if u and wanted(row, t, p, role_terms, regions) and not (d and d < since)]
        by = f"script:{row['source']}:{row.get('board') or 'search'}"
        # A board's postings carry the employer's name as the search row names it, never the board's slug.
        employer = row.get("employer") or re.sub(r"(?i)[\s-]+(jobs|careers|career site|careers page)$", "", row["site"]).strip()
        name = (lambda c: c or row["site"]) if row["source"] == "linkedin" else (lambda c: employer)
        found += [dict(title=t, company=name(c), location=p, date=d, url=u, found_by=by, search=row["id"])
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
    for p in found:
        if p["url"] in new_urls and p["url"] not in seen:
            seen.add(p["url"])
            p["id"] = "P" + hashlib.sha1(p["url"].encode("utf-8")).hexdigest()[:8]
            new.append(p)
    for p in new:
        print(" | ".join((p["company"], p["title"], p["location"], p["date"] or "-", p["url"], p["found_by"])))
    if opts.get("--out"):
        raw = (ENV.get("MAX_NEW_PER_RUN") or "30").strip().lower()
        if raw != "unlimited" and not raw.isdigit():
            sys.exit(f"MAX_NEW_PER_RUN is a number or unlimited: got {raw!r}")
        cap = None if raw == "unlimited" else int(raw)
        with open(ENV.path("TRACKER"), encoding="utf-8") as fh:
            backlog = [dict(id=j["id"], title=j.get("title", ""), company=j.get("company", ""), url=j.get("url", ""),
                            location=j.get("location", ""), date=j.get("date", ""), found_by=j.get("found_by", ""))
                       for j in flat_jobs(json.load(fh))
                       if j.get("status") == "found" and str(j.get("found_by", "")).startswith("script:")
                       and not j.get("prep") and j["id"] not in {p["id"] for p in new}]
        chosen = (sorted(new, key=lambda p: p["date"] or "", reverse=True)
                  + sorted(backlog, key=lambda p: p["date"] or "", reverse=True))[:cap]
        taken = {p["id"] for p in chosen}
        new_out = sum(1 for p in new if p["id"] not in taken)
        # In the tracker, a posting left out waits for the next run; without --add a new one is not there: it is lost.
        waiting = sum(1 for p in backlog if p["id"] not in taken) + (new_out if add else 0)
        later = f"{waiting} wait for the next run" + ("" if add or not new_out else
                                                       f"; {new_out} new left out (not in the tracker without --add)")
        companies = {}
        for p in chosen:
            companies.setdefault(p["company"], []).append({k: p[k] for k in ("id", "title", "url", "location", "date", "found_by")}
                                                          | {"apply_url": p["url"]})
        with open(opts["--out"], "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"companies": [{"name": n, "jobs": j} for n, j in companies.items()]}, fh, ensure_ascii=False, indent=1)
        print(f"{len(chosen)} postings for this run's funnel (MAX_NEW_PER_RUN={raw}); {later}")
    if add:
        for p in new:
            run("track.py", "add", p["id"], p["company"], p["title"], p["url"], f"found_by={p['found_by']}",
                *([f"location={p['location']}"] if p["location"] else []), *([f"date={p['date']}"] if p["date"] else []))
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
