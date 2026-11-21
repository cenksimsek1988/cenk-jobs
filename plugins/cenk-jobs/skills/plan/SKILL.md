---
name: plan
description: "Plan the applications: orders the cleared postings by deadline and fit, picks each CV and letter, lists what the person must do first. Use for 'plan my applications', 'what should I apply to today?', 'which CV for this job?', 'pianifica le candidature', 'başvurularımı planla'. Never sends."
---

# Plan: which applications, in which order

Read `../../RULES.md` first. This skill writes the plan into the tracker; it sends nothing.

## Steps

1. Take the open jobs from the tracker (`track.py list`): cleared by the screen, waiting on the person, or ready to
   send. Leave out excluded, skipped, closed and declined ones.
2. Order them in the apply order's three groups (RULES.md): those that need nothing from the person, then those
   that need only a sign-in (`logins.py show`), then the rest; inside each, deadline first, then fit.
3. For each job, the CV version that fits the role (`CV_VERSIONS_DIR`) and the letter the funnel prepared
   (`track.py brief <id>`: `letter_txt`). A job without one gets it when its open form shows a field `LETTERS`
   fills (`LETTER_BODIES_DIR`; `apply`, "Before filling"). Its PDF is built on the day it is sent
   (`make_letter_pdf.py`).
4. Group by sign-in: one group per site or hiring system. A group needs the person signed in before it can start.
5. List what only the person can do, per job, as to-do items in the tracker (`track.py todo <id> add <kind>
   "<text>" link=<form>`): sign-ins (`click`), answers and essays (`todo`). Open free-text questions are never
   filled for them, unless their setting `draft_answers` is `yes` (RULES.md, "Honesty and what Claude never does").
6. Propose today's batch: the groups the person can start now, high fits first, then normal, then long-shots up to
   `LONG_SHOTS_PER_DAY` a day, newest first in each (the order `track.py sync` prints). Weak fits are listed with
   their score for the person, never in a batch; an unread posting waits for the next run's fit check. Every role that fits at one employer is proposed
   and applied to at the same time: an application already running there is no reason to wait. The running ones are
   listed beside it (role, stage, next date), as information. Under `APPLY=auto` the batch goes to
   `/cenk-jobs:apply` at once (or the coordinator's sessions, one per site; with `send` in `ASK_FIRST` each stops at
   the review page); under `APPLY=list` the batch is the list in the report. Refresh the dashboard.

## Report

The batch, by company and role: the CV, the letter, the sign-in it needs, and what waits on the person. Log it:
`usage.py log plan ok "<n planned>"`.
