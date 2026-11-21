# Dover: site notes

Read by the search session for a posting found on Dover (jobs.dover.com, app.dover.com), and by a session that
applies to one.

- Draft: no draft known.
- A Dover posting page is drawn by script: WebFetch, `fetch_jd.py` and the fit check get no text from it, and Dover's
  API takes only the employer's own key. The fit check marks such a job "unread", and `collect_postings.py` prints
  "no text saved for unread <id>" with the file it waits for.
- The search session reads the posting in the person's Chrome (`navigate`, then `get_page_text`: a posting is a
  short page) and saves the text as that file (`<job id>.md` in `POSTINGS_DIR`); the next fit check reads it. Never
  a screenshot. Example: two Dover postings left "unread" on 20 Nov: their texts saved, the next run checks them.
