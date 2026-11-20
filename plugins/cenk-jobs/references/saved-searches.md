# Saved searches, tuning and alerts

Read by the search session when none is saved, a site has no alert decision yet, or the rows need tuning.

## Saved searches

Every search has a row in `SEARCHES` (`searches.py`), so the next run starts from the row's last check.
- None saved: one row per site and query, from the person's roles and locations. A person with a tracker and no
  rows: `searches.py sites` lists the sites of their jobs that have none; add a row for each.
- A site searched without a row gets its row in the same run. Example: a posting found on a new board:
  `searches.py add "Acme careers" "engineering" alert=no`.
- A row with an alert is read at every run. A site without one is searched at every weekday run, from its last
  check on, and never on a weekend: a check that falls there is due on Monday. `every=7` makes it weekly.

## Tuning the searches

- `searches.py rates`: per row, the postings the funnel screened and its real fits (high or normal; a normal fit cut by `APPLY_FITS=high` counts). A row with 20
  screened and no real fit goes to the Questions page ("Drop the search ...?"); nothing is dropped alone.
- A variant of the searches wins by real fits after the full screening, never by a cheap first pass alone. Seen
  on 18 Nov: a cheap judge's 108 "medium" fits were 16 real ones.
- A tested set of searches is loaded with `searches.py import <profile.json>` (LinkedIn blocks with location,
  remote and queries; boards; feeds); rows already saved are kept. A query with no real fit stays out.
- No new LinkedIn search rows and no board discovery by guessed names: new LinkedIn postings come from alert
  emails, a new board from a posting found elsewhere. LinkedIn rows already saved run last and stop at refusals. Seen 18-19 Nov: every LinkedIn call refused, 15k guessed names gave 3 plausible
  postings. Discovery by web search (`weekly.md`, "Board discovery") is different: it finds boards that exist and
  hold matching postings.

## Alerts

One email alert per saved search, on each site that offers one, so the search is read from email in the background.
- For each site, check once whether it offers a free email alert, and record what was found. Ask the person in one
  question that lists every such site; their yes covers the list. Example: "LinkedIn and Acme careers offer a free
  daily email for your searches. Create both alerts?" Without one: `alert=no note="no alert offered, 2026-11-13"`.
- An alert email that lists no postings and only links to the site is a signal: search that site in the same run,
  from the row's last check on. Record it on the row: `note="the alert only links to the site"`.
- Greenhouse boards offer one per employer ("Create a Job Alert" on a posting): for an employer the person follows.
- No alert without the person's yes for its site. Never create an account: a site that needs a new one is `alert=no`,
  checked on a schedule.
- Create it once, signed in, with the site's own alert setting, in the person's Chrome (RULES.md, "Claude in
  Chrome"). Never through a tick-box on an application form.
- Then record it. Example: `searches.py add LinkedIn "Backend engineer, remote" alert=yes
  gmail="from:jobalerts-noreply@linkedin.com newer_than:2d"`. A site with no alerts: `alert=no`.
