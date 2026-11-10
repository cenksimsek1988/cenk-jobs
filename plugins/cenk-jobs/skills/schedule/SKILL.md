---
name: schedule
description: "Schedule the daily job-search run: creates, moves or stops the scheduled task that starts it in the main session (19:00 local time by default). Use for 'schedule my job search', 'run it every day', 'change the run time to 8am', 'stop the daily run', 'her gün çalıştır'. Not the search itself."
---

# Schedule: the daily run

Read `../../RULES.md` first.

## Create, move or stop

- Create (on the person's OK): a scheduled task "Job search: daily run", every day at `SEARCH_TIME` (default 19:00
  local time; cron `0 19 * * *`; the scheduler may add a few minutes). Its working folder is the main folder; its
  prompt is "Run /cenk-jobs:coordinate for today's run." The task's own session is that day's coordinator: it takes
  the title "Job search coordinator" and starts with the handoff check, so no run pays for an older session's context.
- Move: change the task's time and `SEARCH_TIME` in `job-search.env` together. Stop: disable or delete the task on
  the person's yes.
- Say the result in one line: "Daily run: every day at 19:00, in a fresh main session."
- A trigger's turn may not start other sessions: the run does its pieces as subagents, or proposes each as a card.

## What each run does

The coordinator runs it (RULES.md, "Every run"):
`run started` -> handoff check -> `check_setup.py --needs` -> health check -> Gmail and calendar (`/cenk-jobs:prepare`) -> search (`/cenk-jobs:search`) -> plan
(`/cenk-jobs:plan`) -> apply where the person is signed in (`/cenk-jobs:apply`, one `applier` subagent per application) -> prep for
the nearest steps -> `build_app_folders.py` and the dashboard -> `run ok` and the short report.

Log each step with `usage.py log <step> <ok|failed|stopped> "<note>"`. At the end, `usage.py due`: "ask" asks the
usage-report question once; "due" shows the person the report text and, on their yes, drafts the email (they send
it), then `usage.py mark-drafted`.
