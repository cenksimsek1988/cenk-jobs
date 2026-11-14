# cenk-jobs: your job search with Claude

**For anyone looking for a job** who wants Claude to do the legwork: find and screen job postings, write CVs and
cover letters from your own facts, fill and send application forms in your own Chrome whenever your records answer every question (or after your go-ahead, in review mode), track
every application, put interviews and deadlines in Google Calendar, and prepare you for each interview. It works for
any field: developers, architects, designers, engineers.

A Claude Code plugin by Cenk Simsek, part of his plugin catalog `cenk`
([claude-plugins](https://github.com/cenksimsek1988/claude-plugins); every plugin there is named `cenk-<purpose>` and
installs on its own). Skills:

| Skill | Use it for |
|---|---|
| `cenk-jobs:setup` | the first run, once: programs, logins, your main folder, the defaults, your documents, CV versions, the dashboard and your main session |
| `cenk-jobs:coordinate` | your main session, every day: "run my job search now", "open a session for this job" |
| `cenk-jobs:search` | finding and screening postings only: "find me jobs" |
| `cenk-jobs:plan` | putting the applications in order, with the CV and letter for each: "what should I apply to today?" |
| `cenk-jobs:apply` | filling and sending applications, on their own or after your go-ahead (`APPLY_MODE`): "apply to these jobs" |
| `cenk-jobs:prepare` | interviews and hiring steps: "prepare my interview", "let's practise" |
| `cenk-jobs:cheat-sheet` | your keyword cheat sheet as one page beside a call: "open my cheat sheet" |
| `cenk-jobs:schedule` | the scheduled run: "run it on weekdays at 19:00", "run it every day", "stop the daily run" |

It also understands other languages, for example "iş arıyorum", "cerco lavoro", "Jobsuche", "buscar trabajo".

This repository holds **only the generic skills and their scripts**. Your own data (CVs, master record,
applications) never comes here: it lives in a folder in your own Google Drive, which the plugin creates on its first
run. Your own facts (name, contact, birth date, address, private answers, referees, the true dates of each job) live
in one **profile**, `claude/profile.json` in your Google Drive's "My Drive" folder, shared with the other cenk-*
plugins; Claude asks where to create it if there is none. It is a plain JSON file: Google stores it, and whoever
can open your Drive can read it.

## What you need

- **Claude Code**: the Claude desktop app (Code tab) or the `claude` terminal, on a paid Claude plan.
- **Google Chrome** with the **Claude in Chrome** extension (Chrome Web Store: "Claude"), signed in with the same
  Claude account. Claude fills job applications in your Chrome, with your own sign-ins.
- **Python 3.10 or newer**, **Google Drive for desktop** (recommended, so your job-search folder is in Drive and on
  your computer), **pypdf** (reads your PDFs) and **Poppler** (shows Claude PDF pages). You don't have to install
  these first: on the first run Claude lists what is missing and installs it from the official source, unless you
  say no.
- Connectors in Claude: **Gmail** and **Google Calendar** (claude.ai > Settings > Connectors).
- The plugin: this GitHub repository, or its file **cenk-jobs.plugin** for an upload in the Claude desktop app.

## Install

**Way 1, from the `cenk` catalog**, Cenk Simsek's plugins. In the Claude desktop app,
open the **Code** tab and type:

```
/plugin marketplace add https://github.com/cenksimsek1988/claude-plugins.git
/plugin install cenk-jobs@cenk
```

**Way 2, from this repository** (its own catalog, `cenk-jobs`), or from a clone you change yourself. Type:

```
/plugin marketplace add https://github.com/cenksimsek1988/cenk-jobs.git
/plugin install cenk-jobs@cenk-jobs
```

- For a clone, give its folder instead of the address: your edits then load at the next session, with no new version.

**Way 3, from the single file**: drop **cenk-jobs.plugin** into a chat in the Claude desktop app and press install on
its preview. A new version is a new file to drop in again.

Write the addresses with `https://`: the short form `owner/name` clones over SSH when a GitHub SSH key is found, and
an install from `/plugin` does not fall back to HTTPS. Install one way only: to switch, first uninstall the other copy,
for example `/plugin uninstall cenk-jobs@cenk-jobs`.

Then start a new session and say **"set up my job search"** (or type `/cenk-jobs:setup`). That session becomes your main session: ask there for anything from then on. On the first run Claude:

1. checks your logins and connectors and helps you fix what is missing (Claude in Chrome too);
2. asks where your job-search folder should be and creates it, with a `job-search.env` file that names every
   folder and file;
3. asks for your CVs, old cover letters, LinkedIn profile, diplomas, transcripts, certificates, references and
   anything your field needs (a portfolio, a project catalogue, publications). Just say where they are ("in Canva",
   "in my Drive under Work", "take it from LinkedIn", "somewhere on my laptop") and Claude fetches them, or put
   everything as it is in the **documents-inbox** folder and tell Claude when you've finished. Claude sorts the files,
   reads them into your master record, helps you find skills you never wrote down, and offers to delete old copies;
4. builds your CV versions and asks which job sites need an account (you create the accounts; Claude never types
   passwords);
5. creates your two private pages on claude.ai and gives you their links:
   - the **dashboard**: what you can do now (sign-ins, clicks, tasks such as online tests or AI interviews), your
     open sessions with Claude in the order to answer them, your interviews and deadlines (live from Google
     Calendar, where job-search events get their own color), which logins work and which need you, the employers
     you excluded and why, the hiring steps ahead of you and every application;
   - the **Questions page**: what your applications need and your records don't hold. Answer there, press **Send my
     answers to Claude**, and a note under each question shows what happened. Each is asked once.

   They are named **cenk-jobs · Job applications** and **cenk-jobs · Questions for you** and pinned to your
   claude.ai sidebar (one of the defaults setup offers). Find them again any time there, under **Artifacts**
   (claude.ai/code/artifacts), or with `/artifacts` in a terminal session; each page links to the other, and every
   daily report ends with both links.

Every later session starts with the same health check. Say "check my applications", "apply to new jobs" or
"prepare my interview with ...".

**Daily run:** with your OK, Claude sets up a scheduled task that runs your job search on weekdays at **19:00 your
local time** (emails, calendar, a fresh search, applications sent). Ask for another time whenever
you like.

For bigger days, say **"start the job search coordinator"** (or `/cenk-jobs:coordinate`) in a session opened in your
job-search folder. That session keeps your records and dashboard and starts one short session per piece of work (one
interview to prepare, one search sweep) and one subagent per application; each reports back to it, and it asks you before
anything is sent.

## What Claude will and won't do

- It applies only with true facts from your record, and asks before anything it doesn't know.
- It never creates accounts, types passwords, verification codes or ID numbers, solves CAPTCHAs, or sends an email
  or message without your go-ahead. Applications go out on their own (`APPLY_MODE=auto`) unless you choose review mode.
- It ticks only the data-processing consent a form needs; optional consents (talent pools, marketing) stay off.
- Your pay expectations stay private: never in a CV, letter or the dashboard.
- Your birth date, references, criminal record and relatives at the company: a form that asks for one waits for
  you, unless you let forms answer it from your profile. ID numbers never.

## Settings in your profile

Under `settings.cenk-jobs` in your profile (or `settings.common`, for every cenk-* plugin). Claude changes a setting
only after your yes to its key and value, also one you asked for:

| Setting | Default | Example |
|---|---|---|
| `form_facts` | none: each waits for you | `["birth_date"]`: forms answer your birth date from your profile. Allowed: `birth_date`, `address`, `references`, `criminal_record`, `relatives`, `health` |
| `draft_answers` | `no`: open free-text answers are yours to write | `yes`: Claude writes each open free-text answer from your records and fills it only after your approval |

In `job-search.env`, `CHROME_PROFILE` names the Chrome profile your job search uses, when you have more than one.

## Employer rules and the shared blacklist

Before anything is prepared, each employer is checked in eight categories: ties to the state of Israel, defence
industry, animal cruelty, climate and environmental harm, sexism, human rights, working conditions and sanctions. A
category counts only with a crime-level problem shown by credible news, a ruling, a fine, a sanctions listing or an
official list, with its source. Each finding is direct or indirect by the plugin's levels for its category (one a
detailed search cannot settle is undecided: you are asked, and nothing waits on it); your own
rules for a category (its notes) get a second check on each finding there.

- The default for every category is **discuss**: Claude shows you what it found and you decide, allow or exclude.
  You can set any category to **exclude** or **allow**, and say how to treat indirect ties (an investor's other
  holdings, partners, customers): discuss, warn only, or allow. Your settings live in `employer-rules.json` in your folder.
- The plugin ships a **shared blacklist** (`plugins/cenk-jobs/data/blacklist.json`): employers with
  sourced findings per category, checked by Claude before each new screen. It grows from users' usage reports.
  When a new version changes it, the employers you never gave an opinion on follow it; for each one you gave an
  opinion on (a decision, or a finding you stated), Claude asks you on the Questions page whether to change your
  setting.
- The same list keeps what **employee reviews** say about an employer (rating, number of reviews, repeated complaints,
  source, date), so Claude looks it up once. You see it in the application's `company.md`; it never decides anything.

## Usage reports (only with your yes)

On the first run Claude asks whether it may prepare a weekly usage report for the plugin's developer. It holds no
name, contact, CV, pay or address. It has:
- how many applications you sent each week, the hiring steps they reached and the first "yes" answers;
- which job sites and steps worked;
- the employers checked, with each category's finding and what employee reviews say (rating, number of reviews,
  complaint topics, source).

Claude shows you each report and puts it in a Gmail draft to `cenk.plugins.reports@gmail.com`, an address only for
these reports; you send it yourself. Privacy: a report lists, per application, the employer, the role, the dates and
the hiring steps reached, and the findings and employee reviews of the employers checked; never your name, contact
details, CV, letters, pay or address. Say "no" and nothing is prepared; you can change your answer at any time.

## Updates

Way 1: type `/plugin marketplace update cenk`, then `/reload-plugins` (or start a new session).
Way 2: the same with `cenk-jobs`; an install from a clone's folder needs no update.
Way 3: drop the newer **cenk-jobs.plugin** in again.

Upgrading from this repository's old catalog `cenk` (before 0.4.1) or a Google Drive install (marketplace folder
`cenk-jobs-plugin`): `/plugin marketplace remove cenk`, then install one way above. From the first version (plugin `job-search`, marketplace `cenk-job-search`):
`/plugin uninstall job-search@cenk-job-search` and `/plugin marketplace remove cenk-job-search` first.

## Layout

```
.claude-plugin/marketplace.json          this repository's own catalog "cenk-jobs"
plugins/cenk-jobs/.claude-plugin/plugin.json
plugins/cenk-jobs/RULES.md               the router every skill reads first, with the safety rules
plugins/cenk-jobs/RULES/                 the parts of the rules, by audience
plugins/cenk-jobs/agents/                one short tool list and model per workflow stage
plugins/cenk-jobs/skills/<name>/SKILL.md setup, coordinate, search, plan, apply, prepare, cheat-sheet, schedule
plugins/cenk-jobs/scripts/               check_setup, init_career_folder, build_cv, make_letter_pdf, track,
                                         logins, build_app_folders, fetch_jd, export_dashboard, jsenv (reads
                                         job-search.env), trackerlib (shared tracker reading), employer and
                                         employerlib (employer rules and checks), usage (usage log and report),
                                         profilelib (your profile), move_to_profile (moves your facts there once)
plugins/cenk-jobs/workflows/             screen-and-prepare.js: screens new employers under your own employer
                                         rules (one check per category) and prepares the cleared jobs
plugins/cenk-jobs/templates/             job-search.env.template, employer-rules.json (the default rules), an
                                         example CV version, an example tracker-settings file, the withdrawal
                                         email, the dashboard page and its store documents
plugins/cenk-jobs/data/blacklist.json    the shared blacklist: employers with sourced findings per category
```

The scripts are the same for everyone: every folder, file and setting comes from your `job-search.env`. They also
read a tracker kept before the plugin (`{companies: [{name, jobs}]}`) as well as the plugin's own (`{jobs: [...]}`).
Optional keys for such older records: `TRACKER_SETTINGS` (CV nicknames in notes, older screening runs to merge),
`REDACT_FILE` (private text kept out of the applications folders), `SENT_CVS_DIR` and `SENT_CVS_BEFORE_DIRS` (CVs
sent before the current ones). `build_app_folders.py` never deletes anything you or Claude wrote: when a job moves on,
its files move with it.

```
Main commands (S = this skill's scripts folder, run from your job-search folder or with --env <job-search.env>):
  python -I S/check_setup.py                         health check (read-only)
  python -I S/track.py set <id> <status> "<note>" [cv=<path> letter=<path>]
  python -I S/track.py show|brief|list|summary ...   read the tracker
  python -I S/build_app_folders.py                   rebuild the applications folders
  python -I S/fetch_jd.py <id> [...]                 save the full posting as job-description.md
  python -I S/make_letter_pdf.py --company .. --role .. --body .. --variant "<CV variant>"
  python -I S/build_cv.py [--no-photo]               build the CV PDFs
  python -I S/export_dashboard.py <out dir>          the dashboard's files, then what disagrees with the records
  python -I S/export_dashboard.py --check            only those "check:" lines; writes nothing
  python -I S/sessions.py show                       your open sessions, in the order to answer them
  python -I S/searches.py due                        the saved searches due today
  python -I S/track.py sync <journal.jsonl> [...]    merge a screen-and-prepare run into the tracker
  python -I S/employer.py check "<name>" [...]       what is known about an employer, and the verdict by your rules
  python -I S/employer.py decide "<name>" <exclude|allow> [<category>]
  python -I S/usage.py log <step> <ok|failed|stopped> ["<note>"]
  python -I S/usage.py due | report | mark-drafted   the weekly usage report (only with USAGE_SHARING=yes)
  python -I S/usage.py stats                         jobs turned down by your employer rules (for you; sends nothing)
  python -I S/profilelib.py path | get [<plugin>] <key> | set <key> <json|-> [--old <json>] [--yes] | erase <key> [--yes] | create <path>
  python -I S/move_to_profile.py [--apply [--confirm <key>] | --remove-old]   once: your facts into the profile
For the developer: python -I S/employer.py merge <report.json> [...]   users' reports into data/blacklist.json
```

## Licence

MIT, Cenk Simsek, 2026: see [LICENSE](LICENSE).
