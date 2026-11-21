# LinkedIn Easy Apply: site notes for filling a form

Read by the applier, and by a session that fills this site's form, with `../filling.md`.

- Draft: no draft known; a held Easy Apply dialog is lost when its tab closes.
- An Easy Apply form's fields show only once it is open: the funnel prepares no letter for it, and the session writes
  one only when the open form shows a cover-letter field (`../filling.md`, `LETTERS`).
- LinkedIn Easy Apply fills screening answers saved from earlier applications (example: 3 years of a skill, where the
  record says 6): check every prefilled number against the record before Review. Its salary fields take a number
  only: `50000`, not "EUR 50,000 a year" ("Invalid input").
- LinkedIn Easy Apply's "Upload resume" button has a hidden file input behind it: find it (`find` "file input" or
  `input[type=file]`) and send the chosen CV version with `file_upload`; then check that the new file is the one
  selected. Seen working on 17 Nov.
- Easy Apply's work-experience page blocks Next on an entry without dates. Never invent dates or delete an entry:
  the job waits (`needs-person`) and the person fixes the entry on LinkedIn.
