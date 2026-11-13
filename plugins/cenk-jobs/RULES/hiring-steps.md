# cenk-jobs rules: hiring-steps

A part of `RULES.md`. Read to record an outcome, write a calendar event or handle job-search mail.

## Outcomes

| Category | When | Recorded as |
|---|---|---|
| rejected | the employer said no to the person | `PIPELINE` stage `rejected`, date, reason |
| closed | the role closed, was filled or put on hold, or the person was late: not a rejection | sent: `PIPELINE` stage `closed`; not sent: `track.py set <id> closed` |
| declined | the person said no at some step | sent: `PIPELINE` stage `declined`, `why` (ethics, relocation, pay, other), for ethics the `category` (example: `human_rights`); not sent: `track.py set <id> declined` |
| excluded | the employer rules exclude the employer | `track.py set <id> excluded` |
| skipped | the screen: the posting does not fit the rules | `track.py set <id> skipped` |

Examples: "the position has now been filled" is closed; "we will not move forward with you" is rejected.

## Calendar

Every job-search event carries the category: color `CALENDAR_COLOR` (3 = Grape) and, on events the person owns, the
title prefix `CALENDAR_PREFIX` ("Job search · ").
- A company's invitation already in the calendar: only set its color (`update_event`, `notificationLevel` NONE).
- Otherwise create the event (a deadline: all-day, free, reminders 3 days and 1 day before), with the job id and
  step in the description (`[job-search: <id> step <n>]`).
- Every event the person owns holds the step's own link (meeting, test, booking, interview page) and the email's
  Gmail link; the same two go into the step's `link` and `mail` in `PIPELINE`.
- An online interview without a video link: draft a request for it to the recruiter the day before (a draft).
- Each run, compare the category's coming events with the records. An event of an excluded or withdrawn employer,
  or an invitation the person declined that still has the color, is named to the person; after their yes, an event
  they own is deleted and an invitation loses its color. Example: Acme was excluded on 12 Nov; "Job search · Acme
  interview" on 18 Nov is named.
- A date an employer proposed and nobody confirmed is a step with `"proposed": true` in `PIPELINE`: Hiring steps
  reads "Proposed", and it is no task in Do now. Confirmed: remove the field. Example: a recruiter offers a call
  on 18 Nov at 10:00 and the person has not answered.
- A deadline event follows its to-do or step: a new due date moves it; a step marked done, or a to-do removed,
  removes it.

## Mail

A job-search message whose action is done gets the Gmail label `GMAIL_DONE_LABEL` (default `cenk-jobs/Done`).
- Done: the step is booked and in the calendar, a deadline is in the calendar, a rejection, closed post or
  confirmation is recorded, or the person's reply is sent (the thread has their sent reply after it).
- Not done: a reply draft not sent yet, a CAPTCHA, a sign-in or an answer only the person can give. The message
  stays unlabelled and its to-do stays in Do now.
- Label the message (`label_message`), never the thread: a new reply in the same thread arrives unlabelled.
- Search for new work with `-label:"<GMAIL_DONE_LABEL>"`. Example: `newer_than:3d -label:"cenk-jobs/Done"
  (interview OR availability OR assessment)`.
- Gmail's list shows a thread with the label when any of its messages has it; a new reply shows there as unread.
- Setup creates the label (`create_label`, purple; parents are created with it). Missing at a run: create it.
- Never remove the person's own labels, never archive a message, mark it read or move it to another tab.
- The mail connector is down: read and label the mail in the person's signed-in Chrome instead, say so, and keep
  asking for the reconnect. Search `newer_than:1d -label:<GMAIL_DONE_LABEL>`; to label, tick the handled rows, open
  the Labels menu, type the label, press Enter. A mail's snippet can show a one-time code: mask every code in what
  is printed. Example: `security code: ******`.
