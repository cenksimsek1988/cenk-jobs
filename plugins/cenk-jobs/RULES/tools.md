# cenk-jobs rules: tools

A part of `RULES.md`. Read when you need a script's name. One line per script; the script's own docstring (the top
of its file) has every command and option. Run one as RULES.md, "Where things are", says. Example: `python -I
"<plugin>/scripts/track.py" show J7 --env "<main folder>/job-search.env"`.

## Records

- `track.py`: the tracker: add, set (`--file` for many), wait, todo (add, done, list), show (`--full`), brief, list,
  summary, sync (a screening run's journal), split (summary rows and detail files).
- `questions.py`: the Questions page: add, list, note, answer (`--file`), build (`--check`), record.
- `logins.py`: login state: set, sync, show.
- `sessions.py`: the open sessions and the order to answer them: sync, set, order, show, lock, unlock.
- `employer.py`: employer checks: check (`--full`), own, record, environment, decide, alias (`--not`), rules,
  recheck-running, shared-update (`--apply`), split, repair-clear, import-tracker, merge.
- `searches.py`: saved searches: add, list, due, done, fail, sites (`--add`), seen, rates, import, every, discover.
- `usage.py`: the usage log and the weekly usage report: log, due, run-due, report, mark-drafted, stats.
- `feedback.py`: employer replies as fit clues: add, silent, clues, analyse.
- `profilelib.py`: the person's profile through cenk-base: home, path, get, set (compare-and-set), erase, create,
  pin, coordinator (the shared coordinator rules' path).
- `move_to_profile.py`: once: the person's facts from the master record into the profile.

## Search and the funnel

- `collect_postings.py`: new postings from every due script search, without a model (`--out`, `--add`).
- `employer_lookup.py`: the free public-data lookup of an employer never checked (`--record`).
- `reposts.py`: postings that repeat a role already applied to, declined, or skipped for fit in 30 days.
- `fetch_jd.py`: a posting's full text as `job-description.md`; `--posting`: an unread posting's text for the next
  fit check.
- `workflow_args.py`: the funnel's args (`--search`); `--screen "<name>" --out <dir>`: the full employer check before
  a first hiring step.
- `workflows/screen-and-prepare.js`: the Workflow that screens employers and prepares the cleared jobs; it never
  submits.
- `variants.py`: the run's variant, its models, the good-fit count, the funnel's numbers and the check order.
- `choices.py`: the person's cost choices: show, set, workflow, suggest, grade, fit.

## Documents and pages

- `career_view.py`: one part of the master record (screen, facts, fit), the CV list (cvs), the pay table (pay).
- `build_cv.py`: every CV PDF from its JSON (`--no-photo`).
- `make_letter_pdf.py`: one cover letter PDF, on the day it is sent; `--job-file` and `--job` take the company and
  role from a prepared file.
- `build_app_folders.py`: the application folders; never deletes what the person or Claude wrote.
- `export_dashboard.py`: the dashboard's files, what to upload and the `check:` lines (`--check`, `--uploaded`).
- `cheat_sheet.py`: a step's `keywords.md` as one page beside the call.
- `fx.py`: a pay figure in another currency at the ECB's rate of the day, rounded up.

## Setup and cost

- `check_setup.py`: the health check (`--needs`: what the next run waits on).
- `init_career_folder.py`: the main folder and its `job-search.env` (never overwrites).
- `cost.py`: the plan cost table: table, calibrate, context.
- `statusline.py`: the opt-in status line: install, read.
- `token_report.py`: tokens per run and per agent kind from this computer's transcripts.
- `jsenv.py`, `trackerlib.py`, `employerlib.py`: shared code.

Older records: the scripts also read a tracker kept before the plugin (`{companies: [...]}`). Optional keys:
`TRACKER_SETTINGS`, `REDACT_FILE` (private text replaced in every application file; keep it outside shared
folders), `SENT_CVS_DIR`, `SENT_CVS_BEFORE_DIRS`, `SEARCH_TIME` (the scheduled run's time, default 19:00),
`SEARCH_DAYS` (its days, default `weekdays`).
