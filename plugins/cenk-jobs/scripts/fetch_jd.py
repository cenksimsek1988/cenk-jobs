"""Fetch the full text of job postings and save each as job-description.md in its application's folder.

Usage: python -I fetch_jd.py [--env <job-search.env>] <job id> [<job id> ...] [--force] [--start "<text>"] [--end "<text>"]
For each job: the posting link comes from the tracker (its "url", then its apply link); the text comes from the job
board's public API where there is one (Greenhouse, Lever, Ashby, SmartRecruiters, Workable, LinkedIn's public job
page), else from the page itself. It is saved as job-description.md in the folder whose overview.md names that job id
(run build_app_folders.py first). An existing job-description.md is kept unless --force is given.
--start / --end cut a page's text to the posting itself (for pages that carry site menus or sign-in prompts); use
them with one job id at a time.
Postings change and close: save the text while it is live, best right after applying.
"""
import datetime
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jsenv  # noqa: E402
from trackerlib import companies, expand_row  # noqa: E402

args = sys.argv[1:]
options = {}
for flag in ("--env", "--start", "--end"):
    if flag in args:
        i = args.index(flag)
        options[flag] = args[i + 1]
        del args[i:i + 2]
force = "--force" in args
ids = [a for a in args if a != "--force"]
if not ids:
    sys.exit(__doc__)
env = jsenv.load(options.get("--env"), __file__)
ROOT = env.path("APPLICATIONS_DIR")


class Text(HTMLParser):
    """Visible text with paragraph and list breaks; scripts and styles dropped."""
    BREAK = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "section", "tr"}

    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in ("h1", "h2", "h3", "h4"):
            self.parts.append("\n\n### ")
        elif tag in self.BREAK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip = max(0, self.skip - 1)
        elif tag in self.BREAK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def to_text(markup):
    parser = Text()
    parser.feed(markup or "")
    text = "".join(parser.parts)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n[ ]+", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (job-search assistant)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch(url):
    """(header line, body text) for one posting link."""
    u = urllib.parse.urlparse(url)
    host, parts = u.netloc.lower(), [p for p in u.path.split("/") if p]
    query = urllib.parse.parse_qs(u.query)
    if "greenhouse.io" in host and "jobs" in parts and parts.index("jobs") > 0:
        board, job = parts[parts.index("jobs") - 1], parts[parts.index("jobs") + 1]
        apis = ["boards-api.greenhouse.io"] + (["boards-api.eu.greenhouse.io"] if ".eu." in host else [])
        for i, api in enumerate(apis):
            try:
                data = json.loads(get(f"https://{api}/v1/boards/{board}/jobs/{job}"))
                break
            except Exception:  # noqa: BLE001 (an EU board may answer only on the EU API)
                if i == len(apis) - 1:
                    raise
        return (f"{data.get('title')} | {(data.get('location') or {}).get('name')} | updated {data.get('updated_at')}",
                to_text(html.unescape(data.get("content") or "")))
    if "smartrecruiters.com" in host and len(parts) >= 2:
        company, posting = parts[0], parts[1].split("-")[0]
        data = json.loads(get(f"https://api.smartrecruiters.com/v1/companies/{company}/postings/{posting}"))
        sections = (data.get("jobAd") or {}).get("sections") or {}
        loc = data.get("location") or {}
        return (f"{data.get('name')} | {loc.get('city')}, {loc.get('country')} | released {data.get('releasedDate')}",
                "\n\n".join(f"### {s.get('title')}\n\n{to_text(s.get('text') or '')}" for s in sections.values()
                            if s.get("text")))
    if "lever.co" in host and len(parts) >= 2:
        api = "api.eu.lever.co" if ".eu." in host else "api.lever.co"
        data = json.loads(get(f"https://{api}/v0/postings/{parts[0]}/{parts[1]}"))
        lists = "\n\n".join(f"### {x.get('text')}\n\n{to_text('<ul>' + (x.get('content') or '') + '</ul>')}"
                            for x in data.get("lists") or [])
        cats = data.get("categories") or {}
        return (f"{data.get('text')} | {cats.get('location')} | {cats.get('commitment')}",
                "\n\n".join(x for x in (data.get("descriptionPlain"), lists, data.get("additionalPlain")) if x).strip())
    if "ashbyhq.com" in host and len(parts) >= 2:
        board = json.loads(get(f"https://api.ashbyhq.com/posting-api/job-board/{parts[0]}"))
        job = next((j for j in board.get("jobs", []) if j.get("id") == parts[1]), None)
        if not job:
            raise ValueError("not on the Ashby board any more (closed?)")
        return (f"{job.get('title')} | {job.get('location')} | published {job.get('publishedAt')}",
                to_text(job.get("descriptionHtml")) or job.get("descriptionPlain", ""))
    if host == "jobs.workable.com" and len(parts) >= 2 and parts[0] == "view":
        data = json.loads(get(f"https://jobs.workable.com/api/v1/jobs/{parts[1]}"))
        loc = data.get("location") or {}
        return (f"{data.get('title')} | {loc.get('city')}, {loc.get('countryName') or loc.get('country')} | "
                f"updated {data.get('updated')}",
                "\n\n".join(to_text(data.get(k)) for k in ("description", "requirementsSection", "benefitsSection")
                            if data.get(k)))
    if "workable.com" in host and "j" in parts and parts.index("j") > 0:
        account, code = parts[0], parts[parts.index("j") + 1]
        data = json.loads(get(f"https://apply.workable.com/api/v3/accounts/{account}/jobs/{code}"))
        loc = data.get("location") or {}
        return (f"{data.get('title')} | {loc.get('city')}, {loc.get('country')} | published {data.get('published')}",
                "\n\n".join(to_text(data.get(k)) for k in ("description", "requirements", "benefits") if data.get(k)))
    if "linkedin.com" in host:
        job = (query.get("currentJobId") or [""])[0] or next((p for p in reversed(parts) if p.isdigit()), "")
        if not job:
            m = re.search(r"-(\d{6,})/?$", u.path)
            job = m.group(1) if m else ""
        if job:
            return url, to_text(get(f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job}"))
    return url, to_text(get(url))


def folders():
    """job id -> application folder, from the "Job id" line of every overview.md."""
    out = {}
    for stage in ("approved", "pending", "rejected", "closed", "declined", "not-applied"):
        base = os.path.join(ROOT, stage)
        for name in os.listdir(base) if os.path.isdir(base) else []:
            ov = os.path.join(base, name, "overview.md")
            if os.path.isfile(ov):
                with open(ov, encoding="utf-8") as f:
                    m = re.search(r"^- \*\*Job id:\*\* (\S+)", f.read(), re.M)
                if m:
                    out.setdefault(m.group(1), os.path.join(base, name))
    return out


with open(env.path("TRACKER"), encoding="utf-8") as fh:
    tracker = json.load(fh)
jobs = {j["id"]: (c.get("name", ""), j) for c, j in companies(tracker)}
where = folders()
d = datetime.date.today()
fetched = f"{d.day} {d:%b %Y}"
for job_id in ids:
    if job_id not in jobs:
        print(job_id, "NOT IN TRACKER")
        continue
    company, job = jobs[job_id]
    folder = where.get(job_id)
    if not folder:
        print(job_id, "NO FOLDER (run build_app_folders.py first)")
        continue
    target = os.path.join(folder, "job-description.md")
    if os.path.exists(target) and not force:
        print(job_id, "kept the existing job-description.md (--force replaces it)")
        continue
    job = expand_row(env.path("TRACKER"), job)  # a split row: its prep is in the detail file
    prep = job.get("prep") or {}
    links = [u for u in (job.get("url"), job.get("apply_url"), prep.get("apply_url")) if u]
    head = body = source = ""
    for url in dict.fromkeys(links):
        try:
            got_head, got_body = fetch(url)
        except Exception as exc:  # noqa: BLE001 (any network or format error: try the next link)
            print(job_id, "could not read", url[:80], "-", type(exc).__name__, str(exc)[:80])
            continue
        if len(got_body.strip()) > len(body.strip()):
            head, body, source = got_head, got_body, url
        if len(body.strip()) >= 300:  # a page built by scripts gives only its title: then try the next link
            break
    if not body.strip():
        print(job_id, "FAILED: no link gave the posting text")
        continue
    if len(body.strip()) < 300:
        print(job_id, f"only {len(body.strip())} characters found: open the posting in the browser and save it there")
    start, end = options.get("--start"), options.get("--end")
    body = body[body.find(start):] if start and start in body else body
    body = body[:body.find(end)] if end and end in body else body
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    text = (f"# Job description: {company} - {job.get('title') or prep.get('title') or ''}\n\n"
            f"- **Source:** {source}\n- **Fetched:** {fetched} (the posting can change or close later)\n"
            + (f"- **Posting data:** {head}\n" if not head.startswith("http") else "")
            + f"\n{body}\n")
    with open(target, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(job_id, "saved", len(body), "chars ->", os.path.basename(folder))
