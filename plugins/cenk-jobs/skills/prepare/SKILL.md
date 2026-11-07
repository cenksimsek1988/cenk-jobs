---
name: prepare
description: "Prepare the hiring steps: reads invitations, tests and rejections in Gmail, books interview slots by the person's rules, puts every step and deadline in Google Calendar with its links, writes prep notes and a keyword cheat sheet for each step, studies and practises with the person, and records how each step went. Use for \"prepare my interview\", \"let's practise\", \"book the interview\", \"any interview invitations?\", \"preparami al colloquio\", \"mülakata hazırla\". Never accepts or sends for them."
---

# Prepare: hiring steps and interviews

Read `../../RULES.md` first ("Mail", "Calendar", "Outcomes"). Prepare the nearest steps first; a far-off step's
prep waits.

## Mail and calendar

1. Gmail, messages without the label `GMAIL_DONE_LABEL`: interview invitations, availability requests, booking
   links, tests and forms, rejections and closed posts, confirmations, and replies to the person's own mails.
2. Book slots by the person's scheduling rules (the master record's `preferences`); a reply to a recruiter is a
   draft the person sends.
3. Each step and deadline into the calendar (RULES.md, "Calendar"), with its own link and the email link; the same
   two into the step's `link` and `mail` in `PIPELINE`. A step due within 24 hours: one notification at once
   (RULES.md, "Urgent steps"). Rejections, closed posts and declines into `PIPELINE` as
   their outcome.
4. Each message whose action is done gets the label `GMAIL_DONE_LABEL` (RULES.md, "Mail"). A reply waiting as a
   draft gets it on the run that finds the person's sent reply.

## Prep notes

For each new step, in its step folder: `prep.md` (from the posting and the master record only) and `cheat-sheet.md`
(keyword lines only: facts, numbers, names of things; never scripted sentences, since the person reads it in the
minutes before the call).

## Studying with the person

1. **Brief first**, in short sections for a phone: the company (what it sells, size, owners, recent news, with
   sources), the role, the tech stack (one plain line per term), and their strong and weak points for the role, each
   with its evidence. If the research finds something the employer rules exclude, say so.
2. **Offer to teach the weak points**, one at a time: what it is, what this employer means by it, the closest thing
   the person really did, an honest way to talk about it, one check question.
3. **Then practise**: one likely question at a time; the person answers in their own words; short, honest
   feedback. Sharpen their answers, never script them. Offer the mock interview the day before the step.

## After a step

The person's account of it goes into the step's `feedback.md`, as fact lines. Log it: `usage.py log prep ok`.
