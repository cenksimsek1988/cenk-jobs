# cenk-jobs: the rules every skill follows

Every cenk-jobs skill reads this file first (`<plugin>/RULES.md`; `<plugin>` is two folders above the skill's
folder). The skills: `setup` (first run, once), `coordinate` (the main session), `search`, `plan`, `apply`,
`prepare`, `schedule`. The dashboard has no skill: setup creates it and every run refreshes it.

## Where things are

- One **main folder** holds the person's whole job search (best: a Google Drive folder synced by Google Drive for
  desktop). `job-search.env` at its top names every folder and file. There are no copies of the person's data: the
  master record is one JSON file; only CVs and cover letters are generated files.
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

- The session titled **Job search coordinator** is the person's main session (`coordinate`). The person asks there
  for anything; it starts one session per job or task and records what each reports. Only it writes the records.
- Say so at the start of each run, in one line: "This is your main job-search session: ask here for anything; I
  start one session per job and record what it reports."
- A skill started in another session while a coordinator exists says so in one line and sends the person there
  (a link to that session when the app gives one). A sub-session the coordinator started is the exception: its
  brief names it, and it reports back instead of writing records.

## Every run: health check and status

1. Say when the run starts: "Job-search run started at 21:05 (by hand); I'll tell you when it's done." Log it with
   `usage.py log run started "<by hand|scheduled>"`. At the end: "Run finished at 21:40." plus the short report,
   and `usage.py log run ok` (or `failed` / `stopped`). The dashboard header shows the run's state from these rows.
   "Run my job search now" starts a run at once; if one is running (a "run started" row with no end), say so instead.
2. `check_setup.py`: fix or report each FAIL in one line.
3. Each connector, one cheap read call: Gmail `search_threads` (`pageSize` 1), Google Calendar `list_calendars`,
   Google Drive (the main folder readable on disk, or the Drive connector), Claude in Chrome `tabs_context_mcp`.
   Record each: `logins.py set <id> connected|needs-reconnect "<what you saw>" kind=connector name=<Name> fix=<how>`,
   then `logins.py sync`. `LOGINS` is the one place login state lives.
4. The dashboard: `DASHBOARD_URL` set and readable. If not, create it now (see "Dashboard").

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
- Open free-text questions, essays and self-ratings are the person's: never filled for them; they wait in Do now.
- Never type a password, a verification code, a card number or a government ID number; never solve a CAPTCHA; never
  create an account. Stop at such a field and tell the person.
- Never answer for the person about health, criminal record, references or relatives at the company.
- Consents: tick only the data-processing consent a form needs to be sent. Optional ones (talent pools, newsletters,
  job alerts, marketing, SMS, AI analysis, extra retention) stay off unless the person's settings say otherwise.
- Messages and emails: drafts only (the setting `send_mode`); the person sends them.
- Applications: the setting `APPLY_MODE`. `auto` (the default): Claude fills and submits every application whose
  answers all come from the person's records, and reports after; the daily run does the same on its own. `review`:
  Claude stops at the review page and submits after the person's go-ahead for that job or batch. In both, Claude
  stops only where it cannot act: a CAPTCHA, a password, a sign-up, an emailed code, an ID number, an essay or
  self-rating, pay below the person's target, or a question the records do not answer; each goes to Do now.
  Example: a Greenhouse form with every answer in the master record is sent; one with a motivation essay waits.
- Pay figures and the home address go only into forms the person approved, never into a CV, letter, shared file or
  the dashboard.

## Employer rules

Every employer is checked before anything is prepared, in eight shared categories: ties to Israel's occupation or
military, defence industry, animal cruelty, climate and environmental harm, sexism, human rights, working
conditions, and sanctions (the UN Security Council list plus the lists the person follows, in `lists`). The
person's own filters are extra categories (`"custom": true`). A category counts only with a crime-level problem:
credible news from established outlets, a court ruling, a fine, a sanctions listing or an official list, each with
its source link. A tie is direct (the employer, its group or its majority owner) or indirect (a minority investor,
an investor's other holdings, a partner or a customer).
- **What happens** is the person's choice per category, in `EMPLOYER_RULES`: direct `never` / `ask` (default) /
  `apply`; indirect `ask` (default) / `warn` / `apply`; or a whole category allowed. They change any of them by
  saying so ("never apply to defence companies", "indirect ties are fine there, just warn me"): write it there at
  once, with `{date, field, new}` in `changes`.
- **One list** of the person's employers: `EMPLOYER_CHECKS`, each employer with its findings and the person's
  decisions (`employer.py decide "<name>" <exclude|apply> [<category>] [--group]`; `--group` also covers the group's
  units: "Acme" covers "Acme Cloud Services"). No separate name lists: an older `never_apply` / `always_ok` in
  `EMPLOYER_RULES` moves there with `employer.py migrate-lists`. Every exclusion shows the finding behind it.
- **The Israel check, two steps**, for the employer and its parent or majority owner:
  1. Lists: the BDS movement's current targets (bdsmovement.net, "What to boycott"; past successes do not count),
     the UN OHCHR settlement-business database (latest edition), Who Profits, AFSC Investigate.
  2. Four questions from the company's own site, careers page or annual report, each answered with a source link:
     founded in Israel or headquartered there? its own office, R&D team or subsidiary in Israel (example: "Tel Aviv"
     on its careers page)? its majority owner (then step 1 on the owner)? supplying Israel's military or police, or
     the settlements?
  A list hit or a yes is a direct tie. Indirect ties: a reseller or shop selling the brand in Israel, a minority
  investor's other holdings, customers, a board member's outside seat, a licensee's owner. For a small or new brand,
  find the parent or majority owner first (company registry, the site's legal notice). Nothing found after both
  steps is recorded as `unknown` with the fact "nothing found: <what was checked>", never `clear`.
- `employer.py check "<name>"` shows what the shared blacklist and the person's earlier checks know, and the verdict.
- When a category says ask, tell the person what was found, with the source, and ask: apply, or never? Record it
  with `employer.py decide "<name>" <exclude|apply> [<category>]`.
- A category not checked stays "unknown"; never write "clear" without having looked.
- Record every finding as found, direct or indirect, whatever the person decides: a decision never turns a finding
  into "clear", and never changes its category or level. The shared list holds findings only (category, level,
  fact, source); decisions and settings stay in the person's own files. The shared blacklist keeps every sourced finding, so each person's own rules decide. The plugin's
  developer merges their own findings with `employer.py merge --from-checks`; everyone else's reach it through the
  weekly usage report, with their yes.
- An excluded employer the person applied to, once it writes beyond an automatic confirmation (an invitation to a
  step, a task or test, a recruiter's mail) or offers a job: draft the withdrawal mail from
  `templates/withdrawal-email.txt`, with the employer's sourced fact, so it reads why (a Gmail draft; the person
  sends it). The same when a new check excludes an employer whose process is running. Example: invited to online
  tasks, then a direct tie is found: a draft naming the source.
- A draft always has a recipient. A no-reply sender: the recruiter named in the mail, else the careers contact on the
  employer's own site (example: `careers@` on its FAQ page), else the privacy contact on the posting; check each on
  its page, never guess an address. An employer kept only for practice, or one that already rejected the person,
  gets none.

## Links

Check every link before giving it to the person (a sign-in, an apply page, a to-do): open it and see where it lands.
- An employer's own site or hiring system (Workday, iCIMS, SuccessFactors, Greenhouse, Lever, Ashby, BambooHR) is
  right for that employer's sign-in and form.
- A job board's posting (LinkedIn, Indeed) is right only when the board's own form is the way to apply (Easy Apply,
  Indeed Apply); otherwise follow its Apply link. Example: Acme's sign-in is `acme.wd5.myworkdayjobs.com`, not the
  LinkedIn posting.
- 404, 410, a redirect to a job list or "no longer available" means the posting closed.

## Outcomes

| Category | When | Recorded as |
|---|---|---|
| rejected | the employer said no to the person | `PIPELINE` stage `rejected`, date, reason |
| closed | the role closed, was filled or put on hold, or the person was late: not a rejection | sent: `PIPELINE` stage `closed`; not sent: `track.py set <id> closed` |
| declined | the person said no at some step | sent: `PIPELINE` stage `declined`, `why` (ethics, relocation, pay, other), for ethics the `category` (example: `human_rights`); not sent: `track.py set <id> declined` |
| excluded | the employer rules exclude the employer | `track.py set <id> excluded` |
| skipped | the screen: the posting does not fit the rules | `track.py set <id> skipped` |

Examples: "the position has now been filled" is closed; "we will not move forward with you" is rejected.

## Calendar

Every job-search event carries the category: color `CALENDAR_COLOR` (3 = Grape) and, on events the person owns, the
title prefix `CALENDAR_PREFIX` ("Job search · ").
- A company's invitation already in the calendar: only set its color (`update_event`, `notificationLevel` NONE).
- Otherwise create the event (a deadline: all-day, free, reminders 3 days and 1 day before), with the job id and
  step in the description (`[job-search: <id> step <n>]`).
- Every event the person owns holds the step's own link (meeting, test, booking, interview page) and the email's
  Gmail link; the same two go into the step's `link` and `mail` in `PIPELINE`.
- An online interview without a video link: draft a request for it to the recruiter the day before (a draft).

## Mail

A job-search message whose action is done gets the Gmail label `GMAIL_DONE_LABEL` (default `cenk-jobs/Done`).
- Done: the step is booked and in the calendar, a deadline is in the calendar, a rejection, closed post or
  confirmation is recorded, or the person's reply is sent (the thread has their sent reply after it).
- Not done: a reply draft not sent yet, a CAPTCHA, a sign-in or an answer only the person can give. The message
  stays unlabelled and its to-do stays in Do now.
- Label the message (`label_message`), never the thread: a new reply in the same thread arrives unlabelled.
- Search for new work with `-label:"<GMAIL_DONE_LABEL>"`. Example: `newer_than:3d -label:"cenk-jobs/Done"
  (interview OR availability OR assessment)`.
- Gmail's list shows a thread with the label when any of its messages has it; a new reply shows there as unread.
- Setup creates the label (`create_label`, purple; parents are created with it). Missing at a run: create it.
- Never remove the person's own labels, never archive a message, mark it read or move it to another tab.

## Claude in Chrome

Applying happens in the person's own Chrome, with their sign-ins, through the Claude in Chrome extension ("Claude" in
the Chrome Web Store: pin it, sign in with the same Claude account, turn it on for Claude Code). Each job site asks
for permission the first time. If its tools do not answer, say so and ask the person to open Chrome and reconnect.

## Dashboard

A private page: **Do now** (In progress first: Claude or a session is on it; then sign-ins, answers only the person
can give, tasks with a deadline), **Calendar** (live from Google Calendar), **Logins**, **Hiring steps** and **All
applications**, under the total count and the split by outcome.
- Setup creates it from the Artifact "Dashboard" type (quickstart, intent "other"): upload the five files from
  `export_dashboard.py <out dir>`, write the store documents as in `templates/dashboard/datasets.json` and
  `files/index.html` from `templates/dashboard/index.html`, put its link in `DASHBOARD_URL`, then offer once to pin
  it ("Artifacts > Job applications > Pin"; pin on the person's yes).
- Refresh after each change: `logins.py sync`, `build_app_folders.py`, export, upload the five files, update each
  dataset's `source.url` and `updated`, delete the replaced uploads.
- Logins: each person's own sites and connectors live in their `LOGINS` file; the Logins tab groups them in this
  order: Needs you (needs sign-up, expired, needs sign-in, reconnect, blocked), Signed in, Connected, Not signed in,
  Excluded. `sync` makes a new site row "needs sign-in"; Claude sets `needs-sign-up` (no account yet), `expired` (a
  sign-in page where a form was) and `excluded` (an employer the rules exclude) with `logins.py set`. Example: a
  Workday form at Review, then its sign-in page: `expired`.
- A site no job waits on keeps its last state, with the reason in its note: signed in, or not signed in. Never
  "unknown". Example: a site whose offer closed: `signed-in`, note "no open job: the offer closed".
- Every employer the person turned down for their rules is an "excluded" row, rebuilt by `sync` with its reason in
  words and its jobs by role, so the person remembers it.
- A job's own to-do items: `todo` in the tracker, `[{"kind": "working"|"task"|"click"|"info", "text", "link",
  "due"}]`. `working`: Claude or a session is on it; set when a piece starts, removed when its report is recorded.
- A to-do's link is the email link; a personal access link (a page that opens without a sign-in) stays in the
  calendar and the person's folder. Pay figures and addresses never go into the exported files.

## Tools

| Script | Does |
|---|---|
| `check_setup.py` | health check of the env file, folders, master record, CV versions, tracker and the dashboard key |
| `init_career_folder.py` | creates the main folder and `job-search.env` for a new person (never overwrites) |
| `build_cv.py` | builds every CV PDF from its JSON (`--no-photo` for employers that ask for none) |
| `make_letter_pdf.py` | builds one cover letter PDF from a body file, on the day it is sent |
| `track.py` | tracker: add, set, show, brief, list, summary, sync (merges a screening run) |
| `build_app_folders.py` | rebuilds the application folders; never deletes what the person or Claude wrote |
| `fetch_jd.py` | saves a posting's full text as `job-description.md` |
| `logins.py` | login state: set, sync, show |
| `export_dashboard.py` | exports the dashboard's files: index, applications, steps, actions, logins |
| `employer.py` | employer checks: check, record, decide, import-tracker, merge |
| `usage.py` | usage log (steps and runs) and the weekly usage report (due, report, mark-drafted) |
| `trackerlib.py`, `employerlib.py` | shared code for the scripts above |
| `workflows/screen-and-prepare.js` | Workflow: screens a batch of employers and prepares the cleared jobs; never submits |

Older records: the scripts also read a tracker kept before the plugin (`{companies: [...]}`). Optional keys:
`TRACKER_SETTINGS`, `REDACT_FILE` (private text replaced in every application file; keep it outside shared folders),
`SENT_CVS_DIR`, `SENT_CVS_BEFORE_DIRS`, `SEARCH_TIME` (the scheduled run's time, default 19:00).
