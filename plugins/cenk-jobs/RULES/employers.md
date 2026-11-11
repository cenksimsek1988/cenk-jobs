# cenk-jobs rules: employers

A part of `RULES.md`. Read to check, record or decide an employer, or to draft a withdrawal.

## Employer rules

Every employer is checked before anything is prepared, in eight shared categories: ties to the state of Israel,
defence industry, animal cruelty, climate and environmental harm, sexism, human rights, working conditions, and
sanctions (the UN Security Council list plus the lists the person follows, in `lists`). The person's own filters are
extra categories (`"custom": true`). A category counts only with a crime-level problem: credible news from
established outlets, a court ruling, a fine, a sanctions listing or an official list, each with its source link.
- **Levels, as found:** a finding is direct or indirect by the plugin's levels for its category (`employer.py rules`
  shows them), never by the person's own rules. General: direct = the employer, its group or its majority owner;
  indirect = a minority investor, an investor's other holdings, a partner, a customer, or another firm between them.
  Defence: direct = a defence offering (a defence product line, or a defence sales team or page); indirect = no
  defence line, but named sales to the defence industry, armed forces or a defence ministry; a general product open
  to anyone is no tie (`clear`, with that fact). Police belong to a state category.
  A new fact that removes a finding's basis re-judges its level. Example: "indirect, not used by armed forces", then
  the employer's own page names armed forces as users: direct.
- **The person's own rules** for a category are its `notes` in `EMPLOYER_RULES`. Example: "a defence product offered
  in a state, with no customer named, counts as sold to its armed forces". A finding in a category with notes gets a
  second check against them: `own_level` direct, indirect or none (not counted), with the rule it meets, beside the
  finding, which stays as found. A note that limits which employers are acceptable (an action rule, example:
  "Western countries only") never lowers the level: the level stays as found and the category's action decides,
  exclude or ask; only a note about what counts as a tie sets another level or none. The workflow runs it
  (`excl-own:`); by hand: `employer.py own "<name>" <category>
  <direct|indirect|none> why="<the rule>"`. No finding, no second check. Each second check keeps the fingerprint of
  the notes it judged against (`own_rules`); other notes make it due again, and the earlier one counts until then.
  `employer.py check` lists the due ones in `recheck` and says "discuss" instead of "allow" while one is due.
- **What happens** is the person's choice per category, in `EMPLOYER_RULES`: direct `exclude` / `discuss` (default) /
  `allow`; indirect `discuss` (default) / `warn` / `allow`; or a whole category allowed. They change any of them by
  saying so ("exclude defence companies", "indirect ties are fine there, just warn me"): write it there at
  once, with `{date, field, new}` in `changes` (field example: `defence.notes`).
- **One list** of the person's employers: `EMPLOYER_CHECKS`, each employer with its findings and the person's
  decisions (`employer.py decide "<name>" <exclude|allow> [<category>] [--group]`; `--group` also covers the group's
  units: "Acme" covers "Acme Cloud Services"). No separate name lists. Every exclusion shows the finding behind it.
- **State categories**, for the employer and its parent or majority owner. `israel` is the only default one; another
  state is added only when the person names it (a category with `"state"` and its `lists`), never inferred.
  1. Lists: the category's `lists`. For Israel: the BDS movement's current targets (bdsmovement.net, "What to
     boycott"; past successes do not count), the UN OHCHR settlement-business database (latest edition), Who Profits
     (read its index `/companies?page=N`; its search does not filter), AFSC Investigate. A hit is a direct tie.
  2. From the company's own site, careers page or annual report, each answer with a source link. Direct:
     headquartered in the state; an owner from the state; operating only there or working only for it; selling to a
     body of the state or a state-owned company (government, ministries, armed forces, police, state companies).
     Indirect: its own office, R&D team or subsidiary there (example: "Tel Aviv" on its careers page); selling there,
     itself or through a reseller; a minority investor, an investor's other holdings, or another firm between it and
     the state. No tie: self-service users from the state (a portal anyone signs up to).
  For a small or new brand, find the parent or majority owner first (company registry, the site's legal notice).
  Nothing found after both steps is recorded as `unknown` with the fact "nothing found: <what was checked>", never
  `clear`.
- **Sanctions:** a name check of the employer, its group and its owner on the lists the person follows (`lists`). No
  state-level rule: which lists count is the person's setting, never the plugin's.
- **Records, top-down:** `names.json` (every lookup key of every saved name and alias, one entry each) refers to the
  summary `EMPLOYER_CHECKS` (verdict, decisions, a status per category, links), which refers to files per employer and
  scope in `EMPLOYERS_DIR/<name>/`: `checks.json`, `environment.json`, `history.json`. A question about ties opens only
  `checks.json`. Only `employerlib.py` knows this; `employer.py split --apply` moves an older file into it.
- `employer.py check "<name>"` shows what the shared blacklist and the person's earlier checks know, and the verdict;
  `--full` adds `environment` and `history`. `match`: exact, group (a group entry covers it), possible or none.
- A possible match (a saved name with all of its words, or 85% alike: "Examplia" and "Examplia Internet GmbH") is "discuss",
  never an allow. Settle it once: `employer.py alias "<saved name>" "<name>"` (the same employer; refused when a key
  belongs to another) or `employer.py alias --not "<saved name>" "<name>"` (different; never offered again).
- When a category says discuss, the employer goes to the Questions page ("Allow, or exclude?") with what was found and its
  source; `questions.py record` writes the answer with `employer.py decide "<name>" <exclude|allow> [<category>]`.
- A category not checked stays "unknown"; never write "clear" without having looked.
- Record every finding as found, direct or indirect, whatever the person decides: a decision never turns a finding
  into "clear", and never changes its category or level. The shared list holds findings only (category, level,
  fact, source); decisions, settings and `own_level` stay in the person's own files. The shared blacklist keeps every sourced finding, so each person's own rules decide. The plugin's
  developer merges their own findings with `employer.py merge --from-checks`; everyone else's reach it through the
  weekly usage report, with their yes.
- Working environment: what employee reviews say, apart from the categories. `employer.py check` says in
  `has_environment` whether one is saved (`--full` shows it). When it is false and the employer is not excluded: one WebSearch (`"<name>" reviews glassdoor`;
  Glassdoor blocks WebFetch, so read the rating from the search result; Kununu or Indeed when Glassdoor has nothing),
  then `employer.py environment "<name>" reviews=120 rating=3.8 complaints="long hours; high turnover" source=<url>`.
  Nothing found: `reviews=0`, saved too, so nobody searches again.
- A saved `environment` is reused until the person asks for a refresh (the same command replaces it; `reviews=0` never
  replaces a rating). It is shown in `company.md` and never changes a verdict: the person decides. Complaints are up to 6 topics of a few words that
  reviews repeat; never review text, never a person's name. Details go in the job's `notes.md`.
- **Shared list updates:** `EMPLOYERS_DIR/shared-seen.json` keeps a fingerprint per employer and category of the shared
  list the person last took in (example: `"defence": "flagged direct 1a2b3c4d5e6f"`). Each
  run, in this order: `employer.py shared-update` (a dry run; nothing to do while the plugin's list is the same), each
  `ask` item's `question` to the Questions page (`questions.py add decision`, with its employer, category, fact and
  source), then `employer.py shared-update --apply`, so a stopped run loses no question. The first time `--apply` only
  saves the fingerprints. An employer the person never gave an opinion on follows the new version: the new check replaces
  their own one in that category, a retraction too (flagged to clear), the old one goes to the history, and each
  `updated` item is one line in the run report. An employer with their `opinion` (a decision, or a finding they stated:
  `employer.py record ... --person`) gets one question for all its changed categories; a change their record already
  holds needs none. Then `recheck-running`.
  Example: "Shared list update for Acme Corp: Defence industry: flagged indirect -> flagged direct. Your setting:
  allow since 2026-11-10. Allow, or exclude?"
- **Running applications:** after a change that can move a verdict (the person's rules, a decision, new findings
  from a sync), `employer.py recheck-running` judges again every employer with a sent application that has not ended
  (rejected, closed, declined). It prints those whose verdict moved to exclude or discuss, or whose second check is
  due, and saves each moved verdict. A due second check runs first (the workflow with `known` and `own`, or
  `employer.py own`), then `recheck-running` again. Each moved one goes to the Questions page: `questions.py add
  decision` with the finding, its source and the running jobs (Allow = go on; Exclude = withdraw, below). Example:
  the person sets indirect defence ties to exclude; an employer at the interview stage with one is listed.
- **Withdrawal:** an excluded employer the person applied to, once it writes beyond an automatic confirmation (an
  invitation to a step, a task or test, a recruiter's mail) or offers a job; also an employer that a new check or a
  rule change excludes while its process runs. Ask the person first, in two questions: send a withdrawal mail at
  all? Give the reason? No mail: nothing is drafted. A mail: draft it from `templates/withdrawal-email.txt`, the
  version with the reason (the employer's sourced fact) or the one without it (facts only), as a Gmail draft; the
  person sends it. Example: invited to online tasks, then a direct tie is found: ask, then a draft.
- A draft always has a recipient. A no-reply sender: the recruiter named in the mail, else the careers contact on the
  employer's own site (example: `careers@` on its FAQ page), else the privacy contact on the posting; check each on
  its page, never guess an address. An employer kept only for practice, or one that already rejected the person,
  gets none.
