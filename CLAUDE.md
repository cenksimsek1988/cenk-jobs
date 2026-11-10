# cenk-jobs

The **cenk-jobs** plugin (skills `setup`, `coordinate`, `search`, `plan`, `apply`, `prepare`, `schedule`), with its own one-plugin catalog
`cenk-jobs`. Generic code and instructions only. The public catalog `cenk` is the repository
`cenksimsek1988/claude-plugins`, which lists cenk-jobs (since its catalog 0.2.0, 6 Nov 2026).

## Owner

- Only a session opened in this repository with cenk-workbench loaded changes the plugin. Job-search sessions never
  edit here: they write one-line lessons into `plugin-lessons.md` in the person's main folder, and a session here
  applies each with `/cenk-workbench:teach`.
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
  audience; `skills/<name>/SKILL.md`: one job each; `agents/`: one short tool list and model per stage.
- `plugins/cenk-jobs/scripts/` (Python; every path comes from the person's `job-search.env`),
  `workflows/screen-and-prepare.js`, `templates/` (including `employer-rules.json`, the default rules),
  `data/blacklist.json` (the shared blacklist).
- Usage reports from users arrive by email at the developer's address in `scripts/usage.py`; merge their employers
  with `python -I plugins/cenk-jobs/scripts/employer.py merge <report.json> ...`.
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

## Release

- Commit and push: GitHub installs (`cenk-jobs@cenk`, or `cenk-jobs@cenk-jobs` added from this repository's https
  address) pick up the new version.
- `python -I release.py` builds `dist/cenk-jobs.plugin` from HEAD, for an upload in the Claude desktop app.
