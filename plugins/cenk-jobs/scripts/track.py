"""The applications tracker (TRACKER in job-search.env, e.g. apply/targets.json): add jobs, record outcomes.

python -I track.py add <id> "<company>" "<title>" <url> [key=value ...]   add a job (keys: location, work_mode, cv,
                                                                           letter, apply_url, salary_note, note)
python -I track.py set <id> <status> "<note>" [key=value ...]             record an outcome (and update fields, e.g.
                                                                           cv=<path> letter=<path>)
python -I track.py todo <id> add <kind> "<text>" [key=value ...]          add a to-do to a job (kinds: urgent, working,
                                                                           task, click, todo, waiting; keys: where=pc|phone,
                                                                           due=<date>, link, login, session=<session id>,
                                                                           since=<date>, today when left out)
python -I track.py todo <id> done <n>|all|kind=<kind>|session=<id>        remove to-dos: the one `list` numbers <n>, all,
                                                                           or every one of a kind or a session
python -I track.py todo <id> list                                         the job's to-dos, numbered
python -I track.py show <id> [--full]                                     print one job's summary row and the path of
                                                                           its detail file; --full: the row with its
                                                                           detail merged in (prep, history, earlier)
python -I track.py brief <id> [<id> ...]                                  compact view of prepared jobs: links, CV,
                                                                           letter, answers, open points
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
apply: ethics, relocation, pay, other); any other "needs-<word>" (an older tracker may say "needs-jane") and any status
the tracker already uses are accepted. skipped is Claude's screening verdict (the posting does not fit the rules).
A sent job's later outcome is its stage in PIPELINE (approved, rejected, closed, declined), not its status.
'submitted' also sets applied=<today> when the job was not submitted before. A note about to be replaced is saved in
the job's history first and every change is appended there with its date, so the tracker says what happened and
when. A change of status into submitted, excluded, closed, declined, skipped or failed drops the job's to-dos: they
were about getting it sent. They are printed and kept in that history row ("todo_dropped"). Example: `set J1
submitted "sent"` prints "dropped 2 to-dos: approve the letter; press Submit". A to-do names its session by id
(session=<id>), never by a title in its text: titles change. Both tracker shapes work: {jobs: [...]} and the older {companies: [{name, jobs: [...]}]}, where a job's note
is its "outcome". Add --env <job-search.env> anywhere to pick the env file.

sync also applies the person's employer-rule categories (EMPLOYER_RULES, see employer.py) to each employer's category
checks: an "exclude" category excludes it, a "discuss" category sets its verdict to "discuss" (nothing is
prepared until the person decides with employer.py decide), and the checks are written to EMPLOYER_CHECKS. A
second check against the person's own rules (own: excl-own:) adds own_level beside its finding, and the verdict uses it.
sync reads workflow journals (rows {type: started, agentId, label} and {type: result, agentId, result}); an agent's
label is "<kind prefix><company name, maybe cut short>". By default the kinds are the ones workflows/
screen-and-prepare.js writes (exclusion: excl-judge:, excl-verify:, excl-screen:; own: excl-own:; prep: prep-jobs:,
whose result may be the path of the JSON file the agent wrote). Older runs, search-result files to merge and per-company decisions
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
import employerlib as el  # noqa: E402
import jsenv  # noqa: E402
from trackerlib import (DETAILS, ENDED_STATUS, ISO_DATE, TODO_KINDS, collapse, collapse_row, companies,  # noqa: E402
                        date_in, entries, expand, expand_company,
                        expand_row, flat_jobs, is_company_shape, json_indent, load_settings, needs_of, note_key, split_tracker,
                        write_json)

STATUSES = ("found", "pending", "to-apply", "account-needed", "needs-person", "needs-captcha", "submitted", "skipped",
            "excluded", "failed", "closed", "declined")
args = sys.argv[1:]
env_arg = None
if "--env" in args:
    i = args.index("--env")
    env_arg = args[i + 1]
    del args[i:i + 2]
env = jsenv.load(env_arg, __file__)
PATH = env.path("TRACKER")
today = datetime.date.today().isoformat()


def load():
    with open(PATH, encoding="utf-8") as f:
        return json.load(f)


def save(data):
    indent = json_indent(PATH)
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    os.replace(tmp, PATH)


def find(data, job_id):
    for company, job in companies(data):
        if job["id"] == job_id:
            return company, job
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
    """A prep agent may reply with the path of the JSON file it wrote instead of the JSON itself."""
    value = parse(value)
    if isinstance(value, str):
        path = value.strip().strip('"').splitlines()[0].strip() if value.strip() else ""
        if path.lower().endswith(".json") and os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
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


def newest(done, name, prefixes):
    # Labels carry a cut-short company name; match it back by prefix, the first prefix (newest run) first.
    for prefix in prefixes:
        found = [v for label, v in done if label.startswith(prefix) and label[len(prefix):]
                 and name.startswith(label[len(prefix):]) and isinstance(v, dict)]
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
    screens = labels.get("screen", [])
    refuters = labels.get("refute", [])
    # The defaults are the labels workflows/screen-and-prepare.js gives its agents: the judge's verdict when the two
    # checks disagreed, else the second check's, else the first's.
    preps = labels.get("prep", ["prep-jobs:"])
    exclusions = labels.get("exclusion", ["excl-judge:", "excl-verify:", "excl-screen:"])
    owns = labels.get("own", ["excl-own:"])  # the second check against the person's own rules (their notes)
    refute_also = set(rules.get("refute_incomplete", []))
    overrides = rules.get("verdict_overrides", {})
    exclude_overrides = rules.get("exclude_overrides", {})
    data = expand(load(), PATH)  # every detail merged: sync reads hits and ties and writes prep
    if not is_company_shape(data):
        sys.exit("sync works on the {companies: [...]} tracker, where screening verdicts belong to companies")
    merge_found(data, [tuple(x) for x in rules.get("merge", [])])
    done = results(journals)
    for company in data["companies"]:
        name = company["name"]
        if name in exclude_overrides:
            company["verdict"] = "exclude"
            company["override"] = exclude_overrides[name]
            company["hits"] = [{"criterion": "override", "finding": exclude_overrides[name]}]
            continue
        if company.get("verdict") == "exclude" and not newest(done, name, screens[:1]):
            continue
        x = newest(done, name, exclusions)
        # {category: {own_level, why}}: the level under the person's own rules, beside the finding as found.
        own = {k["category"]: k for k in (newest(done, name, owns) or {}).get("checks", [])
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
            if by_rules == "allow":
                attach_prep(company, newest(done, name, preps))
            else:
                company["rule_reasons"] = reasons
            continue
        if x and x.get("checks"):
            # One result per category: the deciding check's, filled from the first check's for categories it left out.
            first = newest(done, name, ["excl-screen:"]) or {}
            found = {k["category"]: k for k in first.get("checks", []) if k.get("category")}
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
                # The person's category settings: "exclude" excludes, "discuss" waits for their decision (no preparing).
                company["verdict"] = by_rules
                company["rule_reasons"] = reasons
                company[ties_key(x)] = x.get(ties_key(x), [])
                continue
        if x and x.get("verdict") == "exclude":
            company["verdict"] = "exclude"
            company["hits"] = x.get("hits", [])
            continue
        s = newest(done, name, screens)
        if not s and not x:
            continue
        if not s:
            s = {"verdict": "allow", "hits": []}
        r = newest(done, name, refuters)
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
            attach_prep(company, newest(done, name, preps))
    save(collapse(data, PATH))  # rows with a detail file go back to summary rows and their files
    queue = [(c["name"], j) for c in data["companies"] if c.get("verdict") in ("clear", "allow")
             for j in c["jobs"] if "prep" in j and j["status"] == "pending"]
    for name, j in queue:
        p = j["prep"]
        print(j["id"], "|", name, "|", j["title"][:55], "|", p.get("action"), "|", p.get("open"), "|",
              p.get("platform"), "|", "needs:" + str(len(needs_of(p))), "|", (p.get("apply_url") or "")[:100])
    counts = {}
    for c in data["companies"]:
        counts[c.get("verdict", "pending")] = counts.get(c.get("verdict", "pending"), 0) + 1
    print("verdicts:", counts, "| queue:", len(queue))


def attach_prep(company, prep):
    """A prepared-jobs result's jobs into the company's jobs, by id."""
    for pj in (prep or {}).get("jobs", []):
        for job in company["jobs"]:
            if job["id"] == pj.get("id"):
                job["prep"] = pj


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
        crlf = b"\r\n" in fh.read(4096)  # save() writes text mode: on Windows every line ends in CR LF

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


# --- the commands -------------------------------------------------------------------------------------------------
if not args or args[0] not in ("add", "set", "todo", "show", "brief", "list", "summary", "sync", "split"):
    sys.exit(__doc__)
cmd = args[0]
if cmd == "sync":
    sync(args[1:])
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
    save(data)
    print("added", job_id, company, title)
elif cmd == "set":
    job_id, status, note = args[1], args[2], args[3] if len(args) > 3 else ""
    allowed = set(STATUSES) | {j.get("status") for _, j in entries(data) if j.get("status")}
    if status not in allowed and not re.fullmatch(r"needs-[a-z]+", status):
        sys.exit(f"status must be one of {', '.join(sorted(allowed))}, or needs-<word>")
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
    job.update(fields(args[4:]))
    job["status"] = status
    if status == "submitted" and old_status != "submitted" and not job.get("applied"):
        job["applied"] = today
    job[NOTE] = note or old
    change = {"date": today, "status": status, NOTE: note}
    # A job that is sent or over needs none of the to-dos it had: they were about getting it sent.
    dropped = job.pop("todo", None) if status != old_status and status in ("submitted",) + ENDED_STATUS else None
    if dropped:
        change["todo_dropped"] = dropped
    history.append(change)
    collapse_row(PATH, row, job, is_company_shape(data))
    save(data)
    print(job_id, company.get("name", ""), title_of(job)[:60], "->", status)
    if dropped:
        print(f"dropped {len(dropped)} to-do(s): " + "; ".join(t.get("text", "") for t in dropped))
elif cmd == "todo":
    if len(args) < 3:
        sys.exit("todo <id> add|done|list")
    company, row = find(data, args[1])
    if todo_command(row, args[2], args[3:]):
        save(data)
elif cmd == "show":
    company, job = find(data, [a for a in args[1:] if a != "--full"][0])
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
    wanted = args[1:]
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
