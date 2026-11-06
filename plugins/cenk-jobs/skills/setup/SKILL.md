---
name: setup
description: "First run of the job search, once: checks the programs and logins, creates the main folder in the person's Google Drive with job-search.env, offers the default settings in one choice, reads their CVs and documents into one master record, builds CV versions, creates and pins the dashboard, and names the main session. Use for \"set up my job search\", \"start using cenk-jobs\", \"first run\", \"iş aramamı kur\", \"configura la ricerca di lavoro\". Not for daily work: search, plan, apply, prepare and schedule do that."
---

# Setup: the first run

Read `../../RULES.md` first (honesty, consents, never an ID, password, code or CAPTCHA). Run these steps in order and
ask before moving on. Each step is safe to run again: it skips what is already there and says so.

## 1. Programs

- Check Python 3.10+ (`python --version`, or `py --version` on Windows), Google Chrome and Google Drive for desktop.
- For each missing one: say what it is for and ask; on the person's yes, install it from the official source.
  Windows: `winget install -e --id Python.Python.3.12` / `Google.Chrome` / `Google.GoogleDrive`. Mac: `brew install
  python`, `brew install --cask google-chrome`, `brew install --cask google-drive`. One install per yes.
- The person signs in to Google Drive and Chrome themselves. The Claude in Chrome extension: open its Chrome Web
  Store page for them; they click "Add to Chrome", pin it and sign in with their Claude account.

## 2. Logins and connectors

The health-check calls in RULES.md, and the person's LinkedIn signed in in Chrome. Help with each missing one, step
by step.

## 3. The main folder

- Ask where it should be, then `init_career_folder.py "<main folder>" "<Full Name>"`.
- Fill `CONTACT_LINE`, `LETTER_TITLE`, the accounts and `PHOTO` in `job-search.env` with the person.
- On their OK, add `JOB_SEARCH_ENV=<main folder>/job-search.env` to the `env` block of `~/.claude/settings.json`;
  it takes effect in sessions started after the change.

## 4. The defaults: one choice

Show the defaults and ask: "Use these defaults? You can change any of them later by just saying so."

- The search runs every day at 19:00 your local time (`SEARCH_TIME`; `/cenk-jobs:schedule` changes it).
- Optional consents stay off: newsletters, talent pools, job alerts, marketing, SMS, AI analysis of interviews,
  extra data retention.
- Open free-text questions, essays and self-ratings are never filled for you: they wait for you in Do now.
- Emails and messages are drafts; you send them. Applications are sent only after your go-ahead.
- Job-search mails Claude has finished get the Gmail label `cenk-jobs/Done` (`GMAIL_DONE_LABEL`); create it once
  the defaults are accepted. Mails waiting on you stay unlabelled.
- Pay figures and your address go only into forms, never into a CV, letter, shared file or the dashboard.
- Employer checks, in eight categories, each "warn and ask" for a direct tie and for an indirect one:
  ties to Israel's occupation or military; defence industry; animal cruelty; climate and environmental harm;
  sexism; human rights; working conditions; sanctions.
- Sanctions: the UN Security Council list, plus the lists of the country or region you live in. Ask which, with
  examples: EU, UK (OFSI), US (OFAC), a national list. Write them into `lists` of the `sanctions` category.

Then say how to change them, with examples:
- per category, a direct tie: never apply / ask / apply ("never apply to defence companies");
- per category, an indirect tie (an investor, a partner, a customer): ask / just warn / apply ("indirect ties to
  climate harm are fine, just warn me");
- a whole category allowed ("animal cruelty checks are not for me").

Ask once: "Any filter of your own?" Examples: another sanctions list, a sector (gambling, tobacco, fossil fuels), a
country. Write each as a category with `"custom": true`, an id, a label, `what`, `action` and `indirect`.
Write every answer into `EMPLOYER_RULES` (the template is `templates/employer-rules.json`) with `{date, field, new}`
in `changes`.

## 5. Documents

- Ask for every CV (all languages and versions), earlier cover letters, the LinkedIn profile, diplomas and
  transcripts, certificates, language certificates, references and recommendation letters, and the material the
  field needs (a portfolio, publications, a project list, public code).
- The person can just say where things are: "in Google Drive under X", "take it from my LinkedIn", "attached to an
  email I sent", "in Canva", "somewhere on my computer". Fetch it: Drive, Gmail (sent mail with a CV attached),
  LinkedIn in Chrome ("More > Save to PDF"), Canva (export as PDF), Desktop, Documents and Downloads.
- Or they drop everything into `DOCUMENTS_INBOX_DIR` and say when they are done; then file each document (certificates,
  diplomas, portfolio, old CVs into `RECORDS_DIR/previous-documents`) and ask about what could not be placed.
- Read everything into the master record (`MASTER_RECORD`), facts only; a claim nobody confirmed gets
  `"status": "pending"`. Draw skills out of every source and ask a few short questions about their work, so skills
  they never wrote down end up in the record. Show what you found and what is missing.
- References: record name, role, relation and contact only with the person's word that the referee agreed; never
  contact a referee. Never store ID numbers.

## 6. Where and how they will work

Cities, remote, hybrid, relocation; the pay floor (private); how interviews may be scheduled. Write each into
`preferences` as fact lines. Then ask once about the weekly usage report ("It holds no name, contact, CV, pay or
address; you read each one and send it yourself") and write `USAGE_SHARING=yes|no` in `job-search.env`.

## 7. CV versions

One `CV_VERSIONS_DIR/<n> <Variant>.json` per kind of role (from `templates/cv-version-example.json`), each with its
cover-letter template. Build them with `build_cv.py` and check each PDF: two pages at most, nothing invented. Offer
to delete stale copies elsewhere (to the trash only, on their yes).

## 8. The dashboard

Create it without asking (RULES.md, "Dashboard"), put its link in `DASHBOARD_URL`, then: "Your dashboard: <link>.
Pin it to find it in one click: Artifacts > Job applications > Pin. Shall I pin it for you?" Pin only on a yes.

## 9. The main session

Title this session "Job search coordinator" (the app's session-title tool) and say: "This is your main job-search
session. Ask here for anything: I start one session per job (applying, interview prep, essays) and record what each
reports. Keep job-search work out of other sessions." From here on it runs `cenk-jobs:coordinate`.

## 10. The schedule and the first search

With the defaults accepted, create the daily run with `/cenk-jobs:schedule` (19:00 local time), then run the first
search now with `/cenk-jobs:search`. Job sites that need an account come out of that search: the person creates each
account and leaves its profile empty, because Claude fills it when applying.
