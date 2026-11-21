---
name: setup
disable-model-invocation: true
description: "First run of the job search, once: checks programs and logins, creates the main folder, reads the person's CVs into one master record, builds CV versions, creates and pins two pages. Use for 'set up my job search', 'start using cenk-jobs', 'first run', 'iş aramamı kur'. Not for daily work."
---

# Setup: the first run

Read `../../RULES.md` first (honesty, consents, never an ID, password, code or CAPTCHA). Say first, in one plain
sentence, what setup needs from the person; then run these steps in order and ask before moving on. Example: "Setup
needs from you: your OK to install what is missing, your sign-ins to Google Drive, Chrome and LinkedIn, and your CVs
and documents." Each step is safe to run again: it skips what is already there and says so.

## 1. Programs

Check the programs setup needs and install the missing ones by `../../references/install.md` (each program,
what it is for, its check and its install line per system). Ask once, listing only the missing ones with what
each is for: "I'll install these now, unless you say no to any." Example: "pypdf and Poppler are missing: pypdf
reads your PDFs, Poppler shows me their pages. I'll install both now, unless you say no."

## 2. Logins and connectors

The connector calls of the health check (RULES/run.md), and the person's LinkedIn signed in in Chrome. Help with each missing one, step
by step. Read each page in Chrome with `find` or `read_page` (`max_chars` 5000); never take a screenshot.

## 3. The main folder

- The profile first (their own facts, shared with the other cenk plugins through the base plugin cenk-base):
  `profilelib.py path` (Bash tool: only it gets `CENK_BASE`).
  - "cenk-base is not loaded" or no profile yet (exit 1): as RULES.md says ("Keep learning about the person");
    with the base missing, stop setup here. `create` also copies the old profile a `PROFILE` line in an old
    `job-search.env` names.
  - Ask how they want to be referred to, and save it: `set person.pronouns`.
- The main folder: ask where it should be, suggesting `<cenk folder>/jobs/` (the cenk folder: `profilelib.py home`),
  then `init_career_folder.py "<main folder>"`. Say where it was created. An existing main folder stays where it is.
- Fill `LETTER_TITLE`, the accounts and `PHOTO` in `job-search.env` with the person. The name and contact line on
  letters come from the profile (`person.name`, `location`, `phone`, `email`, `links.linkedin`): set the missing ones;
  `CONTACT_LINE` in `job-search.env` only when the person wants another wording.
- On their OK, add `JOB_SEARCH_ENV=<main folder>/job-search.env` to the `env` block of `~/.claude/settings.json`;
  it takes effect in sessions started after the change.

## 4. The defaults: one choice

Show the defaults and ask: "Use these defaults? You can change any of them later by just saying so."

- The search runs on weekdays (Monday to Friday) at 19:00 your local time (`SEARCH_TIME`, `SEARCH_DAYS`;
  `/cenk-jobs:schedule` changes it, also to every day).
- Optional consents stay off: newsletters, talent pools, job alerts, marketing, SMS, AI analysis of interviews,
  extra data retention. A job alert you say yes to for a site is the exception: it replaces repeat searches.
- Your birth date, references, criminal record and relatives at the company: a form asking for one waits for you,
  unless you let forms answer it from your profile (`form_facts`). Example: "let forms answer my birth date" sets
  `settings.cenk-jobs.form_facts` to `["birth_date"]`, after your yes to that key and value. ID numbers never.
- Open free-text questions, essays and self-ratings are never filled for you (unless you turn on the setting
  `draft_answers`: then Claude drafts each answer and fills it only after your approval): they wait for you on your
  Questions page, with every other question your records do not answer. Each answer goes into your records, so it
  is asked once. To write one with Claude: `/cenk-jobs:write`.
- Emails and messages are drafts; you send them.
- Applications: by your cost choices below (`APPLY`, `ASK_FIRST`); you hear what was sent after each run. Only what
  Claude cannot do waits for you in Do now: CAPTCHAs, passwords, sign-ups, emailed codes, ID numbers, essays, pay below your
  target, answers your records do not hold.
- Job-search mails Claude has finished get the Gmail label `cenk-jobs/Done` (`GMAIL_DONE_LABEL`); create it once
  the defaults are accepted. Mails waiting on you stay unlabelled.
- Your two private pages, "cenk-jobs · Job applications" (the dashboard) and "cenk-jobs · Questions for you", are
  pinned to your claude.ai sidebar, so each is one click away.
- Pay figures go only into forms and onto your own Questions page (only you read it); your address only into
  forms. Never into a CV, letter, shared file or the dashboard.
- Employer checks, in eight categories, each "discuss" for a direct tie and for an indirect one (you see the
  finding and decide: allow or exclude):
  ties to the state of Israel (the only state checked until you name another); defence industry; animal cruelty;
  climate and environmental harm; sexism; human rights; working conditions; sanctions.
- Sanctions: the UN Security Council list, plus the lists of the country or region you live in. Ask which, with
  examples: EU, UK (OFSI), US (OFAC), a national list. Write them into `lists` of the `sanctions` category.

Then say how to change them, with examples:
- per category, a direct tie: exclude / discuss / allow ("exclude defence companies");
- per category, an indirect tie (an investor, a partner, a customer): discuss / just warn / allow ("indirect ties to
  climate harm are fine, just warn me");
- a whole category allowed ("animal cruelty checks are not for me");
- your own rule for a category, into its `notes`: a finding there gets a second check against it ("a defence product
  sold in a state with no customer named counts as sold to its armed forces").

Ask once: "Any filter of your own?" Examples: another sanctions list, a sector (gambling, tobacco, fossil fuels),
another state. Write each as a category with `"custom": true`, an id, a label, `what`, `action` and `indirect`; a
state only when the person names it, with `"state"` and its `lists` instead of `what`.
Write every answer into `EMPLOYER_RULES` (the template is `templates/employer-rules.json`) with `{date, field, new}`
in `changes`.

### The cost choices

After the defaults, the cost choices one at a time, each with its cost line: `../../references/choices.md`.

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
- The person's own facts go into the profile, not the master record: name, contact, nationality, languages, birth
  date, address (`person.*`) and each job's true dates (`employment.<employer>-<start year>`: employer, role, start,
  end, location, source). Show them first, then save each with `profilelib.py set` after the person's OK. The
  master record keeps the CV's wording and dates.
- References: a referee goes into the profile as `contacts.referee-<first name>` (name, role, relation, email,
  phone, company, `agreed_on`), only with the person's word that the referee agreed (`agreed_on`: that day); never
  contact a referee. Never store ID numbers.

## 6. Where and how they will work

Cities, remote, hybrid, relocation; the pay floor (private); how interviews may be scheduled. Write each into
`preferences` as fact lines. The scripts read the places from `job-search.env`: `PLACES` (accepted cities and
countries) and `NOT_PLACES` (cities ruled out). Example: PLACES=Rome, Italy; NOT_PLACES=Turin. The pay figure of a
city goes into the private table once it is worked out (`career_view.py pay "<city>" --set "<figure>"`). The roles,
for the scripts' search: `ROLE_TERMS`, as role phrases that match whole words ("tech lead", not "lead", which also
passes "Lead Project Manager"), and `REMOTE_REGIONS`. Then ask once about the weekly usage report ("It holds no
name, contact, CV, pay or address; you read each one and send it yourself") and write `USAGE_SHARING=yes|no` in
`job-search.env`.

## 7. CV versions

One `CV_VERSIONS_DIR/<n> <Variant>.json` per kind of role (from `templates/cv-version-example.json`), each with its
cover-letter template. Build them with `build_cv.py` and check each PDF: two pages at most, nothing invented. Offer
to delete stale copies elsewhere (to the trash only, on their yes).

## 8. The dashboard

Create it without asking (RULES.md, "Dashboard") and put its link in `DASHBOARD_URL`.

Then the Questions page, without asking: publish `templates/questions/index.html` as its own artifact with the
capabilities `{"db": {"rules": [{"path": "questions", "read": "owner", "write": "owner"}, {"path": "answers", "read": "owner", "write": "owner"}, {"path": "status", "read": "owner", "write": "owner"}]}, "user": {}, "comments": {}}` (only the person reads or writes it, even when the page is shared: answers can be
health facts; `comments` lets its send button reach the main session), list its `answers` collection once to check the store answers,
and put its link in `QUESTIONS_PAGE`. Then add every question setup asked before the page existed and still open.

Then tell the person, in these words, what the two pages are and how to find them again; a new person has never
opened an artifact:
- "Your **dashboard**: <link>. What to do now, your interviews, logins, excluded employers and every application."
- "Your **Questions page**: <link>. What your applications need and your records don't hold: answer, then press
  Send my answers to Claude. Each page links to the other."
- "Both are private pages on claude.ai, only for you, pinned in your sidebar as cenk-jobs · Job applications and
  cenk-jobs · Questions for you. Or open them from the links, from Artifacts in the left sidebar
  (claude.ai/code/artifacts), or `/artifacts` in a terminal session."
Pin both when they are created (`pin: true` on the publish) when the person accepted the defaults; if they turned
that one down, leave them unpinned and say how to pin one later (the page's menu, Pin).

## 9. The schedule

With the defaults accepted, create the scheduled run with `/cenk-jobs:schedule` (weekdays at 19:00 local time).

## 10. The report and the main session

- The report, in short lines: what was set up (the main folder, the profile, the CV versions, the two pages with
  their links, the schedule), the choices made, and what waits on the person. Example: "Set up: main folder in
  Drive, 3 CV versions, both pages pinned, runs weekdays at 19:00. Waiting on you: sign in to LinkedIn in Chrome."
- Then the main session, fresh, so its context starts without setup's long reads: start a session in the main
  folder (`start_session`, title "Job search coordinator") with the brief "Run /cenk-jobs:coordinate for the first
  run: `searches.py sites --add`, one saved search per other site and query with its free email alert
  (references/saved-searches.md), then the first search." Tell the person in one line to go on there, with
  its link, and stop here. Without a session tool: they run `claude` in the main folder and type
  `/cenk-jobs:coordinate`.
- Job sites that need an account come out of that search: the person creates each account and leaves its profile
  empty, because Claude fills it when applying.
