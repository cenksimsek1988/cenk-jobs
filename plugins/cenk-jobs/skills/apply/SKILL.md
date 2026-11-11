---
name: apply
description: "Apply to planned jobs in the person's Chrome: fills each form from their records with the right CV and a fresh letter, submits by APPLY_MODE and records it. Use for 'apply to these jobs', 'send the applications', 'candidati per me', 'başvuru yap'. Stops at codes, CAPTCHAs, passwords, essays."
---

# Apply: fill, review, send

Read `../../RULES.md` first: never an ID number, password, verification code or CAPTCHA; optional consents off;
open free-text questions stay the person's. Read `../../RULES/urgent.md` and `../../RULES/questions.md` when a form
waits on the person.

## Before filling

- Check the posting is still open and its link lands on the employer's own form (RULES.md, "Links"). A
  SuccessFactors apply link (`talentcommunity/apply/<id>`) opens the site's home page when signed out: not a closed
  posting; open the job's own page. Signing in there from a job's Apply link can submit at once by quick apply from
  the stored profile, with no CV or answers: upload the CV to the profile first, or sign in from the site's home page,
  then apply.
- Check the form before writing a letter: many have no letter field (often Workable, Rippling, HiBob, Ashby, Lever).
  Ashby keeps no draft, so a form with an essay question waits until the person's answer is in the records.
- Check the employer again if the last check is old (`employer.py check`).
- The person must be signed in to the site. Ask them to tick "Keep me signed in" or "Remember me" where the site
  offers it, and to keep Chrome's "clear cookies when you close all windows" off.
- Fill a site right after the person signs in: sign-ins expire within minutes when idle. Workday can end the session
  after about 25 minutes on one application: save each step as soon as it is filled, and check that the session is
  still signed in before the next step.
- Several applications at once: one `cenk-jobs:applier` subagent per application, started together, one tab each,
  at most `APPLY_PARALLEL` at once (default 2), never two on the same site. A subagent cannot ask the person: its
  brief holds every answer and names the CV and letter, already copied for upload; what it cannot do comes back as
  `needs-person`. It writes no record: this session records each block as it returns, one at a time ("After each
  submission").

## Filling

- Read a form with `find`, `read_page` (`filter: interactive`) or `javascript_tool`; never a screenshot (RULES.md,
  "Claude in Chrome"). `javascript_tool` output shaped like `key=value; ...` is blocked as cookie data: return JSON
  (`JSON.stringify({...})`).
- A dropdown built from `input[type=button]` keeps the choice in its `value` while its label still reads "Select
  one": read the value, not the label. Eightfold careers sites ignore a plain click on a dropdown option: dispatch
  pointerdown, mousedown, pointerup, mouseup and click on the option element, in that order (`javascript_tool`).
- LinkedIn Easy Apply fills screening answers saved from earlier applications (example: 3 years of a skill, where the
  record says 6): check every prefilled number against the record before Review. Its salary fields take a number
  only: `50000`, not "EUR 50,000 a year" ("Invalid input").
- The CV version the plan chose, and the letter built today: `make_letter_pdf.py --company .. --role .. --body
  <body file> --variant "<CV variant>" --out-dir <letter folder>`. Claude in Chrome `file_upload` reads only files
  this session may read: copy both into the session's scratchpad and upload from there. SuccessFactors: the visible
  "Upload a CV" label does nothing; click the `span.addAttachments` icon with `javascript_tool`, and its in-page
  dialog holds `input[type=file]` (name `fileData1`) for `file_upload`. Start the next upload only after the last one
  has finished.
- Every answer from the master record; a health, family or identity answer only from `PERSONAL_RECORD`, read by
  the session that fills the form (never handed to a screen-and-prepare agent; an applier's brief carries the ones its form asks for). Anything
  they do not answer goes to the Questions page with the job that needs it (`questions.py add`, RULES.md "Questions
  for the person"); a question no option of which is true is asked, never ticked.
- The home address only in the form's own address fields, never in a file or a message.
- A form that waits on the person (RULES.md, "Applications"): stop on that page and put the field in Do now. If
  the step expires (an emailed or SMS code, a CAPTCHA, a Submit waiting for their yes, a sign-in page), send one
  notification at once (RULES.md, "Urgent steps"), "At your PC:" or "From your phone:", and keep the tab open.
  A Submit answered by "The captcha is invalid." means an invisible CAPTCHA ran: a CAPTCHA stop.
- A site that sends a one-time code on Submit (example: Greenhouse's emailed security code): fill everything, then
  press Submit while the person is active (they wrote in any job-search session in the last 15 minutes) or has said
  they are at the PC, and pass the code request on at once ("At your PC: type the code Acme just emailed").
  Otherwise stop before Submit and notify "At your PC:".
  Keep-alive while it waits: a second tab on the same site, reloaded every 10 minutes for at most 2 hours; never the
  form's own tab.

## Sending

- `APPLY_MODE=auto` (the default): submit every form whose answers all come from the person's records, then report;
  a form that sends a one-time code on Submit waits until the person is active or at the PC (see "Filling").
- `APPLY_MODE=review`: stop at the review page; submit after the person's go-ahead for that job or batch.
- If the permission check refuses a submit click, stop and ask; never work around it.
- After each submission: `track.py set <id> submitted "<what was sent>" cv=<path> letter=<path>`, `fetch_jd.py
  <id>` while the posting is live, `build_app_folders.py`, and the dashboard refresh.

## Report

One block per job, by company and role: status (submitted, ready at review, needs-person and which field, closed,
failed), the CV and letter sent, every answer given, the next step seen. Log it: `usage.py log apply ok "<n sent>"`.
