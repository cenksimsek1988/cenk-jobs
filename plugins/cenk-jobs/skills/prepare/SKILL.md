---
name: prepare
description: "Prepare the hiring steps: reads invitations and tests in Gmail, books slots, puts steps in the calendar, writes prep notes, practises. Use for 'prepare my interview', 'let's practise', 'book the interview', 'any interview invitations?', 'mülakata hazırla'. Never accepts offers; replies are drafts."
---

# Prepare: hiring steps and interviews

Read `../../RULES.md` first, then `../../RULES/hiring-steps.md` ("Mail", "Calendar", "Outcomes"). Prepare the nearest steps first; a far-off step's
prep waits.

## Mail and calendar

1. Gmail, messages without the label `GMAIL_DONE_LABEL`: interview invitations, availability requests, booking
   links, tests and forms, rejections and closed posts, confirmations, and replies to the person's own mails.
2. With `CALENDAR=auto` (`choices.py show`): book slots by the person's scheduling rules (the master record's
   `preferences`); with `interview` in `ASK_FIRST`, propose the slot and book it after their yes. With
   `CALENDAR=self`: book nothing and write no event; record the date the person gives. A reply to a recruiter is a
   draft the person sends.
3. With `CALENDAR=auto`, each step and deadline into the calendar (RULES.md, "Calendar"), with its own link and the email link; the same
   two into the step (`track.py step <id> add name="<step>" date=<date> link=<url> mail=<message id>`); a step due
   within 24 hours: RULES/urgent.md. Rejections, closed posts and declines: `track.py outcome` (RULES/hiring-steps.md).
   Each employer reply also gets its feedback line: `feedback.py add <id> invitation|rejection
   not_fit="<what did not fit, from the reply and the posting>"`. Example: `not_fit="payments domain; Kotlin"`.
4. Each message whose action is done gets the label `GMAIL_DONE_LABEL` (RULES.md, "Mail"). A reply waiting as a
   draft gets it on the run that finds the person's sent reply.

## Employer check first

A first hiring step at an employer: its full employer check runs before any prep (/cenk-jobs:coordinate,
"Employer check"); the prep waits for its sync. Example: Acme invites to a first interview: the check runs, then
the prep.

## Prep notes

For each new step, in its step folder: `prep.md` (from the posting and the master record only), `cheat-sheet.md`
(the study sheet, read in the minutes before the call: keyword lines, facts, numbers, names of things; never
scripted sentences) and `keywords.md` (the keyword sheet for the call itself: the same blocks, a few words per line,
readable at a glance while listening or speaking). Example: `- 12 engineers, 3 teams` in the study sheet,
`- 12 eng / 3 teams` in the keyword sheet.

Before a call, `/cenk-jobs:cheat-sheet` shows `keywords.md` as one page beside the call, with no scrolling.

When the study starts, read `prep.md` again against the posting and the records as they are now, and correct it
first: a prep written days before goes stale. Example: a prep of 9 Nov names a CV version replaced on 12 Nov.

## Study and after a step

A study session or an after-a-step session reads `../../references/study.md` first: the study notes, studying
with the person, and what to record after a step.

## Report

The session ends with one line per step it handled, by company and role: the step and its date, what was booked,
drafted or prepared, and what waits on the person. Example: "Acme, Staff Engineer: technical interview 18 Nov
14:00, booked; prep notes ready. Waiting on you: send the reply draft." Log it: `usage.py log prep ok`.
