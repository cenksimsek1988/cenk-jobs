# Changelog

All notable changes to the cenk-jobs plugin. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Every change gets an entry here and a new version in
`plugins/cenk-jobs/.claude-plugin/plugin.json` (the catalog entries carry none): a GitHub install updates only when
the version changes.

## [0.46.5] - 2026-11-21

Every pay figure typed into a form is rounded up until its significant part ends in 0 or 5 (a lesson of 21 Nov).

### Changed

- The significant part is the figure counted in its currency's salary unit (thousands a year, hundreds a month,
  tens a day, ones an hour; TRY thousands a month too, and JPY, KRW, INR, HUF, CZK, SEK, NOK, DKK and RUB in the
  units they are usually counted in, `paylib.COUNTED_IN`), rounded up to a whole number; it then goes up to the next
  whole number ending in 0 or 5 (`paylib.py`). Examples: 87,920 USD a year -> 90,000; 6,667 EUR a month -> 7,000;
  14,700 EUR a month -> 15,000; 220,000 TRY a month stays 220,000.
- `fx.py` takes `--per year|month|day|hour` (required) and prints the typed figure after "typed:"; the same
  currency twice gives it with no rate and no network. Example: "87920 USD a year; typed: 90000 USD".
- The funnel's prep turns the fit check's salary, and every pay figure in a form answer, into the typed figure with
  `fx.py`; the review checks it. `references/filling.md` holds the rule for the session and the applier's brief.

## [0.46.4] - 2026-11-21

The last two of the ten lessons of 20-21 Nov: the tracker's ids and to-dos, and a faster folders build.

### Changed

- `track.py` refuses an id that is on two rows, naming both, and writes nothing: a change never lands on the wrong
  job. Example: "job D7 is on 2 rows (Eta: Lead; Iota: Manager)".
- `track.py todo <id> done` that removes nothing says where the to-dos are: dropped into the job's history when it
  was sent or ended (with the date), or on another row at the same employer.
- `build_app_folders.py` reads a row's detail file only for a job that gets a folder, indexes the CV and letter
  folders once instead of once per file, looks up each employer's working environment once, and writes a file only
  when its text changed, so an unchanged one keeps its time and Google Drive syncs nothing. Example: a tracker of
  1,400 rows of which 300 make a folder reads 300 detail files, not 1,400. Not yet: skipping the jobs that did not
  change since the last build.
- `track.py show <id>` prints every row that holds the id, so a duplicate can be looked at before it is fixed.

## [0.46.3] - 2026-11-21

Seven of the ten lessons of 20-21 Nov: letters only where a form takes one, no paid plans, drafts read back, bot
checks and refused Submits left to the person, a vanished form checked in the mail first, and the employer's AI rule
followed.

### Changed

- Letters: the funnel writes one only for a form whose fields the fit check read with a field that takes one (a
  cover-letter field; with `LETTERS=always` a file field too); "unknown" (Easy Apply, a form not read) gets none, and
  the apply session writes one only when the open form shows a field. An application by email counts as a letter
  field. The writer is given the ids of the jobs that take one (its file holds no `letter_field`), and an applier
  that meets a letter field with no letter returns `needs-person` "letter". Before, `always` and "unknown" wrote
  letters no form took.
- Paid plans: never bought or started on any site (RULES.md); a job that applies only through one is skipped
  "applies only through <board> (paid plan)". The fit check's rule covers RemoteOK and freelancermap
  (`references/sites/freelancermap.md`).
- Drafts (RULES/hiring-steps.md, "Mail"): a posting named by company, role and reference, never by a link (the Gmail
  connector rewrites links); after `create_draft`, the stored draft is read back (`get_draft`) for its links and
  attached files; a draft with files is never changed with `update_draft` (it drops them). The apply skill gets the
  path for applying by email; the withdrawal template points to the rule.
- A bot check is the person's: `logins.py set "<site>" blocked`, asked in the sign-in round, tried again in the
  same Chrome profile after they pass it.
- A refused Submit click is the person's step: the tab stays held with that step in its title, its plain link and
  the draft fact; never the Enter key, a script click, `submit()` or another tab. The applier returns
  `needs-person` "Submit refused".
- A held form whose tab is gone: Gmail is searched for the employer's confirmation since it was held before any
  refill; found: `track.py set <id> submitted`.
- The employer's AI rule (posting, form, its own AI-in-hiring page) is quoted and followed: Claude does only what
  it allows (example: the person writes, Claude refines); a Yes/No on the AI policy stays the person's. The write
  skill reads the three sources and checks the live page with `fetch_jd.py <id> --force`; the writer writes no
  draft a rule forbids.

## [0.46.2] - 2026-11-21

Remote Rocketship searches read only real title pages, and `searches.py suggest` proposes the titles and countries
the rows lack.

### Added

- `searches.py suggest [--days <n>]`: for the Remote Rocketship rows, one page each (at most 60, 3 s apart): each
  row's titles with no title page on its own country, the titles of the last n days' fits (default 30) that no row
  searches, and the countries of the scope's remote regions that no row reads (EU: european-union, EMEA: europe,
  anywhere: worldwide). It prints the `searches.py query`, `add` and `every <id> off` (a row left with no title)
  commands, with titles in letters, digits and & + . # - only, and changes nothing: each waits for the person's yes.
  Example: "add country: europe (31 new a week for "engineering manager")".

### Fixed

- A title Remote Rocketship does not know answers 200 with the country's generic list (the 20 newest remote jobs of
  any title), not a 404 (seen 21 Nov: germany/jobs/tech-lead): `collect_postings.py` now skips such a page like a
  404, with a line naming the title to drop, instead of reading it as that title's postings.

## [0.46.1] - 2026-11-21

A form held for the person is never lost with its session, and `track.py reopen` brings back only fits inside the
person's places now.

### Changed

- Held forms: each one is named the same way in the question, its to-do and the handoff's new `Held:` line: the tab
  title, the plain link marked "open in Chrome", and whether the site keeps a draft. A session with `tab=yes` is never
  stopped, ended or archived; `sessions.py set` refuses `state=done` while `tab=yes`, and `sessions.py sync` names a
  session archived while it held a form. Every site note starts with a "Draft:" line (unknown: "no draft known").
- `track.py reopen`: a fit cut by a setting is read from the fit check's own message, with or without "fit: " before
  it (0.46.0 missed the unprefixed form: 18 of 64 found on a copy); a note the person wrote never counts. A cut fit
  outside the person's places now (job-search.env, then the search scope) stays skipped, as the funnel would leave
  it out. Example: "4 to reopen", "60 left skipped: outside the person's places now".
- `collect_postings.load_places` sets the places for both scripts.

## [0.46.0] - 2026-11-21

The fit check grades by the kinds of soft gaps, and more postings reach it: boards' remote flags and region-only
places, LinkedIn's pages without gaps, a board's first read whole, and the posting texts saved at collect time.

### Added

- `track.py reopen [--apply [--per-day N]]`: the fits skipped only by a setting's cut the person's settings no longer
  make (`APPLY_FITS=high` on a normal fit, `LONG_SHOTS_PER_DAY=0` on a long-shot or a weak one), never sent; `--apply`
  sets them back to found with the old fit result in the history row, and the funnel takes them, whoever found them,
  from their "reopened" day: with `--per-day N` the newest N the next run, N more each day after. Example: "reopened
  64: the next run takes 15, then 15 a day until 2026-11-25". Only a skip note starting "fit:" counts, and one whose
  job is in the tracker under a newer row (a repost) stays skipped. A weak fit skipped before 0.46.0 ("weak fit:
  score N") names no setting and is not reopened.
- `FIT_MODEL=sonnet|opus|opus-max` (default sonnet): Opus runs the fit check at medium effort (about 100k W an
  employer against 60k W on Sonnet) or at max effort (about 150-300k W, estimated).
- Gap kinds `stack`, `domain` (with `closest`, or "none"), `scope` and `relocation`, all soft; one list of soft kinds
  (`choices.SOFT`), passed to the workflow as `args.fit.soft`.
- `fetch_jd.py`: a page's JSON-LD JobPosting, Workday's public job JSON, Workable links without the account; LinkedIn
  3 s apart with one 60 s retry after a 429; a text under 300 characters is never saved as the posting.

### Changed

- The grade is the count of soft gap kinds (the 19 Nov reply analysis' gap groups): 0 high, 1 normal, 2 long-shot,
  3 or more weak; two stack gaps count once, a domain kind with no adjacent fact twice. Only a hard gap skips. A
  weak fit goes on within `LONG_SHOTS_PER_DAY`, after the long-shots; the weighted score stays as information. A
  read posting with no must-haves and no requirements is never high ("no evidence"). The workflow and `choices.py
  grade` give the same grade.
- The fitter reads a LinkedIn job with no saved text at its public guest page (`jobs-guest/jobs/api/jobPosting/<n>`):
  seen 21 Nov, two of three LinkedIn postings came back unread from the view link and gave their full text there.
- The fitter reads the person's level from the record's largest scope: a staff, principal, head or director role is
  one `scope` gap, never hard; inside a grade, a job with a scope gap goes after one without in the sync queue. A
  cloud or Kubernetes must-have the record lacks is a `stack` gap with a warning.
- `collect_postings.py`:
  - LinkedIn: newest first (`sortBy=DD`); the row's terms (else `ROLE_TERMS`) joined with OR, a term of two or more
    words quoted; up to 5 pages, each from the posting after the last one read. Seen 21 Nov: the guest search gives
    10 postings a page, so steps of 25 skipped postings 10-24 and 35-49.
  - A board's own remote flag (Ashby, Lever, Workable, SmartRecruiters) makes the place "Remote - <place>"; a place
    that names only regions ("EMEA") is checked against the remote regions, not as an office.
  - "Some overlap with US hours" no longer leaves a posting out; "works US hours" still does.
  - A board row's first read takes every open posting, whatever its date; later reads keep their window.
  - The posting text a board's list carries (Greenhouse with `content=true`, Lever, Ashby) is saved in
    `POSTINGS_DIR` and passed as `text_file`: the fit check reads it whole, with no fetch.
  - The same employer and title in the tracker no longer blocks a posting when that job closed, or was skipped only
    by a setting's cut no longer made; the fit cache passes such a cut too.

## [0.45.1] - 2026-11-21

The person's name and contact line come from their profile; `job-search.env`'s lines only override them.

### Changed

- Letters, the CV and letter file names, the form brief's first name and the usage report's redaction read the name
  and contact from the profile (`profilelib.person`): `person.name`, that name in capitals on top of letters, and the
  contact line "<city> · <phone> · <email> · <LinkedIn>" from `person.location`, `phone`, `email` and
  `links.linkedin`, never the home address. `PERSON_NAME`, `NAME_ON_CV` and `CONTACT_LINE` in `job-search.env` still
  win where set: an install that sets them sees no change, and an empty `CONTACT_LINE` now gives the profile's line.
- The usage report and `employer.py merge --from-checks` mask every spelling of the name and contact, from
  `job-search.env` and the profile together (`profilelib.identity`), and write nothing when no name is known.
- `check_setup.py` no longer requires the three lines, and names one that only repeats the profile (remove it); a line
  with another wording stays.
- `init_career_folder.py` takes only the main folder; the env template's name lines are commented overrides; setup
  fills the profile instead. A letter with no name known stops with the command that sets it.

## [0.45.0] - 2026-11-21

Phase 1 of the data redesign: every write to the shared records goes through one library that refuses a stale base,
checks what it writes and logs it; one check script names every record fault; three facts read from free text become
fields: a waiting job's `waits_on`, a login row's `origin` and a hiring step's `done` date. The file layout does not
change.

### Added

- `recordlib.py`: the one way to write the seven record files (tracker, PIPELINE, logins, questions, sessions,
  employer checks, saved searches). A file changed since the command read it is not written ("STALE: ... run the
  command again", exit 3); a value the command writes wrong is refused ("REFUSED: ...", exit 1): a status outside its
  vocabulary, a job made submitted with no applied date, a job made waiting with no `waits_on`. Older rows never
  block a write. Every write appends `{rev, at, script, file, ids}` to `changes.jsonl` beside the tracker
  (`CHANGES_LOG`). A command that writes two files checks both bases first; collect_postings.py and questions.py run
  a STALE subprocess once more.
- `templates/schemas/<kind>.schema.json`: each file's shape and vocabularies (statuses, to-do kinds, stages, login
  origin), each vocabulary listed once; trackerlib.py and logins.py read theirs from there. The `.schema.json` names
  keep `.gitignore`'s guard on a person's own `pipeline.json`, `logins.json` and `employer-checks.json`.
- `records.py check`: one `check: <id>: ...` line per fault, rows with the same fault on one line: shape, sent,
  waits, links, dupes, steps, employer. `export_dashboard.py --check` prints them; its own lines for an unknown
  status, a repeated role, a wait with no site or no to-do, a sign-in on a job board and a past-due step moved there.
- PIPELINE's writer: `track.py step <id> add name= date= [time= due= with= how= link= mail= proposed=yes]`,
  `step <id> done|cancel <n> [<date>]`, `step <id> set <n> key=value`, and `track.py outcome <id>
  rejected|closed|declined|withdrawn <date> [reason= mail= why= category=]`. Steps keep their number; an entry with
  `same_as` writes into the entry it names; an earlier outcome goes into the entry's history.

### Changed

- A waiting job's `waits_on` `{kind, login, since}`: `track.py set` writes it for a waiting status, `wait` names the
  site (and takes needs-captcha); a sent or ended job keeps it only in its history row. It replaces the job's own
  `login` field, still read on older rows.
- A login row's `origin` (sync, claude, person) replaces reading the sync note's text; `logins.py set` takes
  `origin=person`.
- `track.py set` refuses a status outside the vocabulary (it accepted any `needs-<word>` before).
- Rules and skills: the shared records change only by their scripts, never by hand; a STALE refusal means run the
  command again; PIPELINE changes only by `track.py step` and `outcome`; a sub-session's own script call is safe, and
  the coordinator keeps the other files alone.

### Fixed

- `track.py wait` on the older `{companies}` tracker named a Workday site "Workday · " with no employer.

No Claude tab groups left behind in Chrome, and one order for finishing the open applications.

### Changed

- Chrome tabs: a session works in one tab (an applier in its own), navigated for each page, closes it once its
  piece is done, and closes every own tab before its final report or handoff, except a held `>>>` tab. Every
  sub-session's brief ends with that line, and the run closes its own tabs before its report. Seen 21 Nov: 14 tab
  groups left by sessions that ended with tabs open. A group is its session's alone (its subagents share it) and
  goes with its last tab.
- The run's health check reads Claude in Chrome without `createIfEmpty`, so it opens no window and no tab group.
- On the first run of the week, when no session is open, the report says that Claude tab groups with no `>>>` tab
  can be closed.
- Apply order: first every application that needs nothing from the person; then one round asking for all sign-ins,
  and those applications; last, one list of what the person must do or do with Claude (essays, codes, CAPTCHAs,
  decisions, go-aheads). The run asks at its start only for a missing program or connector, no longer for sign-ins.
  A form whose Submit sends a code is filled and waits for the last list, and so does an expiring step on a held
  form. A finished search's questions join the last list (each is still on the Questions page at once). plan orders
  by these groups first.
- A scheduled run starts no session: it runs the scripts, the workflow, plan and the Gmail step in its own context,
  applies through `cenk-jobs:applier` subagents, and proposes any other piece as a card. "Run my job search now" in
  a coordinator with a conversation behind it starts a fresh session for the run.

### Fixed

- The coordinator no longer submits a sub-session's form itself, since that session's tab is in a group it cannot
  see: it forwards the person's go-ahead, quoted, and the session submits.

## [0.44.3] - 2026-11-20

Four lessons from the 20 Nov search, and the follow-ups of the 0.44.1 commit review.

### Added

- `career_view.py scope [--set remote_regions=<a,b> any_mode_places=<a,b>]`: shows and writes the search scope, so a
  scope the person states reaches the search scripts (it never did: 89 of 103 postings of one run were out of
  scope). An older list of places is kept as `preferences.locations.places`.
- `searches.py scope-ok <id>` (keep a row outside the scope) and `searches.py query <id> "<terms>"` (a row's terms).
- `references/sites/dover.md`: a Dover posting page is drawn by script; the search session saves its text from Chrome.

### Changed

- A search row's own place narrows the person's places, never widens them: an office or hybrid posting must also be
  in the scope. A remote search or a remote posting keeps its own places; a place that names a hybrid or office part
  is not remote.
- `searches.py due` leaves out a script row whose every place is outside the scope, with an "outside the scope" line
  for the Questions page (turn it off, or keep it).
- Remote Rocketship: a title or stack with no page (404) is skipped with one line; the row fails only when every page
  does. Before, one dead title marked the whole row gone after two runs.
- `collect_postings.py` names each unread posting whose text it could not save ("no text saved"), with the file the
  next fit check reads; the fit check reads a dover.com page without that file as "none" instead of fetching it.
- Board discovery uses WebSearch's `allowed_domains`, one board kind per search; `site:` in the query is often ignored.
- The full employer check before a hiring step runs again when the last is over 90 days old.

### Fixed

- An apply job the form step left out of its file, or every apply job when the step wrote no readable file or no
  review, was queued without form answers or review: it is held for the next run like an unreviewed one. Only a form
  step of the same run counts.
- An employer was dated "screened" when its second check or judge failed: only a completed check (a clean screen, or a
  second check after it in the same run) dates it.
- A form step's reply with a Git Bash path (`/c/...`) counted as form-failed, and sync could not read it.
- `--screen` for an employer with new postings and a due second check ran only that check, never the full screen.

## [0.44.2] - 2026-11-20

Smaller rules and skills with one owner per fact, and a hook that holds the no-screenshot rule.

### Added

- `hooks/no_screenshot.py`, a PreToolUse hook on the `computer` and `browser_batch` tools of Claude in Chrome and of
  the app's built-in browser: it denies a screenshot or a zoom in a job-search session (a folder that holds
  `job-search.env`, or one below it), and an unreadable call that names one. Clicks, typing and every other folder
  pass.
- Parts read only when their reader needs them: `RULES/start.md` (a session outside the main folder),
  `RULES/tools.md` (one line per script, `fx.py` and `jsenv.py` added), `references/install.md` (setup step 1),
  `references/choices.md` (setup step 4 and any change of a choice), `references/study.md` (study and after-a-step
  sessions), `references/weekly.md` (the first run of the week) and `references/saved-searches.md` (none saved, an
  alert decision, tuning).

### Changed

- The run's order is one numbered "Each run" list in /cenk-jobs:coordinate; RULES.md, RULES/run.md and the schedule
  skill point to it.
- One owner per fact: the question rule and the profile writes in RULES.md, not in each skill; the lesson route,
  "I'm at my PC" and the start-of-run line in coordinate; the code-on-Submit rule in `references/filling.md`; the
  guarded items in one bullet.
- A step due within 24 hours: one rule in RULES/urgent.md: one notification for all of them at the end of the run
  that finds them, or at once outside a run.
- Page reads are capped: `read_page` with `max_chars` 5000, or `javascript_tool` returning JSON; `get_page_text`
  only on a short page; a booking page with `find` or `read_page`. The link check says how a page is read; a
  SuccessFactors link opened signed out lands on the site's home page.
- `references/filling.md` says each rule once (screenshots, true answers, consents, guarded items); its "(session)"
  marks are fixed for uploads (the session builds and copies the letter, the applier uploads) and for the Greenhouse
  and Ashby question reads.
- Setup says what it needs in one sentence first, asks for `ROLE_TERMS` and `REMOTE_REGIONS` with the places, takes
  its cost lines from `cost.py table`, ends with a report and starts a fresh main session for the first search.
  Prepare ends with a report.
- The calendar's `list_events` and the connector reads run once per run, not before every refresh.
- The search skill's account of `collect_postings.py`'s internals is in the script's docstring, with its LinkedIn
  pacing corrected there (4.5 s; after a refusal 60 s, then 8 s).

### Removed

- The end-of-run message asking every open sub-session to write its handoff.
- `variants.py models` passed by hand to the workflow: `workflow_args.py` already passes it.

## [0.44.1] - 2026-11-20

Four lessons from the job search, the workflow fixes from the workbench review, and the full employer check before a
first hiring step.

### Added

- The full employer check before an employer's first hiring step (RULES/employers.md promised it; nothing called it):
  `workflow_args.py --screen "<name>" --out <dir>`, the coordinator's "Employer check" piece, and prepare waits for
  it. An employer with no new posting runs only the screen (`screen_only`). `track.py sync` marks each screened
  employer with the date, so the check runs once.
- `make_letter_pdf.py --job-file <prepared file> --job <id>`: the company and the role come from the file.
- `references/sites/remoteok.md`.

### Changed

- The prepared-jobs file holds only the jobs to apply to, with the form's fields; `track.py sync` merges it with the
  fit check's result by job id. The form step no longer copies every job's requirements, which saves output tokens and
  copy errors.
- A letter is written once, by the funnel's writer: plan and apply use the prepared one, and only a job without one
  gets it then. Its PDF is still built on the day it is sent.
- The workflow's agents write and change JSON with the Write and Edit tools; Python in the shell mangled accented
  letters (Git Bash on Windows).
- Each step's model comes from its agent's front matter; the workflow names only the judge's and the plain review's.
- A RemoteOK posting is applied to on the employer's own page (Apply there needs a paid plan), else skipped. Before
  filling, the employer's own posting page wins over a job board's "remote" label.
- Workday: a page is never reloaded (a reload can sign the tab out; the saved draft keeps only steps 1 and 2), and
  the go-on-without-AI choice goes to the person at once.

### Fixed

- The writer's and reviewer's letter command took the company and role from posting text inside a shell line, where
  a `$(...)` would run.
- Any reply from the form step counted as a written file; now the reply must name the file, else the route is
  `form-failed`. A reply such as "Wrote <path>" is read by `track.py sync` too.
- A failed writer or reviewer left an unchecked job queued: a job keeps `review: "due"` until the reviewer marks it
  "done", and sync holds a due one for the next run.
- Two companies could share one prepared file (accents, or names alike in their first 40 letters).
- A failed cheap check read as "not needed"; a fit check that failed after it dropped its result.
- The employer prompts carried an argument no caller built (`decided`); the categories were hard-coded instead of
  read from the person's rules.
- `apply: list` still ran the employer checks.
- In the full check: a category the screen left out counted as clean; a judge's partial answer dropped the other
  categories; the verified route merged ties the second check had dropped. A failed judge is `judge-failed`.

## [0.44.0] - 2026-11-20

Write free texts with the person, plain links instead of hidden tabs, both pages kept current, five fixes to the
dashboard and Questions page, and the first fixes from a review against the workbench rules.

### Added

- `/cenk-jobs:write`: one essay, motivation answer or letter, written with the person. The order is the
  employer's AI rule in one line, the company and role in a few sourced lines, the person's matching background and
  gaps, "Why this role for you?", a draft in their voice (a gap mid-paragraph, the end on a strength), then only
  the changed parts. It fills no form; the essays round runs it.
- `questions.py answer <id> --file <text file>`: a long answer from a UTF-8 file.
- `questions.py build --check`: says when a build would now write other files than the last build did (the
  Questions page is behind); `export_dashboard.py --check` prints it, so one check covers both pages. Each build
  records a fingerprint of the files it writes; files built and never written to the page are not caught.
- `track.py wait <id> account-needed ... login=<site>`, kept on the job; `track.py set ... repeat_of=<earlier id>`.
- Every script that changes a record the pages show prints `pages behind: refresh both`.

### Changed

- A page the person only has to look at or act on is given as its address, marked "open in Chrome", and Claude
  closes its own tab: a tab in Claude's tab group is hard to find. Only a tab holding a filled form stays held.
- A turn that changed a record ends with `export_dashboard.py --check`, and both pages are refreshed once when it
  names one. A refresh that writes a page template or uploads every file goes to a fresh session.
- A dropped question shows under Done for 7 days with a note naming what happened, like a closed one.
- Every agent has a `maxTurns` cap (about 2-3 times a long run), and its description ends with `Internal:` and
  the skills that start it.
- The applier loads its Chrome tools in one ToolSearch, reads pages with `read_page` (`max_chars` 5000) or
  `javascript_tool`, and uses `get_page_text` (no size limit in Chrome) only on a short page.
- `/cenk-jobs:setup` starts only when typed (`disable-model-invocation`): it installs programs and changes
  settings. Its description leaves every session (about 75 tokens).
- Safety rules that lived only in a part now stand in RULES.md:
  - a one-time code is masked;
  - military-service answers are private;
  - a private value never goes into a handoff, brief or report;
  - a calendar event is deleted only after the person's yes.
- The coordinator's run ends with `usage.py log run ok` and `sessions.py unlock`. A sub-session's brief names
  `${CLAUDE_PLUGIN_ROOT}` paths.
- The manifest's description is one sentence (the skill list is in the README); it gains `repository`. The catalog
  entry's description and keywords match it.

### Fixed

- A job found on a job board and applied on the employer's own site no longer asks for the board's sign-in: a board
  is the login only for its own form (Easy Apply, Indeed Apply), and `wait ... account-needed` needs `login=` when
  the records name no site. `logins.py sync` files a job under the row of its site, never a second one, and a merged
  row takes its state from the latest check, never from a row `sync` made.
- A login row set by hand that no job waits on says "no application waits on it (since <date>)" instead of an old
  "Sign in ..." note.
- A question the person chose to discuss is no longer dropped when its jobs end; `questions.py add` refuses several
  posting links with one `job=`.
- The Questions page's "to discuss" count is counted at each build, not copied from the last record.
- A re-application recorded with `repeat_of=` is no longer a check line at every run.
- `track.py sync` could record one employer's check for another: a workflow label cut the name at 20 characters,
  and "Acme" matched "Acme Defence". Labels carry the whole name, and sync matches it exactly (a cut label from an
  older run still matches by prefix).
- The apply skill named its filling rules and site notes from its own folder, where none exist: they are the
  plugin's (`../../references/`).
- Contradictions in the rules and skills:
  - a sub-session's new facts go into its handoff, never the master record;
  - pay goes only into a form's pay fields;
  - under `APPLY=auto` a planned batch is applied without a per-batch OK;
  - a run with no end row for 6 hours no longer blocks the next run;
  - a hiring step's Do now row links to its email;
  - an empty `SESSION_MODEL` is Sonnet;
  - an unsure employer-name match goes to the Questions page.
- Privacy:
  - the apply report names the fields answered, never a profile, private, guarded or pay value;
  - a degree example that read like one person's record is replaced with a made-up one;
  - the developer's blacklist merge moves from a job-search rule to the repository's CLAUDE.md.

## [0.43.0] - 2026-11-19

Interview study notes, weekly board discovery, and a coordinator that stays free for messages.

### Added

- Interview study notes: `INTERVIEW_LESSONS_DIR` (default `career-records/interview-lessons`) with `technical.md`,
  `screening.md` and `roadmap.md`. Study and after-a-step sessions read them first and end their handoff with
  `Weak answers:` lines; the coordinator writes them in. Never read for the master record, CVs, letters, forms or
  essays, never in an agent's brief (RULES.md). `init_career_folder.py` creates the three files empty; an older
  folder gets them at the coordinator's first write.
- Weekly board discovery (search, step 8): 8 web searches (Greenhouse, Ashby, Lever, Workable x the remote regions
  and the person's places); `searches.py discover --file <links>` prints each board not saved yet; after the free
  employer checks, each one not excluded becomes a weekly script row. Cost: about 50-100k W a week, 1-2% of a run.
- `searches.py every <id|source> off`: a row never due again, listed as off; a number turns it back on.

### Changed

- The coordinator sends every long piece to a fresh session (searches, workflows, analyses, page-check and
  publish-and-verify rounds, requests from other sessions) and only records and answers: a busy session loses a
  message it does not answer within 20 s (19 Nov: 8 lost in about 1 h of dashboard rounds). The exception for one
  form whose sign-in would expire is gone; a scheduled run still does its pieces as subagents.

## [0.42.1] - 2026-11-19

### Fixed

- `export_dashboard.py --check` no longer says the page is behind on every run: the export time (`meta:generated`)
  is left out of the recorded digest, so `upload:` names index.json only when its other rows change. An upload
  recorded by 0.42.0 or earlier lists index.json once more, until the next `--uploaded`.

## [0.42.0] - 2026-11-19

The dashboard review: the empty tabs fixed, states worked out for today, one row per site, the check lines the
records needed; the Questions page kept current; and the form settings (emailed codes, optional fields).

### Fixed

- Do now, Sessions and Hiring steps were empty: the Dashboard runtime hands a row's list (`apps`, `also`) to the
  page as JSON text, and `.map` on it failed. The page reads both forms (`jaIds`). Seen 19 Nov.
- The page works out each row for the viewer's day: a due date passed is late, a task due today or tomorrow urgent,
  an upcoming step whose day passed is past; the header counts come from those rows (`do_counts`). A step with no
  date is "Proposed, no date yet", never "Past". The summary bar is stored empty, as the runtime asks.
- Claude's own to-dos ("Claude: ...") and a job's note are no longer the person's to-dos: Claude's to-dos, jobs
  ready to send (long-shots held named) and unread postings are Claude's next; a job waiting on the person with no
  to-do shows "Waits on you: <note>" with a check line.
- Logins: a job board's rows are one row (the latest check wins, jobs summed), with a check line to merge them;
  "Needs you" is one rule, the export's `needs` flag. Example: "LinkedIn Easy Apply" and "linkedin".
- Whole words: "Platform architecture interview" is no form task, and the pay mask leaves "Moderate" whole.
- A job whose folder lists no step takes its steps from PIPELINE; a step's detail has no leading ", ".
- The Calendar tab uses `CALENDAR_COLOR` and `CALENDAR_PREFIX`, all-day events first on their day, 250 events.
- A run with no end row for 6 hours reads "no end recorded", never "Running now".
- The Questions page hides Done items older than 7 days itself; every dashboard refresh also builds it.
- From the Job search coordinator's check of the live pages:
  - a to-do with a due date counts as a task on a deadline;
  - the header reads "label: number", so "1 sessions" is gone;
  - the last-run line pairs an end only with its own start, and keeps the end's date;
  - a merged site keeps its plainest name ("LinkedIn");
  - a site no job waits on is never "Needs you";
  - a call with only a meeting link reads "Video call" in Where;
  - an older "done" question is shown under Done;
  - "last answer recorded" moves only when an answer is recorded, and comes from the questions when no round
    recorded one.

### Added

- Check lines: a folder in another stage than the records; the same employer and role sent twice (also a flag on
  the later row, never hidden); a status the plugin does not know (`needs-<name>`); a session that names an employer
  with a running job and has no jobs; a reminder that is not a date or on an ended job; Moving forward with nothing
  for 7 days; the older `rejected.reason` shape. `--check` says when the page is behind the records.
- Tables say "Nothing here" or why a source did not load; Hiring steps shows the due date; session rows link.
- `EMAILED_CODES=off|on` (default off): the session reads an application's emailed code or confirmation link in
  Gmail (the form just submitted, its own sender, 15 minutes); sign-in codes, CAPTCHAs and passwords stay the
  person's. `OPTIONAL_FIELDS=off|fill` (default off): demographic and EEO fields from the profile.
- `fx.py <amount> <from> <to>`: any pay field in another currency at the day's ECB rate, rounded up.
- `track.py brief` starts with the `filling:` line (LETTERS, EMAILED_CODES, OPTIONAL_FIELDS, first name);
  `choices.py show` names essays ask or auto.
- Tabs that wait on the person are titled `>>> <first name>: <company> <action> <<<`; a form is read back before
  it is handed over and refilled without a reload; a refused Submit click is retitled and said, never worked around;
  only the opener closes a tab. An optional letter field gets the letter unless `LETTERS=never`. A number recalled
  with no record never goes into an essay; an employer that forbids AI stops the job even with essays on auto.
- The coordinator never starts an apply session from an automated turn: it proposes a card.

### Changed

- Index row `actions:waiting` counts the jobs waiting on an employer; `meta:generated` has `n` 0.

### Removed

- Dead export fields: `applications.letter`, `steps.upcoming`, `sessions.name` and `due`, index rows `logins:ok`,
  `excluded:n` and `sessions:*`.

## [0.41.0] - 2026-11-19

The fit check as a weighted score, new search sources and a location check before the funnel, employer replies as
fit clues, and a scheduled run that takes over (19 Nov search, 163-reply analysis, 18-19 Nov lessons).

### Added

- Fit score: the fitter returns each requirement in the posting's words with its place (title 4, must-have with
  years 3, must-have 2, nice-to-have 1) and its match (years held / asked, capped at 1; else hands-on 1, adjacent
  0.5, absent 0); code computes the score, the same in the workflow and `choices.py grade`. Example: 72 -> normal.
- Grades: 80+ high, 65-79 normal, 50-64 long-shot, under 50 weak (a skip, listed). A posting not read in full is
  `unread`: it stays found, and the next run's fit check reads its text saved by `fetch_jd.py --posting`.
- `LONG_SHOTS_PER_DAY` (default 0): long-shots sent a day after high and normal; `track.py` holds the rest.
- `FIT_SETTINGS` (`apply/fit-settings.json`, `templates/fit-settings-example.json`): weights, grade bands and
  channel notes per place, which go into the reason line and never change the grade. `choices.py fit` shows them.
- The fitter rates scope, never skips for it: one team's EM is the person's own level; senior or group EM,
  managers of managers, staff or principal, head or director are adjacent (0.5). A domain requirement names the
  record's closest fact or "none". Requirements, score and grade stay with every job, skips too.
- Sources: `remoterocketship` (board=<country>, a term is a title slug, `tech=`; read daily), `himalayas-search`
  (board=<country>; discovery only: `apply_url` empty with an `apply_note`, the fitter finds the employer's page;
  the `himalayas` feed too), `workable-search` (remote, with a place or region of the person's).
- A location check before the funnel (`LOCATION_CHECKS`, default 60 a run): Ashby and Greenhouse locations, the
  page text ("Remote - Poland", "must be based in", US hours); outside the person's places: left out, no tokens.
- `feedback.py`: a line per employer reply (`FEEDBACK_LOG`), silence after 14 days, clues for the fit check
  (`FIT_CLUES`, passed as `fitClues`), and an analysis by score band with proposed grade bands; scripts only.
- `searches.py every <id|source> <days>`.

### Changed

- Two soft gaps (a job from before 0.41.0) is grade `weak`, a skip with that grade; a normal fit cut by
  `APPLY_FITS=high` keeps grade `normal`. The grade output has a score column.
- Feeds wait 3 s between calls; 2 refusals (429) in a row stop a source for the run, its rows stay due.
- Boards and `workable-search` rows are read every 7 days by default; older rows keep theirs
  (`searches.py every greenhouse 7`).
- A posting already in the tracker under another link (the same employer and title) is left out. A "team lead"
  title needs an engineering word.
- No LinkedIn sweeps and no board discovery by guessed names (search skill).
- The coordinator never runs a search, workflow or analysis itself: a piece the app will not start is a card or a
  question. Exceptions: a scheduled run's own session does its pieces as subagents; one form whose sign-in would
  expire runs as a subagent.
- A scheduled run that finds a coordinator active takes over: it asks for its handoff and runs as the day's
  coordinator (16-18 Nov the run stood aside and never ran).
- Each employer reply read from Gmail gets its feedback line (prepare); the search runs `feedback.py silent --add`,
  `clues` and `analyse` weekly.

## [0.40.0] - 2026-11-19

The cost per Claude plan, from the token study of 5-18 Nov (554M W in 14 days; one coordinator session 51%, cache
reads 68%).

### Added

- `data/plan-costs.json`: the static table. Plans as a multiple of Pro (Pro 1, Max 5x 5, Max 20x 20), each step's
  W with its source (setup 5-10M, an estimate; a search run 3.6-8.4M, an application 0.18-1.1M, a hiring step's
  prep 2-11M, measured), a steady week, the 30% target. `pro_week_w` stays null until a calibration week is in.
- `cost.py table [<plan>]`: each step's W and its share of the plan's week ("share unknown" before a calibration);
  `cost.py calibrate [<plan>]`: W per 1% of the week, from the status line log and every transcript on this
  computer; `cost.py context`: the coordinator's context and start day, "hand off" or "keep".
- `statusline.py --log <file>`: a row each time the 7-day share changes (`PLAN_USAGE_LOG`, default
  `apply/plan-usage-log.jsonl`); `statusline.py install` adds it to the setting. A status line set up before
  0.40.0 logs nothing until `statusline.py install` runs again.
- `COORDINATOR_CONTEXT` (default 200000 tokens).

### Changed

- A fresh coordinator per day: at the start of a turn the person started, a coordinator begun before today or past
  `COORDINATOR_CONTEXT` writes its handoff and starts a fresh one (`coordinate`).
- Sub-sessions start on Sonnet by default (`SESSION_MODEL=sonnet`, now a cost choice); an essays round and study
  take the main session's model. An empty `SESSION_MODEL=` (every folder set up before 0.40.0) now means Sonnet
  too; `choices.py set SESSION_MODEL=opus` keeps the larger model.
- `RULES.md` "Cost": subagents are only the plugin's own agents, never general-purpose or Explore.
- `PLAN` takes pro, max5, max20 or other (max: an older max5). Setup shows `cost.py table` before it starts, the
  setup week apart.

## [0.39.0] - 2026-11-18

The coordinator reads the shared coordinator rules from cenk-base.

### Added

- `profilelib.py coordinator`: the path of `$CENK_BASE/references/coordinator.md`; exit 1 with the line to run when
  cenk-base is not loaded or older than 0.2.0 (`claude plugin update cenk-base@cenk`).

### Changed

- `coordinate` reads the shared rules first and keeps only the job search's own part; its copies of one coordinator
  per folder, titles, briefs, quoted go-aheads, hand-off files and archiving are gone. Its step 0 checks the shared
  rules file, so a missing or older cenk-base stops the coordinator before it writes any record.

## [0.38.0] - 2026-11-18

The daily search from the 17-18 Nov experiment's real fits: boards and remote feeds first, rules before any model.

### Added

- Remote job feeds as script sources: `source=remotive|remoteok|jobicy|himalayas|arbeitnow` (no board); a feed's
  posting passes only with a region of the scope in its own location field (none named: it does not pass).
- `searches.py add ... mode=remote|any`: LinkedIn's remote filter for `remote`; `searches.py rates` (real fits per
  row, from the funnel's high and normal grades; a row with 20 screened and none is asked about, never dropped);
  `searches.py import <profile.json>` (LinkedIn blocks, boards, feeds; saved rows kept).
- Title rules before any text is read: `SEARCH_RULES` (default `apply/search-rules.json`;
  `templates/search-rules-example.json`), with forms_out, low, level, senior, senior_need, senior_no, no, soft_no,
  need. The same lists filter boards and feeds.
- A LinkedIn remote search's posting goes to the funnel only when its own text speaks of remote work (`TEXT_FETCHES`
  texts a run, default 40); one unread waits for the next run.
- Fit cache: a posting whose employer and title match one the funnel skipped for fit in the last 30 days is left out;
  the same job from two sources in one run is screened once (the board's link kept).
- The search scope from the master record's `preferences.locations.search_scope`: its `remote_regions` stands for
  `REMOTE_REGIONS` and its `any_mode_places` for `PLACES`, each when present.

### Changed

- collect_postings.py reads boards and feeds first, then LinkedIn by city, then LinkedIn remote searches, and fills
  `MAX_NEW_PER_RUN` in that order. The tracker keeps each posting's search row (`search`).
- LinkedIn: 4.5 s between calls (was 4), a job text 6 s; a refusal (429) pauses 60 s and slows to 8 s; a second
  stops LinkedIn for the run (was the first).
- coordinate, schedule, RULES/run.md: Gmail runs first in every run, right after the handoff check, and is never
  dropped for other work.
- RULES/hiring-steps.md: a message readable only after a sign-in is opened in the signed-in Chrome in the same run,
  else an Urgent to-do.
- references/sites/linkedin.md: Easy Apply's CV upload works through the hidden file input with `file_upload`.
- search: a variant of the searches wins by real fits after the full screening, never by a cheap first pass.

## [0.37.0] - 2026-11-17

Every question reaches the Questions page; a keyword sheet for the call, on the other monitor.

### Added

- `questions.py add general "<question>"`: a question with no job or answer key; `record` prints its answer under
  "act on". Example: "Which monitor holds the call?".
- `questions.py add ... keep=yes`; set by itself when a job was already sent or ended at `add`: the build keeps the
  question open until it is answered. Example: withdraw from a sent application.
- `usage.py run-due [at=<time>]`: "due" on a `SEARCH_DAYS` day after `SEARCH_TIME` with no run started today.
- `cheat_sheet.py call=<n>` (kept as `CALL_MONITOR`) and `--monitors`: on Windows the page opens on a monitor other
  than the call's, placed and sized to the spot, in its own Chrome app window (profile `.cheat-sheet-chrome` in the
  main folder).
- `employer.py decide <name> exclude` prints the employer's running applications (`running: <id> | ...`).
- `export_dashboard.py --calendar <events.json>`: `calendar:` check lines for an event of an ended job, a coming
  step with no event on its date, and a step whose event is at another time. Example: "Job search · Acme: reply
  due 19 Nov" for a job rejected on 16 Nov.
- `export_dashboard.py --page <files/index.html>`: a first check line when the dashboard's page code is not the
  plugin's template. RULES/run.md: each refresh passes both.
- A check line for a sent job recorded `rejected` whose reason says the role was filled, closed or put on hold.

### Changed

- Every skill that asks the person (coordinate, apply, plan, prepare, cheat-sheet, setup): each question goes on the
  Questions page as it is asked, in a run or in chat; a sub-session sends it to the coordinator, which adds it.
- `record` is followed by `build` and the page write in the same turn; `record` prints that as its last line.
- Options separate with `|`, so a label may hold a comma: `options="fix:Yes, I correct them|no:No"`.
- Questions page: the Send bar sits under the questions; sent answers are marked `sent` and shown at once under Done,
  greyed, without buttons; a section "Other questions" for `general`. The coordinator publishes the page again.
- coordinate: fact answers (residence and the like) come only from the records, never from memory; `usage.py
  run-due` at each turn, and the active coordinator starts a fresh session for a due run, never runs it in its own
  context (a run inside the coordinator cost 1.4M tokens). schedule: a scheduled run refused by the lock messages the
  active coordinator.
- prepare writes `keywords.md` (the keyword sheet for the call) beside `cheat-sheet.md` (the study sheet);
  `cheat_sheet.py` builds the wide page from `keywords.md`. cheat-sheet opens the page in the same turn with the
  kept or default spot (top), and asks afterwards.
- `job-search.env.template`: a `CALL_MONITOR` key; `build_app_folders.py` links a step's `keywords.md` in its
  overview; the Questions page's Send message counts the "other" questions too.
- The wide page: coloured heading bands, larger keywords (from 34 px down), spacing, higher contrast.

### Fixed

- A board search's site "Examplia (ashby)" gave the employer "Examplia (ashby)", which `employer.py check` matched to
  the excluded employer "Ashby": `collect_postings.py` drops the board from the name, and employer name keys ignore a
  board in brackets.
- `recheck-running` printed "nothing moved" right after `decide <name> exclude`, which had already saved the verdict:
  `decide` now names the running applications itself.
- Dashboard Calendar tab: times in the viewer's local time (an invitation stored with another zone's offset showed
  that zone's clock), and an event tagged with a job that ended (rejected, closed, declined) is left out.
- The dashboard kept an older copy of its page, which reads fields the export no longer writes (no Sessions tab;
  Hiring steps read `upcoming`): the new `--page` check names it, and the refresh writes the template again.

## [0.36.0] - 2026-11-15

The person's profile moves to the shared base plugin cenk-base.

### Changed

- `plugin.json`: `dependencies` `cenk-base` from the `cenk` catalog; installing cenk-jobs installs it. The catalog
  `cenk-jobs` allows it (`allowCrossMarketplaceDependenciesOn: ["cenk"]`); a clone's install adds the `cenk` catalog
  first.
- `profilelib.py`: no own reader or writer; loads cenk-base's `lib/profile.py` by path from `CENK_BASE` and keeps only
  `form_facts`, cenk-jobs as the default plugin for a setting, and the list of move backups after an erase. Commands
  as cenk-base's: `home`, `path`, `get`, `set`, `erase`, `create [<folder>]`, `pin <folder> --yes`.
- Lookup: cenk-base's. `CENK_HOME`, then `cenk/profile.json` in "My Drive", then `cenk/` in the Claude config folder.
  Old places (`claude/profile.json`, the workbench setting `profile_path`, a `PROFILE` line in `job-search.env`) are
  read with a note to move; `create` copies the profile to the cenk folder. Example: `PROFILE=own/profile.json` is
  read only while `G:/My Drive/cenk/profile.json` does not exist.
- `job-search.env.template`: no `PROFILE` line.
- Setup asks for the profile first, then suggests the main folder `<cenk folder>/jobs/` for a new person. An
  existing main folder stays.
- Setup and the coordinator's handoff check: cenk-base missing stops with the line `claude plugin install
  cenk-jobs@cenk` (a plain update does not install it). `check_setup.py` FAILs on it.
- README: Way 2 adds the `cenk` catalog first.
- Scripts that read the profile run in the Bash tool only: PowerShell does not get `CENK_BASE`.

### Removed

- `profilelib.py create` adding a `PROFILE` line to `job-search.env`, and its check that the other plugins find the
  same file.

## [0.35.1] - 2026-11-15

Fixes from the first real run of 0.35.0: 19.25M W (cost-weighted Opus tokens) for 6 applications; 14 of 21 high
fits were reposts of roles already sent.

### Added

- `reposts.py`: a posting whose employer (its keys and saved names) and title words match a role already applied to
  or declined. `collect_postings.py --out` leaves it out and records it `skipped` "repost of <id>". Example: "Software
  Engineer - Senior" at "Acme" after "Senior Software Engineer (m/f/d)" at "Acme (Parent)".
- `workflow_args.py`: the funnel's args from the scripts (about 8 KB), the person's rules in `rules.json` for the
  agents; an excluded employer is left out and named. The args with the rules and known checks inline were 45 KB.
- `PLACES`, `NOT_PLACES`: the accepted places and the cities ruled out, for every posting, carried ones included,
  and for a search with no place; a ruled-out city is refused inside an accepted country.
- `PAY_TABLE` and `career_view.py pay "<city>" [--set]`: one private pay figure per city; each posting gets its
  city's figure, never the home city's.
- `track.py set --file`: many status changes in one tracker write.
- `sessions.py lock` and `unlock`: one coordinator per main folder writes records; a second is refused while the
  first's beat is under 30 minutes old.

### Changed

- Each fit check reads only its employer's postings (`<outDir>/jobs/<employer>.json`, written by
  `workflow_args.py` with a unique name per employer) and the fit record once:
  measured, each fit check read the whole search file, about 246k characters of tool results.
- Role terms match whole words and phrases: "lead" no longer passes "Leadership Coach".
- The workflow counts the grades before the `APPLY_FITS` cut: high, normal, weak, hard, and how many passed.
- The coordinator title is only the person's own main session's; the handoff file is
  `handoffs/job-search-coordinator.md` and lists every open sub-session with its own handoff file.

### Fixed

- `track.py sync`: the plugin's labels always count; a person's `sync.labels` adds older ones. Seen: older labels
  in a settings file hid every `prep-fit:` result (203 of 239 jobs stayed "found").
- `track.py sync`: a fit's skip sets a job still `found` to `skipped` with its reason, an apply to `pending`.
- `employer_lookup.py`: a 429 is a pause and a second pass (at most 5 a run), not the end of the lookups; a name
  holding " | " is printed with " / ".
- `employer.py alias --not`: the other employer is not offered by any of its keys, an alias key included.
- `searches.py sites --add`: no search for an excluded employer; each new row gets `PLACES`.
- `collect_postings.py --since`: a script search read earlier the same day is read again over the window given.
- `sessions.py sync`: a scheduled run's session is a coordinator, never a piece.

## [0.35.0] - 2026-11-15

Setup asks each cost choice with its token cost; the person's answers decide what a run spends.

### Added

- `choices.py`: the cost choices in `job-search.env`, one key each: `WRITER_MODEL` (opus, sonnet), `EMPLOYER_CHECK`
  (cheap, free), `APPLY` (auto, list), `APPLY_FITS` (normal, high), `LETTERS` (asked, always, never), `ASK_FIRST`
  (send, free_text, interview; empty: all alone), `CALENDAR` (auto, self), `PLAN` (pro, max, other: suggests only).
  `show`, `set` (checks each value), `workflow` (the workflow's args), `suggest <plan>` and `grade`.
- Setup's "The cost choices": ten questions, each with its measured cost in W. Example: "Letters by Opus, about 68k
  W a letter, or the cheaper model, about 40k W".
- The fit grade, in code: the fit check returns the posting's must-haves and its gaps; no gap is high, one soft gap
  (a must-have missing, pay up to 10% under, seniority one step off) is normal, a hard gap or two soft gaps is a
  skip. `APPLY_FITS=high` applies to high fits only. The person reads only "high" and "normal".
- `statusline.py`, opt-in: a status line script that saves the plan's usage share (5 hours, 7 days) to
  `PLAN_USAGE`; `read` gives the run report's line. Claude Code gives the share to no other place.

### Changed

- `ASK_FIRST` replaces `APPLY_MODE`: `send` in it is the old review mode. A folder without the key keeps what it did:
  drafts wait for approval, and applications are sent alone unless `APPLY_MODE=review`.
- A new setup's default is `ASK_FIRST=send,free_text`: an application waits for the person's go-ahead until they
  drop `send`.
- `track.py sync` grades each prepared job and prints the queue high fits first, then the newest.
- `APPLY=list` stops the workflow after the fit check; `EMPLOYER_CHECK=free` runs no cheap check; `LETTERS` and
  `WRITER_MODEL` set the writer's work and model; `CALENDAR=self` books no slot and writes no event.

### Fixed

- Waits the dashboard did not show (16 jobs stayed "found" with no to-do for two days): `track.py wait <id>
  needs-person|account-needed "<what>"` records the status and one to-do with its link together, and the coordinator
  uses it as soon as a wait is known.
- A found or pending job nobody owns is a Do now row of its own ("Waits on you: unknown, ask Claude"), not only a
  check line.
- Workday sign-ins: one row per tenant host. A job on `<tenant>.wd5.myworkdayjobs.com` is "Workday · <Employer>";
  `logins.py sync` matches it to the row of the same host, and renames a row named by its host.
- A data question asked in the chat also goes on the Questions page: a compacted chat loses it.

## [0.34.1] - 2026-11-15

Fixes from the first real run of 0.34.0.

### Added

- `searches.py sites --add`: a script search for every employer whose job links are on a board the script reads,
  named by the employer; setup runs it. `searches.py fail`: a board that answers 404 twice is marked gone, no longer
  due, and listed.
- `collect_postings.py --since`; keys `ROLE_TERMS`, `REMOTE_REGIONS` and `MAX_NEW_PER_RUN` (default 30).
- `career_view.py cvs`: the CV list for the workflow, only versions whose PDF exists.
- `references/sites/smartrecruiters.md`.
- `employer_lookup.py`: the free public-data lookup (Wikidata: founding, headquarters, owners, industry) for an
  employer never checked; one request every 2 seconds (it was throttled at one a second); cached in
  `EMPLOYERS_DIR/public-lookup.json` with the facts found, which are judged again under the person's rules of the
  day. Only an item whose name is the employer's own decides; a prefix match (one item whose name only starts with
  it) is a lead for the cheap check. An exclusion it finds stops the job before any token; what only the person's
  notes can decide goes to the cheap check.
- The cheap employer check: agent `checker` (Sonnet, low effort, at most 2 web searches), label `excl-quick:`, run
  for an employer the lookup could not decide. Measured on 10 real employers: 18.3k W each, against 60.4k W for the
  fit check.
- `variants.py order` and `funnel`: the fit check or the cheap employer check runs first, whichever stops the most
  employers per token for this person; it starts from the measured defaults and follows each run's numbers.
- `career_view.py fit`: a smaller view for the fit check (31 KB against 86 KB for the facts view on a real record).

### Changed

- The plugin's levels: an employer founded in a state, or headquartered there, has a direct tie to it.

### Fixed

- The search window starts at the last finished run (it kept every open posting of a new search, and LinkedIn
  always looked 7 days back); a search's own later check wins; `last_checked` holds date and time.
- A remote posting passes only with one of the search's places or `REMOTE_REGIONS`, or as a bare "Remote" (220 of
  497 were US or Canada remote). A search without terms uses `ROLE_TERMS`; with neither it is skipped.
- A board's postings carry the employer's name from the search row (`employer`, else the site without a trailing
  "jobs" or "careers"), not the board's slug. A search read before starts at its own last read.
- At most `MAX_NEW_PER_RUN` postings enter the funnel per run, newest first; the rest wait in the tracker.
- LinkedIn: up to 3 pages a search over the run's window; a refusal stops LinkedIn for the run and leaves its
  searches due.
- `employer.py check` says "unknown, never checked" for an employer the list does not know (`never_checked`); it
  still goes on, as the person decided.
- The fit check sets salary for each job's own city and never guesses "no letter field" for a form it did not read;
  the form step keeps the fit check's salary and CV file.
- `token_report.py` shows "-" for a run's good-fit figures until they are counted.

## [0.34.0] - 2026-11-14

Fewer tokens per run: search by script where it can, a funnel that checks fit before employers, one agent per kind
of work with its own model, and tools to measure and compare.

### Added

- `collect_postings.py`: every saved search a script can read (Greenhouse, Lever, Ashby, SmartRecruiters and
  Workable boards, LinkedIn's guest search) without a model; filters titles and places by the search's terms, drops
  what the tracker has, `--add` records each new posting with `found_by=script:<source>:<board>`, `--out` writes the
  workflow's search file. Saved searches get `method` (script or agent), `source`, `board` and `place`, and
  `searches.py due --json`. The search skill: a source an agent found without an alert is added as a script row when
  a script can read it.
- Agents `fitter` (fit, open check, pay rule, form questions), `former` (the easy form answers) and `writer` (cover
  letters, and free-text drafts when the person allows them); `preparer` is removed, its work split between them.
- `references/filling.md` (the rules an applier needs) and `references/sites/<site>.md` (Greenhouse, Ashby,
  LinkedIn, SuccessFactors, Workday, Eightfold): the applier reads these two instead of all of `RULES.md` and the
  apply skill.
- `variants.py` and `VARIANTS` (`apply/variants.json`, off until `"on": true`): a named model and effort per step,
  rotated over runs; `models` for the workflow; `count` logs each run's good-fit jobs 7 days after it.
- `token_report.py`: tokens per run and per agent kind from this computer's transcripts, numbers only, sends nothing;
  `--json` for a person who wants to share them. `usage.py log ... variant=<name>`.

### Changed

- The screen-and-prepare workflow is a funnel: the fit check first; the employer check only for an employer passed
  with `screen: true` and a posting that fits; the second employer check only on a hit or an unknown (Opus); then
  the form answers, the writer and the review (Opus only where a letter or a draft was written). Each step's model
  and effort come from the run's variant, else the defaults.
- Only an excluded employer stops an application: unknown, warn and "discuss" employers are applied to, and the
  person is asked about a "discuss" employer (or an undecided level) only once it answers with a hiring step.
  `track.py sync` attaches their prepared jobs, also an unscreened employer's, and its queue takes an unset verdict;
  `questions.py build` asks only then.
- The screener runs on Sonnet by default (was Opus); the reviewer at medium effort.
- The applier returns the fields it filled by name only.
- The dashboard is checked by `export_dashboard.py --check`; a page is read only when a check line or the person
  points at something on it.

## [0.33.0] - 2026-11-14

The upload record holds only what was uploaded; a sent job without a letter says so; lessons from applying.

### Changed

- `export_dashboard.py --uploaded <out dir> <file> ...` records only the files named as on the page and keeps the
  others' earlier record; `all` in place of the names records every file. A bare `--uploaded <out dir>` is refused
  (it recorded every export file found there, also one never uploaded).
- Plan, search and apply: every fitting role at one employer is proposed and applied to at the same time; an
  application running there is no reason to wait (0.31.0 only showed the running ones).
- Plan: open free-text questions are filled when the person's setting `draft_answers` is `yes` (the plan skill had
  missed the 0.31.0 exception).
- Coordinate: `APPLY_MODE` is read at the start of every run and named in the first report line; a finished
  search's questions go to the person at once, in one ordered list.
- Apply, Greenhouse: the plain embed form first, the employer's careers form when the embed fails; the location is
  filled early and the whole form is read again before Submit.

### Fixed

- `build_app_folders.py` listed and copied the prepared cover letter for a sent job whose form had no letter field.
  Now `track.py set <id> submitted ... letter=none` (which apply records for such a form) says no letter was sent:
  the folder lists none and copies none. A record without it keeps its letter line as before.

## [0.32.0] - 2026-11-14

A hiring step's keyword cheat sheet as one page beside the call.

### Added

- The skill `cheat-sheet` and `cheat_sheet.py <job id> [step=<n>] [spot=top|bottom|left|right|corner] [--open]`:
  writes `cheat-sheet-wide.html` in the step's folder from its `cheat-sheet.md` (a heading starts a block, every
  other line is a keyword line) and opens it in a new Chrome window. Columns by the spot: top or bottom half 3, a
  side 1, a corner 2. The top line holds the step, the employer, the date and the call link from `PIPELINE`. The
  page shrinks its own text until it fits the window without scrolling (down to 6px) and shows the size.
- `CHEAT_SHEET_SPOT` in `job-search.env`: the spot, asked once and written by `cheat_sheet.py`.

### Changed

- `build_app_folders.py` lists `cheat-sheet-wide.html` with a step's other files; `prepare` offers the page before a
  call.

## [0.31.0] - 2026-11-14

An undecided finding asks the person instead of excluding; one browser, the person's Chrome; answers drafted for
approval when the person allows it; lessons from applying, preparing and employer checks.

### Added

- A finding's level may be `undecided` (`employer.py record ... flagged level=undecided`, and the screen agents):
  a detailed search could not settle direct or indirect. It excludes nothing and holds nothing up: the Questions
  page asks "Allow, or exclude?", and the search and the applications go on meanwhile.
- The setting `draft_answers` (the profile's `settings.cenk-jobs`, off by default): with `yes`, Claude writes each
  open free-text answer in full from the person's records, shows it and fills it only after their approval. An
  employer's no-AI rule opens the draft as one warning line; a question on AI use is answered truthfully; a "no AI"
  pledge is never ticked by Claude.
- `CHROME_PROFILE` in `job-search.env`: the Chrome profile the job search uses; a page in another profile is named
  with its profile.

### Changed

- `employer.py record ... flagged` without `level=` is refused (it was saved as direct, which could exclude an
  employer on a level nobody judged). An undecided finding never enters the shared blacklist (`employer.py
  merge`) or a usage report.
- One browser: every job site, job board, alert and the mail fallback in the person's Chrome; never the Claude
  desktop app's built-in browser pane (reading and job alerts used it). A browser step names the held tab and how
  to find it; its address is text marked "open in Chrome", and the same address is the to-do's link.
- Lessons: the main session sends new `plugin-lessons.md` lines to the session titled "Coordinator · workbench"
  (0.30.0 named "Coordinator · cenk-jobs" first).
- Apply: read a job's status and pipeline before saying it only needs a yes; read a select field's own options
  before advising a value; replace the stored resume and the capitalised name on every Greenhouse form; Ashby's
  field handling; rank and percentile picks are compared with the evidence text and the records; picks the person
  makes themselves are made in the form, in a named tab; a form in another session's tab group is filled again;
  contractor pay by the contract's length, rounded up, at the day's ECB rate.
- Coordinate: a rebuilt CV is uploaded again by every session that holds a filled form, before any Submit.
- Prepare: the step's date and time are checked against now first, and the next step is named with its time.
- Plan and search: a posting at an employer where applications already run is shown with them, as information;
  several at one employer may run side by side.
- Employers: state lists (the person's country's, the EU's, the UN's, another) are offered as options for a state
  tie.

## [0.30.0] - 2026-11-14

The dashboard shows only what the person does, lists the sessions in the order to answer them, and every export says
what disagrees with the records; searches are saved and read from where the last one stopped.

### Added

- `track.py todo <id> add <kind> "<text>" [where= due= link= login= session= since=]`, `todo <id> done
  <n>|all|kind=<kind>|session=<id>`, `todo <id> list`: to-dos are no longer edited by hand. The kind `waiting`: the
  next move is the employer's; never in Do now, shown in Hiring steps with since when.
- `sessions.py` and the record `SESSIONS` (default `apply/sessions.json`): `sync <list.json>` (the app's session
  list), `set <id|name> state= waits= jobs= due= tab= steps= name=`, `order <id|name> ...|auto`, `show`. The order of
  the sessions that wait on the person: the ones `order` names, urgent, the nearest fixed date, a form held open in
  a browser tab, the fewest steps left, the longest wait.
- The dashboard's Sessions tab and dataset (`sessions.json`, the seventh file), and one numbered "Answer first" row
  per waiting session in Do now; a to-do with `session=<id>` is on its session's row.
- The cross-check: every export ends with one `check:` line per mismatch between the records and the page, then
  `check: <n> mismatches`; `export_dashboard.py --check` prints them and writes nothing. Example: `check: to-do on
  an ended job: J3 (rejected 2026-11-10), 2 to-do(s) -> track.py todo J3 done all`.
- `export_dashboard.py --uploaded <dir>` records what is on the page (`dashboard-uploads.json`); every export ends
  with `upload:` and `unchanged:`, so only a changed file is uploaded.
- Do now kinds `late` ("Past due", never Urgent) and `queued` ("Claude's next": open jobs nobody owns).
- `searches.py sites` (the tracker's sites with no saved search), `add ... note="<text>"`, `--today <date>`; `due`
  with no saved search prints one line that says so.
- `SEARCH_DAYS` in `job-search.env` (`weekdays`, `daily`, `none`, or the days as text), `SESSIONS`, `SESSION_MODEL`
  (the model new sessions start with).
- A hiring step with `"proposed": true` in `PIPELINE` reads "Proposed" and is no task; `"done": "<date>"` marks a
  step done.
- `questions.py build` writes `checked` and `open` into `status/run.json`: the Questions page shows when Claude last
  checked, also before any answer.

### Changed

- The scheduled run is on weekdays at 19:00 by default ("Job search: weekday run", cron `0 19 * * 1-5`); every day
  only when the person asks. The dashboard header reads `SEARCH_DAYS` and `SEARCH_TIME` ("Next: weekdays at 19:00."),
  and each run corrects the two keys from the task's real schedule. A task that runs every day stays so.
- Search: every search has a saved row, created by the plugin (none saved: one per site and query; a person with a
  tracker and no rows: from `searches.py sites`). Each site is checked once for a free email alert and the person is
  asked in one question for all of them. A site without an alert is searched at every weekday run, newest first,
  up to its last check, and never on a weekend (`every=7` makes it weekly; it was every 7 days). An alert email
  that only links to the site starts a search of that site in the same run.
- Logins: a "connected" or "signed in" last checked before the run started reads "not checked since <time>" and is
  not counted as working, connectors too (no run recorded: older than 3 days). The coordinator re-checks each
  connector before every export.
- `track.py set` into submitted or an ended status drops the job's to-dos, prints them and keeps them in the
  history row (`todo_dropped`).
- The export: one application row per job id; a step's date, due, done and cancelled come from `PIPELINE`; no to-do
  of an ended job, except one set on or after a sent job's end date; an open step of a job that is over is "ended",
  never upcoming or past due; an excluded employer's own site leaves the Logins tab (`employerlib.excluded_site`).
- Hiring steps tab: the State column (Upcoming, Proposed, Done, Past, Cancelled, Ended, Waiting since); what is
  ahead first, the nearest first; the steps behind only under "All steps", the latest first.
- Coordinate: keeps `SESSIONS`; a sub-session's title follows its state at once; the person may answer a session's
  one-line question in the main chat; each run compares the calendar with the records and reads every dashboard
  tab in the browser.
- Lessons: the main session sends new `plugin-lessons.md` lines, with their line numbers, to the session titled
  "Coordinator · cenk-jobs" when one is open; a job-search session never starts a session in the plugin's
  repository. A lesson line names no employer and quotes nobody.
- Apply, prepare and the essays round: a later answer beats a prepared one; a hypothetical form question is
  explained first; a public form gets no keep-alive tab; a code step in a held tab is found by the tab's new title;
  a form left at the review page says that Submit sends it as it is; a prep is reread when the study starts; a
  session that drafts answers checks the posting is open before each round of approvals.
- Mail while the connector is down: read and labelled in the person's signed-in Chrome, one-time codes masked.

### Fixed

- A sent job with a kept `not-applied` folder was counted twice.
- A step already done, or due last week, stayed Urgent.
- `logins.py sync` never matched a per-employer site ("Workday · Acme") to its excluded employer.
- A `same_as` application without its own stage was filed under Waiting for a reply.
- With no saved search, a run searched every site again: `searches.py due` printed nothing.

## [0.29.0] - 2026-11-12

The person's own facts live in one profile, shared with the other cenk-* plugins; four lessons from applying.

### Added

- `profilelib.py`: the person's profile (`claude/profile.json` in their Google Drive's "My Drive", or `PROFILE` in
  `job-search.env`): `path`, `get <key>` (`[n]` picks a list item), `get <plugin> <key>` (a setting), `set <key>
  <json|-> [--old <json>]` (compare-and-set: another value there changes nothing and exits 3), `erase <key>` (the value
  and its history; then the earlier versions Google Drive keeps), `create <path>` (only at the path the person chose).
  The writing rules match the workbench's `profile.js`. A key under `settings` changes only with `--yes`, given after
  the person's yes to that key and value: without it, nothing is written, it exits 1 and names the key and both values.
  `erase` also names the backups `move_to_profile.py --remove-old` left, which may still hold the value. With no
  `job-search.env`, `create` refuses a path no lookup finds; after pinning `PROFILE`, it says the other cenk-* plugins
  need the workbench setting `profile_path`.
- `move_to_profile.py`: the one-time move of the person's facts from `MASTER_RECORD` and `PERSONAL_RECORD` into the
  profile. A dry run by default; `--apply` adds what the profile lacks and never writes over another value;
  `--confirm <key>` for a field to confirm (`pronouns_on_linkedin`); `--remove-old` after the person's OK removes
  what the profile holds unchanged, after a backup. Field names and paths only, never a value. It lists for a hand
  move the experience rows' true dates, referees without `agreed_on`, history entries about moved fields, and the
  main-folder files that repeat a profile value.
- The setting `form_facts` (`settings.cenk-jobs`, else `settings.common`, in the profile): the guarded items a form
  may answer from the profile (`birth_date`, `address`, `references`, `criminal_record`, `relatives`, `health`).
  Default none: each goes into the job's needs, as before. ID numbers never.
- `check_setup.py`: the profile (found, readable, `person.name`), `form_facts` names that are no guarded item, and
  old copies (`PERSONAL_RECORD`, person facts or referees in `MASTER_RECORD`); `--needs` names a missing profile. It
  warns when `PROFILE` names another file than the one the other cenk-* plugins find.
- `apply`: SuccessFactors behind a Career Site Builder front end lands on the portal's home page after sign-in: the
  job is opened by its requisition id inside the signed-in portal.
- `apply`: LinkedIn Easy Apply sends only a CV stored on LinkedIn (no file input behind its upload buttons): the
  stored CV's date is checked, and the person is asked once to upload the current CVs.
- `apply`: Easy Apply blocks Next on a work-experience entry without dates: no date is invented and no entry deleted;
  the person fixes it.

### Changed

- `questions.py`: a private answer goes to the profile's `private.<key>` (`typed` is kept as `words`), a
  `key=person.*` answer to `person`; never over another value (listed under "ask the person"; `answer ...
  replace=yes` after the person chose) and never without a profile (listed under "no profile").
- `career_view.py facts` adds the profile's `person` (only name, pronouns, contact, location, languages, links,
  nationality and work authorisation: never address, birth date or a key added later), `employment` and the
  `form_facts` names; never `private` or `contacts`.
- The preparer marks a guarded item that `form_facts` names "from the profile", with no value; the session that fills
  the form types it from the profile.
- A form's questions are read before Chrome opens, from Ashby's `non-user-graphql` (`ApiJobPosting`) or Greenhouse's
  `?questions=true`: `apply`, `plan` and the preparer write a letter only for a form with a letter field, and the
  preparer puts each essay question into needs, so it reaches the Questions page in the same run.
- `PROFILE` replaces `PERSONAL_RECORD` in the env template; the new folder's `career.json` has no person facts or
  references. Setup, coordinate, apply, `RULES.md` and `RULES/questions.md` name the profile: any session saves a fact
  about the person there at once, and a handoff names the key.

## [0.28.0] - 2026-11-11

Lessons from the job-search sessions of 11 Nov 2026: apply sites and the Questions page.

### Added

- `apply`: SuccessFactors uploads a CV through the `span.addAttachments` icon (the "Upload a CV" label does nothing),
  then the dialog's `input[type=file]` (`fileData1`), one upload at a time.
- `apply`: an Eightfold dropdown option takes pointerdown, mousedown, pointerup, mouseup and click, in that order.
- `apply`: Workday can end the session after about 25 minutes on one application: each step is saved as soon as it is
  filled, and the sign-in is checked before the next step.
- `questions.py build` ends a job question whose jobs all ended, so nobody answers it for nothing: `closed`, with a
  note saying when, if one was sent; `dropped` if none was (excluded, declined, skipped, closed, failed).

### Changed

- The run order in `schedule`, `coordinate` and `RULES/run.md` names the shared-list update after the handoff check.
- `questions.py record` records button answers at once and lists every typed answer under "read first": Claude reads
  it, records a plain answer with `answer` (spelling and grammar fixed, meaning unchanged) and replies to a question
  or remark ("did we already send this?") without recording it.

## [0.27.0] - 2026-11-11

A new version of the shared blacklist reaches the person's own records.

### Added

- `EMPLOYERS_DIR/shared-seen.json`: per employer and category, a fingerprint of the shared list the person last took
  in (the status and a sha256 of the fields as found, 12 hex; 37 KB against 128 KB for a copy). The first time, only
  the fingerprints are saved.
- `opinion` (its date) on an employer the person gave an opinion on: a decision (`employer.py decide`, or an answer on
  the Questions page) or a finding they stated (`employer.py record ... --person`); an older entry with a decision
  counts too. `employer.py check` shows it.
- `employer.py shared-update [--from <file>] [--apply]`: per changed check, an employer the person never gave an
  opinion on follows the new version, a retraction too (the old finding goes to the history; one line each in the
  run report); an employer with their opinion gets one `ask` item, with every changed category, and a question for
  the Questions page ("Allow, or exclude?"); a change its record already holds needs none. A check that `merge` would
  refuse (no source on a finding, an unknown level or status, another category) never enters the records. A dry run
  without `--apply`; `--apply` backs the records up first. Only an exact own entry takes an update; a group entry
  covering a unit keeps its record.
- The coordinator runs it each run after the handoff check: a dry run, the questions, then `--apply` (so a stopped run
  loses no question), then `recheck-running`.
- `apply`: signing in to SuccessFactors from a job's Apply link can submit at once by quick apply from the stored
  profile: upload the CV to the profile first, or sign in from the site's home page.

### Changed

- README: eight categories, the first "ties to the state of Israel"; the second check and shared-list updates.
- A note that limits which employers are acceptable ("Western countries only") never lowers a finding's level in the
  second check: the level stays as found and the category's action decides, exclude or ask.

### Fixed

- `recheck-running` and `track.py sync` saved the "discuss" of a due second check as the employer's verdict, so after
  the second check an employer still at "discuss" for a real reason looked unchanged and was never listed. They now
  save the verdict from the findings and levels alone; the jobs still wait while a second check is due.

## [0.26.0] - 2026-11-11

Employer levels per category, a second check against the person's own rules, and running applications checked again.

### Added

- Levels per category in `templates/employer-rules.json`. Defence: direct = a defence offering (a product line, or a
  defence sales team or page); indirect = named sales to the defence industry, armed forces or a defence ministry,
  with no defence line; a general product open to anyone is no tie (`clear`, with that fact).
- State categories (`state_category`): direct = HQ in the state, an owner from it, operating only there or only for
  it, selling to a state body or a state-owned company (police included), or a hit on the category's lists;
  indirect = an own office, R&D team or subsidiary there, selling there itself or through a reseller, an investor or
  another firm between them; self-service users are no tie. `israel` is the only default state, with its four lists;
  another is added only when the person names it.
- A second check against the person's own rules (a category's `notes`), only for a finding in that category:
  `own_level` direct, indirect or none, `own_why`, `own_checked` and `own_rules` beside the finding, which stays as
  found. The workflow runs it as `excl-own:` (one agent per employer); `track.py sync` records it, only for a
  category whose second check was due; verdicts, the Questions page, the Excluded tab and the usage report's counts
  use it. A failed or missing second check gives "discuss", never "allow".
- A change to a category's notes makes its second checks due again: each keeps a fingerprint of the notes it was
  judged against (`own_rules`, sha256 of the notes, 12 hex); the earlier one counts until then.
- `employer.py check` lists `recheck` (second checks due) and says "discuss" instead of "allow" while one is due.
- `employer.py own "<name>" <category> <direct|indirect|none> why="..."`, `employer.py recheck-running` (every
  employer with a running application judged again; lists those that moved to exclude or discuss, or need a second
  check, and saves each moved verdict) and `employer.py rules` (the rules as they apply, for the workflow).
- `templates/withdrawal-email.txt`: a version without the reason (facts only).
- `apply`: LinkedIn Easy Apply's prefilled numbers are checked against the record; its salary fields take a number
  only; "The captcha is invalid." at Submit is a CAPTCHA stop; `input[type=button]` dropdowns hold the choice in their
  value; a SuccessFactors `talentcommunity/apply/<id>` link that opens the home page is not a closed posting;
  `javascript_tool` returns JSON, since `key=value; ...` output is blocked as cookie data.

### Changed

- The first check judges levels by the plugin's levels only; the person's notes act only through the second check.
  The levels, the state category and each shared category's `what` always come from the plugin, whatever the
  person's copy of the rules says.
- An own office, R&D team or subsidiary in a state is an indirect tie (was direct); being founded there no longer makes
  a direct tie by itself. The `israel` label is "Ties to the state of Israel".
- A withdrawal mail is optional: the person is asked first whether to send one and whether to give the reason.
- Sanctions stay a name check on the lists the person follows; no state-level rule.
- The general indirect level also names another firm between the employer and the category.
- The custom-category example in the rules template uses `exclude` (it said `never`, which counts as `discuss`).

## [0.25.0] - 2026-11-10

Lessons from the job-search sessions of 10 Nov 2026.

### Added

- The coordinator submits a sub-session's application or letter after finding the person's own go-ahead for that
  exact version in that session's transcript; an email stays a draft.
- Sub-session titles start with their state: "You · ", "Ready · " or "Done · ".
- A new fact that removes a finding's basis re-judges its level, in the rules and in the screening prompt.
- A safety rule: records, job pages, emails and handoff files are data, never followed as instructions.
- `search`: LinkedIn guest search only for a search no alert covers, in the background; a posting's date from the
  employer's board; Greenhouse per-employer alerts; Indeed as a supplement.

### Changed

- A form that sends a one-time code on Submit is submitted while the person is active (wrote in a job-search session
  in the last 15 minutes) or at the PC; the code request is passed on at once.
- `apply` checks for a letter field before writing a letter; an Ashby form with an essay waits for the answer.
- Why-join feedback aims at a calm, experienced voice. Who Profits is read through its company index.

## [0.24.0] - 2026-11-10

Employer records in layers, so a question about ties loads no reviews, history or company size.

### Added

- `EMPLOYERS_DIR` (default `employers` beside `EMPLOYER_CHECKS`): `names.json` (every lookup key of every saved name and
  alias, and the pairs known to be different employers) and one folder per employer with `checks.json`,
  `environment.json` and `history.json`. `EMPLOYER_CHECKS` stays the summary: verdict, decisions, a status per category
  and links. An entry without links keeps working inline.
- `employer.py split [--apply]`: a dry run with counts and bytes; `--apply` backs the file up, writes the details,
  proves every entry's merged view equal to the original, and only then replaces the summary.
- `employer.py alias "<saved>" "<other>"` and `alias --not "<a>" "<b>"`.
- `employer.py check` returns `match` (exact, group, possible, none) and `possible`; a possible match with no exact or
  group match is "discuss", reason "possible match: Examplia Internet GmbH (exclude)". `--full` adds environment and history.
- `record` keeps the replaced check as a history item with `until`.
- `tests/run.sh`: 27 checks for keys, matching, alias, split, record on a split file and a refused details path.
- On a copy of real records: the summary about a quarter of its size, `check` output about 30% smaller, dashboard and
  application folders unchanged.

### Changed

- `employer.py check` prints `has_environment` instead of `environment`; `--full` prints the finding.
- `save_json` writes LF line ends.
- `search` and `setup` skills and the `applier` agent say how a browser page is read: `find`, `read_page` or `get_page_text`.

### Fixed

- A short name now finds its saved full name as a possible match: `check "Examplia"` is "discuss" against "Examplia Internet GmbH", no longer "allow".
- `keys("A Co")` is "a co", no longer empty: a name that would reduce below 2 characters keeps its legal form.

## [0.23.0] - 2026-11-10

Less context per session and per agent. Measured 4-10 Nov 2026: a main session starts at 84k context, a default
subagent at 66k.

### Added

- `agents/`: `screener`, `verifier`, `preparer`, `reviewer` and `applier`, each with a model and a short tool list. A
  subagent with a short list starts at 15k context instead of 66k.
- `career_view.py screen|facts`: the part of the master record a job needs (42 KB and 78 KB instead of 410 KB).
- `searches.py`: saved searches, read from alert emails or checked on a schedule. `seen` (or `seen --file`) says whether a posting is new.
- `check_setup.py --needs`: the programs, connectors, sign-ins and answers the next run waits on.
- The handoff check in `coordinate`: every sub-session ends with `handoffs/<short name>.md`, and each new coordinator
  reads them first, records them, deletes them and safe-ends the sessions. A handoff names answered fields, never their
  values. New settings: `ARCHIVE_SESSIONS` (empty: ask), `APPLY_PARALLEL` (2), `SEARCHES` (`apply/searches.json`).
- `track.py split [--apply]`: one summary row per job and company with links; details in one file each. On a copy of
  real records: 2.84 MB to 0.70 MB, `track.py show` 3.6 KB to 1.4 KB, generated folders and dashboard unchanged.
- `employer.py repair-clear [--apply]`: a "clear" with no fact and no source becomes "unknown".
- `tests/run.sh`, `.gitattributes` (LF).

### Changed

- `RULES.md` is a router of 10 KB (from 27 KB) with the safety rules; the rest moved word for word to `RULES/`, read by audience.
- `workflows/screen-and-prepare.js`: a model and agent per stage. Compared on 4 employers against recorded verdicts: 4 of
  4 equal, every recorded flag found again, 4-8 turns and 125-203k weighted per agent against an 855k average before.
- `/cenk-jobs:schedule`: the scheduled session is that day's coordinator, since a trigger's turn cannot start a session.
  A task made before this version keeps messaging the old session until `/cenk-jobs:schedule` makes it again.
- `/cenk-jobs:search`: alert emails, then connectors, then job-board scripts, a browser last. An employer whose israel
  or defence check is `unknown` goes to the screen.
- Applying: one `applier` subagent per application, one tab each, at most `APPLY_PARALLEL` at once. An applier has no
  shell and writes no record: the session that started it records each report.
- Job alerts the person says yes to for a site are the one exception to optional consents.
- A job-search session never edits the plugin: a lesson is one line in `plugin-lessons.md`; only a session opened in
  this repository changes it.
- Never read a screenshot. On one posting `get_page_text` is the same in both browsers and `read_page` is 15k characters
  in the built-in browser against 36k in Chrome; applying stays in Chrome, the only one with `file_upload`.

### Fixed

- `employer.py decide` replaced a tracker verdict only when it was "discuss", so excluding an "allow" company left "allow".
- `employer.py import-tracker` wrote israel and defence "clear" with no fact or source; it now writes "unknown".

## [0.22.0] - 2026-11-10

### Added

- Working environment per employer: `employer.py environment "<name>" reviews=<n> rating=<x> complaints="a; b"
  source=<url>` saves what employee reviews say (rating, number of reviews, complaint topics, source, date), apart
  from the categories. `employer.py check` shows it, `merge` holds a report's block to the same limits and carries
  it into the shared `data/blacklist.json`, the usage report includes it and `company.md` gets a section.
- The search looks up the reviews once for each employer that is not excluded; a saved result is reused until the
  person asks for a refresh. It never changes a verdict.

## [0.21.1] - 2026-11-10

### Fixed

- Do now shows every job's own to-dos, whatever the job's status. A sent job's items (an interview reminder, a
  withdrawal to send) were dropped before; only "working" rows showed.

## [0.21.0] - 2026-11-07

### Changed

- Do now's Question rows are the Questions page's open questions (from `QUESTIONS`), one each, so the dashboard and
  the page always agree; a job with an open question there shows no other row from its note. A job waiting on the
  person for anything else shows its note as a **To do** row (a new kind, with a filter and a header count), not as
  a Question; a to-do's `"where": "pc"` shows "at your PC" on it too.
- Without a Questions page (no `QUESTIONS` file yet), employers the rules leave to the person still get a Question
  row in Do now. A tracker to-do without a kind, or with the older "info", now shows as To do.

## [0.20.1] - 2026-11-07

### Changed

- The seven skill descriptions fit the 350-character budget (one clause on what the skill does, "Use for" with the
  phrases a person types, one boundary), so all of them together take about 550 tokens of every session's context.
  Each keeps its main English phrases and one or two in Italian or Turkish.

## [0.20.0] - 2026-11-07

### Added

- Urgent steps say where they can be done: each notification starts with "From your phone:" (a Questions-page
  answer, a yes in a session through Remote Control) or "At your PC:" (a code, a CAPTCHA or a sign-in in the
  Chrome form), and Do now's Urgent rows carry the same tag (a to-do's `"where": "pc"` or `"phone"`).
- A code is started only when the person is at the PC: a form that sends a one-time code on Submit (example:
  Greenhouse's emailed security code) is filled and left open, and Submit waits for "I'm at my PC", so the code
  arrives while the person is there. On "I'm at my PC" the coordinator has every waiting PC step go on, one at a
  time.

## [0.19.0] - 2026-11-07

### Added

- Urgent steps: a step only the person can do that expires (an emailed or SMS code, a CAPTCHA or Submit on a filled
  form, a sign-in page waiting, a Submit left for their yes, a deadline within 24 hours) gets one notification at
  once, on the desktop and on the phone when Remote Control is on, from the session that hit it. Example: "Acme:
  type the emailed code into the open Greenhouse tab in Chrome; valid about 10 min." Never twice, never for what
  can wait; the daily run sends one for deadlines today or tomorrow.
- Do now's Urgent kind (red, first in the list, with its own filter and a count in the header): a job's `todo` with
  `"kind": "urgent"`, and every task due within 24 hours.

## [0.18.1] - 2026-11-07

### Changed

- Both pages carry the plugin's name: "cenk-jobs · Job applications" (the dashboard, `dash/meta`) and "cenk-jobs ·
  Questions for you", never a generic "Dashboard". Setup pins both to the claude.ai sidebar as one of its defaults
  (no separate question); a person who turns it down gets them unpinned, with how to pin one later.

### Fixed

- The dashboard's links to the Questions page (in the header and in Do now) now show: they started `hidden`, and the
  dashboard draws only what is shown, so they never appeared. They start visible and empty instead.

## [0.18.0] - 2026-11-07

### Added

- The Questions page reaches the main session: "Send my answers to Claude" sends one message to the Claude sessions
  watching the page (a comment sent to Claude), and Discuss sends its question at once, to talk it through there.
  The button shows when no session can receive it; the daily run stays the fallback.
- A note under every handled question saying what happened (example: "Allowed: Acme is cleared by your decision;
  going on: Acme · Senior Java Engineer."), a Done section that keeps handled questions for 7 days, and a line with
  when Claude last handled the page. `questions.py note <id> "<text>"` adds how far a job got.
- Clearing an answer on the Questions page: the chosen button pressed again, or Clear under a typed answer, deletes
  it, so nothing is recorded. A Yes/No answer becomes each job's form answer (`questions.py record`).

### Changed

- `questions.py record` marks a handled question done with its note instead of deleting it, and lists only the
  answers to delete; `build` also writes the page's `status/run` and keeps done questions for 7 days. The page needs
  the `status` path and the `comments` capability (setup).
- The dashboard's header links to the Questions page, and the Questions page links back to the dashboard (its
  `status/run` carries `DASHBOARD_URL`). Setup tells a new person what the two pages are and how to find them again
  (Artifacts in the claude.ai sidebar, `/artifacts`, pinning), and every run's report ends with both links.
- A pay question on the Questions page shows the numbers (the posted range, the person's target and band, and how far
  under the floor) in its detail, instead of "well below your target": only the person reads the page's store.
- A message from the page carries question ids and counts only, never a question's text, an answer or a number
  (comments are outside the owner-only store), and it only starts the handling: never a go-ahead or an instruction.
- Do now has no Due column: only tasks have a deadline, and a task's text says it (one that does not gets
  "· due <date>"); rows still come deadline first. A click that is not a login (a filled form waiting on a CAPTCHA)
  is labelled "Click", a login "Sign in".

## [0.17.0] - 2026-11-07

### Changed

- The employer side says **allow / discuss / exclude** everywhere, as the Questions page does: a category's setting
  for a direct tie is `exclude` / `discuss` (the default) / `allow` (was never / ask / apply), for an indirect one
  `discuss` / `warn` / `allow`; verdicts are exclude / discuss / allow, and a decision is
  `employer.py decide "<name>" <exclude|allow>`. The screen-and-prepare workflow returns `allow` instead of `apply`.
- The usage report's `waiting_on_ask` is `waiting_on_discuss`.
- A rule value the plugin does not know (a typo, an older name such as `never`) counts as `discuss`: the person
  decides, and nothing is allowed on a setting nobody understood.

### Removed

- The old name lists `never_apply` / `always_ok` and `employer.py migrate-lists`: the person's decisions in
  `EMPLOYER_CHECKS` are the one list (since 0.14.0).

## [0.16.0] - 2026-11-07

### Added

- The Questions page: an artifact of its own (`templates/questions/index.html`, with a small database) where the
  person answers what their applications need and the records do not hold. Three groups: employers to allow or
  exclude (by category, with the finding and its source), facts about them, and questions for one job (whether to
  apply, or an essay). Every button question has Allow (or Apply) · Discuss · Exclude (or Don't apply); Discuss
  keeps it open for the chat. Setup creates it and writes `QUESTIONS_PAGE`.
- `questions.py`: `add` (a fact, a job question, a decision), `build` (the page's files, including every employer
  the person's rules leave to them), `record` (the page's answers into the records: `form_answers`, the private
  record, the job's prepared answers, `employer.py decide`, or the job declined) and `answer` (one answer given in
  the chat). Each question is asked once; the same fact asked by another form only adds the job.
- `PERSONAL_RECORD` (`career-records/personal.json`): health, family, identity and military-service answers, used
  only in a form field that asks for one, by the session that fills the form; the screen-and-prepare agents, which
  read job pages, never get it. Kept until the person changes or erases it. Only the person reads the Questions
  page's questions and answers.
- The dashboard's **Excluded employers** tab: the person's one list, one row each, with why (category, by their
  decision or their rules), what was found, its source, the jobs and since when, filters (Withdrawn, Your decision,
  Your rules) and a search. Built at each export from their records (`employerlib.excluded_list`, `excluded.json`).

### Changed

- Logins holds only logins: excluded employers left the Logins tab (its "Excluded" group is gone) and `LOGINS` (no
  more employer rows); an excluded employer's site is marked `excluded` and not shown there.
- Do now: "Answers" is now "Questions for you", with a link to the Questions page; an employer the rules leave to
  the person points there ("Allow, or exclude?").
- RULES: a new section "Questions for the person"; health, family and identity answers only from the person's own
  answer in `PERSONAL_RECORD`.

## [0.15.0] - 2026-11-07

### Added

- The setting `APPLY_MODE`: `auto` (the default for everyone) or `review`. In auto mode Claude fills and submits
  every application whose answers all come from the person's records, and reports after; the daily run applies on
  its own. In review mode it stops at the review page and waits for the person's go-ahead, as before. Setup offers
  it among the defaults; the env template has `APPLY_MODE=auto`.

### Changed

- Do now holds only what Claude cannot do: a CAPTCHA, a password, a sign-up, an emailed code, an ID number, an
  essay or self-rating, pay below the person's target, or a question the records do not answer. Before, every
  application waited for a go-ahead.
- The apply and coordinate skills, the setup defaults, the README and the plugin's descriptions follow the setting.
  Emails stay drafts the person sends (`send_mode`), and optional consents stay off.
- Logins: no more "unknown". A new state `excluded` is for an employer the person's rules exclude (no sign-in needed,
  never in Do now); a site no job waits on keeps its last state with the reason in its note, and a needs-sign-in
  row nobody waits on shows as "not signed in". The Logins tab's groups: Needs you, Signed in, Connected, Not
  signed in, Excluded. The health check counts only logins something waits on.
- `logins.py sync` lists every employer the person turned down for their rules (a job excluded, or a withdrawal on
  ethics) as an `excluded` row, rebuilt from their own tracker, pipeline and checks at each sync, so they remember it:
  the reason in words (the finding behind it: what the employer does, its category and level, or their decision)
  and the jobs by role. Example: "Excluded: your decision, Defence industry: Acme builds armoured vehicles. Jobs:
  Team Lead".
- One list of the person's employers: `EMPLOYER_CHECKS`, with findings and decisions. The `never_apply` and
  `always_ok` name lists are gone from the rules template; `employer.py migrate-lists` moves an older one into
  decisions (each with the category of its finding), and `employer.py decide ... --group` lets one decision cover a
  group's units ("Acme" covers "Acme Cloud Services", even when that has an entry of its own). The verdicts stay the
  same.
- Do now has one Answer row per employer the person's rules leave to them ("ask"): the finding, its category and
  level, its source link, and "Apply, or never?". Before, an ask reached the person only in the chat.
- The Applications tab marks every application whose employer has a "warn" finding: a "warning" pill beside its
  stage and the reason in words in its status column.

## [0.14.0] - 2026-11-07

### Added

- Two login states: `needs-sign-up` (no account yet; the person creates it) and `expired` (the person was signed in
  and the session ended). Claude sets them with `logins.py set`; Do now says "Create an account on" and "Sign in
  again to".

### Changed

- The dashboard's Logins tab shows the person's logins in groups, in a fixed order: Needs you (needs sign-up,
  expired, needs sign-in, reconnect, blocked), Signed in, Connected, Unknown, each with its count, and within a group
  the sites with the most waiting applications first. Each state has a label, not only a color. Before, the rows
  were sorted only "needs something" before "OK", so the states mixed.
- Do now marks "Answer" rows like the others (before: an unmarked pill). An existing dashboard gets both by updating
  its `files/index.html` from the template.

## [0.13.1] - 2026-11-07

### Changed

- The withdrawal template covers more cases, with placeholders only, no company or reason written out: a greeting
  when the mail names a recruiter (`{greeting}`), the role titles when the person applied to several roles
  (`{roles}`), the role in the step, and a fact that may join two findings of one category and names its source.
  The draft is shown in the chat as well as in Gmail.

## [0.13.0] - 2026-11-07

### Added

- Setup checks two more programs: pypdf (reads the person's PDFs as text and checks each CV built) and Poppler
  (`pdftoppm`, shows Claude PDF pages as images), with install commands for Windows, Mac and Linux. pypdf goes into
  Python's own folder, since the scripts run with `python -I`.
- `check_setup.py` warns when pypdf or Poppler is missing.

### Changed

- Setup lists every missing program in one question and installs each one unless the person says no, saying which
  licence an install accepts. Before, it asked once per program and installed only on a yes. A command that needs
  `sudo` or an administrator is the person's to run.
- README: `employer.py decide` takes a category, not the person's words; `usage.py stats` is listed.

## [0.12.2] - 2026-11-07

### Added

- `plugins/cenk-jobs/LICENSE`, a copy of the repository's MIT licence: an install fetches only the plugin folder, so
  the licence text now travels with it.

## [0.12.1] - 2026-11-07

### Changed

- The repository history starts again at this version, as one commit: the earlier commits held personal data
  of the developer. The versions below are kept as notes; their commits are gone.

### Fixed

- The shared blacklist holds findings only, labelled by the rules in `RULES.md`, never a person's decision: one
  finding (a parent group named as a creditor in a report that is not one of the four step-1 lists) had the level
  "direct" from the developer's own answer; it is "indirect", as the two-step check defines it. What each person
  does with a finding stays in their own `EMPLOYER_RULES` and `EMPLOYER_CHECKS`.

## [0.12.0] - 2026-11-06

### Added

- The usage report counts the jobs turned down because of the employer rules (`employer_rules`): excluded before
  applying, withdrawn after applying (before or after a hiring step) and waiting on the person's answer to an
  "ask", each by category and by where the finding came from (shared list, own check, decision, never-apply list).
  The person's own filters count as `custom`. The email's summary gets one line. Example: "Turned down because of
  the employer rules: 4 (defence 3, named_list 1) before applying, 1 (climate 1) withdrawn after applying; 2
  (sexism 2) waiting on the person's answer."
- `usage.py stats` prints the same block for the person, whatever `USAGE_SHARING` says; it sends nothing.
- `employerlib.excluding()`: the categories behind an exclude verdict.
- A declined entry in `PIPELINE` with `why: ethics` carries the `category`.

### Fixed

- A `never_apply` name matches every name that starts with it as whole words, and parts in brackets: "Acme"
  catches "Acme Cloud Services" and "Acme Bank (CIB)". Before, only the exact name matched, so a group's units
  passed the list. `always_ok` stays exact. Same in `employerlib.py` and the screening workflow.
- The report's "Steps that did not end ok" no longer lists a run's `started` line.

## [0.11.0] - 2026-11-06

### Added

- The Gmail label `GMAIL_DONE_LABEL` (default `cenk-jobs/Done`) on each job-search message whose action is done:
  booked and in the calendar, recorded, or the person's reply sent. A message waiting on the person stays
  unlabelled. The run searches with `-label:`, labels messages, not threads, so a new reply in a thread is found,
  and never archives, marks read or removes the person's own labels. Setup creates the label (RULES.md, "Mail").
- Withdrawal lines for the `sanctions` category and for custom categories in `templates/withdrawal-email.txt`.

### Changed

- The withdrawal draft goes to every excluded employer the person applied to once it writes beyond an automatic
  confirmation (an invitation, a task, a recruiter's mail) or offers a job, also when a new check excludes it
  mid-process; it states the employer's sourced fact. Before, only an employer that offered a job or invited to a
  step got one.
- A draft always has a recipient. A no-reply sender: the recruiter named in the mail, else the careers contact on
  the employer's own site, else the privacy contact on the posting, each checked on its page.

### Fixed

- `templates/dashboard/datasets.json` parses again: the calendar dataset missed a closing brace since 0.2.0, so
  setup could not read the store documents from it.

## [0.10.0] - 2026-11-06

### Changed

- The Israel check runs in two steps, for the employer and its parent or majority owner: the lists (the BDS
  movement's current targets, the UN OHCHR settlement-business database, Who Profits, AFSC Investigate), then four
  questions from the company's own pages, each with a source link (founded or headquartered in Israel; its own
  office, R&D team or subsidiary there; its majority owner; supplying Israel's military or police, or the
  settlements). A list hit or a yes is a direct tie; resellers, investors' other holdings, customers, board members'
  outside seats and licensees' owners are indirect. A small or new brand is checked through its parent first, and
  nothing found is "nothing found", never "clear". The default stays "warn and ask" for both levels.
- The shared blacklist was checked source by source before going public: each flagged finding was kept, fixed or
  dropped (wrong, a namesake, unsupported, personal data, not a finding, or an ended tie), and true ties judged weak
  stay as indirect findings, so each person's own rules decide. It now holds 268 employers and 148 flagged
  findings (51 direct, 97 indirect).
- `LICENSE` (MIT); the README is written for a public repository.

## [0.9.0] - 2026-11-06

### Changed

- One skill per job, no "jobs" repeated in the names: `setup` (the first run, once), `coordinate` (the main
  session), `search` (find and screen only), `plan` (which applications, in which order, with which CV and letter),
  `apply`, `prepare` (hiring steps and interviews) and `schedule` (the daily run). `start` is gone: its name read as
  setup-only, so people never knew to use it every day. The dashboard has no skill: setup creates it and every run
  refreshes it.
- The rules every skill shares are in `plugins/cenk-jobs/RULES.md`; the scripts, templates, data and workflows
  moved from `skills/start/` to plugin level (`plugins/cenk-jobs/scripts/`, ...).
- The repository is now `cenksimsek1988/cenk-jobs` (was `claude-job-search`), like the plugin's name.
- Every run says when it starts and finishes (`usage.py log run started|ok`); the dashboard header shows "Running
  now" or the last run and the next one (`SEARCH_TIME`, default 19:00).
- The health check fails without a dashboard; the run then creates it and offers to pin it.
- One main session: every run says that the coordinator is the person's main session, and a skill started in
  another session sends the person there.
- Usage reports go to `cenk.plugins.reports@gmail.com` (`DEVELOPER_EMAIL` in `scripts/usage.py`), an address only
  for reports about Cenk Simsek's plugins.

### Added

- Setup offers the defaults in one choice, says how to change each one, and asks for the person's own filters: the
  daily run at 19:00, optional consents off, open questions left to the person, drafts only, and every employer
  category "warn and ask" for direct and indirect ties.
- A `sanctions` category for everyone: the UN Security Council list plus the lists the person follows (`lists`).
- The person's own filters as categories with `"custom": true` (example: gambling); checks, decisions and the
  screening workflow treat them like the shared ones, and they stay out of the shared blacklist.

## [0.8.0] - 2026-11-06

### Added

- An "In progress" kind in Do now (to-do kind `working`): Claude, or a session with the person, is on it, so the
  person waits. Those rows come first, with their own chip, tile and count; the coordinator sets them when a piece
  starts and removes them when its report is recorded.
- The dashboard leads with the full count of applications (sent and not sent) and their split by outcome, a tall
  segmented bar with each part's share, a legend and hover names; colors validated in light and dark mode.
- `employer.py merge --from-checks`: the developer merges their own checks into the shared blacklist, every
  sourced finding, direct and indirect, without their decisions and with their name masked in every fact.
- Keep-alive while a filled form waits for the person: a second tab on the same site is reloaded every 10 minutes,
  for at most 2 hours; the form's own tab never is. At sign-in the person ticks "Keep me signed in".

### Changed

- A decision never turns a finding into "clear": the shared list keeps every sourced finding, so each person's own
  rules decide.
- The shared blacklist now holds 270 employers (it held 18), merged from the developer's own checks.

## [0.7.0] - 2026-11-06

### Added

- Two outcomes beside rejected: `closed` (the role closed, was filled or put on hold, or the person was late: not a
  rejection) and `declined` (the person said no, with `why`: ethics, relocation, pay, other). `PIPELINE` stages
  `closed` and `declined`, tracker statuses `closed` and `declined`, folders `closed/` and `declined/`, README
  sections, dashboard tiles and filters, and counts in the usage report.
- `employer_link` and `JOB_BOARD` in `trackerlib.py`: an employer's own site is never signed in to through a job
  board's page. `logins.py sync` drops such a link and takes the employer's own one from the job.
- Every Do now row on the dashboard has a link: its own, else the step's email, else the job's application page.

### Changed

- Claude checks every link before giving it to the person: it lands on the employer's own site or hiring system, or
  a job board only when that board's form is the way to apply. 404, 410 or "no longer available" means closed.
- The screening stores the employer's own application page in `apply_url`, checked by fetching it.

## [0.6.0] - 2026-11-06

### Added

- A hiring step in `PIPELINE` has `link` (its own page: meeting, test, booking or interview) and `mail` (the Gmail
  link of the email that set it). The job summary (`overview.md`) links both in the step's line.
- Every calendar event the person owns holds the step's own link and the email link in its description.

### Changed

- A to-do's `link` is the email link. A personal access link stays in the calendar and the person's folder, never
  on the dashboard.

## [0.5.2] - 2026-11-06

### Changed

- The dashboard's Calendar tab drops an event once it has ended. Before, an interview earlier today stayed until
  midnight. An existing dashboard gets this by updating its `files/index.html` from the template.

### Fixed

- The Calendar window starts at the viewer's local midnight. Before, it used the UTC date, so in the first hour
  after midnight in Europe it still showed the day before.

## [0.5.1] - 2026-11-06

### Fixed

- The dashboard export masks pay in job titles, folder names and step names too. Before, a title such as
  "Senior Java Software Engineer - EUR 400 a day" reached the dashboard with its rate.

## [0.5.0] - 2026-11-06

### Added

- `templates/withdrawal-email.txt`: the withdrawal mail for an employer the rules exclude that offers a job or
  invites to a step, with one subject and rule line per category. Claude drafts it; the person sends it.

### Changed

- Records the plugin writes in the person's folder are fact lines, never narrative or quoted chat; a decision is a
  value and a date. Example: `exclude, defence, 2026-11-06`.
- `employer.py decide "<name>" <exclude|apply> [<category>]` takes no quote; it stores `{date, verdict, category}`.
  Older decisions with `words` are still read.
- Rule changes in `EMPLOYER_RULES` record `{date, field, new}` in `changes`.
- The coordinate skill's report asks for one fact line per new fact. A go-ahead forwarded between sessions is still
  quoted in that message, and is not stored.
- This repository is developed by the workbench rules: fact lines with an example (`CLAUDE.md`).

### Fixed

- The pay mask hides a whole range: "EUR 70-90k", "70k-90k EUR", "€70,000 – €90,000", "USD 60–100/h",
  "500-650/day". Before, "EUR 70-90k" became "[private]-90k" in the dashboard export.
- The pay mask no longer hides ordinary words: a currency code must stand alone, and TRY counts only in capitals.
  Before, "try 2 times" became "[private] times" and "12 European" became "[private]opean".

## [0.4.1] - 2026-11-06

### Changed

- A session started outside the main folder (another project, a git worktree) now moves there with the app's
  change-directory tool, ends the turn, and reads the main folder's `CLAUDE.md` on the next one. It starts a new
  session there only when the move is refused, and without a session tool it tells the person to run `claude` in
  the main folder. Before, a session in a worktree or another project never tried to move.
- A coordinator that moved takes the title "Job search coordinator", so the daily trigger finds it.
- Install from Cenk Simsek's public catalog `cenk` (repository `cenksimsek1988/claude-plugins`) as `cenk-jobs@cenk`,
  once this repository is public and listed there. This repository's own catalog is renamed from `cenk` to
  `cenk-jobs`, for a clone you work on and for invited people (`cenk-jobs@cenk-jobs`). An install from the old `cenk`
  of this repository: `/plugin marketplace remove cenk`, then install again one way.
- The version lives only in `plugins/cenk-jobs/.claude-plugin/plugin.json`; the catalog entry has none, since
  Claude Code reads `plugin.json` first.

## [0.4.0] - 2026-11-06

0.3.1 was never released; its changes are in this version.

### Added

- Employer rules for everyone: seven default categories (ties to Israel's occupation or military, defence industry,
  animal cruelty, climate and environmental harm, sexism, human rights, working conditions), each counting only with
  a crime-level problem shown by a sourced finding. Default: warn and ask; per category the person picks never / ask
  / apply, and for indirect ties ask / warn / apply (`templates/employer-rules.json`, `EMPLOYER_RULES`).
- The shared blacklist `data/blacklist.json`, seeded from the developer's own sourced exclusions, and
  `employer.py` (check, record, decide, import-tracker, merge).
- The screening workflow returns one check per category and applies the person's settings: "never" excludes, "ask"
  waits for the person; `track.py sync` writes the checks to `EMPLOYER_CHECKS`.
- Usage reports, only with the person's yes (`USAGE_SHARING`): `usage.py` logs routine steps and builds a weekly
  report without personal data (applications per week, outcomes and first "yes" answers, sites, employers checked
  with their findings, steps), drafted in Gmail to the developer for the person to send.
- Calendar: each online interview is checked for a video link; without one, a draft request to the recruiter the
  day before.
- The daily run: on the first run, with the person's OK, a scheduled task "Job search: daily run" every day at 19:00
  in the person's local time (the default for everyone), which starts the run in the coordinator session.
- This changelog, and `CLAUDE.md` for sessions opened in this repository.

### Changed

- The coordinate skill's example session names no longer name real companies: `apply-workday-acme`,
  `prep-acme-18nov`, `study-acme-6nov`.
- `cheat-sheet.md` holds keyword lines only, never scripted sentences.
- The study section offers the mock interview the day before the step, not on its morning.
- `build_app_folders.py` keeps the jobs of an "ask" employer visible; the pay mask moved to `trackerlib.py`.

## [0.3.0] - 2026-11-05

- Shipped from GitHub only; `release.py` builds `dist/cenk-jobs.plugin` from HEAD.
- The job search runs only in its main folder; a study piece for hiring steps.
- The plugin scripts are the only code a job search needs.

## [0.2.0] - 2026-11-05

- Renamed to cenk-jobs, with the skills start and coordinate.
- Published to a Drive folder and as an uploadable `cenk-jobs.plugin`.

## [0.1.0] - 2026-11-05

- The job-search plugin, shared through a Google Drive folder.
- The documents step: say where things are, or drop them in documents-inbox.
- The dashboard as a tree of linked files, a login state file and a job-search calendar category.
- The job-search-coordinator skill.
