---
name: search
description: "Find and screen job postings: searches job boards and company sites under the person's locations, pay and employer rules, checks each employer and records each posting. Use for 'find me jobs', 'search for jobs', 'any new postings?', 'cerca lavoro', 'iş ara', 'Jobsuche'. Never applies."
---

# Search: find and screen postings

Read `../../RULES.md` first, and `../../RULES/employers.md` before step 3. This skill only searches: it writes postings and their screening results into the
tracker, and nothing is prepared or sent.

## Steps

1. Read the person's rules from the master record: where they will work (cities, remote, relocation), the pay
   rule, the roles they want, the languages they work in, and `EMPLOYER_RULES`.
2. `searches.py due` lists the saved searches due today: a run reads only these, never every site again. With none
   saved it says so: create them first ("Saved searches"). For each, the cheapest source that covers it, in this order.
   Keep only postings that match the roles and the location rule; drop what the tracker has (`searches.py seen --file
   <links file>`, one link per line, never typed into a command).
   - Alert emails: Gmail `search_threads` with the row's `gmail` query, `pageSize` 10; open only messages newer than
     the row's last check.
   - Connectors: Indeed `search_jobs` and `get_job_details`; Develop21 `develop21_execute_job_search` (`list` with
     `brief`, `check` to drop rows already seen). Indeed mostly returns older listings: a supplement, not the source
     of new ones.
   - A job board's public JSON (the addresses in `workflows/screen-and-prepare.js`), or `fetch_jd.py`.
   - LinkedIn guest search only for a search no alert covers: 4 s between calls, in the background, each result
     written as it comes (example: 269 calls took 32 minutes).
   - A site without an alert: newest first, and stop at the first posting older than the row's last check or already
     in the tracker. Example: last check 6 Nov; the list reaches a posting of 5 Nov: stop there.
   - A browser last, only for a search nothing else covers. Read each page with `find`, `read_page` or `get_page_text`; never a screenshot
     (RULES.md, "Claude in Chrome").
   After each: `searches.py done <id> found=<n>`. A posting's date comes from the employer's board, since a job
   board's card dated this week is often a repost: `first_published` (Greenhouse), `publishedAt` (Ashby),
   `createdAt` (Lever).
3. Check each employer: `employer.py check "<name>" ...`. "exclude": record the job as `excluded` with its category.
   An "allow" employer whose `unknown` lists israel or defence goes to the screen too: in step 4, without `known`.
   A `recheck` list (a second check against the person's own rules is due) sends it to step 4 with `known` and
   `own` (those categories), before any question about it.
   "discuss": the employer goes to the Questions page with what was found and its source (`questions.py`, RULES.md
   "Questions for the person"); its jobs wait for the answer. Not excluded and `has_environment` is false: look up its
   employee reviews once (RULES.md, "Employer rules").
   `match` "possible" is "discuss" until Claude settles it: after the company register or the site's legal notice,
   `employer.py alias "<saved name>" "<name>"` (same employer) or `alias --not "<saved name>" "<name>"` (different);
   unsure: the job waits (`track.py set <id> needs-person`) and the main session asks the person in the chat, since
   `questions.py add decision` needs a category. Example: "Examplia" against the saved "Examplia Internet GmbH".
4. Screen the rest with `workflows/screen-and-prepare.js` (Workflow tool): pass the search file, `known` (the checks
   from step 3), `employerRules` (the output of `employer.py rules`), the master record and its two parts (`career_view.py screen --out <outDir>/screen.json` as `screenRecord`, `career_view.py facts --out
   <outDir>/facts.json` as `factsRecord`; both are deleted after `track.py sync`). It checks every category, is the
   posting still open, the employer's own apply page (`apply_url`, checked by fetching it), the fit and the pay.
   Then `track.py sync <journal>`, and `employer.py recheck-running` (RULES/employers.md, "Running applications").
5. Record every finding as found (RULES.md, "Employer rules"). Postings that closed: `track.py set <id> closed`.
6. `build_app_folders.py` and the dashboard refresh.

## Saved searches

Every search has a row in `SEARCHES` (`searches.py`), so the next run starts from the row's last check.
- None saved: one row per site and query, from the person's roles and locations. A person with a tracker and no
  rows: `searches.py sites` lists the sites of their jobs that have none; add a row for each.
- A site searched without a row gets its row in the same run. Example: a posting found on a new board:
  `searches.py add "Acme careers" "engineering" alert=no`.
- A row with an alert is read at every run. A site without one is searched at every weekday run, from its last
  check on, and never on a weekend: a check that falls there is due on Monday. `every=7` makes it weekly.

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
- Create it once, signed in, with the site's own alert setting: in the built-in browser when the person has signed
  in there, else in Chrome. Never through a tick-box on an application form.
- Then record it. Example: `searches.py add LinkedIn "Backend engineer, remote" alert=yes
  gmail="from:jobalerts-noreply@linkedin.com newer_than:2d"`. A site with no alerts: `alert=no`.

## Report

One row per posting, by company and role: where, open or closed, the verdict (apply / ask / excluded / skipped)
with its reason, the fit, and the account it needs. Then: "/cenk-jobs:plan puts the cleared ones in order."
Log it: `usage.py log search ok "<n found, n cleared>"`.
