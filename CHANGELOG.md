# Changelog

All notable changes to the cenk-jobs plugin. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Every change gets an entry here and a new version in
`plugins/cenk-jobs/.claude-plugin/plugin.json` (the catalog entries carry none): a GitHub install updates only when
the version changes.

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
