# cenk-jobs rules: urgent

A part of `RULES.md`. Read when a step only the person can do expires.

## Urgent steps

A step only the person can do that expires gets one notification at once (the session's notification tool: the
desktop, and the phone when Remote Control is on) and an Urgent row at the top of Do now until it is done. A step
due within 24 hours has its own rule, the last one below.
- Urgent: a code sent by email or SMS; a CAPTCHA or Submit on a form already filled in; a sign-in page waiting; a
  Submit the permission check left for the person's yes.
- The message, under 200 characters, starts with where it can be done: "From your phone:" (an answer on the
  Questions page, a yes in a session through Remote Control) or "At your PC:" (anything typed into the Chrome form:
  a code, a CAPTCHA, a sign-in). Then the company, what to do and how long it stays valid. Example: "At your PC:
  Acme's form is filled; say I'm at my PC and Claude presses Submit, then type the emailed code."
- A form that sends a one-time code on Submit waits until the person is active or at the PC:
  `references/filling.md`. "I'm at my PC": /cenk-jobs:coordinate.
- One notification per step, from the session that hit it (a sub-session sends its own; the coordinator does not
  repeat it). Never for what can wait, never twice for the same step.
- The Urgent row: `track.py todo <id> add urgent "<what to do>" where=pc` (or `where=phone`); the coordinator
  removes it (`track.py todo <id> done kind=urgent`) once the step is done or expired.
- A step due within 24 hours (a test, a task, a deadline) is Urgent on its own (`export_dashboard.py`) until it has
  `"done"` in `PIPELINE`; a due date that passed reads Past due, never Urgent. In a run, the coordinator sends one
  notification for all such steps at its end, and the session that found one sends none; outside a run, the session
  that finds it notifies at once. Example: a take-home due tomorrow at 10:00, found by the 19:00 run's prep
  session: in the coordinator's last notification of the run.
