"""The applications tracker (TRACKER in job-search.env, e.g. apply/targets.json): add jobs, record outcomes.

python -I track.py add <id> "<company>" "<title>" <url> [key=value ...]   add a job (keys: location, work_mode, cv,
                                                                           letter, apply_url, salary_note, note)
python -I track.py set --file <file>                                      many outcomes in one write: lines
                                                                           "<id><TAB><status><TAB><note>"
python -I track.py set <id> <status> "<note>" [key=value ...]             record an outcome (and update fields, e.g.
                                                                           cv=<path> letter=<path>; letter=none:
                                                                           no letter was sent, the form had no field)
python -I track.py todo <id> add <kind> "<text>" [key=value ...]          add a to-do to a job (kinds: urgent, working,
                                                                           task, click, todo, waiting; keys: where=pc|phone,
                                                                           due=<date>, link, login, session=<session id>,
                                                                           since=<date>, today when left out)
python -I track.py todo <id> done <n>|all|kind=<kind>|session=<id>        remove to-dos: the one `list` numbers <n>, all,
                                                                           or every one of a kind or a session; when it
                                                                           removes nothing, it says where they are (the
                                                                           job's history, another row at the employer)
python -I track.py todo <id> list                                         the job's to-dos, numbered
python -I track.py wait <id> needs-person|needs-captcha|account-needed "<what>" [link=<url>] [login=<site>]
                                                                           a wait on the person, recorded where the
                                                                           dashboard shows it: the status, its waits_on
                                                                           {kind, login, since} and one to-do with its
                                                                           link (the job's own form when no link is
                                                                           given); account-needed: a sign-in to-do with
                                                                           the site. login= names the site; it is
                                                                           required when the records name none (a job
                                                                           board that only forwards). Example:
                                                                           login="Workday · Acme"
python -I track.py step <id> add name="<step>" date=<YYYY-MM-DD> [time=<HH:MM[-HH:MM]>] [due=<date>] [with=<who>]
                     [how=<how>] [link=<url>] [mail=<message id>] [proposed=yes]
                                                                           a hiring step into PIPELINE, numbered 1, 2,
                                                                           ... in the order added (date= or due= is
                                                                           needed; due alone: a task)
python -I track.py step <id> done|cancel <n> [<date>]                     step <n> done or cancelled on that day
                                                                           (today when left out)
python -I track.py step <id> set <n> key=value ...                        change step <n> (the keys of add;
                                                                           proposed=no once the person agreed)
python -I track.py outcome <id> rejected|closed|declined|withdrawn <date> [reason="<why>"] [mail=<message id>]
                     [why=ethics|relocation|pay|other] [category=<category>]
                                                                           a sent job's outcome into PIPELINE; withdrawn
                                                                           is stored as declined, with its why (other
                                                                           when left out)
python -I track.py show <id> [--full]                                     print one job's summary row and the path of
                                                                           its detail file; --full: the row with its
                                                                           detail merged in (prep, history, earlier)
python -I track.py brief <id> [<id> ...]                                  the filling settings (LETTERS, EMAILED_CODES,
                                                                           OPTIONAL_FIELDS), then a compact view of
                                                                           prepared jobs: links, CV,
                                                                           letter, answers, open points
python -I track.py reopen [--apply [--per-day N]]                        the fits skipped only by a setting's cut the
                                                                           person's settings no longer make (APPLY_FITS
                                                                           =high, LONG_SHOTS_PER_DAY=0), never sent;
                                                                           --apply sets them back to found (old fit
                                                                           result in the history row) for the next run;
                                                                           --per-day N: the newest N join the next run,
                                                                           N more each day after
python -I track.py list [<status>]                                        one line per job
python -I track.py summary                                                counts by status (and screening verdict)
python -I track.py sync <journal.jsonl> [...]                             merge screening and preparation results
                                                                           into the tracker, print the queue
python -I track.py split [--apply]                                        split the tracker: one summary row per job
                                                                           and company, the rest in details/jobs/<id>.json
                                                                           and details/companies/<name>.json beside it.
                                                                           A dry run prints the counts and bytes before
                                                                           and after; --apply backs the tracker up
                                                                           (<TRACKER>.before-split-<date>.json), writes the
                                                                           details, proves that every row merges back
                                                                           exactly and only then replaces the tracker
                                                                           (a mismatch changes nothing and exits 1)
A split tracker keeps working with every command: set and brief open only the details they need; sync opens them all.
Statuses: found, pending, to-apply, account-needed, needs-person, needs-captcha, submitted, skipped, excluded, failed,
closed (the posting closed before it was sent: 404, 410, "no longer available"), declined (the person chose not to
apply: ethics, relocation, pay, other), as listed in templates/schemas/tracker.schema.json; another status is refused
(records.py check names an older row's). skipped is Claude's screening verdict (the posting does not fit the rules).
A sent job's later outcome is its stage in PIPELINE (approved, rejected, closed, declined), not its status: PIPELINE
changes only by step and outcome. A step is known by its position and is never removed; a job whose entry has
same_as=<id> writes into that entry. step add makes a pending entry approved, and an ended one approved again with its
outcome kept in the entry's history; an outcome replaces an earlier one the same way.
A waiting status (account-needed, needs-person, needs-captcha) gets waits_on {kind, since}, with the site's login when
the records name it; a sent or ended job keeps it only in that history row, like its to-dos.
'submitted' also sets applied=<today> when the job was not submitted before. A note about to be replaced is saved in
the job's history first and every change is appended there with its date, so the tracker says what happened and
when. A change of status into submitted, excluded, closed, declined, skipped or failed drops the job's to-dos: they
were about getting it sent. They are printed and kept in that history row ("todo_dropped"). Example: `set J1
submitted "sent"` prints "dropped 2 to-dos: approve the letter; press Submit". A to-do names its session by id
(session=<id>), never by a title in its text: titles change. Both tracker shapes work: {jobs: [...]} and the older {companies: [{name, jobs: [...]}]}, where a job's note
is its "outcome". Add --env <job-search.env> anywhere to pick the env file.
Every write goes through recordlib.py: a file changed since this command read it is not written ("STALE: ... run
the command again", exit 3), and a value the command writes wrong is refused ("REFUSED: ...", exit 1).

sync also applies the person's employer-rule categories (EMPLOYER_RULES, see employer.py) to each employer's category
checks: an "exclude" category excludes it, a "discuss" category sets its verdict to "discuss" (its jobs are
prepared and sent like any other; the person decides only if the employer answers with a hiring step), and the
checks are written to EMPLOYER_CHECKS. An employer the run did not screen keeps its verdict, and its prepared jobs
are attached: only an excluded employer stops. A
second check against the person's own rules (own: excl-own:) adds own_level beside its finding, and the verdict uses it.
sync reads workflow journals (rows {type: started, agentId, label} and {type: result, agentId, result}); an agent's
label is "<kind prefix><company name>" (cut at 20 characters before 0.44.0). By default the kinds are the ones workflows/
screen-and-prepare.js writes (exclusion: excl-judge:, excl-verify:, excl-screen:, then excl-quick:, the cheap check; own: excl-own:; prep: prep-jobs:,
whose result may be the path of the JSON file the agent wrote, then prep-fit:, the fit check alone, used when no
file was written because no job fitted). The two are merged by job id: the fit check's fields, with the file's
over them (from 0.44.1 the file holds only the jobs to apply to). A prepared job whose review is still "due" is
held like an unread posting: no prep, "found", marked unreviewed, so the next run prepares it again; so is an apply
job the form step left out of its file, or every one when it wrote no readable file. An employer whose full check
completed (a clean screen, or a second check after it) gets "screened": <today>, which workflow_args.py --screen
reads.
Older runs, search-result files to merge and per-company decisions
come from the "sync" part of the TRACKER_SETTINGS file (see templates/tracker-settings-example.json).
"""
import ast
import collections
import copy
import datetime
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import choices  # noqa: E402
import employerlib as el  # noqa: E402
import jsenv  # noqa: E402
import recordlib  # noqa: E402
from trackerlib import (DETAILS, ENDED_STAGE, ENDED_STATUS, ISO_DATE, STATUSES, TODO_KINDS, collapse,  # noqa: E402
                        collapse_row,
                        companies, date_in, employer_link, entries, expand, expand_company, job_urls, login_of,
                        workday_host, expand_row, flat_jobs, is_company_shape, json_indent, load_settings, needs_of,
                        note_key, split_tracker, write_json)
from trackerlib import PAGES_BEHIND  # noqa: E402

args = sys.argv[1:]
env_arg = None
if "--env" in args:
    i = args.index("--env")
    env_arg = args[i + 1]
    del args[i:i + 2]
env = jsenv.load(env_arg, __file__)
PATH = env.path("TRACKER")
today = datetime.date.today().isoformat()


BASE = ""  # the tracker's fingerprint as this command read it (recordlib refuses a moved base)
WAIT_KIND = {"account-needed": "account", "needs-person": "person", "needs-captcha": "captcha"}


def load():
    global BASE
    data, BASE = recordlib.load(env, "tracker")
    if not BASE:
        sys.exit(f"no tracker at {PATH}")
    return data


def save(data, ids=()):
    global BASE
    BASE = recordlib.save(env, "tracker", data, BASE, "track.py", ids)


def ready():
    """STALE before the first detail file of a split row is written, when the tracker moved since it was read."""
    recordlib.check_base(env, "tracker", BASE)


def find(data, job_id):
    """The one row with this id; an id on two rows is refused, so a change never lands on the wrong one."""
    hits = [(company, job) for company, job in companies(data) if job["id"] == job_id]
    if len(hits) > 1:
        sys.exit(f"job {job_id} is on {len(hits)} rows ("
                 + "; ".join(f"{c.get('name', '') or j.get('company', '')}: {title_of(j)[:40]}" for c, j in hits)
                 + "): an id names one job; give one of them a new id in the tracker before changing it")
    if hits:
        return hits[0]
    sys.exit(f"no job {job_id} in {PATH}")


def title_of(job):
    return job.get("title") or (job.get("prep") or {}).get("title", "")


def fields(pairs):
    out = {}
    for pair in pairs:
        if "=" not in pair:
            sys.exit(f"expected key=value, got {pair!r}")
        key, value = pair.split("=", 1)
        out[NOTE if key == "note" else key] = value
    return out


TODO_KEYS = ("where", "due", "link", "login", "session", "since")


def todo_line(n, item):
    extra = [f"{k} {item[k]}" for k in ("since", "due", "where", "session", "login") if item.get(k)]
    return f"{n:2} {item.get('kind', 'todo'):8} {item.get('text', '')}" + (f"  [{', '.join(extra)}]" if extra else "")


def todo_command(row, action, rest):
    """Add, remove or list the to-dos of one job. They live in the job's summary row, so a split tracker needs no
    detail file here. Returns True when the row changed."""
    todo = row.get("todo") or []
    if action == "list":
        print("\n".join(todo_line(n, t) for n, t in enumerate(todo, 1)) or "no to-dos")
        return False
    if action == "add":
        if len(rest) < 2:
            sys.exit('todo <id> add <kind> "<text>" [key=value ...]')
        kind, text = rest[0], rest[1].strip()
        if kind not in TODO_KINDS:
            sys.exit(f"kind must be one of {', '.join(TODO_KINDS)}")
        if not text:
            sys.exit("a to-do needs its text")
        item = {"kind": kind, "text": text, "since": today}
        for pair in rest[2:]:
            key, eq, value = pair.partition("=")
            if not eq or key not in TODO_KEYS:
                sys.exit(f"expected one of {', '.join(k + '=' for k in TODO_KEYS)} got {pair!r}")
            if key in ("due", "since") and not ISO_DATE.fullmatch(value):
                sys.exit(f"{key} is a date, YYYY-MM-DD: got {value!r}")
            if key == "where" and value not in ("pc", "phone"):
                sys.exit("where is pc or phone")
            item[key] = value
        row["todo"] = todo + [item]
        print("added:", todo_line(len(todo) + 1, item))
        return True
    if action == "done":
        which = rest[0] if rest else ""
        key, eq, value = which.partition("=")
        if which == "all":
            gone = list(todo)
        elif which.isdigit() and 1 <= int(which) <= len(todo):
            gone = [todo[int(which) - 1]]
        elif eq and key in ("kind", "session"):
            # No kind, or an older "info", counts as todo (RULES/run.md).
            gone = [t for t in todo if (t.get(key) or ("todo" if key == "kind" else "")) == value
                    or (key == "kind" and value == "todo" and t.get("kind") == "info")]
        else:
            sys.exit(f"todo <id> done <n>|all|kind=<kind>|session=<id>: this job has {len(todo)} to-do(s)")
        left = [t for t in todo if not any(t is g for g in gone)]
        if left:
            row["todo"] = left
        else:
            row.pop("todo", None)
        print(f"removed {len(gone)} to-do(s)" + (": " + "; ".join(t.get("text", "") for t in gone) if gone else ""))
        return bool(gone)
    sys.exit("todo <id> add|done|list")


def add_job(data, company, job):
    if not is_company_shape(data):
        data["jobs"].append(dict(job, company=company))
        return
    home = next((c for c in data["companies"] if c.get("name", "").lower() == company.lower()), None)
    if home is None:
        home = {"name": company, "jobs": []}
        data["companies"].append(home)
    home.setdefault("jobs", []).append(job)


# --- sync ---------------------------------------------------------------------------------------------------------
def parse(value):
    # Results are JSON text, or a Python dict's text (some workflow runs wrote that), or already a dict.
    if not isinstance(value, str):
        return value
    for reader in (json.loads, ast.literal_eval):
        try:
            return reader(value)
        except (ValueError, SyntaxError):
            continue
    return value


def as_result(value):
    """A prep agent replies with the path of the JSON file it wrote instead of the JSON itself: a whole line, quoted
    or not, or an absolute path after a word; a Git Bash path counts as its Windows one. Example: "Wrote
    C:/run/acme-1.json", or "/c/run/acme-1.json"."""
    value = parse(value)
    if isinstance(value, str):
        for line in value.splitlines():
            line = line.strip().strip("\"'`").strip()
            # Every place a path may start, so "and/or C:/run/acme-1.json" still finds the file.
            found = [m.group(1) for m in re.finditer(r"(?=((?:[A-Za-z]:[\\/]|/).*?\.json))", line)]
            for path in (line, *found):
                for candidate in (path, re.sub(r"^/([A-Za-z])/", r"\1:/", path)):
                    if candidate.lower().endswith(".json") and os.path.isfile(candidate):
                        with open(candidate, encoding="utf-8") as f:
                            return json.load(f)
    return value


def results(journals):
    done = []
    for journal in journals:
        with open(journal, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
        labels = {r["agentId"]: r.get("label", "") for r in rows if r.get("type") == "started"}
        done += [(labels.get(r["agentId"], ""), as_result(r.get("result"))) for r in rows if r.get("type") == "result"]
    return done


def prep_of(done, names, name, preps):
    """The prepared jobs of one employer: the fit check's result (every job, a skip too) with the prepared-jobs file's
    fields over it, by job id. From 0.44.1 the file holds only the jobs to apply to, each with review; an older file
    holds every job, with the fit check's fields, and the same merge gives the same result.
    An apply job with no review is due when the same run had a form step (one after the fit check in the journal):
    the step left it out, wrote no readable file, or wrote no review. Sync holds it for the next run. A run with no
    form step (APPLY=list, or no job fitted) keeps the fit check's result, and an older file never holds a job."""
    file_prep = newest(done, names, name, ["prep-jobs:"])
    fit_kinds = [p for p in preps if p != "prep-jobs:"]
    fit_prep = newest(done, names, name, fit_kinds)
    if not fit_prep:
        return file_prep
    file_jobs = (file_prep or {}).get("jobs", [])
    jobs = {j.get("id"): j for j in fit_prep.get("jobs", [])}
    for j in file_jobs:
        jobs[j.get("id")] = {**jobs.get(j.get("id"), {}), **j}
    fit_at = last_at(done, name, fit_kinds)
    form_ran = fit_at >= 0 and any(label == "prep-jobs:" + name for label, _ in done[fit_at + 1:])
    older_file = any("requirements" in j or "score" in j or j.get("action") == "skip" for j in file_jobs)
    if form_ran and not older_file:
        jobs = {i: {**j, "review": "due"} if j.get("action") == "apply" and "review" not in j else j
                for i, j in jobs.items()}
    return {**fit_prep, **{k: v for k, v in (file_prep or {}).items() if k != "jobs"}, "jobs": list(jobs.values())}


def last_at(done, name, prefixes):
    """Where the newest result of these kinds for this whole name is in done (journals in the order given, then their
    own order), or -1. Example: a second check after the screen of the same run has the higher index."""
    return max((i for i, (label, value) in enumerate(done) if isinstance(value, dict)
                and any(label == p + name for p in prefixes)), default=-1)


def screen_clean(result, categories):
    """A screen that needs no second check: no exclusion, and every category of the person's rules checked clear."""
    checks = {k.get("category"): k.get("status") for k in result.get("checks", []) if isinstance(k, dict)}
    return result.get("verdict") != "exclude" and all(checks.get(c) == "clear" for c in categories)


def newest(done, names, name, prefixes):
    # A label carries the whole company name: an exact match first, the first prefix (newest run) first. A run before
    # 0.44.0 cut the name at 20 characters, so a 20-character label is then matched by prefix, unless it is another
    # employer's whole name (names: every employer in the tracker). Seen: "Acme" took the result of "Acme Defence".
    for exact in (True, False):
        for prefix in prefixes:
            found = [v for label, v in done if label.startswith(prefix) and isinstance(v, dict)
                     and (label[len(prefix):] == name if exact else
                          len(label) - len(prefix) == 20 and label[len(prefix):] not in names
                          and name.startswith(label[len(prefix):]))]
            if found:
                return found[-1]
    return None


def merge_found(data, files):
    # New jobs from search-result files ({companies: [{name, jobs}]}) join the tracker; a known company gets the new
    # jobs appended to its own list.
    known = {c["name"]: c for c in data["companies"]}
    for path, origin in files:
        path = path if os.path.isabs(path) else os.path.join(env.home, path)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            found = json.load(f).get("companies", [])
        for c in found:
            if c["name"] not in known:
                known[c["name"]] = {"name": c["name"], "origin": origin, "jobs": c["jobs"]}
                data["companies"].append(known[c["name"]])
            else:
                ids = {j["id"] for j in known[c["name"]]["jobs"]}
                known[c["name"]]["jobs"] += [j for j in c["jobs"] if j["id"] not in ids]


def ties_key(result):
    return next((k for k in result if k.startswith("ties")), "ties")


def sync(journals):
    rules = load_settings(env).get("sync", {})
    labels = rules.get("labels", {})
    # The plugin's labels (the ones workflows/screen-and-prepare.js gives its agents) always count, first: the judge's
    # verdict when the two checks disagreed, else the second check's, else the first's. A person's own lists only add
    # older labels after them. Seen: a settings file listing older prep labels hid every prep-fit: result.
    both = lambda kind, plugin: plugin + [x for x in labels.get(kind, []) if x not in plugin]  # noqa: E731
    screens = both("screen", [])
    refuters = both("refute", [])
    preps = both("prep", ["prep-jobs:", "prep-fit:"])
    exclusions = both("exclusion", ["excl-judge:", "excl-verify:", "excl-screen:", "excl-quick:"])
    owns = both("own", ["excl-own:"])  # the second check against the person's own rules (their notes)
    refute_also = set(rules.get("refute_incomplete", []))
    overrides = rules.get("verdict_overrides", {})
    exclude_overrides = rules.get("exclude_overrides", {})
    data = expand(load(), PATH)  # every detail merged: sync reads hits and ties and writes prep
    global NOTE
    NOTE = note_key(data)  # the dispatch below sets it only for the other commands
    if not is_company_shape(data):
        sys.exit("sync works on the {companies: [...]} tracker, where screening verdicts belong to companies")
    merge_found(data, [tuple(x) for x in rules.get("merge", [])])
    done = results(journals)
    names = {c["name"] for c in data["companies"]}
    categories = list(el.rules(env).get("categories") or {}) or list(el.CATEGORIES)
    for company in data["companies"]:
        name = company["name"]
        if name in exclude_overrides:
            company["verdict"] = "exclude"
            company["override"] = exclude_overrides[name]
            company["hits"] = [{"criterion": "override", "finding": exclude_overrides[name]}]
            continue
        if company.get("verdict") == "exclude" and not newest(done, names, name, screens[:1]):
            continue
        x = newest(done, names, name, exclusions)
        screen_at = last_at(done, name, ["excl-screen:"])
        second_at = last_at(done, name, ["excl-verify:", "excl-judge:"])
        if screen_at >= 0 and (second_at > screen_at or screen_clean(done[screen_at][1], categories)):
            # The full check is complete: a clean screen, or a second check after it (an older run's does not
            # count). A screen whose second check failed leaves no date, so the next --screen runs the check again.
            company["screened"] = today
        # {category: {own_level, why}}: the level under the person's own rules, beside the finding as found.
        own = {k["category"]: k for k in (newest(done, names, name, owns) or {}).get("checks", [])
               if k.get("category") and k.get("own_level") in el.OWN_LEVELS}
        if own and not x and env.get("EMPLOYER_CHECKS"):
            # A known employer whose second check alone ran: its findings are recorded already. Only a category whose
            # second check was due takes the result: an agent never sets a level where the person has no own rules.
            rule_set, recorded = el.rules(env), el.lookup(env, name)
            for cat, k in own.items():
                if not el.second_check_due(rule_set, cat, recorded.get(cat) or {}):
                    print(f"{name}: the second check of {cat} was not due: not recorded")
                    continue
                try:
                    el.set_own(env, name, cat, k["own_level"], k.get("why", ""))
                except SystemExit as problem:
                    print(f"{name}: the second check of {cat} is not recorded: {problem}")
            # A second check that did not land leaves the category due: never an allow.
            found = el.lookup(env, name)
            by_rules, reasons, _ = el.decide_due(env, name, found)
            # The records keep the verdict from the findings alone; the "discuss" of a due check only holds the jobs.
            el.record(env, name, verdict=el.decide(env, name, found)[0])
            company["verdict"] = by_rules
            if by_rules != "allow":
                company["rule_reasons"] = reasons
            if by_rules != "exclude":
                attach_prep(company, prep_of(done, names, name, preps))
            continue
        if x and x.get("checks"):
            # One result per category: the deciding check's, and for a category it left out the second check's, then
            # the first's (a judge returns only the categories in dispute).
            found = {}
            for kind in ("excl-screen:", "excl-verify:"):
                earlier = newest(done, names, name, [kind]) or {}
                found.update({k["category"]: k for k in earlier.get("checks", []) if k.get("category")})
            found.update({k["category"]: k for k in x["checks"] if k.get("category")})
            checks = {c: {f: k.get(f, "") for f in ("status", "level", "fact", "source_url")}
                      for c, k in found.items() if c in el.CATEGORIES}
            rule_set = el.rules(env)
            for cat, k in own.items():
                # Only a due category (flagged, with the person's notes) takes the second check's level.
                if cat in checks and el.second_check_due(rule_set, cat, checks[cat]):
                    checks[cat].update(el.own_fields(rule_set, cat, k["own_level"], k.get("why", "")))
            company["checks"] = checks
            by_rules, reasons, _ = el.decide_due(env, name, checks)
            saved = el.decide(env, name, checks)[0]  # never the "discuss" of a due second check (recheck_running)
            if env.get("EMPLOYER_CHECKS"):
                el.record(env, name, checks, verdict="exclude" if x.get("verdict") == "exclude" else saved)
            if x.get("verdict") != "exclude" and by_rules in ("exclude", "discuss"):
                # The person's category settings: "exclude" excludes; "discuss" goes on like a warning, and the
                # person decides only if the employer answers with a hiring step.
                company["verdict"] = by_rules
                company["rule_reasons"] = reasons
                company[ties_key(x)] = x.get(ties_key(x), [])
                if by_rules == "discuss":
                    attach_prep(company, prep_of(done, names, name, preps))
                continue
        if x and x.get("verdict") == "exclude":
            company["verdict"] = "exclude"
            company["hits"] = x.get("hits", [])
            continue
        s = newest(done, names, name, screens)
        if not s and not x:
            # Not screened in this run (the funnel screens only where it is needed): the verdict stays as recorded.
            if company.get("verdict") != "exclude":
                attach_prep(company, prep_of(done, names, name, preps))
            continue
        if not s:
            s = {"verdict": "allow", "hits": []}
        r = newest(done, names, name, refuters)
        verdict = s["verdict"]
        if verdict == "clear" or (verdict == "incomplete" and name in refute_also):
            verdict = r["verdict"] if r else "verifying"
        company["hits"] = s.get("hits", []) + (r.get("hits", []) if r else [])
        company["not_counted"] = s.get("not_counted", [])
        if name in overrides:
            verdict, why = overrides[name]
            company["override"] = why
        if x:
            # Every company without clear exclusion evidence is allowed; its weaker ties stay noted.
            company[ties_key(x)] = x.get(ties_key(x), [])
            verdict = "clear" if verdict == "clear" else "allow"
        company["verdict"] = verdict
        if verdict in ("clear", "allow"):
            attach_prep(company, prep_of(done, names, name, preps))
    ready()
    save(collapse(data, PATH))  # rows with a detail file go back to summary rows and their files
    queue = [(c["name"], j) for c in data["companies"] if c.get("verdict", "") in ("clear", "allow", "discuss", "")
             for j in c["jobs"] if "prep" in j and j["status"] == "pending"]
    # The best grades first; inside a grade a job without a scope gap before one with it (a staff, head or director
    # role after a lead or EM role: no positive reply from those in the 19 Nov analysis), then the newest.
    queue.sort(key=lambda q: str(q[1].get("date") or next((h.get("date") for h in q[1].get("history") or []
                                                            if h.get("date")), "")), reverse=True)
    queue.sort(key=lambda q: any(g.get("kind") == "scope" for g in q[1]["prep"].get("gaps") or []
                                 if isinstance(g, dict)))
    queue.sort(key=lambda q: {"high": 0, "normal": 1, "long-shot": 2, "weak": 3}.get(q[1]["prep"].get("grade"), 4))
    # Long-shots and weak fits: at most LONG_SHOTS_PER_DAY a day together, counting today's submitted ones; the rest
    # wait for a later day.
    room = long_shot_room(data)
    held = [q for q in queue if q[1]["prep"].get("grade") in LONG_SHOTS][room:]
    queue = [q for q in queue if q not in held]
    if held:
        print(f"long-shots and weak fits waiting for a later day (LONG_SHOTS_PER_DAY): {len(held)}")
    for name, j in queue:
        p = j["prep"]
        print(j["id"], "|", name, "|", j["title"][:55], "|", p.get("action"), "|", p.get("grade") or "-", "|", p.get("open"), "|",
              p.get("platform"), "|", "needs:" + str(len(needs_of(p))), "|", (p.get("apply_url") or "")[:100])
    counts = {}
    for c in data["companies"]:
        counts[c.get("verdict", "pending")] = counts.get(c.get("verdict", "pending"), 0) + 1
    print("verdicts:", counts, "| queue:", len(queue))


LONG_SHOTS = ("long-shot", "weak")  # the grades LONG_SHOTS_PER_DAY limits together (0.46.0: a weak fit is no skip)


def long_shot_room(data):
    """How many more long-shots and weak fits may go today: LONG_SHOTS_PER_DAY minus those submitted today."""
    cap = int(choices.value(env, "LONG_SHOTS_PER_DAY")[0] or 0)
    sent = sum(1 for _, j in entries(data) if j.get("status") == "submitted" and j.get("applied") == today
               and (j.get("grade") or (j.get("prep") or {}).get("grade")) in LONG_SHOTS)
    return max(cap - sent, 0)


def attach_prep(company, prep):
    """A prepared-jobs result's jobs into the company's jobs, by id, each graded from its score (choices.grade): a fit
    below the person's APPLY_FITS is a skip with the reason, as in the workflow. An unread posting gets no prep: it
    stays "found", marked "unread", so the next run's fit check reads it again with its saved text."""
    level, settings = choices.value(env, "APPLY_FITS")[0], choices.fit_settings(env)
    long_shots = int(choices.value(env, "LONG_SHOTS_PER_DAY")[0] or 0)
    for pj in (prep or {}).get("jobs", []):
        for job in company["jobs"]:
            if job["id"] == pj.get("id"):
                prep_job = choices.graded(pj, level, settings, long_shots)
                if prep_job.get("grade") == "unread" and job.get("status") == "found":
                    job["unread"] = today
                    continue
                if prep_job.get("review") == "due" and prep_job.get("action") == "apply":
                    # The review step failed or was cut short: an unchecked letter or answer is never sent. A job not
                    # moved on yet stays "found" with no prep, so the next run prepares it again.
                    print(f"{job['id']}: not reviewed: held for the next run")
                    if job.get("status") == "found":
                        job["unreviewed"] = today
                    continue
                job.pop("unread", None)
                job.pop("unreviewed", None)
                job["prep"] = prep_job
                if prep_job.get("grade"):
                    job["grade"] = prep_job["grade"]  # on the row, so a split tracker still counts long-shots
                # Only a job no one has moved on yet ("found") takes the fit's decision as its status.
                if job.get("status") == "found":
                    skip = job["prep"].get("action") == "skip"
                    status = "skipped" if skip else "pending"
                    if job["status"] != status:
                        why = "fit: " + (job["prep"].get("reason") or "skip") if skip else "fit: apply"
                        job.setdefault("history", []).append({"date": today, "status": status, NOTE: why})
                        job["status"], job[NOTE] = status, why


# --- split ---------------------------------------------------------------------------------------------------------
def rows_of(tracker):
    """[(label, row without jobs and without "details")]: a company by its position, a job by its id."""
    out = []
    for n, c in enumerate(tracker.get("companies", []), 1):
        out.append((f"company #{n}", {k: v for k, v in c.items() if k not in ("jobs", DETAILS)}))
        out += [(f"job {j.get('id')}", {k: v for k, v in j.items() if k != DETAILS}) for j in c.get("jobs", [])]
    out += [(f"job {j.get('id')}", {k: v for k, v in j.items() if k != DETAILS}) for j in tracker.get("jobs", [])]
    return out


def split_tracker_files(data, apply):
    base = os.path.dirname(PATH)
    taken = [os.path.relpath(os.path.join(root, name), base).replace(os.sep, "/")
             for root, _, names in os.walk(os.path.join(base, DETAILS)) for name in names]
    summary, files = split_tracker(data, taken)
    indent = json_indent(PATH)
    size_before = os.path.getsize(PATH)
    with open(PATH, "rb") as fh:
        crlf = b"\r\n" in fh.read(4096)  # recordlib keeps the file's own line endings: CR LF when it has them

    def size_of(value, indent):
        text = json.dumps(value, ensure_ascii=False, indent=indent)
        return len(text.encode("utf-8")) + (text.count("\n") if crlf else 0)
    size_summary = size_of(summary, indent)
    size_details = sum(size_of(d, 1) for d in files.values())
    jobs_n = sum(1 for rel in files if rel.startswith(f"{DETAILS}/jobs/"))
    print(f"to split: {jobs_n} jobs and {len(files) - jobs_n} companies -> {len(files)} detail files")
    print(f"bytes: tracker {size_before} now; after: tracker {size_summary} + details {size_details}")
    if not files:
        print("nothing to split: every row with a detail is split already")
        return
    if not apply:
        print("dry run: nothing was changed; split --apply does it")
        return
    backup, n = f"{PATH}.before-split-{today}.json", 1
    while os.path.exists(backup):
        n += 1
        backup = f"{PATH}.before-split-{today}-{n}.json"
    ready()
    shutil.copy2(PATH, backup)
    for rel, detail in files.items():
        write_json(os.path.join(base, rel), detail, 1)
    # The proof: read every row back through the detail files just written and compare it with the original.
    was, now = rows_of(expand(copy.deepcopy(data), PATH)), rows_of(expand(copy.deepcopy(summary), PATH))
    bad = next((a[0] for a, b in zip(was, now) if a != b), None) if len(was) == len(now) else "the number of rows"
    if bad is None:
        keep = ("prep", "history", "earlier", DETAILS, "prep_apply_url")
        strip = lambda rows: [{k: v for k, v in r.items() if k not in keep} for r in rows]  # noqa: E731
        if strip(flat_jobs(summary)) != strip(flat_jobs(data)):
            bad = "flat_jobs"
    if bad is not None:
        sys.exit(f"the round trip differs at {bad}: the tracker was not changed (backup {backup}; "
                 f"the detail files written are unused)")
    save(summary)
    print(f"split: {len(files)} detail files written, round trip exact for {len(now)} rows; tracker is now "
          f"{os.path.getsize(PATH)} bytes (backup {backup})")


def site_of_job(company, job):
    """login_of with the employer's name, which a job row of the older {companies} shape does not hold. Seen: a
    Workday wait named "Workday · " with no employer."""
    return login_of(dict(job, company=job.get("company") or company.get("name", "")))


def waits_on(job, status, site=""):
    """A waiting job's waits_on: its kind, since today, and the site: the one given, else the one its earlier wait
    named (an older row's own "login" too)."""
    earlier = (job.get("waits_on") if isinstance(job.get("waits_on"), dict) else {}).get("login") or job.get("login")
    site = site or earlier or ""
    return dict({"kind": WAIT_KIND[status], "since": today}, **({"login": site} if site else {}))


# --- PIPELINE: a sent job's hiring steps and outcome ----------------------------------------------------------------
STEP_KEYS = ("name", "date", "time", "due", "with", "how", "link", "mail", "proposed")
OUTCOME_KINDS = ("rejected", "closed", "declined", "withdrawn")
OUTCOME_KEYS = ("stage", "date", "reason", "why", "category", "mail", "rejected")
PIPELINE_ABOUT = ("A sent job's hiring steps and outcome, by job id: written by track.py step and track.py outcome "
                  "only. A missing entry is pending.")


def pipeline_load():
    if not env.get("PIPELINE"):
        sys.exit("PIPELINE is not set in job-search.env")
    return recordlib.load(env, "pipeline", {"_about": PIPELINE_ABOUT})


def entry_of(pipeline, job_id):
    """(id, entry) where a job's steps and outcome live: its own entry, or the one its same_as names."""
    own = pipeline.get(job_id)
    if isinstance(own, dict) and own.get("same_as"):
        print(f"{job_id} shares the process of {own['same_as']} (same_as): written there")
        return own["same_as"], pipeline.setdefault(own["same_as"], {})
    return job_id, pipeline.setdefault(job_id, {})


def keep_outcome(entry):
    """An ended entry's outcome into its history, with until, before a step or a new outcome replaces it."""
    if entry.get("stage") not in ENDED_STAGE:
        return False
    entry.setdefault("history", []).append(dict({k: entry[k] for k in OUTCOME_KEYS if entry.get(k)}, until=today))
    for key in OUTCOME_KEYS:
        entry.pop(key, None)
    return True


def a_date(value, what):
    if not ISO_DATE.fullmatch(value or ""):
        sys.exit(f"{what} is a date, YYYY-MM-DD: got {value!r}")
    return value


def step_fields(pairs):
    """{key: value} of a step's key=value pairs, checked; proposed=yes gives True, proposed=no None (drop the mark)."""
    out = {}
    for pair in pairs:
        key, eq, value = pair.partition("=")
        value = value.strip()
        if not eq or key not in STEP_KEYS or not value:
            sys.exit(f"a step takes {', '.join(k + '=' for k in STEP_KEYS)} got {pair!r}")
        if key in ("date", "due"):
            a_date(value, key)
        if key == "time" and not re.fullmatch(r"\d{1,2}:\d{2}(-\d{1,2}:\d{2})?", value):
            sys.exit(f"time is HH:MM or HH:MM-HH:MM: got {value!r}")
        if key == "proposed" and value not in ("yes", "no"):
            sys.exit("proposed is yes (a time the employer offered, not agreed yet) or no (agreed)")
        out[key] = (True if value == "yes" else None) if key == "proposed" else value
    return out


def step_number(pid, steps, n, action):
    if not n.isdigit() or not 1 <= int(n) <= len(steps):
        sys.exit(f"step {action} <n>: {pid} has {len(steps)} step(s)"
                 + "".join(f"; {i} {s.get('name', '')}" for i, s in enumerate(steps, 1)))
    return int(n)


def step_command(pipeline, job, rest):
    pid, entry = entry_of(pipeline, job["id"])
    steps = entry.setdefault("steps", [])
    action = rest[0] if rest else ""
    if action == "add":
        step = {k: v for k, v in step_fields(rest[1:]).items() if v is not None}
        if not step.get("name") or not (step.get("date") or step.get("due")):
            sys.exit('step add needs name="<step>" and date=<YYYY-MM-DD> (or due=<date> for a task)')
        if keep_outcome(entry):
            print(f"{pid}: its process had ended; this step makes it approved again (the outcome is in its history)")
        if entry.get("stage", "pending") in ("", "pending"):
            entry["stage"] = "approved"
        steps.append(step)
        print(f"{pid} step {len(steps)}: {step['name']}, {step.get('date') or 'due ' + step['due']}")
        return pid
    if action in ("done", "cancel") and len(rest) >= 2:
        n = step_number(pid, steps, rest[1], action)
        when = a_date(rest[2], "the day") if len(rest) > 2 else today
        word = "done" if action == "done" else "cancelled"
        steps[n - 1][word] = when
        print(f"{pid} step {n} {steps[n - 1].get('name', '')}: {word} {when}")
        return pid
    if action == "set" and len(rest) >= 3:
        # A changed time or due date, a link, or proposed=no once the person agreed: the step keeps its number.
        n = step_number(pid, steps, rest[1], action)
        for key, value in step_fields(rest[2:]).items():
            if value is None:
                steps[n - 1].pop(key, None)
            else:
                steps[n - 1][key] = value
        print(f"{pid} step {n} {steps[n - 1].get('name', '')}: " + ", ".join(rest[2:]))
        return pid
    sys.exit('step <id> add name="<step>" date=<date> [key=value ...] | step <id> done|cancel <n> [<date>] | '
             'step <id> set <n> key=value ...')


def outcome_command(pipeline, job, rest):
    if len(rest) < 2 or rest[0] not in OUTCOME_KINDS:
        sys.exit(f"outcome <id> {'|'.join(OUTCOME_KINDS)} <date> [reason=...] [mail=...] [why=...] [category=...]")
    kind, when = rest[0], a_date(rest[1], "the outcome's date")
    allowed = ("reason", "mail") + (("why", "category") if kind in ("declined", "withdrawn") else ())
    extra = {}
    for pair in rest[2:]:
        key, eq, value = pair.partition("=")
        if not eq or key not in allowed or not value.strip():
            sys.exit(f"outcome {kind} takes {', '.join(k + '=' for k in allowed)} got {pair!r}")
        extra[key] = value.strip()
    if job.get("status") != "submitted" and job["id"] not in pipeline:
        sys.exit(f"{job['id']} is {job.get('status') or 'not sent'}: an outcome is for a sent job; before sending: "
                 f'track.py set {job["id"]} closed|declined "<why>"')
    if kind in ("declined", "withdrawn"):
        extra["why"] = extra.get("why") or "other"
    pid, entry = entry_of(pipeline, job["id"])
    keep_outcome(entry)
    # PIPELINE has no withdrawn stage: its readers show a declined entry with its why (ethics: "Withdrawn").
    entry.update(stage="declined" if kind == "withdrawn" else kind, date=when, **extra)
    print(f"{pid} -> {kind} {when}" + (f" ({extra['reason']})" if extra.get("reason") else ""))
    return pid


# --- the commands -------------------------------------------------------------------------------------------------
if not args or args[0] not in ("add", "set", "todo", "wait", "step", "outcome", "show", "brief", "list", "summary",
                               "sync", "split", "reopen"):
    sys.exit(__doc__)
cmd = args[0]


def set_one(data, job_id, status, note, more):
    """One job's new status and note, kept in its history; the caller saves."""
    if status not in STATUSES:
        sys.exit(f"status must be one of {', '.join(STATUSES)} (templates/schemas/tracker.schema.json)")
    company, row = find(data, job_id)
    job = expand_row(PATH, row)  # a split row: its detail merged in; written back below
    history = job.setdefault("history", [])
    old, old_status = job.get(NOTE, ""), job.get("status", "")
    if old and not any(h.get(NOTE) == old for h in history):
        # A note written before history was kept (or by another tool) is saved before it is replaced.
        history.append({"until": today, "status": old_status, NOTE: old})
    if old_status == "submitted" and not job.get("applied") and date_in(old):
        # An older job's sent date is only in its note: keep it, so its folder name stays when the note changes.
        job["applied"] = date_in(old)
    job.update(fields(more))
    job["status"] = status
    if status == "submitted" and old_status != "submitted" and not job.get("applied"):
        job["applied"] = today
    job[NOTE] = note or old
    change = {"date": today, "status": status, NOTE: note}
    if status in WAIT_KIND and status != old_status:
        # The wait the records and the dashboard read (track.py wait also names its site and its to-do).
        job["waits_on"] = waits_on(job, status, site_of_job(company, job) if status == "account-needed" else "")
    # A job that is sent or over needs none of the to-dos it had, nor its wait: they were about getting it sent.
    over = status != old_status and status in ("submitted",) + ENDED_STATUS
    dropped = job.pop("todo", None) if over else None
    if dropped:
        change["todo_dropped"] = dropped
    if over and job.get("waits_on"):
        change["waits_on"] = job.pop("waits_on")
    history.append(change)
    collapse_row(PATH, row, job, is_company_shape(data))
    print(job_id, company.get("name", ""), title_of(job)[:60], "->", status)
    if dropped:
        print(f"dropped {len(dropped)} to-do(s): " + "; ".join(t.get("text", "") for t in dropped))


if cmd == "sync":
    sync(args[1:])
    print(PAGES_BEHIND)
    sys.exit(0)
data = load()
if not is_company_shape(data):
    data.setdefault("jobs", [])
NOTE = note_key(data)
if cmd == "add":
    job_id, company, title, url = args[1:5]
    if any(j["id"] == job_id for _, j in entries(data)):
        sys.exit(f"{job_id} already exists")
    job = {"id": job_id, "title": title, "url": url, "status": "found", "applied": ""}
    job.update(fields(args[5:]))
    job["history"] = [{"date": today, "status": "found", NOTE: job.get(NOTE) or "added"}]
    add_job(data, company, job)
    save(data, [job_id])
    print("added", job_id, company, title)
    print(PAGES_BEHIND)
elif cmd == "set" and args[1:2] == ["--file"]:
    # Lines "<id><TAB><status><TAB><note>": every change in one tracker write (a Drive-synced file is slow).
    if len(args) < 3:
        sys.exit("set --file <file of id, status and note, tab-separated>")
    with open(args[2], encoding="utf-8") as fh:
        lines = [ln.rstrip("\r\n").split("\t", 2) for ln in fh if ln.strip()]
    bad = [n for n, ln in enumerate(lines, 1) if len(ln) < 2]
    if bad:
        sys.exit(f"set --file: line {bad[0]} needs id, status and note, tab-separated")
    ready()
    for ln in lines:
        set_one(data, ln[0], ln[1], ln[2] if len(ln) > 2 else "", [])
    save(data, [ln[0] for ln in lines])
    print(PAGES_BEHIND)
elif cmd == "set":
    if len(args) < 3:
        sys.exit('set <id> <status> "<note>" [key=value ...]')
    ready()
    set_one(data, args[1], args[2], args[3] if len(args) > 3 else "", args[4:])
    save(data, [args[1]])
    print(PAGES_BEHIND)
elif cmd == "wait":
    # A wait known only in a chat or a hand-off note is invisible on the dashboard: the status and the to-do go
    # together. Seen: 16 jobs waiting on sign-ins and answers stayed "found" with no to-do for two days.
    if len(args) < 4 or args[2] not in WAIT_KIND or not args[3].strip():
        sys.exit('wait <id> needs-person|needs-captcha|account-needed "<what it waits on>" [link=<url>] [login=<site>]')
    job_id, status, what = args[1], args[2], args[3].strip()
    extra = {}
    for pair in args[4:]:
        key, eq, value = pair.partition("=")
        if key not in ("link", "login") or not eq or not value.strip():
            sys.exit(f"wait takes only link=<url> and login=<site>: got {pair!r}")
        extra[key] = value.strip()
    company, row = find(data, job_id)
    job = expand_row(PATH, row)
    named = extra.get("login", "")
    if status == "account-needed" and not (named or site_of_job(company, job)):
        # A job board that only forwards to the employer's site is never the login (trackerlib.login_of).
        sys.exit(f'account-needed needs login=<site>: which site wants the account? Example: login="Workday · '
                 f'{company.get("name", "") or "Acme"}" or login="company site · {company.get("name", "") or "Acme"}"')
    history = job.setdefault("history", [])
    old = job.get(NOTE, "")
    if old and not any(h.get(NOTE) == old for h in history):
        history.append({"until": today, "status": job.get("status", ""), NOTE: old})
    history.append({"date": today, "status": status, NOTE: what})
    job.update(status=status, **{NOTE: what})
    login, host = named or site_of_job(company, job), workday_host(*job_urls(job))
    if host and env.get("LOGINS") and os.path.isfile(env.path("LOGINS")):
        # A Workday site's row is found by its tenant host, as logins.py sync does: one name per site.
        with open(env.path("LOGINS"), encoding="utf-8") as fh:
            login = next((r["id"] for r in json.load(fh).get("logins", []) if r.get("kind") == "site"
                          and r["id"].lower() != host and workday_host(r["id"], r.get("link") or "") == host), login)
    link = extra.get("link") or employer_link(job, login) or job.get("apply_url", "")
    # waits_on holds the site from now on (logins.py sync files the job under it); an older row's own login goes.
    job["waits_on"] = waits_on(job, status, login if status == "account-needed" else named)
    job.pop("login", None)
    ready()
    collapse_row(PATH, row, job, is_company_shape(data))
    kind = "click" if status == "account-needed" else "todo"
    same = next((t for t in row.get("todo") or [] if t.get("text") == what), None)
    if same:  # the same wait again, maybe now a sign-in: one to-do, with the new kind and site
        same["kind"] = kind
        same.pop("login", None)
        same.update({"login": login} if status == "account-needed" and login else {})
        same.update({"link": link} if link else {})
    else:
        todo_command(row, "add", [kind, what, *([f"link={link}"] if link else []),
                                  *([f"login={login}"] if status == "account-needed" and login else [])])
    save(data, [job_id])
    print(job_id, company.get("name", ""), title_of(job)[:60], "->", status)
    print(PAGES_BEHIND)
elif cmd == "todo":
    if len(args) < 3:
        sys.exit("todo <id> add|done|list")
    company, row = find(data, args[1])
    if todo_command(row, args[2], args[3:]):
        save(data, [args[1]])
        print(PAGES_BEHIND)
    elif args[2] == "done":
        # Nothing removed: say where the to-dos went, so nobody looks for them in the wrong place (lesson 21 Nov).
        drops = [h for h in expand_row(PATH, row).get("history") or [] if h.get("todo_dropped")]
        if drops and not row.get("todo"):
            print(f"{len(drops[-1]['todo_dropped'])} to-do(s) of {args[1]} were dropped into its history on "
                  f"{drops[-1].get('date', '')}, when it became {drops[-1].get('status', '')}")
        name = company.get("name", "") or row.get("company", "")
        others = [r["id"] for c, r in companies(data) if name and r is not row and r.get("todo")
                  and (c.get("name", "") or r.get("company", "")) == name]
        if others:
            print(f"to-dos at {name} are on: {', '.join(others)} (track.py todo <id> list)")
elif cmd in ("step", "outcome"):
    # PIPELINE changes only here: the tracker is read for the job, never written.
    if len(args) < 3:
        sys.exit(__doc__)
    company, job = find(data, args[1])
    pipeline, pipeline_base = pipeline_load()
    pid = (step_command if cmd == "step" else outcome_command)(pipeline, job, args[2:])
    recordlib.save(env, "pipeline", pipeline, pipeline_base, "track.py", [pid])
    print(PAGES_BEHIND)
elif cmd == "show":
    # Read only: an id on two rows shows both, so the person can see which one to give a new id (find refuses it).
    wanted = [a for a in args[1:] if a != "--full"][0]
    hits = [(c, j) for c, j in companies(data) if j["id"] == wanted] or [find(data, wanted)]
    for company, job in hits:
        row = {"company": company.get("name", "")}
        if is_company_shape(data):
            row["verdict"] = company.get("verdict")  # the company's screening verdict, which a job's own row lacks
            if company.get(DETAILS):
                row["company_details"] = company[DETAILS]
        row.update(expand_row(PATH, job) if "--full" in args else job)
        print(json.dumps(row, ensure_ascii=False, indent=1))
elif cmd == "split":
    split_tracker_files(data, "--apply" in args)
elif cmd == "brief":
    import profilelib
    wanted = args[1:]
    # The settings that change how a form is filled, once, so every applier's brief carries them.
    # The first name titles a tab that waits on the person: ">>> Jane: Acme type the code <<<".
    print("filling: " + " ".join(f"{k}={choices.value(env, k)[0]}" for k in ("LETTERS", "EMAILED_CODES",
                                                                              "OPTIONAL_FIELDS"))
          + f" first_name={profilelib.person(env)['first']}")
    for company, job in companies(data):
        if job["id"] not in wanted:
            continue
        job = expand_row(PATH, job)
        p = job.get("prep") or job
        print("==", job["id"], company.get("name", ""), "|", job.get("title"), "|", p.get("action"), "|",
              p.get("platform"))
        print("   url:", p.get("apply_url") or job.get("apply_url") or job.get("url"))
        cv = job.get("cv") or p.get("cv_pdf") or ""
        letter = job.get("letter") or p.get("letter_pdf") or ""
        print("   cv:", os.path.basename(cv.replace("\\", "/")), "| letter:", letter.replace("\\", "/"))
        salary = next((p[k] for k in ("salary_eur", "salary") if p.get(k) is not None), job.get("salary_note"))
        print("   salary (private):", salary, "| setup:",
              (p.get("setup") or job.get("setup") or "")[:160])
        for a in p.get("answers") or []:
            print("   Q:", a["question"][:95], "=>", a["answer"][:150])
        for n in needs_of(p):
            print("   NEED:", n[:230])
        print("   reason:", (p.get("reason") or job.get(NOTE) or "")[:260])
elif cmd == "reopen":
    # A fit skipped only by a setting's cut the person's settings no longer make (APPLY_FITS=high on a normal fit,
    # LONG_SHOTS_PER_DAY=0 on a long-shot or weak one), never sent: back to found with the old fit result in its
    # history row, so the next run's funnel checks and prepares it (collect_postings.py takes "reopened" rows).
    # A cut job posted again under a new link is already back in the tracker (collect_postings.py lets it in): the
    # newer row wins and the old one stays skipped, so one job never gets two fit checks; of two cut rows of one job,
    # only the newest comes back.
    import reposts  # noqa: E402
    cuts = [(c, row, choices.setting_cut(row.get(NOTE, ""), env)) for c, row in companies(data)
            if row.get("status") == "skipped" and not row.get("applied")]
    cuts = sorted([t for t in cuts if t[2]], key=lambda t: str(t[1].get("date") or ""), reverse=True)
    # The person's places now (env, then the search scope): a cut fit outside them stays skipped, as the funnel would
    # leave it out (seen 21 Nov: 60 of 64 outside a scope narrowed to remote and one city).
    import collect_postings as cp  # noqa: E402
    regions = cp.load_places(env)
    outside = [t for t in cuts if t[1].get("location") and not cp.place_ok(t[1]["location"], cp.PLACES, regions)]
    cuts = [t for t in cuts if t not in outside]

    def job_keys(c, row):
        return {(k, reposts.title_key(title_of(row))) for k in reposts.employer_keys(env, c.get("name", "")
                                                                                     or row.get("company", ""), {})}
    cut_ids = {row["id"] for _, row, _ in cuts}
    taken = {k: row["id"] for c, row in companies(data) if row["id"] not in cut_ids and row.get("status") != "closed"
             for k in job_keys(c, row)}
    kept, twins = [], 0
    for c, row, cut in cuts:
        keys = job_keys(c, row)
        if any(k in taken for k in keys):
            twins += 1
            continue
        taken.update({k: row["id"] for k in keys})
        kept.append((c, row, cut))
    cuts = kept
    for c, row, cut in cuts:
        print(f"{row['id']} | {c.get('name', '') or row.get('company', '')} | {title_of(row)[:60]} | {cut} no longer "
              "cuts it")
    if outside:
        print(f"{len(outside)} left skipped: outside the person's places now")
    if twins:
        print(f"{twins} left skipped: the same job is in the tracker under a newer row")
    if not cuts:
        print("nothing to reopen: no fit skip by a setting the person's settings no longer make")
    elif "--apply" not in args[1:]:
        print(f"{len(cuts)} to reopen; dry run: nothing was changed (reopen --apply"
              + (" --per-day " + args[args.index("--per-day") + 1] if "--per-day" in args[:-1] else "") + " does it)")
    else:
        # --per-day N: the newest N join the next run, the next N a day later, and so on (the "reopened" date is the
        # day a job joins the funnel). Example: 64 at 15 a day take 5 days.
        at = args.index("--per-day") if "--per-day" in args else -1
        raw = args[at + 1] if 0 <= at < len(args) - 1 else ("?" if at >= 0 else "")
        if raw and not (raw.isdigit() and int(raw) > 0):
            sys.exit(f"--per-day is a whole number above 0: got {raw!r}")
        per_day = int(raw) if raw else len(cuts)
        ready()
        start = datetime.date.today()
        for i, (c, row, cut) in enumerate(cuts):
            job = expand_row(PATH, row)
            change = {"date": today, "status": "found", NOTE: f"reopened: {cut} no longer cuts it"}
            if job.get("prep"):
                change["prep"] = job.pop("prep")
            job.pop("grade", None)
            job.setdefault("history", []).append(change)
            day = (start + datetime.timedelta(days=i // per_day)).isoformat()
            job.update({"status": "found", NOTE: change[NOTE], "reopened": day})
            collapse_row(PATH, row, job, is_company_shape(data))
        save(data, [row["id"] for _, row, _ in cuts])
        last = (start + datetime.timedelta(days=(len(cuts) - 1) // per_day)).isoformat()
        print(f"reopened {len(cuts)}: the next run takes {min(per_day, len(cuts))}"
              + (f", then {per_day} a day until {last}" if last != today else "")
              + "; each gets a fit check and, if it passes, a preparation")
        print(PAGES_BEHIND)
elif cmd == "list":
    for company, job in companies(data):
        if len(args) < 2 or job.get("status") == args[1]:
            print(f"{job['id']:8} {job.get('status', ''):15} {company.get('name', '')[:28]:28} {title_of(job)[:50]}")
elif any(c.get("verdict") for c, _ in companies(data)):
    # A tracker with screening verdicts: counts by verdict and status, then each company left out and why.
    counts = collections.Counter((c.get("verdict", "pending"), j.get("status", "")) for c, j in companies(data))
    for (verdict, status), n in sorted(counts.items()):
        print(verdict, status, n)
    for company in data.get("companies", []):
        if company.get("verdict") in ("exclude", "uncertain", "incomplete"):
            company = expand_company(PATH, company)  # a split row keeps its hits in the detail file
            why = company.get("override") or "; ".join(h["criterion"] + ": " + h["finding"][:110]
                                                       for h in company.get("hits", [])[:2])
            print("  ", company["verdict"].upper(), company["name"], "-", why)
else:
    counts = collections.Counter(j.get("status", "") for _, j in entries(data))
    for status in list(STATUSES) + sorted(set(counts) - set(STATUSES)):
        if counts[status]:
            print(f"{status:15} {counts[status]}")
    print(f"{'total':15} {sum(counts.values())}")
