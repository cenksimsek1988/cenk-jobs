"""Build the job-applications folder from the tracker and the hiring stages: one folder per application.

Usage: python -I build_app_folders.py [--env <job-search.env>]
Layout under APPLICATIONS_DIR:
  README.md       fast-lookup summary: next steps first, then one table per stage
  pending/        sent, no answer yet
  approved/       moved forward; one subfolder per hiring step ("NN <date> <name>") for prep.md, cheat-sheet.md and
                  feedback.md
  rejected/       turned down, with the date and the reason given
  closed/         the position closed, was filled or put on hold before a decision on the person: not a rejection
  declined/       the person said no at some step, with the date and why (ethics, relocation, pay, other)
  not-applied/    prepared or found but not sent, with what blocks each one (and its own README.md)
  _cv-versions/   only with SENT_CVS_DIR: the CVs sent before the current ones in CVS_DIR, as they were sent
Every application folder holds overview.md (read by export_dashboard.py), role.md, company.md, prep.md and the cover
letter. Reruns rewrite those four files and the README files only. Files written later (job-description.md, notes.md
and every file inside a step folder) are never overwritten, and a folder whose stage changed is moved, not recreated.
A step folder gets a feedback.md form once; Claude writes prep.md and cheat-sheet.md there before the step, and the
overview links them once they exist. A sent job's CV and letter are copied into its folder once, so the folder keeps
what was really sent. When a not-applied job is sent or dropped, the files the person or Claude wrote in its folder
(job-description.md, notes.md, ...) move to its new folder, and the old folder is removed only when nothing is left
but files this script writes again; otherwise it stays and the run names it. Nothing else is ever deleted, and a
folder is moved only onto a name that does not exist yet.

Reads TRACKER (either shape, see trackerlib.py), PIPELINE, CVS_DIR and PERSON_NAME, and these optional keys:
  SENT_CVS_DIR          CVs sent before the ones now in CVS_DIR: each is copied once into _cv-versions/, and a sent
                        job without its own "cv" path links its CV there.
  SENT_CVS_BEFORE_DIRS  ';'-separated folders with earlier copies of some of those CVs; a copy found there is the one
                        that was really sent, so it goes into _cv-versions/ instead.
  REDACT_FILE           lines "<regex> => <replacement>" ('#' starts a comment): private text, such as a home address
                        or an ID number typed into a form, is replaced in every file written here. Keep that file
                        outside shared folders.
  TRACKER_SETTINGS      a JSON file; this script reads "cv_names": [[<regex>, <CV file name>], ...] for notes that
                        name a CV in words ("sent with the TD CV"), and "cv_copied_when_note_has": a phrase in a sent
                        job's note meaning its CV is the current one in CVS_DIR rather than one in _cv-versions/.
Pipeline entries: {"stage": "approved", "steps": [{date, time, name, with, how, due, link, mail}], "same_as": <job id>,
"reminder": ...} or {"stage": "rejected", "date": ..., "reason": ...} ("rejected": {date, reason} works too), or
{"stage": "closed", "date": ..., "reason": ...} (the role closed, was filled or put on hold), or {"stage": "declined",
"date": ..., "why": ethics|relocation|pay|other, "reason": ...} (the person said no).
A step's link is its own page (meeting, test, booking, interview) and mail the Gmail link of the email that set it;
the overview's step line links both.
"""
import datetime
import filecmp
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jsenv  # noqa: E402
from trackerlib import applied_on, companies, is_company_shape, load_settings, needs_of, note_key, waits_on_person  # noqa: E402

args = sys.argv[1:]
env = jsenv.load(args[args.index("--env") + 1] if "--env" in args else None, __file__)
out = env.path("APPLICATIONS_DIR")
with open(env.path("TRACKER"), encoding="utf-8") as fh:
    data = json.load(fh)
pipeline = {}
if os.path.isfile(env.path("PIPELINE")):
    with open(env.path("PIPELINE"), encoding="utf-8") as fh:
        pipeline = json.load(fh)
settings = load_settings(env)
today = datetime.date.today().isoformat()
NOTE = note_key(data)
COMPANY_SHAPE = is_company_shape(data)
CV_PREFIX = env.file_prefix() + "-CV-"
FIRST_NAME = (env.get("PERSON_NAME") or "").split(" ")[0]
STAGES = ("pending", "approved", "rejected", "closed", "declined")
# Why the person declined: one of these, so the reasons can be counted.
DECLINED_WHY = ("ethics", "relocation", "pay", "other")
OPEN = {"needs-person": "waiting on you", "needs-captcha": "waiting on you (captcha)",
        "account-needed": "needs your account on the site", "to-apply": "ready to send",
        "pending": "not prepared yet", "found": "not prepared yet"}
OPEN_ORDER = ["waiting on you", "waiting on you (captcha)", "needs your account on the site", "ready to send",
              "not prepared yet"]
FEEDBACK = """# Feedback: {step} - {company}

Filled in after the step, from {who} account of it in chat.

- **When:** {when}
- **With:** {with_}
- **Format:** {how}

## How it went

## Questions they asked

## What they told me (team, product, process, pay, timeline)

## What I would answer better next time

## Follow-ups and open questions

## Outcome and next step
"""


def resolve(path):
    path = (path or "").strip()
    if not path:
        return ""
    return os.path.normpath(path if os.path.isabs(path) else os.path.join(env.home, path))


LIVE_CVS = env.path("CVS_DIR")
LIVE_LINK = os.path.relpath(LIVE_CVS, out).replace(os.sep, "/")
SENT_CVS = env.path("SENT_CVS_DIR") if env.get("SENT_CVS_DIR") else ""
SENT_BEFORE = [resolve(p) for p in (env.get("SENT_CVS_BEFORE_DIRS") or "").split(";") if p.strip()]
NEW_CV_MARK = settings.get("cv_copied_when_note_has", "")

REDACT = []
if env.get("REDACT_FILE"):
    redact_file = env.path("REDACT_FILE")
    if not os.path.isfile(redact_file):
        sys.exit(f"REDACT_FILE names {redact_file}, which does not exist. Nothing was written.")
    with open(redact_file, encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.rstrip("\r\n")
            if raw.strip() and not raw.lstrip().startswith("#") and " => " in raw:
                pattern, replacement = raw.split(" => ", 1)
                REDACT.append((re.compile(pattern.strip()), replacement.strip()))

# Notes may name the CV that was sent in words; the person's own phrases first, then "<Variant> CV" for each CV file.
CV_SAID = [(re.compile(p), name) for p, name in settings.get("cv_names", [])]
for cv_dir in (LIVE_CVS, SENT_CVS):
    for name in sorted(os.listdir(cv_dir)) if cv_dir and os.path.isdir(cv_dir) else []:
        if name.startswith(CV_PREFIX) and name.endswith(".pdf") and not name.endswith("-no-photo.pdf"):
            CV_SAID.append((re.compile(re.escape(name[len(CV_PREFIX):-4].replace("-", " ")) + " CV"), name))


def clean(text):
    text = "" if text is None else str(text)
    for pattern, repl in REDACT:
        text = pattern.sub(repl, text)
    return text


def safe(name, limit=70):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:limit].rstrip(" .")


def note_of(job):
    return job.get(NOTE) or ""


def applied(job):
    return applied_on(job, NOTE) or "undated"


def line(label, value):
    value = clean(value).strip()
    return f"- **{label}:** {value}\n" if value and value not in ("None", "not read", "[]") else ""


def cv_sent(job, prep):
    """The CV recorded on the job wins, then the one its note names (a note may say another CV was sent than the one
    prepared), then the one prepared."""
    if job.get("cv"):
        return os.path.basename(job["cv"].replace("\\", "/"))
    for pattern, name in CV_SAID:
        if pattern.search(note_of(job)):
            return name
    return os.path.basename((prep.get("cv_pdf") or "").replace("\\", "/"))


def where(job, prep):
    """Location and mode; for older rows only the setup's first phrase, cut before any pay figure."""
    if job.get("location"):
        return ", ".join(x for x in (job["location"], job.get("mode") or job.get("work_mode")) if x and x != "not read")
    setup = clean(prep.get("setup") or job.get("setup") or "")
    return re.split(r"[:;~]|\. | EUR| Rent| rent|\(", setup)[0].strip(" ,.")[:60]


def cv_link(cv, sent, job, path):
    """A sent job keeps its own copy of the CV it was sent with; one sent before CVS_DIR's CVs links _cv-versions;
    an unsent one links the current CV."""
    own = os.path.join(path, cv)
    if sent and job.get("cv"):
        src = resolve(job["cv"])
        if not os.path.exists(own) and os.path.isfile(src):
            shutil.copy2(src, own)
        return f"[{cv}](<{cv}>)"
    if sent and SENT_CVS and not (NEW_CV_MARK and NEW_CV_MARK in note_of(job)):
        return f"[{cv}](<../../_cv-versions/{cv}>)"
    if sent:
        if not os.path.exists(own) and os.path.exists(os.path.join(LIVE_CVS, cv)):
            shutil.copy2(os.path.join(LIVE_CVS, cv), own)
        return f"[{cv}](<{cv}>)"
    return f"[{cv}](<../../{LIVE_LINK}/{cv}>)"


def step_folder(n, step):
    return safe(f"{n:02d} {step.get('date', '')} {step.get('name', 'Step')}", 60)


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def place_folder(folder, target_dir):
    """Move an existing folder of this application into its stage directory; create it if new."""
    target = os.path.join(target_dir, folder)
    if not os.path.isdir(target):
        for old_dir in [out] + [os.path.join(out, s) for s in STAGES]:
            old = os.path.join(old_dir, folder)
            if old_dir != target_dir and os.path.isdir(old):
                shutil.move(old, target)
                break
    os.makedirs(target, exist_ok=True)
    return target


def open_label(status):
    return OPEN.get(status) or ("waiting on you" if waits_on_person(status) else "")


def earlier_notes(job):
    """Notes a job had before its current one (track.py keeps them in its history when it replaces one)."""
    current, rows = note_of(job), []
    for h in job.get("history") or []:
        text = h.get(NOTE) or h.get("note") or h.get("outcome") or ""
        if text and text != current and text != "added":
            when = h.get("date") or f"until {h.get('until', '?')}"
            rows.append(f"- {when}, {h.get('status', '')}: {clean(text)}")
    return "## Earlier notes\n\n" + "\n".join(rows) + "\n\n" if rows else ""


os.makedirs(out, exist_ok=True)
if SENT_CVS:
    versions = os.path.join(out, "_cv-versions")
    os.makedirs(versions, exist_ok=True)
    # The record of the earlier CVs as sent: copy only what is missing, never overwrite.
    for name in os.listdir(SENT_CVS):
        if name.endswith(".pdf") and not os.path.exists(os.path.join(versions, name)):
            src = next((os.path.join(d, name) for d in SENT_BEFORE if os.path.isfile(os.path.join(d, name))),
                       os.path.join(SENT_CVS, name))
            shutil.copy2(src, os.path.join(versions, name))
for stage in STAGES:
    os.makedirs(os.path.join(out, stage), exist_ok=True)
pending_dir = os.path.join(out, "not-applied")
os.makedirs(pending_dir, exist_ok=True)
before = set(os.listdir(pending_dir))

folders = {}  # job id -> (stage, folder), for links between applications that share one process
for company, job in companies(data):
    if job.get("status") == "submitted":
        stage = (pipeline.get(job["id"]) or {}).get("stage", "pending")
        stage = stage if stage in STAGES else "pending"
        folders[job["id"]] = (stage, safe(f"{applied(job)} {company['name']} - {job.get('title') or ''}"))

rows = {s: [] for s in STAGES}
open_rows, upcoming = [], []
for company, job in companies(data):
    sent = job.get("status") == "submitted"
    label = "" if sent else open_label(job.get("status", ""))
    verdict = company.get("verdict") or job.get("verdict")
    # "ask": an employer rule flagged it and the person decides; its jobs stay visible until then.
    if not sent and not (label and (not verdict or verdict in ("apply", "clear", "ask"))):
        continue
    # The older tracker keeps what was prepared in "prep"; a flat job row holds those fields itself.
    prep = job.get("prep") or ({} if COMPANY_SHAPE else job)
    info = pipeline.get(job["id"]) or {}
    title = job.get("title") or prep.get("title") or ""
    date = applied(job) if sent else ""
    if sent:
        stage, folder = folders[job["id"]]
        path = place_folder(folder, os.path.join(out, stage))
    else:
        stage, folder = "not-applied", safe(f"{company['name']} - {title}")
        path = os.path.join(pending_dir, folder)
        os.makedirs(path, exist_ok=True)

    cv = cv_sent(job, prep)
    place = where(job, prep)
    letter_src = resolve(job.get("letter") or prep.get("letter_pdf") or "")
    letter = os.path.basename(letter_src) if letter_src else ""
    if letter:
        dest = os.path.join(path, letter)
        # A sent letter is copied once (the folder keeps what was sent); an unsent one follows its latest build.
        if os.path.isfile(letter_src) and not (sent and os.path.exists(dest)):
            shutil.copy2(letter_src, dest)
        if not os.path.isfile(dest):
            letter = ""
    has_jd = os.path.isfile(os.path.join(path, "job-description.md"))

    # Hiring steps: one folder each, with feedback.md seeded once and never overwritten.
    steps_md, shared = "", info.get("same_as")
    if stage == "approved" and shared and shared in folders:
        s_stage, s_folder = folders[shared]
        steps_md = (f"\n## Hiring steps\n\nThis application shares one process with "
                    f"[{s_folder}](<../{s_folder}/overview.md>); its steps, prep and feedback are kept there.\n")
    elif stage == "approved":
        lines = []
        for n, step in enumerate(info.get("steps") or [], 1):
            sf = step_folder(n, step)
            os.makedirs(os.path.join(path, sf), exist_ok=True)
            fb = os.path.join(path, sf, "feedback.md")
            when = f"{step.get('date', '')} {step.get('time', '')}".strip()
            if not os.path.isfile(fb):
                write(fb, FEEDBACK.format(step=step.get("name", "Step"), company=company["name"], when=when,
                                          who=f"{FIRST_NAME}'s" if FIRST_NAME else "the person's",
                                          with_=step.get("with", ""), how=step.get("how", "")))
            have = [f for f in ("prep.md", "prep.pdf", "cheat-sheet.md", "cheat-sheet.pdf", "feedback.md")
                    if os.path.isfile(os.path.join(path, sf, f))]
            links = [f'[{f.replace(".md", "")}](<{sf}/{f}>)' for f in have]
            # The step's own page (meeting, test, booking) and the email that set it.
            links += [f"[{label}](<{step[key]}>)" for key, label in (("link", "step link"), ("mail", "email"))
                      if step.get(key)]
            links = " · ".join(links)
            due = f", due {step['due']}" if step.get("due") else ""
            lines.append(f"{n}. **{step.get('name', 'Step')}** - {when}{due}, {clean(step.get('with', ''))}. {links}")
            if (step.get("due") or step.get("date", "")) >= today:
                how = step.get("how", "") + (f" **Reminder: {info['reminder']}**" if info.get("reminder") else "")
                upcoming.append((step.get("due") or step.get("date", ""),
                                 "deadline" if step.get("due") else step.get("time", ""), company["name"],
                                 step.get("name", "Step"), step.get("with", ""), how, f"approved/{folder}/{sf}"))
        steps_md = "\n## Hiring steps\n\n" + "\n".join(lines) + "\n" if lines else ""

    rejected = info.get("rejected") if isinstance(info.get("rejected"), dict) else {}
    rejected_on = info.get("date") or rejected.get("date") or "?"
    reason = info.get("reason") or rejected.get("reason")
    why = info.get("why") if info.get("why") in DECLINED_WHY else "other"
    if sent:
        status = {"pending": "sent, waiting for a reply", "approved": "moving forward - see the hiring steps",
                  "rejected": f"rejected on {rejected_on}",
                  "closed": f"closed on {rejected_on}: the position closed, was filled or put on hold (not a rejection)",
                  "declined": f"declined by {FIRST_NAME or 'the person'} on {rejected_on} ({why})"}[stage]
    else:
        status = f"not applied - {label}"
    write(os.path.join(path, "overview.md"),
          f"# {clean(company['name'])} - {clean(title)}\n\n"
          # The tracker id is the key the dashboard's files use to point at this application.
          + line("Job id", job["id"])
          + line("Applied", date)
          + line("Status", status)
          + line("Reminder", info.get("reminder"))
          + line("Reason given", reason if stage in ("rejected", "closed") else "")
          + line("Why declined", ((f"{why}: {reason}" if reason else why) if stage == "declined" else ""))
          + line("Posting", job.get("url"))
          + line("Applied through" if sent else "Apply at",
                 f"{prep.get('platform') or job.get('method') or ''} {prep.get('apply_url') or ''}")
          + line("Where", place)
          + line("CV sent" if sent else "CV prepared", cv_link(cv, sent, job, path) if cv else "")
          + line("Cover letter", f"[{letter}](<{letter}>)" if letter else "none sent or not kept")
          + steps_md
          + (f"\n## What happened\n\n{clean(note_of(job))}\n\n" if sent else
             f"\n## What blocks it\n\n{clean(note_of(job) or 'Not prepared yet.')}\n\n")
          + earlier_notes(job)
          + "Files here: [role](<role.md>) · [company](<company.md>) · [prep](<prep.md>)"
          + (" · [job description](<job-description.md>)" if has_jd else "") + "\n")

    write(os.path.join(path, "role.md"),
          f"# Role: {clean(title)}\n\n"
          + line("Company", company["name"])
          + line("Posted", job.get("posted"))
          + line("Location", ", ".join(x for x in (job.get("location"), job.get("country")) if x))
          + line("Work mode", job.get("mode") or job.get("work_mode"))
          + line("Employment", job.get("employment"))
          + line("Pay in the posting", job.get("pay_posted"))
          + line("Who may apply", job.get("eligibility"))
          + line("Skills asked", ", ".join(job.get("skills") or []))
          + line("Fit", job.get("fit"))
          + line("Posting", job.get("url"))
          + "".join(line("Other link", u) for u in job.get("other_urls") or [])
          + f"\n## Posting check and requirements\n\n{clean(prep.get('reason') or 'Not recorded.')}\n\n"
          + ("Full posting text: [job-description.md](<job-description.md>)\n" if has_jd
             else "The full posting text was not saved; open the posting link while it is live.\n"))

    notes = []
    # Ties may sit under "ties" (screen-and-prepare.js) or an older "ties_for_<name>" key: show them all.
    ties = [t for k in company if k.startswith("ties") for t in company.get(k) or []]
    for items, heading in ((company.get("hits") or [], "Screening findings"), (ties, "Ties worth knowing"),
                           (company.get("not_counted") or [], "Checked, not counted")):
        if items:
            notes.append(f"## {heading}\n")
            for item in items:
                if isinstance(item, dict):
                    src = f" ({item['source_url']})" if item.get("source_url") else ""
                    notes.append(f"- {clean(item.get('finding') or item)}{src}")
                else:
                    notes.append(f"- {clean(item)}")
            notes.append("")
    write(os.path.join(path, "company.md"),
          f"# Company: {clean(company['name'])}\n\n" + line("Screening verdict", verdict)
          + "\n" + ("\n".join(notes) if notes else "No screening notes were recorded for this company.\n"))

    answers = "\n".join(f"- **{clean(a.get('question'))}**  \n  {clean(a.get('answer'))}"
                        for a in prep.get("answers") or [])
    needs = "\n".join(f"- {clean(n)}" for n in needs_of(prep))
    letter_txt = ""
    letter_txt_src = resolve(prep.get("letter_txt"))
    if letter_txt_src and os.path.isfile(letter_txt_src):
        with open(letter_txt_src, encoding="utf-8", errors="replace") as fh:
            letter_txt = clean(fh.read()).strip()
    write(os.path.join(path, "prep.md"),
          f"# Prep: {clean(company['name'])} - {clean(title)}\n\n"
          + line("CV variant", job.get("variant") or prep.get("variant"))
          + line("Notes", prep.get("notes"))
          + (f"\n## Answers prepared for the form\n\n{answers}\n" if answers else "")
          + (f"\n## Open points noted before applying\n\n{needs}\n" if needs else "")
          + (f"\n## Cover letter text\n\n{letter_txt}\n" if letter_txt else "")
          + "\n## Private: setup and salary reasoning (never share)\n\n"
          + line("Setup", prep.get("setup") or job.get("setup"))
          + line("Salary used", prep.get("salary_eur") or prep.get("salary") or job.get("salary_note")
                 or job.get("salary_target_eur")))

    short = cv.replace(CV_PREFIX, "").replace(".pdf", "") or "-"
    if sent:
        rows[stage].append((date, company["name"], title, place, short, info, folder))
    else:
        # A note's leading "<day> <month> ...: " is dropped from the table, where the date adds nothing.
        blocker = re.sub(r"^\d{1,2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[^:]*: ", "",
                         clean(note_of(job) or "Not prepared yet."))
        open_rows.append((label, company["name"], title, place,
                          blocker[:140] + ("…" if len(blocker) > 140 else ""), folder))

# A not-applied folder whose job was sent or dropped since the last run. Nothing the person or Claude wrote is ever
# deleted: when the job was sent, such files (job-description.md, notes.md, ...) move into its new folder (never over
# a file there); the folder itself is removed only when nothing is left in it but files this script writes again
# (its four .md files and copies of CVs and letters, whose sources stay in their own folders). Anything else keeps
# the folder, and the run says so.
GENERATED = {"overview.md", "role.md", "company.md", "prep.md"}
SOURCES = [env.path("LETTERS_DIR") if env.get("LETTERS_DIR") else "", LIVE_CVS, SENT_CVS,
           os.path.join(out, "_cv-versions")] + SENT_BEFORE


def has_twin(path):
    """True when a byte-identical copy of this file exists in a folder the copies come from (letters, CVs)."""
    name, size = os.path.basename(path), os.path.getsize(path)
    for base in SOURCES:
        for here, _, names in os.walk(base) if base and os.path.isdir(base) else []:
            twin = os.path.join(here, name)
            if name in names and os.path.getsize(twin) == size and filecmp.cmp(path, twin, shallow=False):
                return True
    return False


def regenerable(folder, name):
    path = os.path.join(folder, name)
    if os.path.isdir(path):
        return False
    if name in GENERATED:
        return True
    # A CV or letter copy goes only when its source still holds the very same file.
    return bool(re.fullmatch(re.escape(env.file_prefix()) + r"-(CV|Cover-Letter)-.+\.pdf", name)) and has_twin(path)


def id_in(overview):
    try:
        with open(overview, encoding="utf-8") as f:
            m = re.search(r"^- \*\*Job id:\*\* (\S+)", f.read(), re.M)
        return m.group(1) if m else ""
    except OSError:
        return ""


removed_stale, kept_stale = 0, []
for gone in sorted(before - {r[5] for r in open_rows}):
    stale = os.path.join(pending_dir, gone)
    if not os.path.isdir(stale):
        continue
    try:
        sent_to = folders.get(id_in(os.path.join(stale, "overview.md")))
        if sent_to:
            dest = os.path.join(out, sent_to[0], sent_to[1])
            for name in os.listdir(stale):
                if not regenerable(stale, name) and os.path.isdir(dest) and not os.path.exists(os.path.join(dest, name)):
                    shutil.move(os.path.join(stale, name), os.path.join(dest, name))
        left = os.listdir(stale)
        if not all(regenerable(stale, name) for name in left):
            kept_stale.append(gone)
            continue
        for name in left:
            os.remove(os.path.join(stale, name))
        os.rmdir(stale)
        removed_stale += 1
    except OSError as exc:  # a synced drive may refuse for a moment: keep what is there and go on
        kept_stale.append(f"{gone} ({exc.strerror or exc})")
open_rows.sort(key=lambda r: (OPEN_ORDER.index(r[0]), r[1].lower()))
write(os.path.join(pending_dir, "README.md"),
      "# Not applied yet\n\n"
      f"{len(open_rows)} jobs prepared or found but not sent. Each folder has the same files as an application "
      "(overview with what blocks it, role, company, prep, cover letter if one was written). When one is sent, "
      "its folder moves to pending on the next daily run.\n\n"
      "| Blocked by | Company | Role | Where | What is missing | Folder |\n|---|---|---|---|---|---|\n"
      + "\n".join(f"| {r[0]} | {clean(r[1])} | {clean(r[2])} | {clean(r[3]) or '-'} | {r[4].replace('|', '/')} | "
                  f"[open](<{r[5]}/overview.md>) |" for r in open_rows) + "\n")

for stage in STAGES:
    rows[stage].sort(key=lambda r: (r[0], r[1]), reverse=True)
upcoming.sort()
total = sum(len(v) for v in rows.values())
sent_dates = [r[0] for v in rows.values() for r in v]


def table(stage, extra):
    head = f"| Applied | Company | Role | Where | CV | {extra} | Folder |\n|---|---|---|---|---|---|---|\n"
    body = []
    for r in rows[stage]:
        info = r[5]
        rej = info.get("rejected") if isinstance(info.get("rejected"), dict) else {}
        when_why = (f"{info.get('date') or rej.get('date') or '?'}: "
                    f"{clean(info.get('reason') or rej.get('reason') or '')[:80]}")
        col = {"approved": ", ".join(s.get("name", "Step") for s in info.get("steps") or []) or "see shared process",
               "rejected": when_why, "closed": when_why,
               "declined": f"{info.get('why') if info.get('why') in DECLINED_WHY else 'other'}, {when_why}",
               "pending": "-"}[stage]
        body.append(f"| {r[0]} | {clean(r[1])} | {clean(r[2])} | {clean(r[3]) or '-'} | {r[4]} | {col} | "
                    f"[open](<{stage}/{r[6]}/overview.md>) |")
    return head + "\n".join(body) + "\n"


sent_span = f" between {min(sent_dates)} and {max(sent_dates)}" if sent_dates else ""
write(os.path.join(out, "README.md"),
      "# Job applications\n\n"
      f"{total} applications sent{sent_span}: "
      f"**{len(rows['approved'])} moving forward**, {len(rows['pending'])} waiting for a reply, "
      f"{len(rows['rejected'])} rejected, {len(rows['closed'])} closed (the position closed: not a rejection), "
      f"{len(rows['declined'])} declined by {FIRST_NAME or 'you'}. "
      f"{len(open_rows)} more are [not applied yet](<not-applied/README.md>). "
      f"Updated {today} from the job-search tracker.\n\n"
      "Folders: `approved/` (one subfolder per hiring step with `prep.md`, `cheat-sheet.md` and `feedback.md`), "
      "`pending/`, `rejected/`, `closed/`, `declined/`, `not-applied/`"
      + (", and `_cv-versions/` (the CVs as sent)" if SENT_CVS else "") + ". Each application holds "
      "`overview.md`, `role.md`, `company.md`, `prep.md`, the cover letter and, where fetched, `job-description.md`. "
      "Keep your own notes in `notes.md`: reruns never overwrite it or anything inside a step folder.\n\n"
      "## Next steps\n\n"
      + ("\n".join(f"- **{u[0]} {u[1]}** {clean(u[2])}: {u[3]}, {clean(u[4])}. {clean(u[5])} "
                   f"[step folder](<{u[6]}/>)" for u in upcoming) or "None scheduled.") + "\n\n"
      f"## Moving forward ({len(rows['approved'])})\n\n" + table("approved", "Steps") + "\n"
      f"## Waiting for a reply ({len(rows['pending'])})\n\n" + table("pending", "Note") + "\n"
      f"## Rejected ({len(rows['rejected'])})\n\n" + table("rejected", "When and why") + "\n"
      f"## Closed ({len(rows['closed'])})\n\n" + table("closed", "When and why") + "\n"
      f"## Declined ({len(rows['declined'])})\n\n" + table("declined", "Why and when"))
print(total, "applications:", {s: len(v) for s, v in rows.items()}, "| not applied:", len(open_rows),
      "| upcoming steps:", len(upcoming))
if removed_stale or kept_stale:
    print(f"not-applied folders of jobs no longer open: {removed_stale} removed (only rewritable files in them)"
          + (f"; kept, as they hold other files: {'; '.join(kept_stale)}" if kept_stale else ""))
