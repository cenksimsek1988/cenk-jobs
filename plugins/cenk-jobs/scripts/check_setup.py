"""Check that a person's job-search setup is healthy: the env file, folders, master record, CV versions, tracker.

Usage: python -I check_setup.py [--env] [<job-search.env or main folder>]
       python -I check_setup.py --needs [--env] [...]    the programs, connectors, sign-ins and answers the next run
                                                         waits on, one line each (RULES.md, "Every run")
       (default: $JOB_SEARCH_ENV, else the job-search.env above the current folder; --env is optional, so the
       check runs the same way as every other script)
Prints one line per check (OK / WARN / FAIL) and exits 1 if anything FAILs. It changes nothing.
Logins and connectors (Gmail, Google Calendar, Google Drive, Claude in Chrome, job sites) cannot be seen from a
script: every run checks those with its own tools (RULES.md, "Every run").
"""
import importlib.util
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jsenv  # noqa: E402  (jsenv.py sits next to this script)
from trackerlib import flat_jobs, login_of, waits_on_person  # noqa: E402

given = [a for a in sys.argv[1:] if a not in ("--env", "--needs")]
env = jsenv.load(given[0] if given else None, __file__)


def needs():
    """Programs, logins, connectors and answers a run waits on, from this computer and the records as last seen."""
    unread = []

    def records(key, inner):
        try:
            with open(env.path(key), encoding="utf-8") as f:
                return json.load(f).get(inner, [])
        except (FileNotFoundError, SystemExit, ValueError):
            unread.append(key)
            return []
    logins = {r["id"]: r for r in records("LOGINS", "logins")}
    fine = ("connected", "signed-in", "excluded")
    lines = [f"install {what}: {detail}" for level, what, detail in programs() if level != "OK"]
    lines += [f"connector {r.get('name') or r['id']}: {r.get('status')}" + (f"; {r['fix']}" if r.get("fix") else "")
              for r in logins.values() if r.get("kind") == "connector" and r.get("status") not in fine]
    try:
        with open(env.path("TRACKER"), encoding="utf-8") as f:
            jobs = flat_jobs(json.load(f))
    except (FileNotFoundError, SystemExit, ValueError):
        unread.append("TRACKER")
        jobs = []
    by_login, waiting = {}, {}
    for job in jobs:
        status = job.get("status") or ""
        if status == "to-apply":
            by_login.setdefault(login_of(job), []).append(job)
        elif waits_on_person(status):
            waiting[status] = waiting.get(status, 0) + 1
    for login, planned in sorted(by_login.items()):
        if logins.get(login, {}).get("status") not in fine:
            lines.append(f"sign in to {login}: {len(planned)} planned, first {planned[0].get('company')}, {planned[0].get('title')}")
    lines += [f"{n} job(s) wait: {status}" for status, n in sorted(waiting.items())]
    questions = records("QUESTIONS", "questions")
    open_questions = [q for q in (questions.values() if isinstance(questions, dict) else questions) if q.get("status") == "open"]
    if open_questions:
        lines.append(f"{len(open_questions)} open question(s) on the Questions page")
    lines += [f"cannot read {key}: check it in job-search.env" for key in unread]
    print("\n".join(lines) if lines else "nothing needed from the person")


def programs():
    """(level, what, detail) for each program the job search uses."""
    chrome = env.get("CHROME")
    chrome = chrome if chrome and os.path.exists(chrome) else (
        next((c for c in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                          r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                          "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome") if os.path.exists(c)), None)
        or shutil.which("google-chrome") or shutil.which("chrome"))
    drive = next((p for p in (r"C:\Program Files\Google\Drive File Stream", "/Applications/Google Drive.app") if os.path.exists(p)), None)
    pypdf = importlib.util.find_spec("pypdf")
    poppler = shutil.which("pdftoppm")
    return [("OK" if chrome else "FAIL", "Google Chrome (prints CVs and letters to PDF, runs Claude in Chrome)",
             chrome or "not found; install Chrome or set CHROME in job-search.env"),
            ("OK" if drive else "WARN", "Google Drive for desktop (keeps the main folder in Drive and on this computer)",
             drive or "not found; install it, or keep the main folder somewhere that is backed up"),
            ("OK" if pypdf else "WARN", "pypdf (reads PDFs as text: old CVs, documents, each CV built)",
             os.path.dirname(pypdf.origin) if pypdf else "not found; python -I -m pip install pypdf (setup, step 1)"),
            ("OK" if poppler else "WARN", "Poppler pdftoppm (lets Claude see PDF pages as images)",
             poppler or "not found; install Poppler (setup, step 1), then start a new session")]


if "--needs" in sys.argv:
    needs()
    sys.exit(0)
results = []
REQUIRED_DIRS = ("RECORDS_DIR", "CVS_DIR", "CV_VERSIONS_DIR", "CERTIFICATES_DIR", "APPLICATIONS_DIR", "LETTERS_DIR",
                 "LETTER_BODIES_DIR")
OPTIONAL_DIRS = ("DOCUMENTS_INBOX_DIR", "DIPLOMAS_DIR", "PORTFOLIO_DIR")
REQUIRED_KEYS = ("PERSON_NAME", "NAME_ON_CV", "CONTACT_LINE", "MASTER_RECORD", "TRACKER", "PIPELINE") + REQUIRED_DIRS


def report(level, what, detail=""):
    results.append(level)
    print(f"{level:4}  {what}" + (f" - {detail}" if detail else ""))


def load_json(path, what):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        report("OK", what, os.path.basename(path))
        return data
    except FileNotFoundError:
        report("FAIL", what, f"missing: {path}")
    except json.JSONDecodeError as e:
        report("FAIL", what, f"not valid JSON: {e}")
    return None


print(f"Env file: {env.file}\nMain folder: {env.home}\n")
missing_keys = [k for k in REQUIRED_KEYS if not env.get(k)]
report("FAIL" if missing_keys else "OK", "job-search.env has every required value",
       "empty or missing: " + ", ".join(missing_keys) if missing_keys else "")
if not os.path.isdir(env.home):
    report("FAIL", "Main folder (JOB_SEARCH_HOME)", f"missing: {env.home}")
    sys.exit(1)

report("OK" if sys.version_info >= (3, 10) else "FAIL", "Python 3.10 or newer", sys.version.split()[0])
for level, what, detail in programs():
    report(level, what, detail)

for key in REQUIRED_DIRS + OPTIONAL_DIRS:
    if env.get(key):
        path = env.path(key)
        ok = os.path.isdir(path)
        report("OK" if ok else ("WARN" if key in OPTIONAL_DIRS else "FAIL"), key, path if ok else f"missing: {path}")
for stage in ("pending", "approved", "rejected", "closed", "declined", "not-applied"):
    path = env.path("APPLICATIONS_DIR", stage)
    report("OK" if os.path.isdir(path) else "FAIL", f"applications/{stage}", "" if os.path.isdir(path) else f"missing: {path}")
# Optional keys for older records: when set, what they name must exist (build_app_folders.py stops otherwise).
if env.get("SENT_CVS_DIR"):
    path = env.path("SENT_CVS_DIR")
    report("OK" if os.path.isdir(path) else "FAIL", "SENT_CVS_DIR (CVs sent before the current ones)", path)
for part in (env.get("SENT_CVS_BEFORE_DIRS") or "").split(";"):
    if part.strip():
        path = os.path.normpath(part if os.path.isabs(part) else os.path.join(env.home, part.strip()))
        report("OK" if os.path.isdir(path) else "FAIL", "SENT_CVS_BEFORE_DIRS entry", path)
if env.get("REDACT_FILE"):
    path = env.path("REDACT_FILE")
    report("OK" if os.path.isfile(path) else "FAIL", "REDACT_FILE (private text kept out of the folders)",
           "found" if os.path.isfile(path) else f"missing: {path}")  # its path only: the file itself is private
if env.get("TRACKER_SETTINGS"):
    load_json(env.path("TRACKER_SETTINGS"), "Tracker settings (TRACKER_SETTINGS)")
if env.get("EMPLOYER_RULES"):
    load_json(env.path("EMPLOYER_RULES"), "Employer rules (EMPLOYER_RULES)")
else:
    report("WARN", "EMPLOYER_RULES", "not set: the plugin's defaults apply (every category: warn and ask)")
if env.get("USAGE_SHARING", "").lower() not in ("yes", "no"):
    report("WARN", "USAGE_SHARING", "not set: ask the person once whether usage reports may go to the developer")
master = load_json(env.path("MASTER_RECORD"), "Master record")
if master is not None:
    missing = [k for k in ("profile", "experience", "education") if not master.get(k)]
    report("WARN" if missing else "OK", "Master record has profile, experience, education",
           "still empty: " + ", ".join(missing) if missing else "")
    unfinished = [e for e in master.get("education", []) if isinstance(e, dict) and e.get("completed") is False]
    if unfinished:
        report("OK", "Unfinished degrees are marked", f"{len(unfinished)} marked completed=false")

if env.get("PHOTO"):
    report("OK" if os.path.exists(env.path("PHOTO")) else "WARN", "CV photo (optional)", env.path("PHOTO"))

vdir = env.path("CV_VERSIONS_DIR")
versions = sorted(n for n in os.listdir(vdir) if n.endswith(".json") and n[0].isdigit()) if os.path.isdir(vdir) else []
report("OK" if versions else "WARN", "CV versions", f"{len(versions)} found" if versions else "none yet")
spec = importlib.util.spec_from_file_location("build_cv", os.path.join(HERE, "build_cv.py"))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
for name in versions:
    data = load_json(os.path.join(vdir, name), f"CV version {name}")
    if data is None:
        continue
    pdf = env.path("CVS_DIR", builder.pdf_name(name, data.get("name", "")))
    if not os.path.exists(pdf):
        report("WARN", f"No PDF for {name}", "build it with build_cv.py")
    elif os.path.getmtime(pdf) < os.path.getmtime(os.path.join(vdir, name)):
        report("WARN", f"PDF older than {name}", "rebuild with build_cv.py")

load_json(env.path("TRACKER"), "Tracker")
load_json(env.path("PIPELINE"), "Hiring stages")
if env.get("LOGINS"):
    logins = load_json(env.path("LOGINS"), "Logins (connectors and job-site sign-ins)")
    if logins is not None:
        # Only logins something waits on: a connector, or a site with a job or a fix; an excluded employer never.
        waiting = [r["id"] for r in logins.get("logins", []) if r.get("status") not in ("connected", "signed-in", "excluded")
                   and (r.get("kind") == "connector" or r.get("jobs") or r.get("fix"))]
        report("WARN" if waiting else "OK", "Logins needing the person", ", ".join(waiting[:8]) + (" ..." if len(waiting) > 8 else ""))
# The dashboard always exists: a run that finds no link creates it (RULES.md, "Dashboard").
report("OK" if env.get("DASHBOARD_URL") else "FAIL", "Dashboard",
       env.get("DASHBOARD_URL") or "not created yet: create it now, then offer to pin it")

print(f"\n{results.count('OK')} OK, {results.count('WARN')} warnings, {results.count('FAIL')} failures")
sys.exit(1 if "FAIL" in results else 0)
