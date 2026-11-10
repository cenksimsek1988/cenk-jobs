---
name: apply
description: "Apply to planned jobs in the person's Chrome: fills each form from their records with the right CV and a fresh letter, submits by APPLY_MODE and records it. Use for 'apply to these jobs', 'send the applications', 'candidati per me', 'başvuru yap'. Stops at codes, CAPTCHAs, passwords, essays."
---

# Apply: fill, review, send

Read `../../RULES.md` first: never an ID number, password, verification code or CAPTCHA; optional consents off;
open free-text questions stay the person's. Read `../../RULES/urgent.md` and `../../RULES/questions.md` when a form
waits on the person.

## Before filling

- Check the posting is still open and its link lands on the employer's own form (RULES.md, "Links").
- Check the employer again if the last check is old (`employer.py check`).
- The person must be signed in to the site. Ask them to tick "Keep me signed in" or "Remember me" where the site
  offers it, and to keep Chrome's "clear cookies when you close all windows" off.
- Fill a site right after the person signs in: sign-ins expire within minutes when idle.
- Several applications at once: one `cenk-jobs:applier` subagent per application, started together, one tab each,
  at most `APPLY_PARALLEL` at once (default 2), never two on the same site. A subagent cannot ask the person: its
  brief holds every answer and names the CV and letter, already copied for upload; what it cannot do comes back as
  `needs-person`. It writes no record: this session records each block as it returns, one at a time ("After each
  submission").

## Filling

- Read a form with `find`, `read_page` (`filter: interactive`) or `javascript_tool`; never a screenshot (RULES.md,
  "Claude in Chrome").
- The CV version the plan chose, and the letter built today: `make_letter_pdf.py --company .. --role .. --body
  <body file> --variant "<CV variant>" --out-dir <letter folder>`. Claude in Chrome `file_upload` reads only files
  this session may read: copy both into the session's scratchpad and upload from there.
- Every answer from the master record; a health, family or identity answer only from `PERSONAL_RECORD`, read by
  the session that fills the form (never handed to a screen-and-prepare agent; an applier's brief carries the ones its form asks for). Anything
  they do not answer goes to the Questions page with the job that needs it (`questions.py add`, RULES.md "Questions
  for the person"); a question no option of which is true is asked, never ticked.
- The home address only in the form's own address fields, never in a file or a message.
- A form that waits on the person (RULES.md, "Applications"): stop on that page and put the field in Do now. If
  the step expires (an emailed or SMS code, a CAPTCHA, a Submit waiting for their yes, a sign-in page), send one
  notification at once (RULES.md, "Urgent steps"), "At your PC:" or "From your phone:", and keep the tab open.
- A site that sends a one-time code on Submit (example: Greenhouse's emailed security code): fill everything, stop
  before Submit, notify "At your PC:", and press Submit only when the person says they are at the PC.
  Keep-alive while it waits: a second tab on the same site, reloaded every 10 minutes for at most 2 hours; never the
  form's own tab.

## Sending

- `APPLY_MODE=auto` (the default): submit every form whose answers all come from the person's records, then report;
  a form that sends a one-time code on Submit waits until the person is at the PC (see "Filling").
- `APPLY_MODE=review`: stop at the review page; submit after the person's go-ahead for that job or batch.
- If the permission check refuses a submit click, stop and ask; never work around it.
- After each submission: `track.py set <id> submitted "<what was sent>" cv=<path> letter=<path>`, `fetch_jd.py
  <id>` while the posting is live, `build_app_folders.py`, and the dashboard refresh.

## Report

One block per job, by company and role: status (submitted, ready at review, needs-person and which field, closed,
failed), the CV and letter sent, every answer given, the next step seen. Log it: `usage.py log apply ok "<n sent>"`.
