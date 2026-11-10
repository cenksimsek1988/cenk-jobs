# cenk-jobs rules: employers

A part of `RULES.md`. Read to check, record or decide an employer, or to draft a withdrawal.

## Employer rules

Every employer is checked before anything is prepared, in eight shared categories: ties to Israel's occupation or
military, defence industry, animal cruelty, climate and environmental harm, sexism, human rights, working
conditions, and sanctions (the UN Security Council list plus the lists the person follows, in `lists`). The
person's own filters are extra categories (`"custom": true`). A category counts only with a crime-level problem:
credible news from established outlets, a court ruling, a fine, a sanctions listing or an official list, each with
its source link. A tie is direct (the employer, its group or its majority owner) or indirect (a minority investor,
an investor's other holdings, a partner or a customer).
- **What happens** is the person's choice per category, in `EMPLOYER_RULES`: direct `exclude` / `discuss` (default) /
  `allow`; indirect `discuss` (default) / `warn` / `allow`; or a whole category allowed. They change any of them by
  saying so ("exclude defence companies", "indirect ties are fine there, just warn me"): write it there at
  once, with `{date, field, new}` in `changes`.
- **One list** of the person's employers: `EMPLOYER_CHECKS`, each employer with its findings and the person's
  decisions (`employer.py decide "<name>" <exclude|allow> [<category>] [--group]`; `--group` also covers the group's
  units: "Acme" covers "Acme Cloud Services"). No separate name lists. Every exclusion shows the finding behind it.
- **The Israel check, two steps**, for the employer and its parent or majority owner:
  1. Lists: the BDS movement's current targets (bdsmovement.net, "What to boycott"; past successes do not count),
     the UN OHCHR settlement-business database (latest edition), Who Profits, AFSC Investigate.
  2. Four questions from the company's own site, careers page or annual report, each answered with a source link:
     founded in Israel or headquartered there? its own office, R&D team or subsidiary in Israel (example: "Tel Aviv"
     on its careers page)? its majority owner (then step 1 on the owner)? supplying Israel's military or police, or
     the settlements?
  A list hit or a yes is a direct tie. Indirect ties: a reseller or shop selling the brand in Israel, a minority
  investor's other holdings, customers, a board member's outside seat, a licensee's owner. For a small or new brand,
  find the parent or majority owner first (company registry, the site's legal notice). Nothing found after both
  steps is recorded as `unknown` with the fact "nothing found: <what was checked>", never `clear`.
- `employer.py check "<name>"` shows what the shared blacklist and the person's earlier checks know, and the verdict.
- When a category says discuss, the employer goes to the Questions page ("Allow, or exclude?") with what was found and its
  source; `questions.py record` writes the answer with `employer.py decide "<name>" <exclude|allow> [<category>]`.
- A category not checked stays "unknown"; never write "clear" without having looked.
- Record every finding as found, direct or indirect, whatever the person decides: a decision never turns a finding
  into "clear", and never changes its category or level. The shared list holds findings only (category, level,
  fact, source); decisions and settings stay in the person's own files. The shared blacklist keeps every sourced finding, so each person's own rules decide. The plugin's
  developer merges their own findings with `employer.py merge --from-checks`; everyone else's reach it through the
  weekly usage report, with their yes.
- Working environment: what employee reviews say, apart from the categories. `employer.py check` shows the saved
  `environment`. When it is null and the employer is not excluded: one WebSearch (`"<name>" reviews glassdoor`;
  Glassdoor blocks WebFetch, so read the rating from the search result; Kununu or Indeed when Glassdoor has nothing),
  then `employer.py environment "<name>" reviews=120 rating=3.8 complaints="long hours; high turnover" source=<url>`.
  Nothing found: `reviews=0`, saved too, so nobody searches again.
- A saved `environment` is reused until the person asks for a refresh (the same command replaces it; `reviews=0` never
  replaces a rating). It is shown in `company.md` and never changes a verdict: the person decides. Complaints are up to 6 topics of a few words that
  reviews repeat; never review text, never a person's name. Details go in the job's `notes.md`.
- An excluded employer the person applied to, once it writes beyond an automatic confirmation (an invitation to a
  step, a task or test, a recruiter's mail) or offers a job: draft the withdrawal mail from
  `templates/withdrawal-email.txt`, with the employer's sourced fact, so it reads why (a Gmail draft; the person
  sends it). The same when a new check excludes an employer whose process is running. Example: invited to online
  tasks, then a direct tie is found: a draft naming the source.
- A draft always has a recipient. A no-reply sender: the recruiter named in the mail, else the careers contact on the
  employer's own site (example: `careers@` on its FAQ page), else the privacy contact on the posting; check each on
  its page, never guess an address. An employer kept only for practice, or one that already rejected the person,
  gets none.
