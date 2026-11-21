---
name: search
description: "Find and screen job postings: searches job boards and company sites under the person's locations, pay and employer rules, checks each employer and records each posting. Use for 'find me jobs', 'any new postings?', 'cerca lavoro', 'iş ara', 'Jobsuche'. Never applies."
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
   `script`: a job board's public API, a remote job feed, LinkedIn's guest search) without a model, in the order and
   with the filters its docstring gives; it adds the new postings to the tracker with `found_by` and the row's
   `search` id.
   - Remote Rocketship, one row per country: `searches.py add "Remote Rocketship Italy" "<titles>"
     source=remoterocketship board=italy` (a title becomes its page, `tech=Java` adds a stack filter), read daily.
     Himalayas (`himalayas-search board=Italy`) finds postings only: the funnel applies on the employer's own
     careers page (`../../references/sites/himalayas.md`: its texts are saved from Chrome). Boards and
     `workable-search` are read weekly (`every=7`, their default; older rows: `searches.py every greenhouse 7`).
   - RemoteOK's Apply needs a paid plan: the fit check takes the employer's own posting, else skips the job
     (`../../references/sites/remoteok.md`).
   - The scope: `preferences.locations.search_scope` in the master record; its `remote_regions` stands for
     `REMOTE_REGIONS` and its `any_mode_places` for `PLACES`, each when present. A scope the person states is written
     in the same turn, after their yes: `career_view.py scope --set remote_regions=Germany,EU,Worldwide
     any_mode_places=Springfield`.
   - Its lines for the session: "outside the scope" (from `searches.py due`): one question each on the Questions
     page, `questions.py add general "Turn off the saved search <site> (<place>)? It is outside your search scope."
     options="off:Turn it off|keep:Keep it"`; the answer runs `searches.py every <id> off` or `searches.py scope-ok
     <id>`. "no Remote Rocketship page": `searches.py query <id> "<the other titles>"`. "no text saved": read that
     posting in Chrome and save its text as the file the line names (`../../references/sites/dover.md`).

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
   - A browser last, only for a search nothing else covers: one tab for the whole sweep, navigated per page, closed
     at the end. Read each page with `find` or `read_page` (`max_chars` 5000); never a screenshot (RULES.md,
     "Claude in Chrome").
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
   unsure: the job waits (`track.py set <id> needs-person`) and the page asks: `questions.py add general "Is <name>
   the same employer as <saved name>?" job=<id> options="same:Same|other:Different"`; its answer is `alias` or
   `alias --not`. Example: "Examplia" against the saved "Examplia Internet GmbH".
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
   A run that widens in rounds (new search rows each round): a round reads only its new rows (`collect_postings.py
   --rows <ids> --out ... --add`), and the widening stops after 3 rounds in a row below the best round's real fits
   (high and normal). Example: real fits 12, 5, 3, 2: stop after the fourth round.
6. `build_app_folders.py` and the dashboard refresh.
7. The first run of the week: `../../references/weekly.md` (reply clues, board discovery).

## Saved searches

None saved, a site with no alert decision yet, or the rows to tune: `../../references/saved-searches.md`.

## Report

One row per posting, by company and role: where, open or closed, the verdict (apply / ask / excluded / skipped)
with its reason, the fit, and the account it needs. A posting at an employer where the person has applications
running is shown with them, as information. Every fitting role at one employer is proposed at the same time: a
running application there never holds another back. Example: "Acme, Staff Engineer · running there: Engineer
(interview 18 Nov), Analyst (sent 10 Nov)". Then: "/cenk-jobs:plan puts the cleared ones in order."
Log it: `usage.py log search ok "<n found, n cleared>"`.
