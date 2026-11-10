# cenk-jobs rules: run

A part of `RULES.md`. Read when you run the health check, create or refresh the dashboard, or need a script's name.

## Every run: health check and status

After step 1: the handoff check (`coordinate`), then `check_setup.py --needs` as one list to the person (RULES.md, "Every run"), with what step 3 finds.

1. Say when the run starts: "Job-search run started at 21:05 (by hand); I'll tell you when it's done." Log it with
   `usage.py log run started "<by hand|scheduled>"`. At the end: "Run finished at 21:40." plus the short report,
   and `usage.py log run ok` (or `failed` / `stopped`). The dashboard header shows the run's state from these rows.
   "Run my job search now" starts a run at once; if one is running (a "run started" row with no end), say so instead.
2. `check_setup.py`: fix or report each FAIL in one line.
3. Each connector, one cheap read call: Gmail `search_threads` (`pageSize` 1), Google Calendar `list_calendars`,
   Google Drive (the main folder readable on disk, or the Drive connector), Claude in Chrome `tabs_context_mcp`.
   Record each: `logins.py set <id> connected|needs-reconnect "<what you saw>" kind=connector name=<Name> fix=<how>`,
   then `logins.py sync`. `LOGINS` is the one place login state lives.
4. The dashboard: `DASHBOARD_URL` set and readable. If not, create it now (see "Dashboard"). The same for
   `QUESTIONS_PAGE` (see "Questions for the person").

## Dashboard

A private page: **Do now** (Urgent first: a step only the person can do that expires; then In progress: Claude or a
session is on it; then sign-ins, things to do, the Questions page's open questions (with its link), and tasks
with a deadline), **Calendar** (live from Google Calendar),
**Logins**, **Excluded employers**, **Hiring steps** and **All applications**, under the total count and the split by
outcome.
- Setup creates it from the Artifact "Dashboard" type (quickstart, intent "other"): upload the six files from
  `export_dashboard.py <out dir>`, write the store documents as in `templates/dashboard/datasets.json` and
  `files/index.html` from `templates/dashboard/index.html`, and put its link in `DASHBOARD_URL`. Its name is
  "cenk-jobs · Job applications" (`dash/meta`), the Questions page's "cenk-jobs · Questions for you": the plugin's
  name, so a page is never just "Dashboard". Both are pinned to the claude.ai sidebar, one of the defaults setup
  offers.
- Refresh after each change: `logins.py sync`, `build_app_folders.py`, export, upload the six files, update each
  dataset's `source.url` and `updated`, delete the replaced uploads.
- Logins: each person's own sites and connectors live in their `LOGINS` file; the Logins tab groups them in this
  order: Needs you (needs sign-up, expired, needs sign-in, reconnect, blocked), Signed in, Connected, Not signed in.
  `sync` makes a new site row "needs sign-in" and marks an excluded employer's site `excluded` (not shown there);
  Claude sets `needs-sign-up` (no account yet) and `expired` (a sign-in page where a form was) with `logins.py set`.
  Example: a Workday form at Review, then its sign-in page: `expired`.
- A site no job waits on keeps its last state, with the reason in its note: signed in, or not signed in. Never
  "unknown". Example: a site whose offer closed: `signed-in`, note "no open job: the offer closed".
- Excluded employers have their own tab, one row each, rebuilt at every export from the person's decisions, findings
  and tracker (`employerlib.excluded_list`): employer, Excluded or Withdrawn, why (category, by their decision or
  their rules), what was found, the source, the jobs, since when. Example: "Acme · Defence industry, your rules ·
  supplies drone parts to a national army (news, 2025) · Source".
  The tab shows the person's own decisions, which can reveal their views: the dashboard is shared only with people
  they choose, and Claude says so when they share it.
- A job's own to-do items: `todo` in the tracker, `[{"kind": "urgent"|"working"|"task"|"click"|"todo", "where",
  "text", "link", "due"}]`; no kind, or an older "info", counts as `todo`. `working`: Claude or a session is on it;
  set when a piece starts, removed when its report is recorded.
- Do now's Question rows are the Questions page's open questions (`QUESTIONS`), nothing else; before the page exists,
  the employers the rules leave to the person. A job that waits on the person without a to-do or a question shows
  its note as a To do.
- A to-do's link is the email link; a personal access link (a page that opens without a sign-in) stays in the
  calendar and the person's folder. Pay figures and addresses never go into the exported files.

## Tools

| Script | Does |
|---|---|
| `check_setup.py` | health check of the env file, folders, master record, CV versions, tracker and the dashboard key; `--needs`: what the next run waits on |
| `init_career_folder.py` | creates the main folder and `job-search.env` for a new person (never overwrites) |
| `build_cv.py` | builds every CV PDF from its JSON (`--no-photo` for employers that ask for none) |
| `make_letter_pdf.py` | builds one cover letter PDF from a body file, on the day it is sent |
| `track.py` | tracker: add, set, show (`--full`), brief, list, summary, sync (merges a screening run), split (summary rows and detail files) |
| `build_app_folders.py` | rebuilds the application folders; never deletes what the person or Claude wrote |
| `fetch_jd.py` | saves a posting's full text as `job-description.md` |
| `logins.py` | login state: set, sync, show |
| `export_dashboard.py` | exports the dashboard's files: index, applications, steps, actions, logins, excluded |
| `career_view.py` | one part of the master record: screen (rules and decisions), facts (what a letter or form may use) |
| `searches.py` | saved searches: add, list, due, done, seen (is a posting new) |
| `questions.py` | questions for the person: add, list, build (the Questions page's files), record (answers into the records) |
| `employer.py` | employer checks: check (`--full`), record, environment, decide, alias (`--not`), split (`--apply`), repair-clear, import-tracker, merge |
| `usage.py` | usage log (steps and runs) and the weekly usage report (due, report, mark-drafted) |
| `trackerlib.py`, `employerlib.py` | shared code for the scripts above |
| `workflows/screen-and-prepare.js` | Workflow: screens a batch of employers and prepares the cleared jobs; never submits |

Older records: the scripts also read a tracker kept before the plugin (`{companies: [...]}`). Optional keys:
`TRACKER_SETTINGS`, `REDACT_FILE` (private text replaced in every application file; keep it outside shared folders),
`SENT_CVS_DIR`, `SENT_CVS_BEFORE_DIRS`, `SEARCH_TIME` (the scheduled run's time, default 19:00).
