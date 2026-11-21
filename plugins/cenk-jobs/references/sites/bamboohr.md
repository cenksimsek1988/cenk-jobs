# BambooHR: site notes

Read by the search session for a posting on a BambooHR careers site (<company>.bamboohr.com/careers), and by a session
that applies to one.

- Draft: no draft known.
- A BambooHR posting page is drawn by script: `fetch_jd.py` and the fit check get no text from it. The search session
  reads it in the person's Chrome and saves the text as `<job id>.md` in `POSTINGS_DIR` (as for Dover,
  `dover.md`); the next fit check reads it. Example: one BambooHR posting saved this way on 21 Nov.
