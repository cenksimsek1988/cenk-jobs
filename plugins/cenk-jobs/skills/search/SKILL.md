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
2. First `collect_postings.py --out <outDir>/search.json --add` (the window starts at the last finished run;
   the search file holds at most `MAX_NEW_PER_RUN` postings, the rest wait for the next run; a repost of a role
   already applied to or declined is left out and recorded `skipped`, `reposts.py`): every due search a script can read (method
   `script`: a job board's public API, a remote job feed, LinkedIn's guest search) without a model; it adds the new
   postings to the tracker with `found_by` and the row's `search` id. What it does, in order:
   - Sources in this order, and the funnel filled in it: company boards and remote feeds (remotive, remoteok,
     jobicy, himalayas, arbeitnow, remoterocketship, himalayas-search, workable-search), then LinkedIn by city
     (`mode=any`), then LinkedIn remote searches (`mode=remote`). On 19 Nov Remote Rocketship gave 12 of 14 fits.
   - Remote Rocketship, one row per country: `searches.py add "Remote Rocketship Italy" "<titles>"
     source=remoterocketship board=italy` (a title becomes its page, `tech=Java` adds a stack filter). Each page
     holds its 20 newest postings, so it is read daily. Himalayas (`himalayas-search board=Italy`) finds postings
     only: the funnel applies on the employer's own careers page. Boards and `workable-search` are read weekly
     (`every=7`, their default; older rows: `searches.py every greenhouse 7`).
   - Each feed 3 s between calls; 2 refusals (429) in a row stop it for the run, its rows stay due.
   - Before the funnel, each posting's own page (Ashby and Greenhouse locations, the page text): every place
     outside the person's places, "must be based in" another country, or US hours: left out, no tokens spent.
     Seen 19 Nov: 32 of 40 "Europe" postings were single-country elsewhere.
   - A posting already in the tracker under another link (the same employer and title) is left out. A "team lead"
     title needs an engineering word ("Team Lead, Customer Success" is out).
   - The person's title rules (`SEARCH_RULES`, see `templates/search-rules-example.json`) before any text is read:
     another language's title form, a low level, no level word, a word they drop, no engineering word. The same
     lists filter boards and feeds, whose postings are often sales or operations roles.
   - A feed's posting passes only with a region of the scope in its own location field; one that names none does
     not. Example: "Remote, Europe" passes with the region Europe; "Remote, USA only" does not.
   - A LinkedIn remote search's posting goes to the funnel only when its own text speaks of remote work (one text
     read, no model; `TEXT_FETCHES` a run). Seen: 73 of 82 were hybrid in one city.
   - The same job from two sources is screened once; one the funnel skipped for fit in the last 30 days is not
     screened again (`reposts.py`).
   - LinkedIn: 4.5 s between calls, a text 6 s; one refusal pauses 60 s and slows to 8 s; a second stops it.
   - The scope: `preferences.locations.search_scope` in the master record; its `remote_regions` stands for
     `REMOTE_REGIONS` and its `any_mode_places` for `PLACES`, each when present. Those two fields are written only
     with the person's yes. Example: `"remote_regions": ["Germany", "EU", "Worldwide"], "any_mode_places":
     ["Springfield"]`.

   Then `searches.py due` for the rest (method `agent`): a run reads only these, never every
   site again. With none saved it says so: create them first ("Saved searches"). For each, the cheapest source that
   covers it, in this order.
   Keep only postings that match the roles and the location rule; drop what the tracker has (`searches.py seen --file
   <links file>`, one link per line, never typed into a command).
   - Alert emails: Gmail `search_threads` with the row's `gmail` query, `pageSize` 10; open only messages newer than
     the row's last check.
   - Connectors: Indeed `search_jobs` and `get_job_details`; Develop21 `develop21_execute_job_search` (`list` with
     `brief`, `check` to drop rows already seen). Indeed mostly returns older listings: a supplement, not the source
     of new ones.
   - A job board's public JSON (the addresses in `workflows/screen-and-prepare.js`), or `fetch_jd.py`.
   - A site without an alert: newest first, and stop at the first posting older than the row's last check or already
     in the tracker. Example: last check 6 Nov; the list reaches a posting of 5 Nov: stop there.
   - A browser last, only for a search nothing else covers. Read each page with `find`, `read_page` or `get_page_text`; never a screenshot
     (RULES.md, "Claude in Chrome").
   After each: `searches.py done <id> found=<n>`; each posting an agent finds is added with `found_by=agent:<source>`.
   A source an agent found that has no alert: check whether a script can read it (a public board API, a plain page);
   if so, add it as a script row (`searches.py add ... source=<kind> board=<name>`), so the script's share grows. A posting's date comes from the employer's board, since a job
   board's card dated this week is often a repost: `first_published` (Greenhouse), `publishedAt` (Ashby),
   `createdAt` (Lever).
3. Look up each employer without a model: `employer.py check "<name>" ...`. "exclude": record the job as `excluded`
   with its category; nothing else stops. An employer it calls "unknown, never checked" goes on, and the run report
   counts such employers. A `recheck` list (a second check against the person's own rules is due)
   sends it to step 4 with `screen: true`, `known` and `own` (those categories); so does a recorded finding still to
   judge. Unknown, warn and "discuss" go to step 4 without a screen: the funnel checks fit first, and the person is
   asked about a "discuss" employer only once it answers (RULES/employers.md). Then, for every employer never
   checked: `employer_lookup.py --file <outDir>/search.json --record` (free public data, about 6 seconds an employer,
   no model): "exclude" stops its jobs at once; "undecided" is passed with `quick: true` and `lookup` (its line,
   so the cheap check starts from what was found). Not excluded and `has_environment` is false: look up its employee reviews once, after a posting fits
   (RULES.md, "Employer rules").
   `match` "possible" is "discuss" until Claude settles it: after the company register or the site's legal notice,
   `employer.py alias "<saved name>" "<name>"` (same employer) or `alias --not "<saved name>" "<name>"` (different);
   unsure: the job waits (`track.py set <id> needs-person`) and the main session asks the person in the chat, since
   `questions.py add decision` needs a category. Example: "Examplia" against the saved "Examplia Internet GmbH".
4. The funnel, `workflows/screen-and-prepare.js` (Workflow tool), with the args `workflow_args.py --search
   <outDir>/search.json --lookup <the lookup's --out file>` builds in `<outDir>/args.json` (about 8 KB; it leaves out
   each excluded employer and names it; one jobs file per employer; the record parts, deleted after `track.py
   sync`). Pass that file's content as the Workflow args. The funnel: the fit check and the cheap employer check
   (for a company with `quick: true`, from its lookup line) in the order `variants.py order` gives; the full
   employer check only for one with `screen: true`; then the form answers, the letter and the review.
   Then `track.py sync <journal>` (a fit's skip becomes `skipped` with its reason, an apply `pending`; many single
   changes by hand go in one `track.py set --file`), `variants.py funnel <the workflow's result>`, and `employer.py
   recheck-running` (RULES/employers.md, "Running applications").
5. Record every finding as found (RULES.md, "Employer rules"). Postings that closed: `track.py set <id> closed`.
6. `build_app_folders.py` and the dashboard refresh.
7. Weekly (the first run of the week): `feedback.py silent --add`, `feedback.py clues` (the fit check reads it
   next run), and `feedback.py analyse`. Its proposals go to the Questions page; FIT_SETTINGS changes only on the
   person's yes. Scripts only, no model.
8. Weekly, at the same run as step 7: board discovery. 8 web searches, the 4 board kinds (`site:greenhouse.io`,
   `site:jobs.ashbyhq.com`, `site:jobs.lever.co`, `site:apply.workable.com`) x 2 scopes (the remote regions; the
   person's places), each with the role terms. Example: `site:jobs.ashbyhq.com "backend engineer" remote Europe`.
   - The result links go into a file, one per line; `searches.py discover --file <links file>` prints each board
     not saved yet: `new <kind> <board> <link>`.
   - For each: the employer's name from its board page, `employer.py check "<name>"` and `employer_lookup.py
     "<name>" --record` (both free). Excluded: no row. Else `searches.py add "<name>" "<role terms>" source=<kind>
     board=<board> employer="<name>"`, read weekly by the script from then on.
   - An agent row that did this by hand is turned off after the person's yes: `searches.py every <id> off`.
   - Cost: 8 web searches and about 50-100k W a week (1-2% of a 3.6-8.4M W run). The new boards' postings share
     `MAX_NEW_PER_RUN`: more choice per run, not more postings.

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
  postings. Discovery by web search (step 8) is different: it finds boards that exist and hold matching postings.

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

## Report

One row per posting, by company and role: where, open or closed, the verdict (apply / ask / excluded / skipped)
with its reason, the fit, and the account it needs. A posting at an employer where the person has applications
running is shown with them, as information. Every fitting role at one employer is proposed at the same time: a
running application there never holds another back. Example: "Acme, Staff Engineer · running there: Engineer
(interview 18 Nov), Analyst (sent 10 Nov)". Then: "/cenk-jobs:plan puts the cleared ones in order."
Log it: `usage.py log search ok "<n found, n cleared>"`.
