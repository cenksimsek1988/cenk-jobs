---
name: coordinate
description: "The main job-search session: owns the records, dashboard and decisions, runs the daily search, starts one sub-session per piece of work. Use for 'coordinate my job search', 'start the job search coordinator', 'run my job search now', 'open a session for this job'. Long work goes to sub-sessions."
---

# Coordinate: the main session

Read first the shared coordinator rules: the path `profilelib.py coordinator` prints (Bash tool), which is
`$CENK_BASE/references/coordinator.md` (cenk-base 0.2.0 or later). They hold one coordinator per folder, the
titles, briefs, questions, quoted go-aheads, messages, hand-off files and archiving; this skill adds only the job
search. Exit 1 (cenk-base missing or older): handle it as step 0 of the handoff check.

Then `../../RULES.md`: its rules (honesty, consents, never an ID number, password, verification code or
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
ended or is ending; create it if missing. This check is the job search's take-over (shared rules, "One
coordinator"): the new coordinator writes no other record until the older one's handoff is recorded and it is
archived. A scheduled run reaches the older one's sub-sessions by message and restarts none.

0. The base plugin: `profilelib.py coordinator` (Bash tool). Exit 1: stop here, write no record, and tell the
   person in plain words with the line for their terminal, then a new session. "cenk-base is not loaded":
   `claude plugin install cenk-jobs@cenk` (or `@<the marketplace they installed from>`; a plain `claude plugin
   update` does not bring the base). "coordinator.md is missing" (cenk-base older than 0.2.0): `claude plugin
   update cenk-base@cenk`. A scheduled run puts the same line in Do now and ends.
1. List the open sessions in the main folder (`list_sessions`, this session left out).
2. A session active since the previous "run started" row in `USAGE_LOG` (at the first check: every session): one message (`SendMessage` to
   its `local_...` id): "Write your handoff to handoffs/<short name>.md, then stop." A running session finishes first.
3. Read every file in `handoffs/`, oldest first. Each fact goes into its record, as in "The handoff" below; each
   open item into the job's to-dos (`track.py todo`) or the Questions page.
4. Archive by the shared rules (`ARCHIVE_SESSIONS`), the older coordinator last; one the app will not archive, or
   one the person still uses, stays and is named in Do now.
   Example: a prep session whose interview is tomorrow stays.
5. Delete each recorded file: its facts are in the records now.
6. One line: "Read 4 handoffs; ended 3 sessions; kept 'Prep Acme' until the interview on 12 Nov."

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
- At each turn on a search day: `usage.py run-due`. "due" (example: the scheduled run did not start): this
  coordinator starts a fresh session for today's run at once ("Run /cenk-jobs:coordinate for today's run."), never
  runs it itself: a run inside a long coordinator cost 1.4M tokens on 16 Nov. A turn the app will not let start a
  session (one a message or a trigger started) proposes it as a card and names it in Do now.
- An apply session is never started from an automated turn (a message from another session or a trigger): it is
  proposed as a card, with one line saying so. Its forms may need the person, who may be away.
- A finished search's questions go to the person at once, in one ordered list (the order of "Answer first"), even
  while another task is open; they never wait for that task to end.
- Runs in the main folder and is titled **Job search coordinator**: only the person's own main session, started in
  their main folder by them or by the schedule. A development or test session that loads this skill keeps its own
  title and writes no record. It tells the person, at the start of each run, that this is their main session
  (RULES.md, "One main session").
- Before it writes any record: `sessions.py lock <its own local_... id>`; again before each later step that writes
  (it refreshes the beat); `sessions.py unlock <id>` at the end. Refused (another coordinator's beat within 30
  minutes): it writes nothing, asks that coordinator to write its handoff and stop (as in the handoff check), and
  takes the lock once it is free. A scheduled run refused this way takes over: it sends the holder one message ("Today's
  scheduled run takes over: write your handoff, unlock, reply 'handoff written' to <its id>, then stop."), ends
  its turn, and on the reply takes the lock and runs as the day's coordinator. Seen: 16-18 Nov the run stood aside
  and never ran. The holder that gets this message does just that, never a card. Example: a test coordinator started while the person's own one runs waits for its handoff.
- **Is the only writer of the shared records**: `TRACKER`, `PIPELINE`, `LOGINS`, `SESSIONS`, `MASTER_RECORD`,
  `QUESTIONS`, `EMPLOYER_RULES`, `EMPLOYER_CHECKS`, `USAGE_LOG`, the study notes (`INTERVIEW_LESSONS_DIR`), the application folders (through
  `build_app_folders.py`), the calendar category, the dashboard and the Questions page (a refresh session, below, writes only the pages). Sub-sessions report; the coordinator records. Why: the files sync through Google Drive, and two
  sessions writing one file lose each other's changes.
- The person's profile is not a shared record: any session saves a fact about the person there at once, by
  compare-and-set (`profilelib.py set`, RULES.md "Keep learning about the person"), and its handoff names the key.
- Never changes the plugin and never starts a session in its repository (RULES.md, "The plugin's own files"): a
  lesson is one line in `plugin-lessons.md`, a sub-session's lesson too, and the new lines go in one message to the
  session titled "Coordinator · workbench" when one is open.
- The Gmail step runs first in every run, right after the handoff check, and is never dropped for other work.
  Seen on 17 Nov: a day spent on applying left 15 rejections and an interview invitation unread.
- Each run: "run started", the handoff check, Gmail (`/cenk-jobs:prepare`, "Mail and calendar"), the shared-list update, `check_setup.py --needs`, the health check, then the pieces of the day (`/cenk-jobs:schedule` lists the order),
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
- A turn in which a script printed `pages behind` (any record change: a job submitted, skipped, rejected or closed, a
  new or done step, a to-do, a login, a question) ends with `export_dashboard.py --check`; when it names a page, both
  pages are refreshed in that turn, once, after all its records (RULES/run.md, "Dashboard"). Example: three handoffs
  recorded in one turn, one refresh. A refresh that writes a page template or uploads every file goes to a fresh
  session that writes only the pages; the coordinator refreshes nothing while it runs.
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
  `MASTER_RECORD` or asks the person, and records each new fact as a dated fact line. A forwarded go-ahead (a
  submission, an email, a term to accept) is quoted, never stored.
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
- Titles follow the shared rules; here "Done · " means its jobs are sent or rejected, or its step is past. The
  record's state comes first; `sessions.py show` names each title to set.
- Essays and study stay in their own session, never answered in this chat.
- New sessions start with the `SESSION_MODEL` that `choices.py show` prints (`start_session`'s `model`; default
  `sonnet`, also when empty), except an essays round and study for a step, which take the main session's model. The app takes the main session's model
  or a cheaper one and ignores a higher one: then say so to the person.
- A fresh coordinator per day: at the start of each turn the person's message started, never inside a run,
  `cost.py context`. "hand off" (it started before today, or its context is over `COORDINATOR_CONTEXT`, 200k by
  default): write `handoffs/job-search-coordinator.md`, `sessions.py unlock`, start a fresh session in the main
  folder ("Run /cenk-jobs:coordinate. The person asked: <their request, in a few words>."), tell the person in one
  line to go on there, with its link, and do nothing more here. Seen 6-18 Nov: one coordinator ran 12 days, its
  context up to 966k, and cost 241M W, half of all.

## Pieces

One sub-session per piece (`start_session`): fresh context, the same main folder, a short name. Its brief (shared
rules) names the jobs by company, role and id, the CV and letter files, the answers from `MASTER_RECORD` it needs,
`${CLAUDE_PLUGIN_ROOT}/RULES.md` and the skill it runs, the script path (`${CLAUDE_PLUGIN_ROOT}/scripts`), and
the handoff below.

Every long piece goes to a fresh session: searches, workflows, analyses, page-check rounds, publish-and-verify
rounds, and requests from other sessions. The coordinator records results and answers messages: a busy session
that does not answer within 20 s loses a message. Seen 19 Nov: three dashboard rounds in the coordinator, about
1 h, and 8 messages from another job session lost. A piece the app will not start (a turn a message started) is
a card or a question to the person (shared rules), never run in the coordinator's own context, a form whose
sign-in may expire included. Seen 18 Nov: search, a 39-agent workflow and an analysis ran inside the coordinator.
One exception: a scheduled run's own fresh session does its pieces as subagents (a trigger's turn may not start
sessions; `/cenk-jobs:schedule`).

| Piece | What the sub-session does | Example name |
|---|---|---|
| Apply | One `cenk-jobs:applier` subagent per application, started together, one tab each: fills the form and submits by `ASK_FIRST` (with `send`: after the forwarded go-ahead), reports. At most `APPLY_PARALLEL` at once, never two on the same site. A form that needs the person live: a sub-session with `/cenk-jobs:apply`. | `apply-acme` |
| Prepare one step | `/cenk-jobs:prepare` prep notes for one hiring step, in its own folder. | `prep-acme-18nov` |
| Study for one step | `/cenk-jobs:prepare` studying: brief, weak points, practice, with the person. | `study-acme-6nov` |
| Search sweep | `/cenk-jobs:search`; one row per posting. | `search-2026-11-06` |
| Essays round | `/cenk-jobs:write` with the person, one question or letter at a time: the company and role, their background and gaps, a draft in their voice, revised together. | `write-acme-why` |

An essays round, and every session that drafts answers for a form, checks that the posting is still open at the
start of the session and again before each round of approvals, not only before filling. Approved answers of a
posting that closed are kept in that job's prepared answers, each with its question and date, for reuse.
Example: six essays approved over two days; the posting closed on the first day: the check before the second round names it.

In progress: a piece in a sub-session has its jobs in the sessions record (`sessions.py set <name> jobs=<ids>`), not
in to-dos. Work in a scheduled run's subagent gets a `working` to-do on each job, removed when its report is
recorded. Example: `track.py todo J1 add working "Claude: filling the Workday form; wait"`. A to-do that belongs to
a session names it by id (`session=<id>`), never by its title.

Limits: at most `APPLY_PARALLEL` (default 2) sessions or subagents use the browser at once, each only in tabs it opened. A piece that needs a file
outside its own step folder or `apply/bodies` / `apply/letters` asks the coordinator first.

## The handoff every sub-session ends with

Written to `handoffs/<short name>.md` in the main folder (shared rules). One block per job, by company and role: status (`submitted`, `needs-person`, `account-needed`, `skipped`, `closed`,
`failed`); what was sent (CV file, letter file); the fields answered on the form, by name only (their values are in the records); new facts the person stated (one fact
line each; a fact about the person themselves is already in the profile: only its key, such as `person.phone`); hiring steps or deadlines seen (date, time, name, link); sign-ins seen; employee reviews looked up
(employer, rating, number of reviews, complaint topics, source); a study or after-a-step session's `Weak answers:`
lines (/cenk-jobs:prepare, "Study notes"); a `write` session's approved text: its job, question and file
(`handoffs/<short name>.answer.md`). Nothing else.

The coordinator records it: `track.py set`, `PIPELINE`, `MASTER_RECORD`, `logins.py set` and `sync`, `employer.py
record`, `environment` or `decide`, `usage.py log`, `build_app_folders.py`, calendar events, the `working` to-do
removed, the session's state and title (`sessions.py set <name> state=done`), and both pages refreshed (above). Each
`Weak answers:` line goes into its file in `INTERVIEW_LESSONS_DIR` (the folder and the three files created when
missing), and `roadmap.md` is kept in order: what to study next first. An approved text: `questions.py answer
<question id> --file handoffs/<short name>.answer.md` (after `questions.py add job "<question>" job=<id>` when the
page never asked it), then that file is deleted with the handoff.

## Ending

- A sub-session ends once its handoff is recorded: the coordinator archives it (`ARCHIVE_SESSIONS`: `yes` without
  asking, empty when the person agrees).
- Every run ends with `handoffs/job-search-coordinator.md` (the coordinator's hand-off, shared rules): what is open,
  what waits on the person, what is next, and every open sub-session. Before it, each open sub-session
  writes or updates its own handoff file (the message of the handoff check, step 2). An older
  `handoffs/coordinator.md` is read once by the next handoff check, like any other file there.
- The run ends with a short report: what was sent, what waits on the person (Do now, and how many questions are
  open on the Questions page), what is planned next, and the two links (`DASHBOARD_URL`, `QUESTIONS_PAGE`), so the
  person never has to look for them.
- The scheduled run is its own session, the day's coordinator (`/cenk-jobs:schedule`). By hand: this skill. The records
  and `handoffs/` hold everything a new one needs.
- Last: `usage.py log run ok` (or `failed` / `stopped`), then `sessions.py unlock <id>`: a lock left behind holds
  the next coordinator for 30 minutes.
