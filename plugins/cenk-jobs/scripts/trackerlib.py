"""Shared reading of the tracker, used by track.py, build_app_folders.py, logins.py and export_dashboard.py so all
name jobs, notes, dates and logins alike.

Two tracker shapes are read: {jobs: [...]} (the plugin's: one flat row per job, its note in "note") and
{companies: [{name, verdict, hits, jobs: [{..., prep: {...}}]}]} (an older, richer one: a job's note is "outcome").

flat_jobs(tracker)   every job as one flat dict, from either shape.
entries(tracker)     every job as (company name, the job's own dict), for scripts that change jobs in place;
                     note_key(tracker) names the field that holds a job's note in that shape.
companies(tracker)   every job as (company dict, job dict); in the flat shape the company dict is {"name": ...}.
needs_of(prep)       the open points only the person can answer ("needs", or an older "needs_<name>" list).
waits_on_person(s)   True for statuses where the person must act: account-needed, needs-person, needs-captcha and
                     any other "needs-<word>" (an older tracker may name the person, e.g. "needs-jane").
date_in(text)        the first "<day> <month>" in a note as YYYY-MM-DD, the year nearest to today (notes such as
                     "3 Nov: sent on Greenhouse" carry no year); "" when there is none.
applied_on(job, note) the job's "applied" date, else the first date in its note.
login_of(job)        the id of the sign-in a job waits on: the job's own "login" field when set, else its platform
                     with the company for platforms where each employer has its own account (Workday,
                     SuccessFactors, Cornerstone, a company's own site), else the shared platform, else the
                     apply link's site. Why: the apply link is often a LinkedIn page that only forwards to the
                     employer's site, so the link alone names the wrong login.
"""
import datetime
import json
import re
import urllib.parse

# Pay figures and salary or rate phrases: masked in every file other people may read (dashboard, usage report).
# A range is one match, so "EUR 70-90k" leaves no "-90k" behind (seen: a posted range in a note, 6 Nov 2026).
# Currency codes stand alone ("12 European" is not pay); TRY only in capitals ("try 2 times" is not pay).
_CUR = r"(?:(?<![A-Za-z])(?:EUR|USD|GBP|SEK|CHF|(?-i:TRY))(?![A-Za-z])|€|\$|£)"
_NUM = r"\d[\d.,]*(?:\s?[kK](?![a-z]))?"
_RANGE = _NUM + r"(?:\s?(?:-|–|—|to)\s?(?:" + _CUR + r"\s?)?" + _NUM + r")?"
_UNIT = r"(?:\s?(?:/|per\s|a\s)\s?(?:h|hr|hour|day|month|year|yr|annum)\b)?"
PAY = re.compile(r"(?i)" + _CUR + r"\s?" + _RANGE + r"(?:\s?" + _CUR + r")?" + _UNIT
                 + r"|" + _RANGE + r"\s?(?:k€|" + _CUR + r")" + _UNIT
                 + r"|" + _RANGE + r"\s?/\s?(?:h|hr|hour|day|month|year)\b"
                 + r"|salary[^.;]*|rate[^.;]*\d[^.;]*")
PER_EMPLOYER = re.compile(r"(?i)workday|successfactors|cornerstone|taleo|icims|oracle|phenom|company site|careers site")
# Job boards: their posting only forwards to the employer's own site, where the person signs in and applies
# (seen: a LinkedIn link given as an employer's Workday sign-in, 6 Nov 2026).
JOB_BOARD = re.compile(r"(?i)^https?://([a-z0-9-]+\.)*(linkedin\.com|indeed\.com|glassdoor\.[a-z.]+|stepstone\.[a-z.]+|"
                       r"infojobs\.net|monster\.[a-z.]+)(/|$)")
BOARD_NAME = re.compile(r"(?i)linkedin|indeed|glassdoor|stepstone|infojobs|monster")
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
DAY_MONTH = re.compile(r"(\d{1,2})\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(?:uary|ruary|ch|il|e|y|ust|t|tember|ober|ember)?(?![a-z])")


def is_company_shape(tracker):
    return "jobs" not in tracker and "companies" in tracker


def entries(tracker):
    if is_company_shape(tracker):
        return [(c.get("name", ""), j) for c in tracker["companies"] for j in c.get("jobs", [])]
    return [(j.get("company", ""), j) for j in tracker.get("jobs", [])]


def companies(tracker):
    if is_company_shape(tracker):
        return [(c, j) for c in tracker["companies"] for j in c.get("jobs", [])]
    return [({"name": j.get("company", "")}, j) for j in tracker.get("jobs", [])]


def note_key(tracker):
    # The older shape keeps a job's note in "outcome"; writing "note" there would hide it from that shape's tools.
    return "outcome" if is_company_shape(tracker) else "note"


def needs_of(prep):
    if prep.get("needs"):
        return prep["needs"]
    return next((v for k, v in prep.items() if k.startswith("needs_") and isinstance(v, list)), [])


def no_pay(text):
    return re.sub(r"\s{2,}", " ", PAY.sub("[private]", text or "")).strip()


def waits_on_person(status):
    return status == "account-needed" or (status or "").startswith("needs-")


def flat_jobs(tracker):
    if "jobs" in tracker:
        return [dict(j, apply_url=j.get("apply_url") or j.get("url", "")) for j in tracker["jobs"]]
    out = []
    for company in tracker.get("companies", []):
        for job in company.get("jobs", []):
            prep = job.get("prep") or {}
            out.append(dict(job, company=job.get("company") or company.get("name", ""),
                            title=prep.get("title") or job.get("title", ""),
                            apply_url=job.get("apply_url") or prep.get("apply_url") or job.get("url", ""),
                            platform=job.get("platform") or prep.get("platform") or "",
                            needs=needs_of(prep)))
    return out


def date_in(text, today=None):
    m = DAY_MONTH.search(text or "")
    if not m:
        return ""
    day, month = int(m.group(1)), MONTHS.index(m.group(2).lower()) + 1
    today = today or datetime.date.today()
    best = None
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            d = datetime.date(year, month, day)
        except ValueError:
            continue
        if best is None or abs((d - today).days) < abs((best - today).days):
            best = d
    return best.isoformat() if best else ""


def applied_on(job, note_field="note"):
    return (job.get("applied") or "")[:10] or date_in(job.get(note_field) or "")


def site_of(url):
    host = urllib.parse.urlparse(url or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def login_of(job):
    if job.get("login"):
        return job["login"]
    platform = re.split(r"[(;,]", job.get("platform") or "")[0].strip()
    if platform and PER_EMPLOYER.search(platform):
        name = "company site" if re.search(r"(?i)company site|careers site", platform) else platform
        return f"{name} · {job.get('company', '').split(' (')[0].strip()}"
    return platform or site_of(job.get("apply_url"))


def employer_link(job, login=""):
    """Where the person signs in or applies for a job: the employer's own page, unless the login is a job board whose
    own form is the way to apply (LinkedIn Easy Apply, Indeed Apply). For an employer's own site (Workday,
    SuccessFactors, a company site) a job board's page never counts: "" when the records hold no other link, so
    Claude finds it on the posting."""
    prep = job.get("prep") or {}
    urls = [u for u in (job.get("apply_url"), prep.get("apply_url"), *(job.get("other_urls") or []), job.get("url")) if u]
    if not BOARD_NAME.search(login or ""):
        own = [u for u in urls if not JOB_BOARD.search(u)]
        urls = own or ([] if PER_EMPLOYER.search(login or "") else urls)
    return urls[0] if urls else ""


def load_settings(env):
    """The person's TRACKER_SETTINGS file (optional): names and overrides their older records need, kept out of the
    scripts so the scripts stay the same for everyone. {} when the key is not set."""
    if not env.get("TRACKER_SETTINGS"):
        return {}
    path = env.path("TRACKER_SETTINGS")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"TRACKER_SETTINGS names {path}, which does not exist")


def json_indent(path, default=2):
    """The indent a JSON file already uses, so a rewrite changes only what changed."""
    try:
        with open(path, encoding="utf-8") as f:
            f.readline()
            second = f.readline()
    except OSError:
        return default
    spaces = len(second) - len(second.lstrip(" "))
    return spaces or default
