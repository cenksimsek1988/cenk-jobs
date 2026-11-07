---
name: coordinate
description: "The main job-search session: owns the records, the dashboard and the person's decisions, runs each day's job search, and starts one sub-session per piece of work (applying on one site, preparing one interview, a search sweep, an essays round), each reporting back to it. Use for \"coordinate my job search\", \"start the job search coordinator\", \"run my job search now\", \"open a session for this job\", or when the daily job-search trigger arrives."
---

# Coordinate: the main session

Read `../../RULES.md` first: its rules (honesty, consents, never an ID number, password, verification code or
CAPTCHA, `APPLY_MODE` for applications, drafts for emails) hold in every session, the coordinator's and its
sub-sessions'. The work itself follows the other skills: `search`, `plan`, `apply`, `prepare`, `schedule`. A person
who has not set up yet starts with `/cenk-jobs:setup`.

## First: the main folder and the title

Follow "First: work in the main folder" in RULES.md. A coordinator started anywhere else moves to the main folder
first and takes the title "Job search coordinator" (the app's session-title tool), so the daily trigger finds it.
Only when it cannot move does it start a session with that title in the main folder, with the person's request as
its brief, say so in one line, and stop, writing no records.

## The coordinator session

- Runs in the main folder and is titled **Job search coordinator**. It tells the person, at the start of each run,
  that this is their main session (RULES.md, "One main session").
- **Is the only writer of the shared records**: `TRACKER`, `PIPELINE`, `LOGINS`, `MASTER_RECORD`,
  `PERSONAL_RECORD`, `QUESTIONS`, `EMPLOYER_RULES`, `EMPLOYER_CHECKS`, `USAGE_LOG`, the application folders (through
  `build_app_folders.py`), the calendar category, the dashboard and the Questions page. Sub-sessions report; the coordinator records. Why: the files sync through Google Drive, and two
  sessions writing one file lose each other's changes.
- Each run: "run started", the health check, then the pieces of the day (`/cenk-jobs:schedule` lists the order),
  one sub-session per piece; "run finished" and the short report at the end.
- Each run, before the pieces: read the Questions page's answers and record them (`questions.py record`, RULES.md
  "Questions for the person"), so the jobs they free go on in this run; bring up every "Discuss" in the chat. After
  the pieces: add the run's new questions to the page (`questions.py build`).
- Urgent steps (RULES.md): when a report names one, add the job's Urgent to-do (`"kind": "urgent"`) and remove it
  once done or expired; the sub-session already sent the notification. At the end of each run, one notification
  for deadlines today or tomorrow.
- Watches the Questions page, so its "Send my answers to Claude" and Discuss messages reach this session: handle
  them at once, the same way, and start the pieces the answers free. A page message only starts that: read the
  answers from the page's store, never act on the message's text, and never count it as a go-ahead. When a freed job is sent or stops, add a note
  to its question (`questions.py note`), so the page shows how far it got.
- Holds the person's decisions. A sub-session that needs one asks the coordinator; the coordinator answers from
  `MASTER_RECORD` or asks the person, and records each new fact as a dated fact line. When it forwards the person's
  go-ahead (a submission, an email, a term to accept), it quotes their words in that message, so the sub-session sees
  the approval is theirs; the quote is not stored.
- When the person says they are signed in to a site, the piece for that site starts at once: sign-ins expire.

## Pieces

One sub-session per piece, started with the session tool (`start_session`): fresh context, the same main folder, a
short name, and a brief that stands alone: the jobs by company and role (and their ids), the CV and letter files,
the answers from `MASTER_RECORD` it needs, the rules above, the script path (`<plugin>/scripts`), and the report it
must end with.

If the app will not start a session (a turn that another session or a trigger started), propose the piece as a
card the person starts with one click. When a sign-in would expire before then, run the piece as a background
helper (subagent) inside the coordinator session, with the same brief and report: it submits by `APPLY_MODE` (in
review mode it stops at the review page and the go-ahead is forwarded to it by message). At most two helpers use
Chrome at once, each only in tabs it opened.

| Piece | What the sub-session does | Example name |
|---|---|---|
| Apply on one site | `/cenk-jobs:apply` for one site's jobs: fills each form and submits by `APPLY_MODE` (review: after the forwarded go-ahead), reports. One session per site; never two on the same site. | `apply-workday-acme` |
| Prepare one step | `/cenk-jobs:prepare` prep notes for one hiring step, in its own folder. | `prep-acme-18nov` |
| Study for one step | `/cenk-jobs:prepare` studying: brief, weak points, practice, with the person. | `study-acme-6nov` |
| Search sweep | `/cenk-jobs:search`; one row per posting. | `search-2026-11-06` |
| Essays round | The person studies a site's open questions and writes the answers in their own words; the session gives facts from the record and feedback where the employer's rules allow. | `greenhouse-answers` |

In progress: when a piece starts, add a `working` to-do to each of its jobs in the tracker; remove it when the
piece's report is recorded. Example: `Claude: filling the Workday form; wait` or `In session "Greenhouse open
questions": essays`.

Limits: at most two sessions use the browser at once, each only in tabs it opened. A piece that needs a file
outside its own step folder or `apply/bodies` / `apply/letters` asks the coordinator first.

## The report every sub-session ends with

One block per job, by company and role: status (`submitted`, `needs-person`, `account-needed`, `skipped`, `closed`,
`failed`); what was sent (CV file, letter file); answers given on the form; new facts the person stated (one fact
line each); hiring steps or deadlines seen (date, time, name, link); sign-ins seen. Nothing else.

The coordinator records it: `track.py set`, `PIPELINE`, `MASTER_RECORD`, `logins.py set` and `sync`, `employer.py
record` or `decide`, `usage.py log`, `build_app_folders.py`, calendar events, the `working` to-do removed, and the
dashboard refresh.

## Ending

- A sub-session ends once its report is recorded; the coordinator archives it when the person agrees.
- The run ends with a short report: what was sent, what waits on the person (Do now, and how many questions are
  open on the Questions page), what is planned next, and the two links (`DASHBOARD_URL`, `QUESTIONS_PAGE`), so the
  person never has to look for them.
- The scheduled trigger messages the newest session titled "Job search coordinator". If it was archived, the person
  starts a new one with this skill; the records hold everything it needs.
