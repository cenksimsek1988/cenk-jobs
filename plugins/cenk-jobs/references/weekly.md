# The weekly steps

Read by the search session at the first run of the week.

## Reply clues

`feedback.py silent --add`, `feedback.py clues` (the fit check reads it next run), and `feedback.py analyse`. Its
proposals go to the Questions page; FIT_SETTINGS changes only on the person's yes. Scripts only, no model.

## Remote Rocketship rows

`searches.py suggest`: the rows' titles with no title page, and the fits' titles and the scope's countries the rows
lack, each checked on one page (about 2 minutes, no model). Each printed `searches.py query` or `add` command runs
only after the person's yes. Example: "add country: europe (31 new a week for "engineering manager")". Seen 19 Nov:
12 of 14 fits came from 2 Remote Rocketship rows.

## Board discovery

At the same run: 8 web searches, the 4 board kinds x 2 scopes (the remote regions; the person's places), each with
the role terms. Each board kind goes in WebSearch's `allowed_domains`, never as `site:` in the query, which the
search tool often ignores (seen 20 Nov): `job-boards.greenhouse.io` and `boards.greenhouse.io`; `jobs.ashbyhq.com`;
`jobs.lever.co`; `apply.workable.com`. Example: query `"backend engineer" remote Europe`, `allowed_domains:
["jobs.ashbyhq.com"]`.
- The result links go into a file, one per line; `searches.py discover --file <links file>` prints each board
  not saved yet: `new <kind> <board> <link>`.
- For each: the employer's name from its board page, `employer.py check "<name>"` and `employer_lookup.py
  "<name>" --record` (both free). Excluded: no row. Else `searches.py add "<name>" "<role terms>" source=<kind>
  board=<board> employer="<name>"`, read weekly by the script from then on.
- An agent row that did this by hand is turned off after the person's yes: `searches.py every <id> off`.
- Cost: 8 web searches and about 50-100k W a week (1-2% of a 3.6-8.4M W run). The new boards' postings share
  `MAX_NEW_PER_RUN`: more choice per run, not more postings.
