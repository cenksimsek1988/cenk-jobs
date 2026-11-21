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
- A trigger's turn may not start other sessions: the run, a fresh session, does its pieces itself and applies through
  `cenk-jobs:applier` subagents (the one exception, /cenk-jobs:coordinate "Pieces"), or proposes a piece as a card.
- A scheduled run that finds a coordinator active (its lock is held) takes over: it asks that coordinator for its
  handoff ("write your handoff, unlock, reply 'handoff written', then stop"), and on the reply takes the lock and
  runs as the day's coordinator. Example: the coordinator was active 4 minutes before 19:00; it hands off and the
  19:00 session runs. Seen 16-18 Nov: the run stood aside and never ran.

## What each run does

The coordinator's "Each run" list (/cenk-jobs:coordinate), in its order. In a scheduled run the pieces run in the
run's own session, applying through `applier` subagents, or become cards, since a trigger's turn starts no session
(above).
