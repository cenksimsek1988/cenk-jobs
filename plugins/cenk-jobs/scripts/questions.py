"""Questions for the person: what the applications need and the records do not answer, asked once on their Questions
page (QUESTIONS_PAGE: an artifact with a small database), and each answer written into the records.

python -I questions.py add fact "<question>" key=<answer key> [job=<id>] [personal=yes] [detail="..."] [placeholder="..."]
    a fact forms ask for; key: the form-answer key it becomes (example: notice_period). personal=yes: a private fact
    (health, family, identity), kept only in PERSONAL_RECORD. The same key again adds the job to the same question.
python -I questions.py add job "<question>" job=<id> [job=<id> ...] [detail="..."] [options="yes:Yes,no:No"]
    writing only the person can do for one application (a motivation answer, an essay); with options, buttons
    instead of a reply box: the chosen label becomes each job's form answer, and "decline" (options
    "apply:Apply,decline:Don't apply") makes the job declined
python -I questions.py add decision "<question>" employer="<name>" category=<category> [job=<id> ...] [detail="..."]
    [source=<url>]
    allow or exclude for an employer the build does not ask about by itself (example: one excluded through its
    owner, where the person's rule is unclear); allow clears its excluded jobs, exclude excludes the others
python -I questions.py list
    the open questions, one line each
python -I questions.py build <out dir> [--page <dir>]
    the page's files: <out dir>/questions/<id>.json for each open question and each one done in the last 7 days
    (with its note), and <out dir>/status/run.json (when Claude last handled the page, and what). First adds the
    "Allow, or exclude?" questions from the person's employer rules (an employer whose finding is "discuss", with a
    job not sent yet). --page <dir>: the page's questions as an ArtifactData list saved there (<dir>/questions/*.json):
    prints the ids to delete on the page (done more than 7 days ago, or dropped).
python -I questions.py record <answers dir>
    the page's answers, an ArtifactData list of "answers" saved there (<dir>/answers/<id>.json): a decision goes to
    employer.py decide (exclude: its jobs not sent yet become excluded), a fact into the master record's form_answers
    or PERSONAL_RECORD, a job answer into that job's prepared answers. Each handled question gets a note saying what
    happened (example: "Allowed: Acme is cleared by your decision; 1 job goes on.") and stays on the page as done.
    Prints the jobs that can go on and the answers to delete on the page. "discuss" (the middle button on every
    allow-or-exclude and yes-or-no question) records nothing: the question stays open with a note, and is printed
    under "discuss", for Claude to bring up with the person in the chat.
python -I questions.py answer <id> "<answer>"
    record one answer the person gave in the chat (example: after discussing it), the same way as record
python -I questions.py note <id> "<text>"
    a new note on a question, to show how far its job got (example: "Submitted on 8 Nov; confirmation in Gmail.")
Files: QUESTIONS (default apply/questions.json), PERSONAL_RECORD (default career-records/personal.json),
MASTER_RECORD, TRACKER, PIPELINE. Add --env <job-search.env> anywhere to pick the env file.
"""
import datetime
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jsenv  # noqa: E402
from trackerlib import collapse_row, expand_row, flat_jobs, is_company_shape, json_indent  # noqa: E402

DONE = ("submitted", "excluded", "skipped", "closed", "declined", "failed")
KEEP_DONE_DAYS = 7  # a handled question stays on the page this long, with its note
args = sys.argv[1:]
env_args = []
if "--env" in args:
    i = args.index("--env")
    env_args = args[i:i + 2]
    del args[i:i + 2]
env = jsenv.load(env_args[1] if env_args else None, __file__)
today = datetime.date.today().isoformat()
# UTC, in the page's own format (Date.toISOString), so the page can compare it with an answer's time.
now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def path_of(key, default):
    return env.path(key) if env.get(key) else os.path.join(env.home, default)


QUESTIONS = path_of("QUESTIONS", "apply/questions.json")
PERSONAL = path_of("PERSONAL_RECORD", "career-records/personal.json")


def load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    """Keep the file's own indent and line endings, so a rewrite changes only what changed."""
    crlf = os.path.exists(path) and b"\r\n" in open(path, "rb").read(4096)
    text = json.dumps(data, ensure_ascii=False, indent=json_indent(path) if os.path.exists(path) else 2) + "\n"
    with open(path + ".tmp", "wb") as f:
        f.write((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    os.replace(path + ".tmp", path)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "q"


def pairs(items):
    out = {}
    for item in items:
        if "=" not in item:
            sys.exit(f"expected key=value, got {item!r}")
        k, v = item.split("=", 1)
        out[k] = v
    return out


def raw_jobs(tracker):
    """The tracker's own job dicts (flat_jobs gives copies), in both tracker shapes."""
    if "jobs" in tracker:
        return {j["id"]: j for j in tracker["jobs"]}
    return {j["id"]: j for c in tracker.get("companies", []) for j in c.get("jobs", [])}


def labels(tracker):
    """{job id: "Company · title"}; flat_jobs gives each job its company in both tracker shapes."""
    return {j["id"]: f"{j.get('company', '')} · {j.get('title', '')}"[:80] for j in flat_jobs(tracker)}


def job_label(names, job_id):
    return names.get(job_id, job_id)


def asks(tracker, pipeline):
    """{company: {cat, label, level, fact, source, more, jobs}} for each employer the person's rules leave to them."""
    import employerlib as el
    rule_set = el.rules(env)
    out = {}
    for job in flat_jobs(tracker):
        company = job.get("company", "")
        if job.get("status") in DONE or job["id"] in pipeline:
            continue
        if company in out:
            out[company]["jobs"].append(job["id"])
            continue
        checks = el.lookup(env, company)
        if el.decide(env, company, checks, rule_set)[0] != "discuss":
            continue
        found = []
        for cat, k in checks.items():
            s = rule_set["categories"].get(cat)
            if k.get("status") != "flagged" or s is None:
                continue
            level = k.get("level", "direct")
            if (s.get("action", "discuss") if level == "direct" else s.get("indirect", "discuss")) == "discuss":
                found.append({"cat": cat, "label": s.get("label", cat), "level": level, "fact": k.get("fact", ""),
                              "source": k.get("source_url", "")})
        if found:
            out[company] = dict(found[0], more=found[1:], jobs=[job["id"]])
    return out


def page_doc(q, jobs):
    doc = {"kind": q["kind"], "text": q["text"], "detail": q.get("detail", ""), "source": q.get("source", ""),
           "employer": q.get("employer", ""), "role": q.get("role", ""),
           "jobs": [job_label(jobs, j) for j in q.get("jobs", [])][:8], "personal": bool(q.get("personal")),
           "category": q.get("category_label", ""), "placeholder": q.get("placeholder", ""),
           "open": q["status"] == "open", "done": q["status"] == "answered", "note": q.get("note", ""),
           "noted_at": q.get("noted_at", ""), "order": q.get("order", 0), "options": q.get("options", [])}
    return {k: v for k, v in doc.items() if v not in ("", [], None) or k in ("open", "personal", "done")}


def recent(q):
    """A question done within KEEP_DONE_DAYS: it stays on the page with its note."""
    if q["status"] != "answered" or not q.get("noted_at"):
        return False
    noted = datetime.datetime.fromisoformat(q["noted_at"].replace("Z", "+00:00"))
    return datetime.datetime.now(datetime.timezone.utc) - noted < datetime.timedelta(days=KEEP_DONE_DAYS)


def run(script, *argv):
    cmd = [sys.executable, "-I", os.path.join(HERE, script), *argv, *env_args]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if res.returncode:
        raise RuntimeError(f"{script} {' '.join(argv)} failed: {res.stderr.strip() or res.stdout.strip()}")
    return res.stdout.strip()


if not args or args[0] not in ("add", "list", "build", "record", "answer", "note"):
    sys.exit(__doc__)
data = load(QUESTIONS, {"_about": "Questions for the person, asked once on their Questions page (questions.py). "
                                  "status: open, answered (written into the records) or dropped.",
                        "questions": {}})
qs = data["questions"]

if args[0] == "add":
    if len(args) < 3 or args[1] not in ("fact", "job", "decision"):
        sys.exit(__doc__)
    kind, text = args[1], args[2]
    job_ids = [a.split("=", 1)[1] for a in args[3:] if a.startswith("job=")]
    opts = pairs(a for a in args[3:] if not a.startswith("job="))
    if job_ids:
        opts["job"] = job_ids[0]
    if kind == "fact" and not opts.get("key"):
        sys.exit("a fact needs key=<answer key>")
    if kind == "job" and not opts.get("job"):
        sys.exit("a job question needs job=<id>")
    if kind == "decision" and not (opts.get("employer") and opts.get("category")):
        sys.exit("a decision needs employer=<name> and category=<category>")
    if kind == "decision":
        import employerlib as el
        if opts["category"] not in el.categories(env):
            sys.exit(f"category must be one of {', '.join(el.categories(env))}")
    qid = {"fact": lambda: f"fact-{slug(opts['key'])}",
           "job": lambda: f"job-{slug(opts['job'])}-{slug(text)[:30].rstrip('-')}",
           "decision": lambda: f"ask-{slug(opts['employer'])}"}[kind]()
    q = qs.get(qid)
    if q and q["status"] == "open":
        q["jobs"] += [j for j in job_ids if j not in q["jobs"]]
    else:
        q = qs[qid] = {"kind": kind, "text": text, "status": "open", "asked": today, "jobs": list(job_ids)}
        for k in ("key", "detail", "placeholder", "source", "employer", "category"):
            if opts.get(k):
                q[k] = opts[k]
        if kind == "decision":
            import employerlib as el
            q["category_label"] = el.rules(env)["categories"].get(opts["category"], {}).get("label", opts["category"])
            q["manual"] = True  # asked by hand: the build keeps it until it is answered
        if opts.get("options"):
            q["options"] = [dict(zip(("value", "label"), o.split(":", 1))) for o in opts["options"].split(",")]
        if kind == "job":
            j = next((x for x in flat_jobs(load(env.path("TRACKER"), {})) if x["id"] == opts["job"]), {})
            q.update(employer=j.get("company", ""), role=j.get("title", ""))
        if opts.get("personal") in ("yes", "true", "1"):
            q["personal"] = True
    save(QUESTIONS, data)
    print(qid, "->", ", ".join(q["jobs"]) or "no job")

elif args[0] == "list":
    for qid, q in qs.items():
        if q["status"] == "open":
            print(f"{qid:44} {q['kind']:8} {q['text'][:70]}  [{', '.join(q.get('jobs', []))}]")

elif args[0] == "note":
    if len(args) < 3 or args[1] not in qs:
        sys.exit(__doc__ if len(args) < 3 else f"no question {args[1]!r}")
    qs[args[1]].update(note=args[2], noted_at=now)
    save(QUESTIONS, data)
    print(args[1], "-> note set; run build and write its file to the page")

elif args[0] == "build":
    if len(args) < 2:
        sys.exit(__doc__)
    out_dir, page_dir = args[1], None
    if "--page" in args:
        page_dir = args[args.index("--page") + 1]
    tracker = load(env.path("TRACKER"), {})
    pipeline = load(env.path("PIPELINE"), {}) if env.get("PIPELINE") else {}
    jobs = labels(tracker)
    asked = asks(tracker, pipeline)
    for company, a in asked.items():
        qid = f"ask-{slug(company)}"
        more = "".join(f" Also: {m['label']} ({m['level']}): {m['fact']}" for m in a["more"])
        q = qs.get(qid)
        if not q or q["status"] != "open":
            q = qs[qid] = {"kind": "decision", "status": "open", "asked": today}
        q.update(text=f"Allow {company}, or exclude?", employer=company, category=a["cat"],
                 category_label=a["label"], detail=f"{a['label']} ({a['level']}): {a['fact']}{more}",
                 source=a["source"], jobs=sorted(set(q.get("jobs", [])) | set(a["jobs"])))
    # A decision nobody needs any more (decided elsewhere, or its jobs went): dropped, with the date.
    for qid, q in qs.items():
        if q["kind"] == "decision" and q["status"] == "open" and not q.get("manual") and q.get("employer") not in asked:
            q.update(status="dropped", dropped=today)
    save(QUESTIONS, data)
    os.makedirs(os.path.join(out_dir, "questions"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "status"), exist_ok=True)
    shown, open_ids = [], []
    for n, (qid, q) in enumerate(sorted(((k, v) for k, v in qs.items() if v["status"] == "open" or recent(v)),
                                        key=lambda kv: (kv[1].get("category_label", ""), kv[1]["asked"], kv[0]))):
        q["order"] = n
        with open(os.path.join(out_dir, "questions", qid + ".json"), "w", encoding="utf-8") as f:
            json.dump(page_doc(q, jobs), f, ensure_ascii=False, indent=1)
        shown.append(qid)
        if q["status"] == "open":
            open_ids.append(qid)
    with open(os.path.join(out_dir, "status", "run.json"), "w", encoding="utf-8") as f:
        # The dashboard's link too, so the page links back to it.
        json.dump(dict(data.get("handled") or {"at": "", "summary": ""}, dashboard=env.get("DASHBOARD_URL") or ""), f,
                  ensure_ascii=False, indent=1)
    print(f"{len(open_ids)} open and {len(shown) - len(open_ids)} done questions -> {os.path.join(out_dir, 'questions')}")
    print("on the page:", " ".join(shown))
    if page_dir:
        on_page = [os.path.basename(p)[:-5] for p in glob.glob(os.path.join(page_dir, "questions", "*.json"))]
        print("delete on the page:", " ".join(sorted(set(on_page) - set(shown))) or "none")

else:  # record, answer
    if len(args) < (3 if args[0] == "answer" else 2):
        sys.exit(__doc__)
    if args[0] == "answer":
        given = [(args[1], args[2], "chat")]
    else:
        given = [(os.path.basename(f)[:-5], (load(f, {}) or {}).get("answer", ""), "Questions page")
                 for f in sorted(glob.glob(os.path.join(args[1], "answers", "*.json")))]
    tracker_path = env.path("TRACKER")
    tracker = load(tracker_path, {})
    jobs = raw_jobs(tracker)
    master = load(env.path("MASTER_RECORD"), {})
    personal = load(PERSONAL, {"_about": "Private facts the person gave for application forms (health, family, "
                                         "identity): used only in forms, never in a CV, letter or shared file.",
                               "facts": {}})
    changed = {"tracker": False, "master": False, "personal": False}
    go_on, delete, discuss = [], [], []
    names = labels(tracker)

    def titles(ids):
        return ", ".join(names.get(j, j) for j in ids) or "no job waiting"

    def flush():
        """Write what this run changed so far: before a script rewrites the tracker, before stopping, at the end."""
        if changed["tracker"]:
            save(tracker_path, tracker)
        if changed["master"]:
            save(env.path("MASTER_RECORD"), master)
        if changed["personal"]:
            os.makedirs(os.path.dirname(PERSONAL), exist_ok=True)
            save(PERSONAL, personal)
        save(QUESTIONS, data)
        changed.update(tracker=False, master=False, personal=False)

    def call(script, *argv):
        """Run employer.py or track.py, which rewrite the tracker: flush first, then read the tracker back."""
        global tracker, jobs
        flush()
        try:
            out = run(script, *argv)
        except RuntimeError as e:
            sys.exit(f"{e}. The answers before it are recorded; this one and the rest stay open.")
        tracker = load(tracker_path, {})
        jobs = raw_jobs(tracker)
        return out

    for qid, answer, source in given:
        q = qs.get(qid)
        answer = str(answer).strip()
        if not q or q["status"] != "open" or not answer:
            print(f"{qid}: skipped ({'no such open question' if not q or q['status'] != 'open' else 'empty answer'})")
            if q and q["status"] != "open":
                delete.append(qid)
            continue
        if answer == "discuss":
            q.setdefault("discuss", today)
            if not q.get("note", "").startswith("You chose Discuss"):
                q.update(note="You chose Discuss: Claude brings it up with you in your main session.", noted_at=now)
            discuss.append(f"{qid} ({q.get('employer') or ', '.join(q.get('jobs', []))}: {q['text']})")
            continue
        entry = {"answer": answer, "date": today, "source": source}
        if q["kind"] == "decision":
            if answer not in ("allow", "exclude"):
                print(f"{qid}: skipped (a decision is allow or exclude)")
                continue
            print(call("employer.py", "decide", q["employer"], answer, q["category"]))
            waiting = [j for j in q.get("jobs", []) if (jobs.get(j) or {}).get("status") not in DONE or
                       (answer == "allow" and (jobs.get(j) or {}).get("status") == "excluded")]
            note = (f"Allowed: {q['employer']} is cleared by your decision; going on: {titles(waiting)}."
                    if answer == "allow" else
                    f"Excluded: {q['employer']} is on your Excluded employers list now; "
                    + (f"not sent and excluded: {titles(waiting)}." if waiting else "its jobs were excluded already."))
            for job_id in q.get("jobs", []):
                status = (jobs.get(job_id) or {}).get("status")
                if answer == "exclude" and status not in DONE:
                    call("track.py", "set", job_id, "excluded",
                        f"employer excluded: your decision ({source}, {q.get('category_label', '')}), {today}")
                elif answer == "allow":
                    if status == "excluded":
                        call("track.py", "set", job_id, "pending",
                            f"employer cleared: your decision ({source}, {q.get('category_label', '')}), {today}")
                    go_on.append(job_id)
        elif q["kind"] == "fact":
            store, key = (personal["facts"], "personal") if q.get("personal") else \
                (master.setdefault("form_answers", {}), "master")
            old = store.get(q["key"])
            if old:
                entry["history"] = (old.get("history", []) if isinstance(old, dict) else []) + \
                    [{k: v for k, v in (old if isinstance(old, dict) else {"answer": old}).items() if k != "history"}]
            store[q["key"]] = dict(entry, question=q["text"])
            changed[key] = True
            go_on += q.get("jobs", [])
            note = ("Kept in your private record; used only in a form field that asks for it." if q.get("personal")
                    else f"Saved in your records: \"{answer[:80]}\". Forms take it from there; waiting on it: "
                         f"{titles(q.get('jobs', []))}.")
        elif q.get("options"):
            if answer not in [o["value"] for o in q["options"]]:
                print(f"{qid}: skipped (not one of the options)")
                continue
            label = next(o["label"] for o in q["options"] if o["value"] == answer)
            note = ("Not applying: the job is marked declined." if answer == "decline"
                    else f"{label}: the application goes on; Claude prepares and sends it, and notes here how far it got.")
            # A Yes/No field's choice is the form's answer too, kept with each job's prepared answers; an
            # apply-or-decline question is a decision about the job, not a form field.
            if not any(o["value"] == "decline" for o in q["options"]):
                for row in [jobs[j] for j in q.get("jobs", []) if j in jobs]:
                    job = expand_row(tracker_path, row)  # a split row: the detail with the prep is merged in
                    given = job.setdefault("prep", {}).setdefault("answers", [])
                    given[:] = [a for a in given if a.get("question") != q["text"]] + [dict(entry, answer=label, question=q["text"])]
                    collapse_row(tracker_path, row, job, is_company_shape(tracker))
                    changed["tracker"] = True
            for job_id in q.get("jobs", []):
                if answer == "decline" and (jobs.get(job_id) or {}).get("status") not in DONE:
                    call("track.py", "set", job_id, "declined", f"your answer ({source}): {q['text']} - no, {today}")
                elif answer != "decline":
                    go_on.append(job_id)
        else:
            row = jobs.get(q["jobs"][0]) if q.get("jobs") else None
            if not row:
                print(f"{qid}: skipped (job not in the tracker)")
                continue
            job = expand_row(tracker_path, row)  # a split row: the detail with the prep is merged in
            answers = job.setdefault("prep", {}).setdefault("answers", [])
            answers[:] = [a for a in answers if a.get("question") != q["text"]] + [dict(entry, question=q["text"])]
            collapse_row(tracker_path, row, job, is_company_shape(tracker))
            changed["tracker"] = True
            go_on += q["jobs"]
            note = "Saved with the application's answers; Claude puts it into the form."
        q.update(status="answered", answered=today, note=note, noted_at=now)
        delete.append(qid)
        print(f"{qid}: recorded - {note}")
    handled = len(delete)
    if handled or discuss:
        # Every open question waiting on a talk, not only this run's.
        talks = sum(1 for x in qs.values() if x["status"] == "open" and x.get("discuss"))
        data["handled"] = {"at": now, "summary": f"{handled} recorded" + (f", {talks} to discuss" if talks else "")}
    flush()
    # Only jobs still to send: one this round excluded (an "exclude" answer) does not go on.
    go_on = sorted({j for j in go_on if (jobs.get(j) or {}).get("status") not in DONE})
    print("go on with:", " ".join(go_on) or "none")
    print("delete these answers on the page (their questions stay as done; then run build):", " ".join(delete) or "none")
    print("discuss with the person:", "; ".join(discuss) or "none")
