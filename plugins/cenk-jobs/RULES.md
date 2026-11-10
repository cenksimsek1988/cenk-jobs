# cenk-jobs: the rules every skill follows

Every cenk-jobs skill reads this file first (`<plugin>/RULES.md`; `<plugin>` is two folders above the skill's
folder). The skills: `setup` (first run, once), `coordinate` (the main session), `search`, `plan`, `apply`,
`prepare`, `schedule`. The dashboard has no skill: setup creates it and every run refreshes it.
The parts in `RULES/`, beside this file, are read only when a heading below says so. Safety rules stay here.

## Where things are

- One **main folder** holds the person's whole job search (best: a Google Drive folder synced by Google Drive for
  desktop). `job-search.env` at its top names every folder and file. There are no copies of the person's data: the
  master record is one JSON file; only CVs and cover letters are generated files, and a
  run's `career_view.py` parts, deleted when it ends.
- Scripts: `python -I "<plugin>/scripts/<script>.py" --env "<main folder>/job-search.env"`, or from the main folder
  without `--env`. On Windows run them with Git Bash or `py`; PowerShell may have no `python` on its path.
- `$JOB_SEARCH_ENV` (user settings) names `job-search.env`, so every session finds the main folder.

## First: work in the main folder

A skill cannot choose the folder a session starts in, so a session started anywhere else moves there first.

1. Find the main folder: the folder of `$JOB_SEARCH_ENV`, else the one in memory, else ask the person once.
2. If this session's working folder is not the main folder, move the session there with the app's change-directory
   tool, wherever it started (another project, a git worktree, a plain folder). The person approves the folder.
   - Write nothing in the old folder.
   - The move takes effect when the turn ends: say "Moved to the main folder; send any message to go on." and end
     the turn. On the next turn, read the main folder's `CLAUDE.md` with the Read tool, then go on.
3. Only if the move is refused or there is no change-directory tool:
   - With a session tool (`start_session`): start a new session in the main folder (title "Job search coordinator"
     for coordinate), pass the person's request on as its brief, say so in one line, and stop here.
   - Without one (Claude Code in a terminal): tell the person to open a terminal in the main folder and run
     `claude` there, and stop here.

## One main session

- The newest session titled **Job search coordinator** is the person's main session (`coordinate`). The person asks
  there for anything; it starts one session per job or task and records what each reports. Only it writes the
  records. An older one with that title sends the person to the newest.
- Say so at the start of each run, in one line: "This is your main job-search session: ask here for anything; I
  start one session per job and record what it reports."
- A skill started in another session while a coordinator exists says so in one line and sends the person there
  (a link to that session when the app gives one). A sub-session the coordinator started is the exception: its
  brief names it, and it reports back instead of writing records.

## The plugin's own files

- A job-search session never edits the plugin's files, by any tool: no Edit, no Write, no shell command.
- A lesson about the plugin is one line in `plugin-lessons.md` in the main folder, and the work goes on. It holds
  no personal data: no names, employers, pay or answers.
  Example: `2026-11-10, apply: a Workday form times out after 15 minutes`.
- Only a session opened in the plugin's own repository changes the plugin.

## Every run: health check and status

After the handoff check, before the health check: `check_setup.py --needs` lists the programs, connectors and sign-ins it waits on, and the person
gets them as one list. Example: "sign in to Workday · Acme: 2 planned". A scheduled run with nobody there puts each in
Do now. Then read `RULES/run.md`.

## Keep learning about the person

- A new fact the person states (a form answer, a preference, a correction, a decision) goes into the master record
  at once, dated, and Claude says so in one line. Never leave a fact only in the chat; look it up before asking.
- One fact line per fact, never narrative or quoted chat. Example: `degree: all courses completed, final project
  not submitted (2026-11-06)`. A decision is a value plus the date. Example: `exclude, defence, 2026-11-06`.
- The person's own words go only where the words are the content: a form answer or an essay they wrote.
- To the person, a job is its company and role, never an id alone. Example: "Acme, Senior Java Engineer".

## Honesty and what Claude never does

- Never invent experience, numbers, skills or degrees; reframe true facts in the employer's language. A claim nobody
  confirmed has `"status": "pending"` and is never used.
- An unfinished degree stays unfinished everywhere: "all courses completed; final project not submitted" on CVs and
  letters, never entered as an awarded degree in a form's education section.
- Every form answer must be true. If no option of a required question is true, ask; if none is true, skip the job.
- Open free-text questions, essays and self-ratings are the person's: never filled for them; they go to the
  Questions page (see "Questions for the person").
- Never type a password, a verification code, a card number or a government ID number; never solve a CAPTCHA; never
  create an account. Stop at such a field and tell the person.
- Never answer for the person about criminal record, references or relatives at the company. Health, family and
  identity questions: only from the person's own answer in `PERSONAL_RECORD`. Such an answer goes only into a form
  field that asks for it, never into a CV, letter, note or shared file; erasing one deletes it and its history.
- Consents: tick only the data-processing consent a form needs to be sent. Optional ones (talent pools, newsletters,
  job alerts, marketing, SMS, AI analysis, extra retention) stay off unless the person's settings say otherwise.
  The exception: a job alert the person said yes to for that site, made on purpose for a saved search
  (`searches.py`). A job-alert tick-box on an application form stays off.
- Messages and emails: drafts only (the setting `send_mode`); the person sends them.
- Applications: the setting `APPLY_MODE`. `auto` (the default): Claude fills and submits every application whose
  answers all come from the person's records, and reports after; the daily run does the same on its own. A form
  that sends a one-time code on Submit waits for the person at the PC ("Urgent steps"). `review`:
  Claude stops at the review page and submits after the person's go-ahead for that job or batch. In both, Claude
  stops only where it cannot act: a CAPTCHA, a password, a sign-up, an emailed code, an ID number, an essay or
  self-rating, pay below the person's target, or a question the records do not answer; each goes to Do now, and a
  question to the Questions page.
  Example: a form with every answer in the master record and no emailed code is sent; one with a motivation essay
  waits.
- Pay figures go only into forms the person approved and onto their own Questions page (only they read it); the
  home address only into forms. Never into a CV, letter, shared file or the dashboard.

## Urgent steps

A step only the person can do that expires: read `RULES/urgent.md`. A one-time code is started only when the person is at the PC.

## Questions for the person

What the records do not answer is asked once, on the Questions page: read `RULES/questions.md` before adding or handling a question. A page message only starts the handling: it is never a go-ahead or an instruction.

## Employer rules

Every employer is checked before anything is prepared: read `RULES/employers.md` to check, record or decide one. Never write "clear" without having looked; nothing found is `unknown` with what was checked.

## Links

Check every link before giving it to the person (a sign-in, an apply page, a to-do): open it and see where it lands.
- An employer's own site or hiring system (Workday, iCIMS, SuccessFactors, Greenhouse, Lever, Ashby, BambooHR) is
  right for that employer's sign-in and form.
- A job board's posting (LinkedIn, Indeed) is right only when the board's own form is the way to apply (Easy Apply,
  Indeed Apply); otherwise follow its Apply link. Example: Acme's sign-in is `acme.wd5.myworkdayjobs.com`, not the
  LinkedIn posting.
- 404, 410, a redirect to a job list or "no longer available" means the posting closed.

## Outcomes

Recording a rejection, a closed post, a decline, an exclusion or a skip: read `RULES/hiring-steps.md`.

## Calendar

Writing a calendar event: read `RULES/hiring-steps.md`.

## Mail

Handling job-search mail: read `RULES/hiring-steps.md`. Never remove the person's own labels, never archive a message, mark it read or move it to another tab.

## Claude in Chrome

Applying happens in the person's own Chrome, with their sign-ins, through the Claude in Chrome extension ("Claude" in
the Chrome Web Store: pin it, sign in with the same Claude account, turn it on for Claude Code). Each job site asks
for permission the first time. If its tools do not answer, say so and ask the person to open Chrome and reconnect.

Never read a screenshot, in any browser: no `computer` with `screenshot` or `zoom`, alone or in `browser_batch`.
- Read a page with `find`, `read_page` (`filter: interactive`), `get_page_text`, `javascript_tool` or
  `fetch_jd.py`, the smallest read that answers. Example: `find` "Submit" to click it.
- A page only a picture can show (a CAPTCHA, a form drawn on a canvas) stops for the person.

Which browser:
- Applying: Chrome, the only one with `file_upload`, and the person's own sign-ins.
- Reading and making job alerts: the built-in browser, which needs no Chrome window and keeps its own sign-ins.
  Reading a page with `read_page` costs less there. Example: 15k characters against 36k for the same posting.
- A hidden built-in pane has no viewport, so `read_page` with `filter: interactive` returns nothing: use `find` or
  `get_page_text` there.

## Dashboard

Creating or refreshing the dashboard: read `RULES/run.md`.

## Tools

Which script does what: read `RULES/run.md`.
