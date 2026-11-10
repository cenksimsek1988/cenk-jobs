---
name: search
description: "Find and screen job postings: searches job boards and company sites under the person's locations, pay and employer rules, checks each employer and records each posting. Use for 'find me jobs', 'search for jobs', 'any new postings?', 'cerca lavoro', 'iş ara', 'Jobsuche'. Never applies."
---

# Search: find and screen postings

Read `../../RULES.md` first. This skill only searches: it writes postings and their screening results into the
tracker, and nothing is prepared or sent.

## Steps

1. Read the person's rules from the master record: where they will work (cities, remote, relocation), the pay
   rule, the roles they want, the languages they work in, and `EMPLOYER_RULES`.
2. Search the sources the person uses (the master record's search brief): job boards and their APIs, LinkedIn in
   Chrome, company career sites. Keep only postings that match the roles and the location rule.
3. Check each employer: `employer.py check "<name>" ...`. "exclude": record the job as `excluded` with its category.
   "discuss": the employer goes to the Questions page with what was found and its source (`questions.py`, RULES.md
   "Questions for the person"); its jobs wait for the answer. Not excluded and `environment` is null: look up its
   employee reviews once (RULES.md, "Employer rules").
4. Screen the rest with `workflows/screen-and-prepare.js` (Workflow tool): pass the search file, `known` (the checks
   from step 3), `employerRules` (the rules file's content) and the master record. It checks every category, is the
   posting still open, the employer's own apply page (`apply_url`, checked by fetching it), the fit and the pay.
   Then `track.py sync <journal>`.
5. Record every finding as found (RULES.md, "Employer rules"). Postings that closed: `track.py set <id> closed`.
6. `build_app_folders.py` and the dashboard refresh.

## Report

One row per posting, by company and role: where, open or closed, the verdict (apply / ask / excluded / skipped)
with its reason, the fit, and the account it needs. Then: "/cenk-jobs:plan puts the cleared ones in order."
Log it: `usage.py log search ok "<n found, n cleared>"`.
