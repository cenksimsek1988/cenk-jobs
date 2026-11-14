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
- SuccessFactors behind a Career Site Builder front end: after sign-in, the Apply link lands on the portal's home
  page. Open the job by its requisition id inside the signed-in portal (example: search its jobs for `12345`).
- Read the form's questions before opening Chrome, from the board's public API:
  - Ashby: a POST to `https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobPosting` (Python; WebFetch only gets),
    variables `organizationHostedJobsPageName` and `jobPostingId`: `applicationForm` sections, each field in
    `fieldEntries` with `isRequired`.
  - Greenhouse: `https://boards-api.greenhouse.io/v1/boards/<board>/jobs/<id>?questions=true`.
- Write a letter only for a form with a letter field: many have none (often Workable, Rippling, HiBob, Ashby, Lever).
  Each essay question goes to the Questions page before filling. Ashby keeps no draft, so a form with an essay
  question waits until the person's answer is in the records.
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
- Fill a site right after the person signs in: sign-ins expire within minutes when idle. Workday can end the session
  after about 25 minutes on one application: save each step as soon as it is filled, and check that the session is
  still signed in before the next step.
- Every fitting role at one employer is applied to at the same time: never wait for one application there to
  finish before sending the next.
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
- Greenhouse: open the plain embed form, `job-boards.greenhouse.io/embed/job_app?for=<board>&token=<job id>`, not
  the employer's heavy careers page. When the embed answers "error processing your application", use the form on
  the employer's own careers page.
- Greenhouse, signed in, after the location pick: the form can render again, clear typed fields or add education
  rows from the stored profile. Fill the location early, read the whole form again before Submit and remove the
  rows that are wrong.
- Greenhouse, signed in: the candidate profile prefills a stored resume of unknown date and the name in capitals.
  Replace both on every Greenhouse form: upload the CV the plan chose, type the name as the records write it.
- Ashby: a React field takes the native value setter, then `input` and `change` events; Yes/No answers are buttons
  over hidden checkboxes; a radio or checkbox is set by clicking its label. The public posting API answers 403
  without a browser User-Agent.
- A form with rank or percentile picks and an evidence text: compare each pick with the numbers in the text and in
  the records, and say when a pick is above them. Read the hint under a count question before proposing the count.
  Example: "top 5%" picked while the evidence says 3 of 40.
- Picks the person asks to make themselves: open the form in their Chrome at that question, name the tab and say
  which fields are theirs. A notes file is no place to select.
- A tab in another session's tab group cannot be seen: a form another session filled is filled again by the session
  that takes it over; say so, do not look for the tab.
- LinkedIn Easy Apply fills screening answers saved from earlier applications (example: 3 years of a skill, where the
  record says 6): check every prefilled number against the record before Review. Its salary fields take a number
  only: `50000`, not "EUR 50,000 a year" ("Invalid input").
- LinkedIn Easy Apply has no file input behind its upload buttons: it sends only a CV already stored on LinkedIn.
  Check the stored CV's date against the CV version the plan chose; an older one: ask the person once to upload the
  current CVs to LinkedIn.
- Easy Apply's work-experience page blocks Next on an entry without dates. Never invent dates or delete an entry:
  the job waits (`needs-person`) and the person fixes the entry on LinkedIn.
- The CV version the plan chose, and the letter built today: `make_letter_pdf.py --company .. --role .. --body
  <body file> --variant "<CV variant>" --out-dir <letter folder>`. Claude in Chrome `file_upload` reads only files
  this session may read: copy both into the session's scratchpad and upload from there. SuccessFactors: the visible
  "Upload a CV" label does nothing; click the `span.addAttachments` icon with `javascript_tool`, and its in-page
  dialog holds `input[type=file]` (name `fileData1`) for `file_upload`. Start the next upload only after the last one
  has finished.
- Every answer from the master record, and the person's own facts from their profile (`profilelib.py get <key>`):
  a health, family or identity answer only from `private.<key>`, read by the session that fills the form (never
  handed to a screen-and-prepare agent; an applier's brief carries the ones its form asks for). A prepared answer
  "from the profile" is a guarded item the person's `form_facts` names: type their value from the profile (example:
  `get person.birth_date`). Anything they do not answer goes to the Questions page with the job that needs it
  (`questions.py add`, RULES.md "Questions for the person"); a question no option of which is true is asked, never
  ticked.
- The home address and the birth date only in the form's own fields, never in a file or a message.
- A contractor pay field, from the person's rates and day counts in their records, by the contract's length: one
  year or longer, the day rate x the working days of a year / 12 for a month; about six months, the day rate x the
  working days of a month; no length, or only some hours a day, the hourly rate x the hours. Always round up. A form
  in another currency: the day's ECB rate
  (`data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?lastNObservations=1&format=csvdata`), fetched with
  `curl` where Python's `urllib` fails the TLS check.
- A form that waits on the person (RULES.md, "Applications"): stop on that page and put the field in Do now. If
  the step expires (an emailed or SMS code, a CAPTCHA, a Submit waiting for their yes, a sign-in page), send one
  notification at once (RULES.md, "Urgent steps"), "At your PC:" or "From your phone:", and keep the tab open.
  A Submit answered by "The captcha is invalid." means an invisible CAPTCHA ran: a CAPTCHA stop.
- A site that sends a one-time code on Submit (example: Greenhouse's emailed security code): fill everything, then
  press Submit while the person is active (they wrote in any job-search session in the last 15 minutes) or has said
  they are at the PC, and pass the code request on at once ("At your PC: type the code Acme just emailed").
  Otherwise stop before Submit and notify "At your PC:".
  Keep-alive while it waits: a second tab on the same site, reloaded every 10 minutes for at most 2 hours; never the
  form's own tab. A public form without a sign-in gets none (a reload clears it): say so and name the refill time.
  Example: "This form has no login: if the tab closes, I refill it in about 5 minutes."
- A code or CAPTCHA step in a tab this session holds: a link would open a fresh, empty copy with no code field.
  Rename the held tab (`document.title = ">>> TYPE THE CODE HERE <<<"`), scroll the field into view, and tell the
  person to find the tab with Chrome's tab search (Ctrl+Shift+A). The page's address is given only as text.
- A hypothetical question is explained in plain words before an option is proposed: it can read as a booking.
  Example: "How comfortable would you be doing that tomorrow?" asks how ready the person is, not for a meeting
  tomorrow.

## Sending

- `APPLY_MODE=auto` (the default): submit every form whose answers all come from the person's records, then report;
  a form that sends a one-time code on Submit waits until the person is active or at the PC (see "Filling").
- `APPLY_MODE=review`: stop at the review page; submit after the person's go-ahead for that job or batch.
- A form left filled at the review page for the person: the tab's title and the question both say that Submit sends
  the form as it is now (example title: ">>> REVIEW: Submit sends this as it is <<<"). A change asked later waits
  until the person confirms they have not pressed Submit. After a go-ahead, read the page first: a form already sent
  is recorded as sent, never changed.
- If the permission check refuses a submit click, stop and ask; never work around it.
- After each submission: `track.py set <id> submitted "<what was sent>" cv=<path> letter=<path>`; a form without a
  letter field: `letter=none`, so its folder lists no prepared letter. Then `fetch_jd.py
  <id>` while the posting is live, `build_app_folders.py`, and the dashboard refresh.

## Report

One block per job, by company and role: status (submitted, ready at review, needs-person and which field, closed,
failed), the CV and letter sent, every answer given, the next step seen. Log it: `usage.py log apply ok "<n sent>"`.
