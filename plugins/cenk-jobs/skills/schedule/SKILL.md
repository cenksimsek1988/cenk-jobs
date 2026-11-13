---
name: schedule
description: "Schedule the job-search run: creates, moves or stops the scheduled task that starts it in the main session (weekdays at 19:00 by default). Use for 'schedule my job search', 'run it every day', 'change the run time to 8am', 'stop the daily run', 'her gün çalıştır'. Not the search itself."
---

# Schedule: the scheduled run

Read `../../RULES.md` first.

## Create, move or stop

- Create (on the person's OK): a scheduled task "Job search: weekday run", Monday to Friday at `SEARCH_TIME`
  (default 19:00 local time; cron `0 19 * * 1-5`; the scheduler may add a few minutes). Weekend runs only when the
  person asks: then "Job search: daily run", cron `0 19 * * *`. Its working folder is the main folder; its
  prompt is "Run /cenk-jobs:coordinate for today's run." The task's own session is that day's coordinator: it takes
  the title "Job search coordinator" and starts with the handoff check, so no run pays for an older session's context.
- Move: change the task and `job-search.env` together: `SEARCH_TIME`, and `SEARCH_DAYS` (`weekdays`, `daily`, or the
  days as text, example `Mon, Wed`). Stop: disable or delete the task on the person's yes, and `SEARCH_DAYS=none`.
- The dashboard header reads the two keys ("Next: weekdays at 19:00."). Each run, compare them with the task's real
  schedule (the scheduled-tasks list) and correct the keys. A task that runs every day stays so until the person
  changes it. Example: the task has cron `0 19 * * *` and the key says `weekdays`: write `SEARCH_DAYS=daily`.
- Say the result in one line: "Scheduled run: weekdays at 19:00, in a fresh main session."
- A trigger's turn may not start other sessions: the run does its pieces as subagents, or proposes each as a card.

## What each run does

The coordinator runs it (RULES.md, "Every run"):
`run started` -> handoff check -> shared-list update (`employer.py shared-update`, its questions, `--apply`) ->
`check_setup.py --needs` -> health check -> Gmail and calendar (`/cenk-jobs:prepare`) -> search (`/cenk-jobs:search`) -> plan
(`/cenk-jobs:plan`) -> apply where the person is signed in (`/cenk-jobs:apply`, one `applier` subagent per application) -> prep for
the nearest steps -> `build_app_folders.py` and the dashboard -> `run ok` and the short report.

Log each step with `usage.py log <step> <ok|failed|stopped> "<note>"`. At the end, `usage.py due`: "ask" asks the
usage-report question once; "due" shows the person the report text and, on their yes, drafts the email (they send
it), then `usage.py mark-drafted`.
