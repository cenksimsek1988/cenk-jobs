# The weekly steps

Read by the search session at the first run of the week.

## Reply clues

`feedback.py silent --add`, `feedback.py clues` (the fit check reads it next run), and `feedback.py analyse`. Its
proposals go to the Questions page; FIT_SETTINGS changes only on the person's yes. Scripts only, no model.

## Board discovery

At the same run: 8 web searches, the 4 board kinds (`site:greenhouse.io`, `site:jobs.ashbyhq.com`,
`site:jobs.lever.co`, `site:apply.workable.com`) x 2 scopes (the remote regions; the person's places), each with the
role terms. Example: `site:jobs.ashbyhq.com "backend engineer" remote Europe`.
- The result links go into a file, one per line; `searches.py discover --file <links file>` prints each board
  not saved yet: `new <kind> <board> <link>`.
- For each: the employer's name from its board page, `employer.py check "<name>"` and `employer_lookup.py
  "<name>" --record` (both free). Excluded: no row. Else `searches.py add "<name>" "<role terms>" source=<kind>
  board=<board> employer="<name>"`, read weekly by the script from then on.
- An agent row that did this by hand is turned off after the person's yes: `searches.py every <id> off`.
- Cost: 8 web searches and about 50-100k W a week (1-2% of a 3.6-8.4M W run). The new boards' postings share
  `MAX_NEW_PER_RUN`: more choice per run, not more postings.
