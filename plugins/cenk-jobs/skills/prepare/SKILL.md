---
name: prepare
description: "Prepare the hiring steps: reads invitations and tests in Gmail, books slots, puts steps in the calendar, writes prep notes, practises. Use for 'prepare my interview', 'let's practise', 'book the interview', 'any interview invitations?', 'mülakata hazırla'. Never accepts offers; replies are drafts."
---

# Prepare: hiring steps and interviews

Read `../../RULES.md` first, then `../../RULES/hiring-steps.md` ("Mail", "Calendar", "Outcomes"). Prepare the nearest steps first; a far-off step's
prep waits.
Every question this skill asks the person goes on the Questions page as it is asked, in a run or in the chat (RULES/questions.md); in a sub-session, by a message to the coordinator, which adds it. Example: "Which slot, Tuesday 10:00 or Wednesday 15:00?" is
also `questions.py add job "Which slot for Acme?" job=J7 options="tue:Tuesday 10:00|wed:Wednesday 15:00"`.

## Mail and calendar

1. Gmail, messages without the label `GMAIL_DONE_LABEL`: interview invitations, availability requests, booking
   links, tests and forms, rejections and closed posts, confirmations, and replies to the person's own mails.
2. With `CALENDAR=auto` (`choices.py show`): book slots by the person's scheduling rules (the master record's
   `preferences`); with `interview` in `ASK_FIRST`, propose the slot and book it after their yes. With
   `CALENDAR=self`: book nothing and write no event; record the date the person gives. A reply to a recruiter is a
   draft the person sends.
3. With `CALENDAR=auto`, each step and deadline into the calendar (RULES.md, "Calendar"), with its own link and the email link; the same
   two into the step's `link` and `mail` in `PIPELINE`. A step due within 24 hours: one notification at once
   (RULES.md, "Urgent steps"). Rejections, closed posts and declines into `PIPELINE` as
   their outcome.
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

## Study notes

`INTERVIEW_LESSONS_DIR` (default `career-records/interview-lessons`) holds `technical.md` (technical questions and
concepts), `screening.md` (recruiter and HR questions: motivation, pay, notice, gaps) and `roadmap.md` (what to
study next, in order). Lines are facts with date and step. Example: `- 2026-11-19 Acme technical: Kafka consumer
groups, answered weakly -> study rebalancing`.
- A study session and an after-a-step session read the three files first; a weak point seen before is taught
  first. A missing file is empty.
- Their handoff ends with `Weak answers:`, one line per weak answer, with its file. Example: `- technical.md:
  2026-11-19 Acme technical: Kafka consumer groups, answered weakly -> study rebalancing`.
- The coordinator writes the lines in. The notes are for study only (RULES.md, "Honesty and what Claude never
  does").

## Studying with the person

0. **The time first**: check the step's date and time against now, and name the next step and when, so two steps
   on one day are never mixed up. Example: "Now 09:40. Next: Acme technical interview, today 14:00; then Beta
   screening call, today 16:30."
1. **Brief first**, in short sections for a phone: the company (what it sells, size, owners, recent news, with
   sources), the role, the tech stack (one plain line per term), and their strong and weak points for the role, each
   with its evidence. If the research finds something the employer rules exclude, say so.
2. **Offer to teach the weak points**, one at a time: what it is, what this employer means by it, the closest thing
   the person really did, an honest way to talk about it, one check question.
3. **Then practise**: one likely question at a time; the person answers in their own words; short, honest
   feedback. Sharpen their answers, never script them. Offer the mock interview the day before the step.

## After a step

Read the study notes first ("Study notes"). The person's account of it goes into the step's `feedback.md`, as fact
lines; each question they answered weakly is a `Weak answers:` line of the handoff. Log it: `usage.py log prep ok`.
