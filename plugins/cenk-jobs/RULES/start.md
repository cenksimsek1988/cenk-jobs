# cenk-jobs rules: start

A part of `RULES.md`. Read when a session's working folder is not the main folder.

## First: work in the main folder

A skill cannot choose the folder a session starts in, so a session started anywhere else moves there first.

1. Find the main folder: the folder of `$JOB_SEARCH_ENV`, else the one in memory, else ask the person once.
2. If this session's working folder is not the main folder, move the session there with the app's change-directory
   tool, wherever it started (another project, a git worktree, a plain folder). The person approves the folder.
   - Write nothing in the old folder.
   - The move takes effect when the turn ends: say "Moved to the main folder; send any message to go on." and end
     the turn. On the next turn, read the main folder's `CLAUDE.md` with the Read tool, then go on.
3. Only if the move is refused or there is no change-directory tool:
   - With a session tool (`start_session`): start a new session in the main folder (title "Job search coordinator"
     for coordinate), pass the person's request on as its brief, say so in one line, and stop here.
   - Without one (Claude Code in a terminal): tell the person to open a terminal in the main folder and run
     `claude` there, and stop here.
