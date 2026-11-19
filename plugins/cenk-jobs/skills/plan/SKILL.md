---
name: plan
description: "Plan the applications: orders the cleared postings by deadline and fit, picks each CV and letter, lists what the person must do first. Use for 'plan my applications', 'what should I apply to today?', 'which CV for this job?', 'pianifica le candidature', 'başvurularımı planla'. Never sends."
---

# Plan: which applications, in which order

Read `../../RULES.md` first. This skill writes the plan into the tracker; it sends nothing.
Every question this skill asks the person goes on the Questions page as it is asked, in a run or in the chat (RULES/questions.md); in a sub-session, by a message to the coordinator, which adds it.

## Steps

1. Take the open jobs from the tracker (`track.py list`): cleared by the screen, waiting on the person, or ready to
   send. Leave out excluded, skipped, closed and declined ones.
2. Order them: deadline first, then fit, then the sites the person is signed in to (`logins.py show`).
3. For each job, the CV version that fits the role (`CV_VERSIONS_DIR`) and its letter template; the letter itself is
   written now (`LETTER_BODIES_DIR`) by `LETTERS` (`asked`: only for a form with a letter field, `apply`, "Before
   filling"; `always`; `never`), and its PDF
   built on the day it is sent (`make_letter_pdf.py`).
4. Group by sign-in: one group per site or hiring system. A group needs the person signed in before it can start.
5. List what only the person can do, per job, as to-do items in the tracker (`track.py todo <id> add <kind>
   "<text>" link=<form>`): sign-ins (`click`), answers and essays (`todo`). Open free-text questions are never
   filled for them, unless their setting `draft_answers` is `yes` (RULES.md, "Honesty and what Claude never does").
6. Propose today's batch: the groups the person can start now, high fits first, then normal, then long-shots up to
   `LONG_SHOTS_PER_DAY` a day, newest first in each (the order `track.py sync` prints). Weak fits are listed with
   their score for the person, never in a batch; an unread posting waits for the next run's fit check. Every role that fits at one employer is proposed
   and applied to at the same time: an application already running there is no reason to wait. The running ones are
   listed beside it (role, stage, next date), as information. On their OK, `/cenk-jobs:apply` (or the coordinator's
   sessions, one per site) takes them. Refresh the dashboard.

## Report

The batch, by company and role: the CV, the letter, the sign-in it needs, and what waits on the person. Log it:
`usage.py log plan ok "<n planned>"`.
