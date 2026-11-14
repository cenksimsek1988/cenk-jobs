"""Collect new postings without a model: every saved search with method "script" (searches.py), read from the job
board's public API or LinkedIn's guest search, filtered by its terms and places, minus what the tracker already has.

python -I collect_postings.py [--out <search file>] [--add] [--from <dir>]
    prints one line per new posting: company | title | place | date | link | found_by, then one line per search read.
    --out: also writes the postings as a search file for workflows/screen-and-prepare.js
    ({companies: [{name, jobs: [{id, title, url, apply_url, location, date, found_by}]}]}).
    --add: also adds each new posting to the tracker (track.py add <id> ... found_by=<source>), status found.
    --from <dir>: reads each source's answer from <dir>/<source>-<board>.json (or .html for linkedin) instead of the
    web; for tests.
Only searches due today are read (searches.py due), and each is marked read (searches.py done <id> found=<n>).
A search row: site, query (terms, comma-separated: a title must hold one; empty: any title), source, board (the
name in the board's address; for linkedin: none), place (terms, comma-separated: the place must hold one, or the
posting is remote; empty: any place). Example: searches.py add "Acme jobs" "engineer, architect" source=greenhouse
board=acme place="Rome, Italy".
A posting older than the search's last check is left out when its date is known. LinkedIn: one request per search,
4 seconds apart. found_by is script:<source>:<board>; the run report counts script and agent finds apart.
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
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jsenv  # noqa: E402

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


def answer(row, from_dir, last_request):
    source, board = row["source"], row.get("board", "")
    if from_dir:
        name = f"{source}-{board or 'search'}." + ("html" if source == "linkedin" else "json")
        with open(os.path.join(from_dir, name), encoding="utf-8") as fh:
            return fh.read()
    if source == "linkedin":
        wait = 4 - (time.monotonic() - last_request[0])
        if wait > 0:
            time.sleep(wait)
        last_request[0] = time.monotonic()
        query = urllib.parse.urlencode({"keywords": row.get("query", ""), "location": row.get("place", ""),
                                        "f_TPR": "r604800", "start": 0})
        return get(LINKEDIN.format(query=query))
    return get(API[source].format(board=urllib.parse.quote(board)))


def terms(text):
    return [t.strip().lower() for t in str(text or "").split(",") if t.strip()]


def wanted(row, title, place):
    """A title must hold one of the search's terms, and the place one of its places or "remote"."""
    words, places = terms(row.get("query")), terms(row.get("place"))
    if words and not any(w in title.lower() for w in words):
        return False
    return not places or any(p in place.lower() for p in places) or "remote" in place.lower()


def run(script, *more):
    res = subprocess.run([sys.executable, "-I", os.path.join(HERE, script), *more, "--env", ENV.file],
                         capture_output=True, text=True, encoding="utf-8")
    if res.returncode:
        sys.exit(f"{script} {' '.join(more[:2])} failed: {res.stderr.strip()[-300:]}")
    return res.stdout


def main():
    global ENV
    args = sys.argv[1:]
    opts = {}
    for flag in ("--env", "--out", "--from"):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                sys.exit(f"{flag} takes a path")
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    add = "--add" in args
    if [a for a in args if a != "--add"]:
        sys.exit(__doc__)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ENV = jsenv.load(opts.get("--env"), __file__)
    rows = [r for r in json.loads(run("searches.py", "due", "--json") or "[]") if r.get("method") == "script"]
    found, read, last_request = [], [], [0.0]
    for row in rows:
        try:
            postings = parse(row["source"], row.get("board", ""), answer(row, opts.get("--from"), last_request))
        except (OSError, ValueError) as problem:
            read.append(f"search {row['id']} {row['site']}: not read ({problem}); it stays due")
            continue
        since = (row.get("last_checked") or "")[:10]
        kept = [(t, c, p, d, u) for t, c, p, d, u in postings
                if u and wanted(row, t, p) and not (since and d and d < since)]
        by = f"script:{row['source']}:{row.get('board') or 'search'}"
        found += [dict(title=t, company=c or row["site"], location=p, date=d, url=u, found_by=by, search=row["id"])
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
        companies = {}
        for p in new:
            companies.setdefault(p["company"], []).append({k: p[k] for k in ("id", "title", "url", "location", "date", "found_by")}
                                                          | {"apply_url": p["url"]})
        with open(opts["--out"], "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"companies": [{"name": n, "jobs": j} for n, j in companies.items()]}, fh, ensure_ascii=False, indent=1)
    if add:
        for p in new:
            run("track.py", "add", p["id"], p["company"], p["title"], p["url"], f"found_by={p['found_by']}",
                *([f"location={p['location']}"] if p["location"] else []))
    # Marked read only now: a search whose postings failed to be written stays due, so none is lost to its date.
    for item in read:
        if isinstance(item, str):
            print(item)
            continue
        row, n, by = item
        run("searches.py", "done", str(row["id"]), f"found={sum(1 for p in new if p['search'] == row['id'])}")
        print(f"search {row['id']} {row['site']}: {n} matching, read")
    print(f"{len(new)} new postings from {sum(1 for x in read if not isinstance(x, str))} searches read by script"
          + (", added to the tracker" if add and new else ""))


if __name__ == "__main__":
    main()
