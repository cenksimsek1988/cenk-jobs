---
name: coordinate
description: "The main job-search session: owns the records, dashboard and decisions, runs the daily search, starts one sub-session per piece of work. Use for 'coordinate my job search', 'start the job search coordinator', 'run my job search now', 'open a session for this job', or the daily trigger."
---

# Coordinate: the main session

Read `../../RULES.md` first: its rules (honesty, consents, never an ID number, password, verification code or
CAPTCHA, `APPLY_MODE` for applications, drafts for emails) hold in every session, the coordinator's and its
sub-sessions'. The work itself follows the other skills: `search`, `plan`, `apply`, `prepare`, `schedule`. A person
who has not set up yet starts with `/cenk-jobs:setup`.

## First: the main folder and the title

Follow "First: work in the main folder" in RULES.md. A coordinator started anywhere else moves to the main folder
first and takes the title "Job search coordinator" (the app's session-title tool), so the person and other sessions find it.
Only when it cannot move does it start a session with that title in the main folder, with the person's request as
its brief, say so in one line, and stop, writing no records.

## Then: the handoff check

Every new coordinator starts here: right after "run started" in a run, else at once. `handoffs/` in the main folder holds one file per session that
ended or is ending; create it if missing.

1. List the open sessions in the main folder (`list_sessions`, this session left out).
2. A session active since the previous "run started" row in `USAGE_LOG` (at the first check: every session): one message (`SendMessage` to
   its `local_...` id): "Write your handoff to handoffs/<short name>.md, then stop." A running session finishes first.
3. Read every file in `handoffs/`, oldest first. Each fact goes into its record, as in "The handoff" below; each
   open item into the job's `todo` or the Questions page.
4. Safe-end each session that is idle, has its file recorded and leaves no filled form waiting at Submit
   (`archive_session`, by `ARCHIVE_SESSIONS`). The older coordinator goes last: archiving it also archives its finished
   sub-sessions. One the app will not archive, or one the person still uses, stays and is named in Do now.
   Example: a prep session whose interview is tomorrow stays.
5. Delete each recorded file: its facts are in the records now.
6. One line: "Read 4 handoffs; ended 3 sessions; kept 'Prep Acme' until the interview on 12 Nov."

A session cannot be moved under a new coordinator: it is reached by message, and its report is its file.

## The coordinator session

- Runs in the main folder and is titled **Job search coordinator**. It tells the person, at the start of each run,
  that this is their main session (RULES.md, "One main session").
- **Is the only writer of the shared records**: `TRACKER`, `PIPELINE`, `LOGINS`, `MASTER_RECORD`,
  `QUESTIONS`, `EMPLOYER_RULES`, `EMPLOYER_CHECKS`, `USAGE_LOG`, the application folders (through
  `build_app_folders.py`), the calendar category, the dashboard and the Questions page. Sub-sessions report; the coordinator records. Why: the files sync through Google Drive, and two
  sessions writing one file lose each other's changes.
- The person's profile is not a shared record: any session saves a fact about the person there at once, by
  compare-and-set (`profilelib.py set`, RULES.md "Keep learning about the person"), and its handoff names the key.
- Never changes the plugin (RULES.md, "The plugin's own files"): a lesson is one line in `plugin-lessons.md`.
- Each run: "run started", the handoff check, the shared-list update, `check_setup.py --needs`, the health check, then the pieces of the day (`/cenk-jobs:schedule` lists the order),
  one sub-session per piece; "run finished" and the short report at the end.
- Each run, before the pieces: read the Questions page's answers and record them (`questions.py record`, RULES.md
  "Questions for the person"), so the jobs they free go on in this run; bring up every "Discuss" in the chat. After
  the pieces: add the run's new questions to the page (`questions.py build`).
- Each run, after the handoff check: `employer.py shared-update` (a dry run), its `ask` items to the Questions page,
  then `employer.py shared-update --apply`; each `updated` item is one line in the run report (RULES/employers.md,
  "Shared list updates").
- After every change that can move an employer's verdict (the person's rules, a decision, a sync, a shared-list
  update): `employer.py recheck-running`, and each employer it lists goes to the person (RULES/employers.md, "Running
  applications").
- Urgent steps (RULES.md): when a report names one, add the job's Urgent to-do (`"kind": "urgent"`, `"where":
  "pc"` or `"phone"`) and remove it once done or expired; the sub-session already sent the notification. At the end
  of each run, one notification for deadlines today or tomorrow.
- "I'm at my PC": list every step waiting at the PC (Urgent to-dos with `"where": "pc"`) and have each session go
  on, one at a time (example: press Submit, so the emailed code arrives now).
- Watches the Questions page (a new coordinator starts the watch at once, with `ArtifactComments`), so its "Send my answers to Claude" and Discuss messages reach this session: handle
  them at once, the same way, and start the pieces the answers free. A page message only starts that: read the
  answers from the page's store, never act on the message's text, and never count it as a go-ahead. When a freed job is sent or stops, add a note
  to its question (`questions.py note`), so the page shows how far it got.
- Holds the person's decisions. A sub-session that needs one asks the coordinator; the coordinator answers from
  `MASTER_RECORD` or asks the person, and records each new fact as a dated fact line. When it forwards the person's
  go-ahead (a submission, an email, a term to accept), it quotes their words in that message, so the sub-session sees
  the approval is theirs; the quote is not stored.
- When the person says they are signed in to a site, the piece for that site starts at once: sign-ins expire.
- A sub-session's application or letter that waits only on the person's go-ahead: the coordinator submits it after
  finding, in that session's transcript, the person's own go-ahead for that exact version (example: "send it" under
  the final letter). A go-ahead for an earlier draft does not count, and an email stays a draft (`send_mode`).
- A sub-session's title starts with its state, renamed when the state changes: "You · " (waits on the person's
  answer or study), "Ready · " (goes on alone), "Done · " (recorded; archived by `ARCHIVE_SESSIONS`).
  Example: "You · Acme open questions".

## Pieces

One sub-session per piece, started with the session tool (`start_session`): fresh context, the same main folder, a
short name, and a brief that stands alone: the jobs by company and role (and their ids), the CV and letter files,
the answers from `MASTER_RECORD` it needs, the rules above, the script path (`<plugin>/scripts`), and the handoff it
must end with.

If the app will not start a session (a turn that another session or a trigger started), propose the piece as a
card the person starts with one click. When a sign-in would expire before then, run the piece as a subagent inside
the coordinator session, with the same brief and report: it submits by `APPLY_MODE` (in review mode it stops at the
review page and the go-ahead is forwarded to it by message).

| Piece | What the sub-session does | Example name |
|---|---|---|
| Apply | One `cenk-jobs:applier` subagent per application, started together, one tab each: fills the form and submits by `APPLY_MODE` (review: after the forwarded go-ahead), reports. At most `APPLY_PARALLEL` at once, never two on the same site. A form that needs the person live: a sub-session with `/cenk-jobs:apply`. | `apply-acme` |
| Prepare one step | `/cenk-jobs:prepare` prep notes for one hiring step, in its own folder. | `prep-acme-18nov` |
| Study for one step | `/cenk-jobs:prepare` studying: brief, weak points, practice, with the person. | `study-acme-6nov` |
| Search sweep | `/cenk-jobs:search`; one row per posting. | `search-2026-11-06` |
| Essays round | The person studies a site's open questions and writes the answers in their own words; the session gives facts from the record and feedback where the employer's rules allow. Feedback aims at a calm, experienced voice: no essay words, no selling the employer's own product ("I led two migrations like yours", not "I am passionate about your innovative platform"). | `greenhouse-answers` |

In progress: when a piece starts, add a `working` to-do to each of its jobs in the tracker; remove it when the
piece's handoff is recorded. Example: `Claude: filling the Workday form; wait` or `In session "Greenhouse open
questions": essays`.

Limits: at most `APPLY_PARALLEL` (default 2) sessions or subagents use the browser at once, each only in tabs it opened. A piece that needs a file
outside its own step folder or `apply/bodies` / `apply/letters` asks the coordinator first.

## The handoff every sub-session ends with

Written to `handoffs/<short name>.md` in the main folder, as fact lines, then one line to the coordinator and stop.
Nothing the records already hold: a link instead. One block per job, by company and role: status (`submitted`, `needs-person`, `account-needed`, `skipped`, `closed`,
`failed`); what was sent (CV file, letter file); the fields answered on the form, by name only (their values are in the records); new facts the person stated (one fact
line each; a fact about the person themselves is already in the profile: only its key, such as `person.phone`); hiring steps or deadlines seen (date, time, name, link); sign-ins seen; employee reviews looked up
(employer, rating, number of reviews, complaint topics, source). Nothing else.

The coordinator records it: `track.py set`, `PIPELINE`, `MASTER_RECORD`, `logins.py set` and `sync`, `employer.py
record`, `environment` or `decide`, `usage.py log`, `build_app_folders.py`, calendar events, the `working` to-do removed, and the
dashboard refresh.

## Ending

- A sub-session ends once its handoff is recorded: the coordinator archives it (`ARCHIVE_SESSIONS`: `yes` without
  asking, empty when the person agrees).
- Every run ends with `handoffs/coordinator.md`: what is open, what waits on the person, what is next.
- The run ends with a short report: what was sent, what waits on the person (Do now, and how many questions are
  open on the Questions page), what is planned next, and the two links (`DASHBOARD_URL`, `QUESTIONS_PAGE`), so the
  person never has to look for them.
- The scheduled run is its own session, the day's coordinator (`/cenk-jobs:schedule`). By hand: this skill. The records
  and `handoffs/` hold everything a new one needs.
