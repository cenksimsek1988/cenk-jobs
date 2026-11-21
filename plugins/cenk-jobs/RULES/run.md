# cenk-jobs rules: run

A part of `RULES.md`. Read when you run the health check, or create or refresh the dashboard.

## The health check

A step of the run (/cenk-jobs:coordinate, "Each run"):

1. `check_setup.py`: fix or report each FAIL in one line.
2. Each connector, one cheap read call, once per run: Gmail `search_threads` (`pageSize` 1), Google Calendar
   `list_calendars`, Google Drive (the main folder readable on disk, or the Drive connector), Claude in Chrome
   `tabs_context_mcp` without `createIfEmpty`: any answer, "no tab group" included, means connected; with
   `createIfEmpty` the call would open a window and a tab group. Record each:
   `logins.py set <id> connected|needs-reconnect "<what you saw>" kind=connector name=<Name> fix=<how>`, then
   `logins.py sync`. `LOGINS` is the one place login state lives. The export cannot call a connector: it names
   each one not checked since the run started in a `check:` line.
3. The dashboard: `DASHBOARD_URL` set and readable. If not, create it now (see "Dashboard"). The same for
   `QUESTIONS_PAGE` (`RULES/questions.md`).

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
- A script that changes a record the pages show prints `pages behind: refresh both`: the turn ends with
  `export_dashboard.py --check`, and both pages are refreshed once when it names one (/cenk-jobs:coordinate).
- Refresh: `sessions.py sync <list.json>`, `logins.py sync`, `build_app_folders.py`, export. Upload
  only the files its `upload:` line names, update each one's `source.url` and `updated`, delete the replaced
  uploads; a file under `unchanged:` gets only its dataset's `updated.at`. Then `export_dashboard.py --uploaded
  <out dir> <the files you uploaded>`: only those are recorded as on the page, and a bare `--uploaded <out dir>` is
  refused. Example: `upload: index.json actions.json`, both uploaded: `--uploaded <out dir> index.json
  actions.json`; an upload that failed is left out and stays under `upload:` at the next export.
- The same refresh builds the Questions page: `questions.py build <dir> --page <dir>`, write its files, delete the
  ids it lists (RULES/questions.md). A dashboard uploaded without it leaves the page a run behind. Seen 19 Nov:
  two questions open for jobs sent the day before.
- Each refresh also passes the page and the calendar: save the store's `files` (ArtifactData list with `out_dir`)
  as JSON, and Google Calendar's `list_events` from today to 60 days ahead once per run (a later refresh in the run
  passes the same file), then `export_dashboard.py <out dir> --page <dir>/files/index.html.json --calendar
  <events.json>`. "the dashboard page is not the plugin's template":
  write `files/index.html` from `templates/dashboard/index.html` in the same run. Example: after a plugin update the
  page still lacks the Sessions tab.
- Every export ends with one `check:` line per mismatch between the records and the page (`export_dashboard.py
  --check` prints them alone and writes nothing, with "the Questions page is behind the records" from `questions.py
  build --check`). Fix each in the same run, or name it in the run report. Example:
  `check: to-do on an ended job: J3 (rejected 2026-11-10), 2 to-do(s) -> track.py todo J3 done all`.
- Logins: each person's own sites and connectors live in their `LOGINS` file; the Logins tab groups them in this
  order: Needs you (a connector, or a site jobs wait on, and not signed in; a site no job waits on is Not signed
  in), Signed in, Connected, Not signed in. A job board's rows are one row on the page ("LinkedIn Easy Apply" and
  "linkedin"), with a check line to merge them in `LOGINS`; its state is the latest check, never a row `sync` made.
  A job board is the login only for its own form (Easy Apply, Indeed Apply): a job found on a board and applied on
  the employer's site waits with `track.py wait <id> account-needed "<what>" login="<platform> · <employer>"`.
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
- A hiring step's Do now row links to its email (`mail` in `PIPELINE`), never the step's own page: a personal
  access link (a page that opens without a sign-in) stays in the calendar and the person's folder. Pay figures and addresses never go into the exported files.
