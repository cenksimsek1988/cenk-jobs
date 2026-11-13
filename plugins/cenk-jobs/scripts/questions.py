"""Questions for the person: what the applications need and the records do not answer, asked once on their Questions
page (QUESTIONS_PAGE: an artifact with a small database), and each answer written into the records.

python -I questions.py add fact "<question>" key=<answer key> [job=<id>] [personal=yes] [detail="..."] [placeholder="..."]
    a fact forms ask for; key: the form-answer key it becomes (example: notice_period), or a key in the person's
    profile (person.birth_date, person.phone). personal=yes: a private fact (health, family, identity), kept only in
    the profile's private.<key>. The same key again adds the job to the same question.
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
    (with its note), and <out dir>/status/run.json (at and summary: when an answer was last recorded, and what;
    checked: the time of this build; open: how many questions wait). First adds the
    "Allow, or exclude?" questions from the person's employer rules (an employer whose finding is "discuss", with a
    job not sent yet), and ends each job question whose jobs all ended: closed, with a note saying when, if one was
    sent; dropped if none was (excluded, declined, skipped, closed, failed). --page <dir>: the page's questions as an ArtifactData list saved there (<dir>/questions/*.json):
    prints the ids to delete on the page (done more than 7 days ago, or dropped).
python -I questions.py record <answers dir>
    the page's answers, an ArtifactData list of "answers" saved there (<dir>/answers/<id>.json). A typed answer (a
    fact, or a job question without options) is not recorded: it is printed under "read first", and its question
    stays open, for Claude to read it: a plain answer is recorded with answer (spelling and grammar fixed, meaning
    unchanged), a question or remark to Claude is replied to. A button answer is recorded at once: a decision goes to
    employer.py decide (exclude: its jobs not sent yet become excluded), a fact into the master record's form_answers
    or the profile, a job answer into that job's prepared answers. Each handled question gets a note saying what
    happened (example: "Allowed: Acme is cleared by your decision; 1 job goes on.") and stays on the page as done.
    Prints the jobs that can go on and the answers to delete on the page. "discuss" (the middle button on every
    allow-or-exclude and yes-or-no question) records nothing: the question stays open with a note, and is printed
    under "discuss", for Claude to bring up with the person in the chat.
python -I questions.py answer <id> "<answer>" [typed="<their words>"] [replace=yes]
    record one answer the person gave in the chat (example: after discussing it), the same way as record;
    typed=: a page answer Claude read and corrected (spelling, grammar): the record keeps their words and the page
    as its source. replace=yes: the profile holds another value and the person, shown both, chose this one.
    A profile answer is never written over another value (it is printed under "ask the person", the question stays
    open), nor without a profile (printed under "no profile"; the person chooses where it goes first).
python -I questions.py note <id> "<text>"
    a new note on a question, to show how far its job got (example: "Submitted on 8 Nov; confirmation in Gmail.")
Files: QUESTIONS (default apply/questions.json), MASTER_RECORD, TRACKER, PIPELINE, and the person's profile
(profilelib.py). Add --env <job-search.env> anywhere to pick the env file.
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
import profilelib as pl  # noqa: E402
from trackerlib import collapse_row, expand_row, flat_jobs, is_company_shape, json_indent  # noqa: E402

DONE = ("submitted", "excluded", "skipped", "closed", "declined", "failed")  # job statuses
HANDLED = ("answered", "closed")  # question statuses shown under Done
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
PROFILE_SECTIONS = ("person.", "private.")  # a fact key starting with one of these is a key in the profile


def profile_key(q):
    """The profile key a fact's answer goes to, or None for the master record's form_answers."""
    if q["key"].startswith(PROFILE_SECTIONS):
        return q["key"]
    return f"private.{q['key']}" if q.get("personal") else None


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
        checks = el.lookup(env, company, facts="flagged")
        if el.decide(env, company, checks, rule_set)[0] != "discuss":
            continue
        found = []
        for cat, k in checks.items():
            s = rule_set["categories"].get(cat)
            if k.get("status") != "flagged" or s is None:
                continue
            level = el.level_of(k)  # the second check's own level when there is one
            if level != "none" and el.act_for(s, level) == "discuss":
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
           "open": q["status"] == "open", "done": q["status"] in HANDLED, "note": q.get("note", ""),
           "noted_at": q.get("noted_at", ""), "order": q.get("order", 0), "options": q.get("options", [])}
    return {k: v for k, v in doc.items() if v not in ("", [], None) or k in ("open", "personal", "done")}


def recent(q):
    """A question done within KEEP_DONE_DAYS: it stays on the page with its note."""
    if q["status"] not in HANDLED or not q.get("noted_at"):
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
                                  "status: open, answered (written into the records), closed (its jobs were sent "
                                  "first) or dropped.",
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
    # A job question whose jobs all ended (the asks() rule: a DONE status or a PIPELINE row), so nobody answers it for
    # nothing: closed with a note when one was sent, else dropped, like a decision nobody needs.
    flat = flat_jobs(tracker)
    sent = {j["id"]: j.get("applied") or "" for j in flat if j.get("status") == "submitted" or j["id"] in pipeline}
    ended = set(sent) | {j["id"] for j in flat if j.get("status") in DONE}
    for qid, q in qs.items():
        if q["kind"] == "job" and q["status"] == "open" and q.get("jobs") and all(j in ended for j in q["jobs"]):
            if any(j in sent for j in q["jobs"]):
                when = max(sent.get(j, "") for j in q["jobs"]) or today
                q.update(status="closed", closed=today, noted_at=now,
                         note=f"Closed: the application was sent on {when}; nothing to answer now.")
            else:
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
        # at: when an answer was last recorded (the page's Send button counts the answers saved after it). checked:
        # this build, so a page nobody answered for two runs still says when Claude last looked, and open: how many
        # questions wait. The dashboard's link too, so the page links back to it.
        json.dump(dict(data.get("handled") or {"at": "", "summary": ""}, checked=now, open=len(open_ids),
                       dashboard=env.get("DASHBOARD_URL") or ""), f, ensure_ascii=False, indent=1)
    print(f"{len(open_ids)} open and {len(shown) - len(open_ids)} done questions -> {os.path.join(out_dir, 'questions')}")
    print("on the page:", " ".join(shown))
    if page_dir:
        on_page = [os.path.basename(p)[:-5] for p in glob.glob(os.path.join(page_dir, "questions", "*.json"))]
        print("delete on the page:", " ".join(sorted(set(on_page) - set(shown))) or "none")

else:  # record, answer
    if len(args) < (3 if args[0] == "answer" else 2):
        sys.exit(__doc__)
    typed, replace = "", False
    if args[0] == "answer":
        # typed="<their words>": a page answer Claude read and corrected keeps its source and the person's wording.
        typed = next((a.split("=", 1)[1] for a in args[3:] if a.startswith("typed=")), "")
        replace = "replace=yes" in args[3:]
        given = [(args[1], args[2], "Questions page, read by Claude" if typed else "chat")]
    else:
        given = [(os.path.basename(f)[:-5], (load(f, {}) or {}).get("answer", ""), "Questions page")
                 for f in sorted(glob.glob(os.path.join(args[1], "answers", "*.json")))]
    tracker_path = env.path("TRACKER")
    tracker = load(tracker_path, {})
    jobs = raw_jobs(tracker)
    master = load(env.path("MASTER_RECORD"), {})
    changed = {"tracker": False, "master": False}
    go_on, delete, discuss, read_first, ask_person, no_profile = [], [], [], [], [], []
    names = labels(tracker)

    def titles(ids):
        return ", ".join(names.get(j, j) for j in ids) or "no job waiting"

    def flush():
        """Write what this run changed so far: before a script rewrites the tracker, before stopping, at the end."""
        if changed["tracker"]:
            save(tracker_path, tracker)
        if changed["master"]:
            save(env.path("MASTER_RECORD"), master)
        save(QUESTIONS, data)
        changed.update(tracker=False, master=False)

    def to_profile(key, value, private):
        """Writes one answer into the profile by compare-and-set: (True, "") when it is there now, else (False, why):
        "different", or why there is no readable profile. A private answer with the same answer counts as there."""
        try:
            current = pl.get(key, env)
            if private and isinstance(current, dict) and current.get("answer") == value["answer"]:
                return True, ""
            pl.set_value(key, value, current if replace else pl.ABSENT, env)
            return True, ""
        except pl.ProfileError as e:
            return False, ("different" if e.code == 3 else str(e))

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
        # Typed text is what the page shows as a reply box: no buttons (index.html), never a decision.
        if source == "Questions page" and q["kind"] != "decision" and not q.get("options"):
            # Typed text: Claude reads it first. A plain answer is recorded with answer, its spelling and grammar
            # fixed; a question or remark to Claude ("did we already send this?") gets a reply, nothing recorded.
            read_first.append(("[private] " if q.get("personal") else "") + f"{qid} | {q['text']} | {answer}")
            continue
        entry = {"answer": answer, "date": today, "source": source}
        if args[0] == "answer" and typed and typed != answer:
            entry["typed"] = typed
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
        elif q["kind"] == "fact" and profile_key(q):
            # The person's own facts live only in their profile (profilelib.py), never written over another value.
            key = profile_key(q)
            private = key.startswith("private.")
            value = (dict({k: v for k, v in entry.items() if k != "typed"}, words=typed or answer, question=q["text"])
                     if private else answer)
            ok, why = to_profile(key, value, private)
            if not ok:
                if why == "different":
                    ask_person.append(f"{qid} ({key}): the profile holds another value; show the person both "
                                      f"(profilelib.py get {key}) and record their choice with answer ... replace=yes")
                    q.update(note="Your profile already holds another answer: Claude asks you which one is right.",
                             noted_at=now)
                else:
                    no_profile.append(f"{qid} ({key}): {why}")
                continue
            go_on += q.get("jobs", [])
            note = ("Kept in your profile, private; used only in a form field that asks for it." if private
                    else f"Saved in your profile ({key}); forms take it from there. Waiting on it: "
                         f"{titles(q.get('jobs', []))}.")
        elif q["kind"] == "fact":
            store = master.setdefault("form_answers", {})
            old = store.get(q["key"])
            if old:
                entry["history"] = (old.get("history", []) if isinstance(old, dict) else []) + \
                    [{k: v for k, v in (old if isinstance(old, dict) else {"answer": old}).items() if k != "history"}]
            store[q["key"]] = dict(entry, question=q["text"])
            changed["master"] = True
            go_on += q.get("jobs", [])
            note = (f"Saved in your records: \"{answer[:80]}\". Forms take it from there; waiting on it: "
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
    print("ask the person (not recorded; the answer stays on the page):", "; ".join(ask_person) or "none")
    print("no profile (not recorded; ask the person where it goes, then profilelib.py create <path>):",
          "; ".join(no_profile) or "none")
    print("read first (record each plain answer with answer, spelling and grammar fixed; reply to a question):")
    print("\n".join(read_first) or "none")
