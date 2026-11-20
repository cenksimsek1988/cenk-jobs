---
name: apply
description: "Apply to planned jobs in the person's Chrome: fills each form from their records with the right CV and a fresh letter, submits by ASK_FIRST and records it. Use for 'apply to these jobs', 'send the applications', 'candidati per me', 'başvuru yap'. Stops at codes, CAPTCHAs, passwords, essays."
---

# Apply: fill, review, send

Read `../../RULES.md` first: never an ID number, password, verification code or CAPTCHA; optional consents off;
open free-text questions stay the person's. Read `../../RULES/urgent.md` and `../../RULES/questions.md` when a form
waits on the person.
Every question this skill asks the person goes on the Questions page as it is asked, in a run or in the chat (RULES/questions.md); in a sub-session, by a message to the coordinator, which adds it.

## Before filling

- Check the posting is still open and its link lands on the employer's own form (RULES.md, "Links"). The site's
  own notes are in `../../references/sites/<site>.md` (greenhouse, ashby, linkedin, smartrecruiters, successfactors, workday, eightfold):
  read the one for the form in hand.
- Write a letter by `LETTERS`: `asked` (the default) only for a form with a letter field: many have none (often
  Workable, Rippling, HiBob, Ashby, Lever); `always` for every form, attached where it takes a file; `never` none.
  Each essay question goes to the Questions page before filling.
- Check the employer again if the last check is old (`employer.py check`).
- Before telling the person a job "only needs a yes", read its tracker status and its `PIPELINE` entry: a job
  already sent or rejected needs nothing. Example: a form marked ready whose job was rejected two days earlier.
- Before advising a value for a select field, read the field's own option list; the board's question API gives it
  without touching the form. Example: a count of 3 is no option where the list starts at 5.
- A job's prepared answers go stale after the person's later answers: fill the newer answer from the records and
  correct the prepared answers with it. Example: the prep says 6 years of Java, a later answer says 8: fill 8 and
  update the prep.
- The person must be signed in to the site. Ask them to tick "Keep me signed in" or "Remember me" where the site
  offers it, and to keep Chrome's "clear cookies when you close all windows" off.
- Every fitting role at one employer is applied to at the same time: never wait for one application there to
  finish before sending the next.
- Several applications at once: one `cenk-jobs:applier` subagent per application, started together, one tab each,
  at most `APPLY_PARALLEL` at once (default 2), never two on the same site. A subagent cannot ask the person: its
  brief holds every answer, names the CV and letter, already copied for upload, the `filling:` line of `track.py
  brief` (with the first name for tab titles), and the site's notes file
  (`../../references/sites/<site>.md`, when there is one); what it cannot do comes back as
  `needs-person`. It writes no record: this session records each block as it returns, one at a time ("After each
  submission").

## Filling

The filling rules are in `../../references/filling.md`, and each site's in `../../references/sites/<site>.md`: read
both before the first field. Read each page with `find`, `read_page` (`filter: interactive`) or `get_page_text`;
never take a screenshot.

## Sending

- `send` not in `ASK_FIRST` (`choices.py show`): submit every form whose answers all come from the person's
  records, then report; a form that sends a one-time code on Submit waits until the person is active or at the PC
  (see "Filling").
- `send` in `ASK_FIRST` (or the older `APPLY_MODE=review`): stop at the review page; submit after the person's
  go-ahead for that job or batch.
- `APPLY=list`: no form is filled; the fitting jobs are listed with their links.
- A form left filled at the review page for the person: read it back first (`filling.md`), then the tab's title and
  the question both say that Submit sends the form as it is now (example title: ">>> Jane: Acme review, Submit
  sends it <<<"). A change asked later waits until the person confirms they have not pressed Submit. After a
  go-ahead, read the page first: a form already sent is recorded as sent, never changed.
- If the permission check refuses a submit click: retitle the tab for the person, say so in one line, and try no
  other way.
- `EMAILED_CODES=on` (`choices.py show`): after a Submit that emails a code or a confirmation link, this session reads
  it in Gmail (the site's own sender, within 15 minutes, this form only) and types it in the held tab or opens it. A
  sign-in or sign-up code, a CAPTCHA and a password stay the person's.
- After each submission: `track.py set <id> submitted "<what was sent>" cv=<path> letter=<path>`; a form without a
  letter field: `letter=none`, so its folder lists no prepared letter. Then `fetch_jd.py
  <id>` for every job sent, while the posting is live (the next reply analysis reads it), `build_app_folders.py`, and the dashboard refresh.

## Report

One block per job, by company and role: status (submitted, ready at review, needs-person and which field, closed,
failed), the CV and letter sent, the fields answered by name (a value only from the master record's form
answers; never a profile, private, guarded or pay value), the next step seen. Log it: `usage.py log apply ok "<n sent>"`.
