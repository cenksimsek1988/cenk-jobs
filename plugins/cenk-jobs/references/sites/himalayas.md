# Himalayas: site notes

Read by the search session for a posting found on Himalayas (himalayas.app), and by a session that applies to one.

- Draft: no draft known; the form is the employer's own.
- A Himalayas page answers `fetch_jd.py` and WebFetch with 403; in the person's Chrome its Cloudflare check passes by
  itself after about 10 s. The search session reads the posting there and saves its text as `<job id>.md` in
  `POSTINGS_DIR`, for the fit check. Example: 11 posting texts saved this way on 21 Nov.
- Its "Apply now" opens the employer's own form (seen: Dover, Zoho Recruit): that form's address is the job's
  apply_url (`track.py set <id> <its current status> "apply link from Himalayas" apply_url=<address>`), never the
  Himalayas page.
