# cenk-jobs rules: run

A part of `RULES.md`. Read when you run the health check, create or refresh the dashboard, or need a script's name.

## Every run: health check and status

After step 1: the handoff check and the shared-list update (`coordinate`), then `check_setup.py --needs` as one list to the person (RULES.md, "Every run"), with what step 3 finds.

1. Say when the run starts: "Job-search run started at 21:05 (by hand); I'll tell you when it's done." Log it with
   `usage.py log run started "<by hand|scheduled>"`. At the end: "Run finished at 21:40." plus the short report,
   and `usage.py log run ok` (or `failed` / `stopped`). The dashboard header shows the run's state from these rows.
   "Run my job search now" starts a run at once; if one is running (a "run started" row with no end), say so instead.
2. `check_setup.py`: fix or report each FAIL in one line.
3. Each connector, one cheap read call: Gmail `search_threads` (`pageSize` 1), Google Calendar `list_calendars`,
   Google Drive (the main folder readable on disk, or the Drive connector), Claude in Chrome `tabs_context_mcp`.
   Record each: `logins.py set <id> connected|needs-reconnect "<what you saw>" kind=connector name=<Name> fix=<how>`,
   then `logins.py sync`. `LOGINS` is the one place login state lives. Again before every dashboard export in the
   run: the export cannot call a connector, and names each one not checked since the run started in a `check:` line.
4. The dashboard: `DASHBOARD_URL` set and readable. If not, create it now (see "Dashboard"). The same for
   `QUESTIONS_PAGE` (see "Questions for the person").

## Dashboard

A private page: **Do now**, **Sessions**, **Calendar** (live from Google Calendar), **Logins**, **Excluded
employers**, **Hiring steps** and **All applications**, under the total count and the split by outcome.
- Do now, in this order: Urgent (a step only the person can do that expires); Answer first (one numbered row per
  session that waits on the person); In progress (Claude or a session is on it); then sign-ins, things to do, the
  Questions page's open questions (with its link) and tasks, a deadline first and a past one on top ("Past due":
  the person says whether it was done), then the longest wait first; last Claude's next (jobs that wait on nobody
  but Claude). Every open job has one owner there: the person, a session, the employer or Claude.
- Setup creates it from the Artifact "Dashboard" type (quickstart, intent "other"): upload the seven files from
  `export_dashboard.py <out dir>`, write the store documents as in `templates/dashboard/datasets.json` and
  `files/index.html` from `templates/dashboard/index.html`, and put its link in `DASHBOARD_URL`. Its name is
  "cenk-jobs · Job applications" (`dash/meta`), the Questions page's "cenk-jobs · Questions for you": the plugin's
  name, so a page is never just "Dashboard". Both are pinned to the claude.ai sidebar, one of the defaults setup
  offers.
- Refresh after each change: `sessions.py sync <list.json>`, `logins.py sync`, `build_app_folders.py`, export. Upload
  only the files its `upload:` line names, update each one's `source.url` and `updated`, delete the replaced
  uploads; a file under `unchanged:` gets only its dataset's `updated.at`. Then `export_dashboard.py --uploaded
  <out dir>`. Example: `upload: index.json actions.json` leaves five files as they are.
- Every export ends with one `check:` line per mismatch between the records and the page (`export_dashboard.py
  --check` prints them alone and writes nothing). Fix each in the same run, or name it in the run report. Example:
  `check: to-do on an ended job: J3 (rejected 2026-11-10), 2 to-do(s) -> track.py todo J3 done all`.
- Logins: each person's own sites and connectors live in their `LOGINS` file; the Logins tab groups them in this
  order: Needs you (needs sign-up, expired, needs sign-in, reconnect, blocked), Signed in, Connected, Not signed in.
  `sync` makes a new site row "needs sign-in" and marks an excluded employer's site `excluded` (not shown there),
  whatever its last state; Claude sets `needs-sign-up` (no account yet) and `expired` (a sign-in page where a form
  was) with `logins.py set`. Example: a Workday form at Review, then its sign-in page: `expired`.
- A row's state is what the last check found, with its time. A "connected" or "signed in" from before this run
  started reads "not checked since <time>" and is not counted as working: look again before a job needs it, and
  record what the page shows (`logins.py set`). Example: Greenhouse, signed in, last checked 6 Nov 08:10, on 13 Nov.
- A row whose note asks the person to sign in or to create an account is never `signed-in`: `needs-sign-in` or
  `needs-sign-up`. The export names such a row in a `check:` line.
- A site no job waits on keeps its last state, with the reason in its note: signed in, or not signed in. Never
  "unknown". Example: a site whose offer closed: `signed-in`, note "no open job: the offer closed".
- Excluded employers have their own tab, one row each, rebuilt at every export from the person's decisions, findings
  and tracker (`employerlib.excluded_list`): employer, Excluded or Withdrawn, why (category, by their decision or
  their rules), what was found, the source, the jobs, since when. Example: "Acme · Defence industry, your rules ·
  supplies drone parts to a national army (news, 2025) · Source".
  The tab shows the person's own decisions, which can reveal their views: the dashboard is shared only with people
  they choose, and Claude says so when they share it.
- A job's own to-do items: `todo` in the tracker, written with `track.py todo <id> add <kind> "<text>"` and
  `todo <id> done <n>`, never by hand: `[{kind, text, where, link, due, since, session}]`. Kinds: `urgent`,
  `working`, `task`, `click`, `todo`, `waiting`; no kind, or an older "info", counts as `todo`.
  - `waiting`: the next move is the employer's. Never in Do now; in Hiring steps as "waiting since <date>".
    Example: `track.py todo J1 add waiting "feedback on the take-home"`.
  - `working`: Claude is on it inside the main session; set when the work starts, removed when it is recorded. A
    piece in a sub-session is in the sessions record instead.
  - A to-do names its session by id (`session=<id>`), never by a title in its text: titles change. It is then on
    that session's row, not a row of its own (an urgent or past-due one stays).
  - A job that is sent or ends loses its to-dos: `track.py set` drops and prints them. A to-do for after the end
    is added after it. Example: "send the withdrawal email", added on the day the person declined.
- A hiring step that is done gets `"done": "<date>"` in `PIPELINE`: it leaves Do now and the README's next steps,
  and Hiring steps says Done. What is awaited next is a `waiting` to-do. Example: a take-home handed in on 13 Nov:
  `"done": "2026-11-13"`, then `track.py todo J1 add waiting "feedback on the take-home"`.
- Sessions: `SESSIONS` (`sessions.py`) holds every open sub-session: its state (`you`, `ready`, `done`), what it
  waits on, its jobs (the one in hand first), a date, `tab` (it holds a filled form open in a browser tab) and
  `steps` (the person's steps left). The coordinator keeps it; the export only reads it. The order to answer them:
  the ones `sessions.py order` names, then urgent, then the nearest fixed date, then a form held open in a tab, then
  the fewest steps left, then the longest wait. The coordinator's list of questions uses the same order. Example:
  1 `apply-acme` (urgent), 2 `study-beta` (by 2026-11-16), 3 `apply-gamma` (form open in a tab), 4 `answers-delta`
  (1 step left).
- Do now's Question rows are the Questions page's open questions (`QUESTIONS`), nothing else; before the page exists,
  the employers the rules leave to the person. A job that waits on the person without a to-do or a question shows
  its note as a To do.
- A to-do's link is the email link; a personal access link (a page that opens without a sign-in) stays in the
  calendar and the person's folder. Pay figures and addresses never go into the exported files.

## Tools

| Script | Does |
|---|---|
| `check_setup.py` | health check of the env file, folders, profile, master record, CV versions, tracker and the dashboard key; `--needs`: what the next run waits on |
| `init_career_folder.py` | creates the main folder and `job-search.env` for a new person (never overwrites) |
| `build_cv.py` | builds every CV PDF from its JSON (`--no-photo` for employers that ask for none) |
| `make_letter_pdf.py` | builds one cover letter PDF from a body file, on the day it is sent |
| `track.py` | tracker: add, set, todo (add, done, list), show (`--full`), brief, list, summary, sync (merges a screening run), split (summary rows and detail files) |
| `build_app_folders.py` | rebuilds the application folders; never deletes what the person or Claude wrote |
| `fetch_jd.py` | saves a posting's full text as `job-description.md` |
| `logins.py` | login state: set, sync, show |
| `sessions.py` | the open sessions and the order to answer them: sync (the app's session list), set, order, show |
| `export_dashboard.py` | exports the dashboard's files: index, applications, steps, actions, logins, excluded, sessions; then what to upload and the check lines. `--check`: the check lines alone; `--uploaded <dir>`: these files are on the page now |
| `career_view.py` | one part of the master record: screen (rules and decisions), facts (what a letter or form may use, with the profile's person facts but no address, birth date, private answers or contacts) |
| `profilelib.py` | the person's profile: path, get, set (compare-and-set), erase, create; exit 3 when it holds another value; a key under `settings` only with `--yes`, after the person's yes |
| `move_to_profile.py` | once: moves the person's facts from the master record and the old private record into the profile (dry run, `--apply`, `--confirm <key>`, then `--remove-old` after the person's OK) |
| `cheat_sheet.py` | a step's cheat-sheet.md as one page for the call (`cheat-sheet-wide.html`), opened in Chrome |
| `searches.py` | saved searches: add, list, due (on a weekday for a site without an alert), done, sites (the tracker's sites with no saved search), seen (is a posting new) |
| `questions.py` | questions for the person: add, list, build (the Questions page's files), record (answers into the records) |
| `employer.py` | employer checks: check (`--full`), record, environment, decide, alias (`--not`), split (`--apply`), repair-clear, import-tracker, merge |
| `usage.py` | usage log (steps and runs) and the weekly usage report (due, report, mark-drafted) |
| `trackerlib.py`, `employerlib.py` | shared code for the scripts above (`profilelib.py` too) |
| `workflows/screen-and-prepare.js` | Workflow: screens a batch of employers and prepares the cleared jobs; never submits |

Older records: the scripts also read a tracker kept before the plugin (`{companies: [...]}`). Optional keys:
`TRACKER_SETTINGS`, `REDACT_FILE` (private text replaced in every application file; keep it outside shared folders),
`SENT_CVS_DIR`, `SENT_CVS_BEFORE_DIRS`, `SEARCH_TIME` (the scheduled run's time, default 19:00), `SEARCH_DAYS` (its days, default `weekdays`).
