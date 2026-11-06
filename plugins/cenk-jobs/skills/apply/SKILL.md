---
name: apply
description: "Apply to planned jobs in the person's own Chrome: fills each form from the master record with the right CV and a letter built today, stops at the review page, and submits only after the person's go-ahead; then records the application, saves the posting and refreshes the folders and dashboard. Use for \"apply to these jobs\", \"send the applications\", \"fill the Workday form\", \"candidati per me\", \"başvuru yap\", \"Bewerbung abschicken\". Never sends without the go-ahead."
---

# Apply: fill, review, send

Read `../../RULES.md` first: never an ID number, password, verification code or CAPTCHA; optional consents off;
open free-text questions stay the person's.

## Before filling

- Check the posting is still open and its link lands on the employer's own form (RULES.md, "Links").
- Check the employer again if the last check is old (`employer.py check`).
- The person must be signed in to the site. Ask them to tick "Keep me signed in" or "Remember me" where the site
  offers it, and to keep Chrome's "clear cookies when you close all windows" off.
- Fill a site right after the person signs in: sign-ins expire within minutes when idle. For several sites at once,
  give each site its own background helper; at most two use Chrome at once, each only in tabs it opened.

## Filling

- The CV version the plan chose, and the letter built today: `make_letter_pdf.py --company .. --role .. --body
  <body file> --variant "<CV variant>" --out-dir <letter folder>`. Claude in Chrome `file_upload` reads only files
  this session may read: copy both into the session's scratchpad and upload from there.
- Every answer from the master record. Stop and ask for anything it does not answer; a question no option of which
  is true is asked, never ticked.
- The home address only in the form's own address fields, never in a file or a message.
- Stop at the review page, or the last page before submit. Keep-alive while it waits: a second tab on the same site,
  reloaded every 10 minutes for at most 2 hours; never the form's own tab.

## Sending

- Submitting is the person's decision: show what was filled and get their go-ahead for that job or batch. If the
  permission check refuses a submit click, stop and ask; never work around it.
- After each submission: `track.py set <id> submitted "<what was sent>" cv=<path> letter=<path>`, `fetch_jd.py
  <id>` while the posting is live, `build_app_folders.py`, and the dashboard refresh.

## Report

One block per job, by company and role: status (submitted, ready at review, needs-person and which field, closed,
failed), the CV and letter sent, every answer given, the next step seen. Log it: `usage.py log apply ok "<n sent>"`.
