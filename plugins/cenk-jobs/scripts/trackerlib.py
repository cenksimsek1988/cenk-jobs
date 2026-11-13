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

A job's own to-do items are its "todo" list, kept in the summary row: [{kind, text, where, link, due, login, since,
session}]. TODO_KINDS names the kinds; "waiting" means the next move is the employer's.
pipeline_entry(pipeline, id) a job's PIPELINE entry; one with "same_as" takes the stage, date and steps of the entry
                     it names, where it has none of its own.
ended(job, pipeline) (how, date) when a job is over, else ("", ""): by its tracker status (ENDED_STATUS; no date,
                     the row holds none) or, for a sent job, by its PIPELINE stage (ENDED_STAGE) with that date.
step_done(step)      the date a PIPELINE step was done ("yes" when no date is known), "" when it is not done: its
                     "done" field, else a "how" that says done (older records).

A split tracker (track.py split) keeps one summary row per job and per company; the rest sits in a detail file
named by the row's "details" key (a path relative to the tracker's folder). Only this module knows that layout:
read_detail(path, row)       the detail of a row, {} when the row has no "details" key (an unsplit tracker).
expand_row(path, row)        a job row with its detail merged back: the row as it was before the split (plus its
                             "details" key). The row itself when it has no detail. expand_company likewise.
collapse_row(path, row, full, company_shape)
                             write a changed merged job back, in place: the detail file and the summary row. A row
                             without a "details" key keeps everything inline. collapse_company likewise.
expand(tracker, path) / collapse(tracker, path)
                             the same for every row, for a command that works on the whole tracker.
split_tracker(tracker, names)  the summary tracker and the detail files, for the rows not split yet.
A job's summary row holds what flat_jobs needs (title, apply_url, platform, needs, resolved with flat_jobs's
precedence); its detail holds prep, history and earlier. A company's detail holds ties*, hits, not_counted, checks.
"""
import copy
import datetime
import hashlib
import json
import os
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


DETAILS = "details"
META = "_split"  # in a job's detail file: how to rebuild the row exactly (see split_job)
JOB_DETAIL_KEYS = ("prep", "history", "earlier")
COMPANY_DETAIL_EXACT = ("hits", "not_counted", "checks")  # and every key starting with "ties"


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


# A job's to-do kinds. "waiting": the next move is the employer's (shown in Hiring steps, never in Do now).
TODO_KINDS = ("urgent", "working", "task", "click", "todo", "waiting")
ENDED_STATUS = ("excluded", "closed", "declined", "skipped", "failed")  # tracker statuses: over before it was sent
ENDED_STAGE = ("rejected", "closed", "declined")  # PIPELINE stages: over after it was sent
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
# "done" as a word in a step's "how" (older records), not "not done" or "to be done".
_DONE_WORD = re.compile(r"(?i)(?<!not )(?<!to be )\bdone\b")


def pipeline_entry(pipeline, job_id):
    own = (pipeline or {}).get(job_id) or {}
    shared = (pipeline or {}).get(own.get("same_as")) or {} if own.get("same_as") else {}
    return dict(shared, **own) if shared else own


def ended(job, pipeline=None):
    status = job.get("status") or ""
    if status in ENDED_STATUS:
        return status, ""
    entry = pipeline_entry(pipeline, job.get("id"))
    if entry.get("stage") in ENDED_STAGE:
        rejected = entry.get("rejected") if isinstance(entry.get("rejected"), dict) else {}
        return entry["stage"], str(entry.get("date") or rejected.get("date") or "")[:10]
    return "", ""


def step_done(step):
    done = step.get("done")
    if done:
        found = ISO_DATE.search(str(done))
        return found.group(0) if found else str(step.get("date") or "yes")[:10]
    said = _DONE_WORD.search(step.get("how") or "")
    if said:
        found = ISO_DATE.search(step["how"][said.end():])
        return found.group(0) if found else str(step.get("date") or "yes")[:10]
    return ""


def flat_jobs(tracker):
    """Every job as one flat dict; opens no detail file (a split row already holds the resolved fields)."""
    if "jobs" in tracker:
        return [dict(j, apply_url=j.get("apply_url") or j.get("url", "")) for j in tracker["jobs"]]
    out = []
    for company in tracker.get("companies", []):
        for job in company.get("jobs", []):
            if job.get(DETAILS):
                out.append(dict(job, company=job.get("company") or company.get("name", ""), title=job.get("title", ""),
                                apply_url=job.get("apply_url") or job.get("url", ""), platform=job.get("platform") or "",
                                needs=job.get("needs") or []))
                continue
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
    # A split row keeps the prepared link, when it differs from apply_url, as prep_apply_url.
    urls = [u for u in (job.get("apply_url"), prep.get("apply_url") or job.get("prep_apply_url"),
                        *(job.get("other_urls") or []), job.get("url")) if u]
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


# --- the split layout: summary rows in the tracker, details beside it --------------------------------------------------
def _company_detail_key(key):
    return key.startswith("ties") or key in COMPANY_DETAIL_EXACT


def _resolved(job):
    """The fields flat_jobs takes from prep, with its precedence (company shape only)."""
    prep = job.get("prep") if isinstance(job.get("prep"), dict) else {}
    return {"title": prep.get("title") or job.get("title", ""),
            "apply_url": job.get("apply_url") or prep.get("apply_url") or job.get("url", ""),
            "platform": job.get("platform") or prep.get("platform") or "",
            "needs": needs_of(prep)}


def split_job(job, rel, company_shape):
    """(summary row, detail) of a merged job. The row keeps everything but prep, history and earlier, and gets the
    resolved title, apply_url, platform and needs, so it alone answers status and links. The detail's prep drops what
    the row already says (id, title, apply_url, platform, needs). META lists what join_job restores: which prep keys
    came from the row ("same_as_row"), which resolved fields the job did not have itself ("added") and the job's own
    values where they differed from the resolved ones ("own"), so that join_job gives the job back exactly."""
    row = {k: v for k, v in job.items() if k not in JOB_DETAIL_KEYS}
    detail = {k: copy.deepcopy(job[k]) for k in JOB_DETAIL_KEYS if k in job}
    row[DETAILS] = rel
    meta = {}
    prep = detail.get("prep")
    if company_shape:
        own, added = {}, []
        for field, value in _resolved(job).items():
            if field in job:
                if job[field] != value:
                    own[field] = job[field]
                row[field] = value
            elif value not in ("", []):
                added.append(field)
                row[field] = value
        same = {}
        if isinstance(prep, dict):
            if prep.get("id") and prep["id"] == job.get("id"):
                same["id"] = "id"
            for field in ("title", "platform"):
                if prep.get(field) and prep[field] == row.get(field):
                    same[field] = field
            if prep.get("apply_url"):
                if prep["apply_url"] == row.get("apply_url"):
                    same["apply_url"] = "apply_url"
                else:
                    row["prep_apply_url"] = prep["apply_url"]
                    same["apply_url"] = "prep_apply_url"
            needs_key = "needs" if prep.get("needs") else next(
                (k for k, v in prep.items() if k.startswith("needs_") and isinstance(v, list)), "")
            if needs_key and prep[needs_key]:
                same[needs_key] = "needs"
        for key in same:
            del prep[key]
        for name, value in (("same_as_row", same), ("own", own), ("added", added)):
            if value:
                meta[name] = value
    if meta:
        detail[META] = meta
    return row, detail


def join_job(row, detail):
    """The merged job: the row with its detail put back (the inverse of split_job); keeps the "details" key."""
    job = dict(row)
    meta = detail.get(META, {})
    prep = copy.deepcopy(detail["prep"]) if "prep" in detail else None
    for key, source in meta.get("same_as_row", {}).items():
        prep[key] = copy.deepcopy(row[source])
    if "prep_apply_url" in meta.get("same_as_row", {}).values():
        job.pop("prep_apply_url", None)
    for field in meta.get("added", []):
        job.pop(field, None)
    job.update(copy.deepcopy(meta.get("own", {})))
    job.update({k: copy.deepcopy(v) for k, v in detail.items() if k not in (META, "prep")})
    if prep is not None:
        job["prep"] = prep
    return job


def split_company(company, rel):
    """(summary row, detail) of a company: ties*, hits, not_counted and checks move; its jobs stay in the row."""
    detail = {k: copy.deepcopy(v) for k, v in company.items() if _company_detail_key(k)}
    row = {k: v for k, v in company.items() if not _company_detail_key(k)}
    row[DETAILS] = rel
    return row, detail


def join_company(row, detail):
    return dict(row, **copy.deepcopy(detail))


DETAIL_PATH = re.compile(rf"^{DETAILS}/(jobs|companies)/[A-Za-z0-9._-]+\.json$")


def detail_file(tracker_path, row):
    """The absolute path of a row's detail file, "" when the row has none. Only a path split_tracker writes is
    accepted, so a "details" value set by hand never reads or writes another file."""
    rel = row.get(DETAILS)
    if not rel:
        return ""
    if not DETAIL_PATH.match(rel):
        raise SystemExit(f"not a detail file path: {rel!r}")
    return os.path.normpath(os.path.join(os.path.dirname(tracker_path), rel))


def read_detail(tracker_path, row):
    """The detail of a job or company row: {} when the row has no "details" key (unsplit tracker, flat rows)."""
    path = detail_file(tracker_path, row)
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"the row names {row[DETAILS]}, which does not exist beside {tracker_path}")


def write_json(path, data, indent=2):
    """tmp plus os.replace, like every write of the tracker."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    os.replace(path + ".tmp", path)


def write_detail(path, detail):
    """Write a detail file only when its content changed."""
    try:
        with open(path, encoding="utf-8") as f:
            if json.load(f) == detail:
                return
    except (FileNotFoundError, ValueError):
        pass
    write_json(path, detail, 1)


def expand_row(tracker_path, row):
    return join_job(row, read_detail(tracker_path, row)) if row.get(DETAILS) else row


def expand_company(tracker_path, company):
    return join_company(company, read_detail(tracker_path, company)) if company.get(DETAILS) else company


def collapse_row(tracker_path, row, full, company_shape):
    """Write a changed merged job back, in place: its detail file and its summary row. A row without a "details" key
    keeps everything inline (the caller changed it in place)."""
    if not row.get(DETAILS):
        return
    new_row, detail = split_job(full, row[DETAILS], company_shape)
    write_detail(detail_file(tracker_path, row), detail)
    row.clear()
    row.update(new_row)


def collapse_company(tracker_path, row, full):
    if not row.get(DETAILS):
        return
    new_row, detail = split_company(full, row[DETAILS])
    write_detail(detail_file(tracker_path, row), detail)
    row.clear()
    row.update(new_row)


def expand(tracker, path):
    """Every row merged with its detail, in place: the tracker as before the split, plus the "details" keys."""
    if is_company_shape(tracker):
        tracker["companies"] = [dict(expand_company(path, c), jobs=[expand_row(path, j) for j in c.get("jobs", [])])
                                for c in tracker["companies"]]
    elif "jobs" in tracker:
        tracker["jobs"] = [expand_row(path, j) for j in tracker["jobs"]]
    return tracker


def collapse(tracker, path):
    """The summary tracker of a merged one: rows with a "details" key go back to summary rows, their detail files
    rewritten where they changed. Returns a new tracker; the argument is left as it was."""
    shape = is_company_shape(tracker)

    def job_row(j):
        if not j.get(DETAILS):
            return j
        row, detail = split_job(j, j[DETAILS], shape)
        write_detail(detail_file(path, j), detail)
        return row
    out = {k: v for k, v in tracker.items() if k not in ("companies", "jobs")}
    if shape:
        out["companies"] = []
        for c in tracker["companies"]:
            row = dict(c, jobs=[job_row(j) for j in c.get("jobs", [])])
            if c.get(DETAILS):
                row, detail = split_company(row, c[DETAILS])
                write_detail(detail_file(path, c), detail)
            out["companies"].append(row)
    elif "jobs" in tracker:
        out["jobs"] = [job_row(j) for j in tracker["jobs"]]
    return out


WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def _file_name(text, used):
    """A file-safe name, unique ignoring case (Windows folders do not tell "A1" from "a1")."""
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-.")[:60].strip("-.") or "x"  # cut, then strip: no trailing "."
    if base.split(".")[0].upper() in WINDOWS_RESERVED:  # a folder "NUL" cannot be written on Windows
        base += "-x"
    name = base
    n = 0
    while name.lower() in used:  # the same text twice gives the same hash: count on until the name is free
        name = f"{base}-{hashlib.sha1((text + (f'#{n}' if n else '')).encode('utf-8')).hexdigest()[:6]}"
        n += 1
    used.add(name.lower())
    return name


file_name = _file_name  # the one safe-name helper; employerlib names an employer's folder with it


def split_tracker(tracker, taken=()):
    """(summary tracker, {relative path: detail}) for every row without a "details" key and with something to move.
    taken: relative paths already in use, so names stay unique."""
    shape = is_company_shape(tracker)
    used = {kind: {os.path.basename(p)[:-5].lower() for p in taken if p.startswith(f"{DETAILS}/{kind}/")}
            for kind in ("jobs", "companies")}
    files = {}

    def job_row(j):
        if j.get(DETAILS) or not any(k in j for k in JOB_DETAIL_KEYS):
            return j
        rel = f"{DETAILS}/jobs/{_file_name(str(j.get('id', 'job')), used['jobs'])}.json"
        row, detail = split_job(j, rel, shape)
        files[rel] = detail
        return row
    out = {k: v for k, v in tracker.items() if k not in ("companies", "jobs")}
    if shape:
        out["companies"] = []
        for c in tracker["companies"]:
            row = dict(c, jobs=[job_row(j) for j in c.get("jobs", [])])
            if not c.get(DETAILS) and any(_company_detail_key(k) for k in c):
                rel = f"{DETAILS}/companies/{_file_name(str(c.get('name', 'company')), used['companies'])}.json"
                row, detail = split_company(row, rel)
                files[rel] = detail
            out["companies"].append(row)
    elif "jobs" in tracker:
        out["jobs"] = [job_row(j) for j in tracker["jobs"]]
    return out, files
