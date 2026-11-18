---
name: coordinate
description: "The main job-search session: owns the records, dashboard and decisions, runs the daily search, starts one sub-session per piece of work. Use for 'coordinate my job search', 'start the job search coordinator', 'run my job search now', 'open a session for this job', or the daily trigger."
---

# Coordinate: the main session

Read `../../RULES.md` first: its rules (honesty, consents, never an ID number, password, verification code or
CAPTCHA, the person's choices for applications, drafts for emails) hold in every session, the coordinator's and its
sub-sessions'. The work itself follows the other skills: `search`, `plan`, `apply`, `prepare`, `cheat-sheet`, `schedule`. A person
who has not set up yet starts with `/cenk-jobs:setup`.

## First: the main folder and the title

Follow "First: work in the main folder" in RULES.md. A coordinator started anywhere else moves to the main folder
first and takes the title "Job search coordinator" (the app's session-title tool), so the person and other sessions find it.
Only when it cannot move does it start a session with that title in the main folder, with the person's request as
its brief, say so in one line, and stop, writing no records.

## Then: the handoff check

Every new coordinator starts here: right after "run started" in a run, else at once. `handoffs/` in the main folder holds one file per session that
ended or is ending; create it if missing.

0. The base plugin: `profilelib.py path` (Bash tool). "cenk-base is not loaded" (exit 1): stop here and tell the
   person in plain words that cenk-jobs needs its base plugin cenk-base, with the line for their terminal:
   `claude plugin install cenk-jobs@cenk` (or `@<the marketplace they installed from>`; a plain `claude plugin
   update` does not bring the base), then a new session. A scheduled run puts the same line in Do now and ends.
1. List the open sessions in the main folder (`list_sessions`, this session left out).
2. A session active since the previous "run started" row in `USAGE_LOG` (at the first check: every session): one message (`SendMessage` to
   its `local_...` id): "Write your handoff to handoffs/<short name>.md, then stop." A running session finishes first.
3. Read every file in `handoffs/`, oldest first. Each fact goes into its record, as in "The handoff" below; each
   open item into the job's to-dos (`track.py todo`) or the Questions page.
4. Safe-end each session that is idle, has its file recorded and leaves no filled form waiting at Submit
   (`archive_session`, by `ARCHIVE_SESSIONS`). The older coordinator goes last: archiving it also archives its finished
   sub-sessions. One the app will not archive, or one the person still uses, stays and is named in Do now.
   Example: a prep session whose interview is tomorrow stays.
5. Delete each recorded file: its facts are in the records now.
6. One line: "Read 4 handoffs; ended 3 sessions; kept 'Prep Acme' until the interview on 12 Nov."

A session cannot be moved under a new coordinator: it is reached by message, and its report is its file.

## The coordinator session

- Reads the person's choices (`choices.py show`) at the start of every run and names the apply ones in the first
  line of the run's report, with the plan's share when `statusline.py read` prints one. Under `APPLY=auto`, an
  application whose answers all come from the records is sent without asking, unless `ASK_FIRST` holds `send`: then
  it waits at the review page. Under `APPLY=list`, nothing is filled: the report lists the fitting jobs with links.
  Example: "Job-search run started at 19:02 (scheduled); apply: auto, high fits, sent alone. Plan used: 5 hours 23%,
  7 days 41%."
- A job that waits on the person gets its status and a to-do with its link as soon as the wait is known:
  `track.py wait <id> needs-person|account-needed "<what>"`. A wait kept only in a chat or a hand-off note is
  invisible on the dashboard. Example: `track.py wait J7 account-needed "Workday sign-in for Acme"`.
- Every question for the person, its own or a sub-session's, goes on the Questions page as it is asked: `questions.py
  add`, `build`, write the page, in the same turn (RULES/questions.md). Example: "your notice period?" asked in chat
  is also `questions.py add fact "What is your notice period?" key=notice_period job=J7`.
- Fact answers (residence, citizenship, work permit, notice period) come only from the records: a prepared answer
  is changed only by the records or the person, never from memory. Example: the record says resident in Spain and
  Italy, so "resident in Spain: Yes" stays.
- At each turn on a search day: `usage.py run-due`. "due" (example: the scheduled session stood aside while this one
  was active): this coordinator starts a fresh session for today's run at once ("Run /cenk-jobs:coordinate for
  today's run."), never runs it itself: a run inside a long coordinator cost 1.4M tokens on 16 Nov. A turn the app
  will not let start a session (one a message or a trigger started) proposes it as a card and names it in Do now. A
  message from the scheduled session saying the run is due is checked the same way.
- A finished search's questions go to the person at once, in one ordered list (the order of "Answer first"), even
  while another task is open; they never wait for that task to end.
- Runs in the main folder and is titled **Job search coordinator**: only the person's own main session, started in
  their main folder by them or by the schedule. A development or test session that loads this skill keeps its own
  title and writes no record. It tells the person, at the start of each run, that this is their main session
  (RULES.md, "One main session").
- Before it writes any record: `sessions.py lock <its own local_... id>`; again before each later step that writes
  (it refreshes the beat); `sessions.py unlock <id>` at the end. Refused (another coordinator's beat within 30
  minutes): it writes nothing, asks that coordinator to write its handoff and stop (as in the handoff check), and
  takes the lock once it is free. A scheduled run refused this way sends the holder one message instead: "Today's
  scheduled run is due: usage.py run-due", and ends. Also `list_sessions`: another running "Job search coordinator" in the same folder
  is the same case. Example: a test coordinator started while the person's own one runs waits for its handoff.
- **Is the only writer of the shared records**: `TRACKER`, `PIPELINE`, `LOGINS`, `SESSIONS`, `MASTER_RECORD`,
  `QUESTIONS`, `EMPLOYER_RULES`, `EMPLOYER_CHECKS`, `USAGE_LOG`, the application folders (through
  `build_app_folders.py`), the calendar category, the dashboard and the Questions page. Sub-sessions report; the coordinator records. Why: the files sync through Google Drive, and two
  sessions writing one file lose each other's changes.
- The person's profile is not a shared record: any session saves a fact about the person there at once, by
  compare-and-set (`profilelib.py set`, RULES.md "Keep learning about the person"), and its handoff names the key.
- Never changes the plugin and never starts a session in its repository (RULES.md, "The plugin's own files"): a
  lesson is one line in `plugin-lessons.md`, a sub-session's lesson too, and the new lines go in one message to the
  session titled "Coordinator · workbench" when one is open.
- Each run: "run started", the handoff check, the shared-list update, `check_setup.py --needs`, the health check, then the pieces of the day (`/cenk-jobs:schedule` lists the order),
  one sub-session per piece; "run finished" and the short report at the end.
- Each run, before the pieces: read the Questions page's answers and record them (`questions.py record`, RULES.md
  "Questions for the person"), then `build` and write the page in the same turn, so the jobs they free go on in this
  run and the page shows them done; act on each "act on" line; bring up every "Discuss" in the chat. After
  the pieces: add the run's new questions to the page (`questions.py build`).
- Each run, after the handoff check: `employer.py shared-update` (a dry run), its `ask` items to the Questions page,
  then `employer.py shared-update --apply`; each `updated` item is one line in the run report (RULES/employers.md,
  "Shared list updates").
- After every change that can move an employer's verdict (the person's rules, a decision, a sync, a shared-list
  update): `employer.py recheck-running`, and each employer it lists goes to the person (RULES/employers.md, "Running
  applications").
- Urgent steps (RULES.md): when a report names one, add the job's Urgent to-do (`track.py todo <id> add urgent
  "<what to do>" where=pc`, or `where=phone`) and remove it once done or expired; the sub-session already sent the
  notification. At the end of each run, one notification for deadlines today or tomorrow.
- Each run, after the health check: the calendar check (RULES/hiring-steps.md, "Calendar"). After each dashboard
  refresh: every `check:` line of the export is fixed, or named in the run report (RULES/run.md, "Dashboard").
- The dashboard is checked by `export_dashboard.py --check`, not by reading its tabs: a page is opened only when a
  check line names something the page shows wrong, or the person reports one. The Calendar tab is compared by the
  calendar check (RULES/hiring-steps.md, "Calendar").
- Variants (`variants.py`, off unless the person turned them on): at "run started", `variants.py current` names the
  run's variant; log it (`usage.py log run started "<how>" variant=<name>`) and pass `variants.py models` to the
  workflow. The run report's last line: `token_report.py --days 1` for the run's W, and, from the run 7 days back,
  `variants.py count`.
- A hiring step that is done: `"done": "<date>"` on its `PIPELINE` step, and what is awaited next as a to-do.
  Example: `track.py todo J1 add waiting "feedback on the take-home"`.
- A CV rebuilt while forms are filled and not sent: tell every session that holds one to upload the new file again,
  and to correct the same wording in its essays, before any Submit.
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
- Keeps the sessions record (`SESSIONS`), which the dashboard's Answer first rows and Sessions tab read. After
  every start, change of state and handoff: save the app's session list as a file (`list_sessions`, limit 200,
  archived included: it lists 20 by default), `sessions.py sync <file>`, then `sessions.py set <name>
  state=you|ready|done waits="<what it waits on>" jobs=<ids, the one in hand first> due=<a fixed date>
  tab=yes|no steps=<n>` (`tab`: it holds a filled form open in a browser tab; `steps`: the person's steps left to
  finish). `sessions.py show` gives the order to answer them; `sessions.py order <name> ...` overrides it.
  Example: `sessions.py set apply-acme state=you waits="your yes to send 2 forms" jobs=J1,J2 tab=yes steps=1`.
- A sub-session's title starts with its state and follows it at once: "You · " (waits on the person's answer or
  study), "Ready · " (goes on alone), "Done · " (its jobs are sent or rejected, or its step is past; recorded;
  archived by `ARCHIVE_SESSIONS`). The record's state comes first; `sessions.py show` names each title to set.
  Example: "You · Acme open questions" becomes "Done · Acme open questions" when both forms are sent.
- The person may answer a session's one-line question in this chat: forward their words, quoted, to that session
  (a message to its id). Essays and study stay in their own session. Example: "yes, send both" goes to `apply-acme`
  as: The person wrote: "yes, send both".
- New sessions start with `SESSION_MODEL` when it is set (`start_session`'s `model`). The app takes the main
  session's model or a cheaper one and ignores a higher one: then say so to the person.

## Pieces

One sub-session per piece, started with the session tool (`start_session`): fresh context, the same main folder, a
short name, and a brief that stands alone: the jobs by company and role (and their ids), the CV and letter files,
the answers from `MASTER_RECORD` it needs, the rules above, the script path (`<plugin>/scripts`), and the handoff it
must end with.

If the app will not start a session (a turn that another session or a trigger started), propose the piece as a
card the person starts with one click. When a sign-in would expire before then, run the piece as a subagent inside
the coordinator session, with the same brief and report: it submits by `ASK_FIRST` (with `send` it stops at the
review page and the go-ahead is forwarded to it by message).

| Piece | What the sub-session does | Example name |
|---|---|---|
| Apply | One `cenk-jobs:applier` subagent per application, started together, one tab each: fills the form and submits by `ASK_FIRST` (with `send`: after the forwarded go-ahead), reports. At most `APPLY_PARALLEL` at once, never two on the same site. A form that needs the person live: a sub-session with `/cenk-jobs:apply`. | `apply-acme` |
| Prepare one step | `/cenk-jobs:prepare` prep notes for one hiring step, in its own folder. | `prep-acme-18nov` |
| Study for one step | `/cenk-jobs:prepare` studying: brief, weak points, practice, with the person. | `study-acme-6nov` |
| Search sweep | `/cenk-jobs:search`; one row per posting. | `search-2026-11-06` |
| Essays round | The person studies a site's open questions and writes the answers in their own words; the session gives facts from the record and feedback where the employer's rules allow. Feedback aims at a calm, experienced voice: no essay words, no selling the employer's own product ("I led two migrations like yours", not "I am passionate about your innovative platform"). | `greenhouse-answers` |

With the person's setting `draft_answers` set to `yes`, the essays round drafts each answer in full for their
approval, and fixes the English of a text they wrote at once (RULES.md, "Honesty and what Claude never does").

An essays round, and every session that drafts answers for a form, checks that the posting is still open at the
start of the session and again before each round of approvals, not only before filling. Approved answers of a
posting that closed are kept in that job's prepared answers, each with its question and date, for reuse.
Example: six essays approved over two days; the posting closed on the first day: the check before the second round names it.

In progress: a piece in a sub-session has its jobs in the sessions record (`sessions.py set <name> jobs=<ids>`), not
in to-dos. Work inside the coordinator (a subagent) gets a `working` to-do on each job, removed when its report is
recorded. Example: `track.py todo J1 add working "Claude: filling the Workday form; wait"`. A to-do that belongs to
a session names it by id (`session=<id>`), never by its title.

Limits: at most `APPLY_PARALLEL` (default 2) sessions or subagents use the browser at once, each only in tabs it opened. A piece that needs a file
outside its own step folder or `apply/bodies` / `apply/letters` asks the coordinator first.

## The handoff every sub-session ends with

Written to `handoffs/<short name>.md` in the main folder, as fact lines, then one line to the coordinator and stop.
Nothing the records already hold: a link instead. One block per job, by company and role: status (`submitted`, `needs-person`, `account-needed`, `skipped`, `closed`,
`failed`); what was sent (CV file, letter file); the fields answered on the form, by name only (their values are in the records); new facts the person stated (one fact
line each; a fact about the person themselves is already in the profile: only its key, such as `person.phone`); hiring steps or deadlines seen (date, time, name, link); sign-ins seen; employee reviews looked up
(employer, rating, number of reviews, complaint topics, source). Nothing else.

The coordinator records it: `track.py set`, `PIPELINE`, `MASTER_RECORD`, `logins.py set` and `sync`, `employer.py
record`, `environment` or `decide`, `usage.py log`, `build_app_folders.py`, calendar events, the `working` to-do
removed, the session's state and title (`sessions.py set <name> state=done`), and the dashboard refresh.

## Ending

- A sub-session ends once its handoff is recorded: the coordinator archives it (`ARCHIVE_SESSIONS`: `yes` without
  asking, empty when the person agrees).
- Every run ends with `handoffs/job-search-coordinator.md`: what is open, what waits on the person, what is next,
  and every sub-session still open, one line each: id, state, what it waits on, its handoff file. Example:
  `local_ab12 | idle | waits on the Workday sign-in | handoffs/apply-acme.md`. Before it, each open sub-session
  writes or updates its own handoff file (the message of the handoff check, step 2). An older
  `handoffs/coordinator.md` is read once by the next handoff check, like any other file there.
- The run ends with a short report: what was sent, what waits on the person (Do now, and how many questions are
  open on the Questions page), what is planned next, and the two links (`DASHBOARD_URL`, `QUESTIONS_PAGE`), so the
  person never has to look for them.
- The scheduled run is its own session, the day's coordinator (`/cenk-jobs:schedule`). By hand: this skill. The records
  and `handoffs/` hold everything a new one needs.
