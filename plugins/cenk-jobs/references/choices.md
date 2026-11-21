# The cost choices

Read by /cenk-jobs:setup, step 4, and by the session where the person changes a choice.

Ask each on its own, with its cost line, after the defaults. W is a cost-weighted Opus token, measured on real runs.
Write the answers with `choices.py set KEY=value ...`; `choices.py show` lists them. Free in every case: the search
by script, the list lookup, the public-data lookup, employers the person adds by hand.
First ask the plan (Pro, Max 5x, Max 20x or other): `choices.py suggest pro|max5|max20|other` gives the starting
answers, never the final ones. Example: Pro suggests `APPLY=list`, `LETTERS=never` and one run a week.
Then show the cost before anything starts, as `cost.py table <plan>` prints it: the setup week apart and a steady
week against the target share of a Pro week, each figure measured or an estimate as the table says. While it prints
"unknown" for a share, give the W figures and say the shares come after a calibration week. Example: "Setup: <the
table's figure> (estimate). A steady week: 5 searches, 10 applications, 1 interview prep. Its share of your Pro
week: not known yet."

1. Letters and free text: Opus, which writes better (about 68k W a letter), or the cheaper model with its review
   (about 40k W). `WRITER_MODEL=opus|sonnet`, default opus.
2. Employer check: the list and the public-data lookup always run, free, and their warnings always show. The cheap
   model check where the lookup cannot decide: about 18k W per new employer, once. `EMPLOYER_CHECK=cheap|free`,
   default cheap.
3. Applying: fill and send where the records answer everything (about 210k to 280k W an application), or only a
   list of fitting jobs with links, sent by the person (the fit check alone, about 60k W an employer).
   `APPLY=auto|list`, default auto.
4. Which fits: the fit check names each gap between the posting and the record. A hard gap (place, work mode,
   eligibility, a required language, a clearance) skips the job; the kinds of soft gaps count: none high, one normal,
   two long-shot, three or more weak (a domain gap with no adjacent fact counts two). Send high and normal, or only
   high. Each application less saves about 280k W. `APPLY_FITS=normal|high`, default normal. Long-shots and weak
   fits a day on top: `LONG_SHOTS_PER_DAY`, default 0 (none, listed for the person; about 180k-1.1M W each). The
   weighted score stays as information; the soft kinds and channel notes: `FIT_SETTINGS`
   (`templates/fit-settings-example.json`).
   After `APPLY_FITS` goes from high to normal, or `LONG_SHOTS_PER_DAY` up from 0: `track.py reopen` lists the fits
   the old setting skipped, never sent; on the person's yes, `track.py reopen --apply --per-day 15` sets them back to
   found, 15 a day newest first (one fit check and one preparation each); a fit outside the places now stays skipped.
   Example: "4 to reopen".
   The fit check's model: Sonnet (about 60k W an employer), Opus at medium effort (about 100k W, estimated), which
   reads the requirements against the record closer, or Opus at max effort (about 150-300k W, estimated; up to 30M W
   on a day of 100 employers). `FIT_MODEL=sonnet|opus|opus-max`, default sonnet.
5. Cover letters: where the form shows a cover-letter field, also where a file field takes one, or never; about 68k W
   a letter with its review. A form not read (Easy Apply) gets one only when it is open and shows a field.
   `LETTERS=asked|always|never`, default asked.
6. What waits for the person (only with `APPLY=auto`), one answer per step: sending an application (`send`); a
   free-text answer Claude drafted under `draft_answers` (`free_text`); booking an interview slot (`interview`).
   `ASK_FIRST=send,free_text` by default; empty: all alone. Asking costs the person's time, not tokens. Essays
   "auto" is `free_text` left out; `choices.py show` names it.
   Form filling: an emailed application code read in Gmail by Claude (`EMAILED_CODES=off|on`, default off; one or
   two Gmail reads a form, about 5-10k W), and optional demographic fields filled from the profile
   (`OPTIONAL_FIELDS=off|fill`, default off).
7. Interview slots: Claude books them and keeps the calendar (about 50k to 80k W an invitation, estimated), or the
   person does and Claude records the date. `CALENDAR=auto|self`, default auto.
8. Runs: weekdays, some days, weekly or by hand (`SEARCH_DAYS`, `SEARCH_TIME`, through `/cenk-jobs:schedule`).
   Each run has a start cost (1.7M to 4.7M W measured in long sessions; a fresh run less); fewer runs take more
   postings each, and some close in between. Default weekdays at 19:00.
9. Postings per run: a number or `unlimited` (`MAX_NEW_PER_RUN`, default 30). Applications go high fits first, then
   the newest.
10. The plan's share in the run report, opt-in: Claude Code gives it only to a status line script. On a yes,
    `statusline.py install` copies the script into the main folder and prints the `statusLine` setting; add it to
    the person's Claude Code settings after their yes to that change. An existing status line stays, with `--then`.
    It also logs each change of the 7-day share (`PLAN_USAGE_LOG`); after a week, `cost.py calibrate <plan>` gives
    W per 1% of the week, the figure the shares come from.
11. Sub-sessions: Sonnet (0.6 of the Opus cost per turn; measured: apply, search and prep sessions cost about 130M
    W in 12 days on Opus) or Opus. Essays and study always take the main session's model.
    `SESSION_MODEL=sonnet|opus|haiku`, default sonnet (empty counts as sonnet).
