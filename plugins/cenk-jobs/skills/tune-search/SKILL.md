---
name: tune-search
description: "Tune the saved searches: candidate searches compared over one week of the same postings, each job fit-checked once; the ones with the most high fits replace the saved ones. Use for 'tune my search', 'find better searches', 'aramayı iyileştir', 'migliora la ricerca'. Never applies."
---

# Tune the search: candidate searches compared by high fits

Read `../../RULES.md` first. This skill changes the saved searches and title rules, and adds the high fits it finds
as found jobs; nothing is prepared or sent. Its script: `tune.py` (its docstring has every command).

## Steps

1. `tune.py start` (window: the last 7 days, fixed; the counted model: `FIT_MODEL`; the budget: `TUNE_TOKENS`,
   default 35M). Read how the search works today: `searches.py list`, `searches.py rules`, the collector's docstring.
2. Write `round-<n>.json` in the run's folder: candidates, each `{"name", "rows": [saved-search rows], "rules":
   title rules or null for the person's own, "row_terms": "filter" or "search", optional}`. A row has the saved
   form (`site`, `query`, `source`, `board`, `place`, `mode`, `tech`, `tag`, `employer`). Round 1 holds today's rows
   as they are, as candidate "today", beside the new ones.
3. `tune.py round <n>`: every row read once (cached), every candidate run over the same postings. Past records grade
   what they know.
4. `tune.py fit <n>`, then the Workflow tool with the script it names (`scriptPath`); then `tune.py score <n>
   <journal>`. Again while the table shows jobs "to check": a check that failed on its output (about 4% a run) goes
   into the next one. With a counted model other than Sonnet: `tune.py fit <n> --recheck`, its Workflow run, then
   `tune.py score <n> <journal> --recheck`.
5. Read the table: why do the candidates differ? Write the next round's candidates from that reason, the strongest
   source's directions first. Stop when `score` says 3 rounds in a row without a new best, or when `fit` refuses over
   the budget.
6. `tune.py winner <round> <candidate>`, a dry run, then `--apply`: the best candidate's rows replace the saved
   searches, its rules the title rules, and its high fits no tracker job holds go in with their fit results, each a
   pending high fit for the next apply run. The person is not asked first (decided 23 Nov 2026); the report names
   every change.
7. Report: the rounds' tables, why the searches differ, the winner and what it changed, the tokens spent. `tune.py
   winner --apply` deletes the cache; after a run without a winner, `tune.py clean`.

## Candidates

- A candidate varies rows and title rules only, never the person's places or remote regions. Example: no row may
  widen `REMOTE_REGIONS`; a wider region is a finding for the person, in the report.
- The source decides. Seen 23 Nov 2026: a remote board's search by country (Himalayas) gave most high fits, company
  boards almost none in a week. Try depth and more terms on the best source before new sources.
- Terms are not title filters on a searching source: with `need` in the title rules a LinkedIn or Himalayas row's
  terms only search (`ROW_TERMS`). Seen 23 Nov: a row "java" lost "Senior Backend Developer"; on rows already wide,
  the same rule added fit checks and no high fit.
- Level words in title rules cost high fits (seen 23 Nov: a lead-title rule kept 5 of 26); off-profile titles
  (DevOps, data, QA) held almost none.
- A lenient model keeps finding one more: the counted model decides, never the screen. Seen 23 Nov: Sonnet graded 44
  high, Opus kept 10.

## Limits

- Calls: at most 600 LinkedIn and 650 Himalayas calls a run; a refusal stops that source for the round, and its
  rows' postings count as not found ("LinkedIn unread").
- Tokens: `fit` estimates employers times one fit check's cost and refuses past `TUNE_TOKENS`.
- Files: the run's folder `apply/tune/<date>/` keeps the rounds, tables and every fit result whole
  (`fit-results.json`, graded again under today's rules); the raw answers are in the system's temp folder.
