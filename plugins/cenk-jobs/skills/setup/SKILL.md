---
name: setup
description: "First run of the job search, once: checks programs and logins, creates the main folder, reads the person's CVs into one master record, builds CV versions, creates and pins two pages. Use for 'set up my job search', 'start using cenk-jobs', 'first run', 'iş aramamı kur'. Not for daily work."
---

# Setup: the first run

Read `../../RULES.md` first (honesty, consents, never an ID, password, code or CAPTCHA). Run these steps in order and
ask before moving on. Each step is safe to run again: it skips what is already there and says so.

## 1. Programs

- Check each program:

  | Program | What it is for | Check |
  |---|---|---|
  | Python 3.10+ | runs every script | `python --version` (Windows also `py --version`) |
  | Google Chrome | prints CVs and letters to PDF; Claude in Chrome applies in it | `check_setup.py` |
  | Google Drive for desktop | keeps the main folder in Drive and on the computer | `check_setup.py` |
  | pypdf | reads the person's PDFs as text (old CVs, documents) and checks each CV built | `python -I -c "import pypdf"` |
  | Poppler (`pdftoppm`) | lets Claude see PDF pages as images (a scanned diploma, a CV's layout) | `pdftoppm -v` |

- Ask once, listing only the missing ones with what each is for: "I'll install these now, unless you say no to any."
  Install every one the person does not refuse, from the official source. Example: "pypdf and Poppler are missing:
  pypdf reads your PDFs, Poppler shows me their pages. I'll install both now, unless you say no." Say that an
  install accepts the program's own licence (Poppler: GPL; Chrome and Drive: Google's terms).

  | System | Python | Chrome | Drive | pypdf | Poppler |
  |---|---|---|---|---|---|
  | Windows | `winget install -e --id Python.Python.3.12` | `winget install -e --id Google.Chrome` | `winget install -e --id Google.GoogleDrive` | `python -I -m pip install pypdf` | `winget install -e --id oschwartz10612.Poppler` |
  | Mac | `brew install python` | `brew install --cask google-chrome` | `brew install --cask google-drive` | `python3 -I -m pip install pypdf` | `brew install poppler` |
  | Linux | the distribution's `python3` | google.com/chrome | none: keep the main folder backed up | `python3 -I -m pip install pypdf` (refused as externally managed: `sudo apt install python3-pypdf`) | `sudo apt install poppler-utils` |

- pypdf goes into Python's own folder (`-I` above): the scripts run with `python -I`, which skips per-user packages.
- A command that needs `sudo` or an administrator: the person runs it; give them the line.
- A program installed with winget is on the PATH in sessions started after the install: say so, then run
  `check_setup.py` again.
- The person signs in to Google Drive and Chrome themselves. The Claude in Chrome extension: open its Chrome Web
  Store page for them; they click "Add to Chrome", pin it and sign in with their Claude account. Read each page in
  the browser with `find`, `read_page` or `get_page_text`; never a screenshot.

## 2. Logins and connectors

The health-check calls in RULES/run.md, and the person's LinkedIn signed in in Chrome. Help with each missing one, step
by step.

## 3. The main folder

- Ask where it should be, then `init_career_folder.py "<main folder>" "<Full Name>"`.
- Fill `CONTACT_LINE`, `LETTER_TITLE`, the accounts and `PHOTO` in `job-search.env` with the person.
- On their OK, add `JOB_SEARCH_ENV=<main folder>/job-search.env` to the `env` block of `~/.claude/settings.json`;
  it takes effect in sessions started after the change.
- The profile (their own facts, shared with the other cenk-* plugins): `profilelib.py path`. None yet: ask where to
  create it, suggesting the place `check_setup.py` names (`claude/profile.json` in their Google Drive's "My Drive"),
  then `profilelib.py create <path>`. Ask how they want to be referred to, and save it: `set person.pronouns`.

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
  is asked once.
- Emails and messages are drafts; you send them.
- Applications are sent on their own when every answer comes from your records (`APPLY_MODE=auto`); you hear what
  was sent after each run. Say "ask me before each application" for `APPLY_MODE=review`. Only what Claude cannot
  do waits for you in Do now: CAPTCHAs, passwords, sign-ups, emailed codes, ID numbers, essays, pay below your
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
`preferences` as fact lines. Then ask once about the weekly usage report ("It holds no name, contact, CV, pay or
address; you read each one and send it yourself") and write `USAGE_SHARING=yes|no` in `job-search.env`.

## 7. CV versions

One `CV_VERSIONS_DIR/<n> <Variant>.json` per kind of role (from `templates/cv-version-example.json`), each with its
cover-letter template. Build them with `build_cv.py` and check each PDF: two pages at most, nothing invented. Offer
to delete stale copies elsewhere (to the trash only, on their yes).

## 8. The dashboard

Create it without asking (RULES.md, "Dashboard") and put its link in `DASHBOARD_URL`.

Then the Questions page, without asking: publish `templates/questions/index.html` as its own artifact with the
capabilities `{"db": {"rules": [{"path": "questions", "read": "owner", "write": "owner"}, {"path": "answers", "read": "owner", "write": "owner"}, {"path": "status", "read": "owner", "write": "owner"}]}, "user": {}, "comments": {}}` (only the person reads or writes it, even when the page is shared: answers can be
health facts; `comments` lets its send button reach the main session), list its `answers` collection once to check the store answers,
and put its link in `QUESTIONS_PAGE`.

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

## 9. The main session

Title this session "Job search coordinator" (the app's session-title tool) and say: "This is your main job-search
session. Ask here for anything: I start one session per job (applying, interview prep, essays) and record what each
reports. Keep job-search work out of other sessions." From here on it runs `cenk-jobs:coordinate`.

## 10. The schedule and the first search

With the defaults accepted, create the scheduled run with `/cenk-jobs:schedule` (weekdays at 19:00 local time), then run the first
search now with `/cenk-jobs:search`: it saves one search per site and query and offers the sites' free email alerts
(`search`, "Saved searches"), so later runs read only what is new. Job sites that need an account come out of that search: the person creates each
account and leaves its profile empty, because Claude fills it when applying.
