# cenk-jobs

The **cenk-jobs** plugin (skills `setup`, `coordinate`, `search`, `plan`, `apply`, `prepare`, `cheat-sheet`, `schedule`, `write`), with its own one-plugin catalog
`cenk-jobs`. Generic code and instructions only. The public catalog `cenk` is the repository
`cenksimsek1988/claude-plugins`, which lists cenk-jobs (since its catalog 0.2.0, 6 Nov 2026).

## Owner

- Only a session opened in this repository with cenk-workbench loaded changes the plugin: the session titled
  "Development · cenk-jobs", started by "Coordinator · workbench", and the sessions it starts. Job-search sessions
  never edit here and never start a session here: their main session writes one-line lessons into
  `plugin-lessons.md` in the person's main folder and sends the new lines, with their line numbers, to
  "Coordinator · workbench", which passes the cenk-jobs group to "Development · cenk-jobs"; each is applied with
  `/cenk-workbench:teach`.
- Lessons come in two groups: the plugin's own, built here; and the general ones (true for any plugin), which
  belong to the workbench and are never built here. One that reaches this session directly is kept and named to
  "Coordinator · workbench" in one line.
- Every question for Cenk, a plan and a commit go-ahead included, goes to "Coordinator · workbench" in one message;
  his answer comes back quoted.
- The job-search folder's `.claude/settings.local.json` denies file edits on this repository (one `Edit(...)` rule, which also covers Write). It does not cover
  edits made through a shell command: `RULES.md` forbids those. The manifest has no workbench dependency: this
  plugin is public, the workbench private.
- A person's data never goes here: no real names, employers from a real search, CVs, records, pay, addresses or
  logins, not even in examples. Examples use made-up ones (Jane Doe, Acme).
- Develop by the workbench rules: skills, docs, CHANGELOG and the records the scripts write into the person's folder
  are fact lines with an example, never narrative or quoted chat. Example: `exclude, defence, 2026-11-06`, not a
  quote of what the person said.
- The one exception is `plugins/cenk-jobs/data/blacklist.json`: real employers with public, sourced
  findings per category, merged from usage reports with `employer.py merge`. It holds no person's data: never who
  checked an employer or why they looked at it. A flagged check always has its source link.
- Commit only when Cenk asks. Local git identity: Cenk Simsek <35446555+cenksimsek1988@users.noreply.github.com>.
  The pre-commit hook runs the workbench secret scan.

## Layout

- `.claude-plugin/marketplace.json`: the catalog `cenk-jobs`, for a clone and for invited people. Cenk's own install
  is `cenk-jobs@cenk-jobs` from this folder (6 Nov 2026): edits load at the next session, with no new version. Never
  install `cenk-jobs@cenk` beside it.
- `plugins/cenk-jobs/.claude-plugin/plugin.json`: the plugin manifest.
- `plugins/cenk-jobs/RULES.md`: the router every skill reads first, with the safety rules; `RULES/`: its parts, by
  audience; `skills/<name>/SKILL.md`: one job each; `agents/`: one short tool list and model per stage; `references/`: what an
  agent reads instead of the whole rules (`filling.md`, `sites/<site>.md`), and the parts a skill reads only on their
  trigger (example: `weekly.md`, the first run of the week); `hooks/`: the no-screenshot guard (`no_screenshot.py`).
- `plugins/cenk-jobs/scripts/` (Python; every path comes from the person's `job-search.env`),
  `workflows/screen-and-prepare.js`, `templates/` (including `employer-rules.json`, the default rules),
  `data/blacklist.json` (the shared blacklist).
- Usage reports from users arrive by email at the developer's address in `scripts/usage.py`; merge their employers
  with `python -I plugins/cenk-jobs/scripts/employer.py merge <report.json> ...`, and Cenk's own findings with
  `employer.py merge --from-checks`, both run here, never from a job-search session.
- `release.py`: builds `dist/cenk-jobs.plugin` from HEAD; `dist/` is git-ignored.
- `CHANGELOG.md`.

## Every change

- An entry in `CHANGELOG.md`.
- A new version in `plugins/cenk-jobs/.claude-plugin/plugin.json` only. The catalog entries (here and in `cenk`)
  carry none: Claude Code reads `plugin.json` first. A GitHub install updates only when the version changes.

## Checks

- `claude plugin validate .`
- `claude plugin validate plugins/cenk-jobs`
- `python -I -m py_compile plugins/cenk-jobs/scripts/*.py`
- `sh tests/run.sh` (a throwaway folder; never touches real records). It takes about 15 to 25 minutes: run it in the
  background, on a copy (`cp -r tests plugins <scratch>/t`, then `sh <scratch>/t/tests/run.sh`) when edits go on
  meanwhile, since `sh` reads `run.sh` as it runs.
- With the workbench: `sh <workbench>/scripts/check-plugin.sh --base main plugins/cenk-jobs` (the plugin folder: the
  repository root has no plugin.json). From workbench 0.23.0 its personal-data check reads the person's profile for
  the values it looks for; it prints none.
- The profile is cenk-base's (`profilelib.py` loads its `lib/profile.py` from `CENK_BASE`). `tests/run.sh` finds
  cenk-base from `CENK_BASE_SRC`, else `CENK_BASE`, else `cenk-base` beside the main checkout, and keeps `CENK_HOME`
  inside its throwaway folder. A test that unsets `CENK_HOME` passes made-up `roots` and `claude_dir`: otherwise
  `drive_roots()` looks for the real `<letter>:\My Drive\cenk\profile.json`. A session whose `CENK_BASE` is an
  installed cenk-base older than the source sets `CENK_BASE_SRC` to the cenk-base checkout: the coordinator-rules
  test fails otherwise.
- `workflows/screen-and-prepare.js` parses with `node --check` only as a copy wrapped in `(async () => { ... })()`:
  it has a top-level `return`.
- A test on a copy of a job-search folder: a short path; a deep one breaks `shutil.copytree` on Windows path length.
- `tests/run.sh` covers `export_dashboard.py`, `sessions.py`, `searches.py` and `track.py todo` on a made-up folder,
  and parses both page scripts with `node --check` on the extracted `<script>` (without node: one line, skipped).
- `export_dashboard.py --check` writes nothing: safe on a copy of a real folder, and on the real one.
- A fixture with a non-ASCII character (the middle dot of "Workday · Acme") is written by a Python heredoc with the
  escape `\u00b7`, never passed in argv: Git Bash on Windows mangles it. A script that prints one calls
  `sys.stdout.reconfigure(errors="replace")` first: a cp1252 console raises otherwise.
- An edit that holds a backslash (a regex, `\n` in a test) is made with the Edit tool or a script file, never a
  Python heredoc in the Bash tool: the escape can reach the file as a control character (seen: `\b` as 0x08).
- A `\uXXXX` escape is the exception: the Edit and Write tools write the character itself (seen: a regex range of
  combining accents). Write it with a script that builds the backslash from `chr(92)`, then check the line with
  `ascii()`.
- The page: `python -m http.server <port>` on a made-up export with a stub of the Dashboard runtime, read as text;
  the built-in browser shows a `file://` page as a static snapshot. Stop the server afterwards.
- The Dashboard runtime gives the page a row's list field (`apps`, `also`) as JSON text: page code reads a list with
  `window.jaIds`. The live page's faults are in its store's `data/users/me/check` and `runs` (ArtifactData, read
  only), written only while something fails.
- A dev version is checked on the live pages by a sub-session the Job search coordinator starts, never by the
  coordinator itself: it publishes the worktree's templates, exports with the worktree's scripts and checks every
  tab, chip and count against its records. This session sends it no values. Example: 0.42.0, 19 Nov 2026, three
  rounds.

## Release

- Commit and push: GitHub installs (`cenk-jobs@cenk`, or `cenk-jobs@cenk-jobs` added from this repository's https
  address) pick up the new version.
- `python -I release.py` builds `dist/cenk-jobs.plugin` from HEAD, for an upload in the Claude desktop app.
