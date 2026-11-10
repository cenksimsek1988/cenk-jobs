# cenk-jobs rules: urgent

A part of `RULES.md`. Read when a step only the person can do expires.

## Urgent steps

A step only the person can do that expires gets one notification at once (the session's notification tool: the
desktop, and the phone when Remote Control is on) and an Urgent row at the top of Do now until it is done.
- Urgent: a code sent by email or SMS; a CAPTCHA or Submit on a form already filled in; a sign-in page waiting; a
  Submit the permission check left for the person's yes; a test, task or deadline due within 24 hours.
- The message, under 200 characters, starts with where it can be done: "From your phone:" (an answer on the
  Questions page, a yes in a session through Remote Control) or "At your PC:" (anything typed into the Chrome form:
  a code, a CAPTCHA, a sign-in). Then the company, what to do and how long it stays valid. Example: "At your PC:
  Acme's form is filled; say I'm at my PC and Claude presses Submit, then type the emailed code."
- A code is started only while the person is active or at the PC: a form that sends a one-time code on Submit is
  filled, and Submit waits until the person wrote in any job-search session in the last 15 minutes or says they are
  at the PC. Then Submit at once and pass the code request on, so the code arrives while they are there. Example: a
  Greenhouse form that emails a security code after Submit.
- "I'm at my PC": the coordinator lists every step waiting at the PC and has each session go on, one at a time, so
  the person clears them in one sitting.
- One notification per step, from the session that hit it (a sub-session sends its own; the coordinator does not
  repeat it). Never for what can wait, never twice for the same step.
- The Urgent row: a `todo` on the job with `"kind": "urgent"` and `"where": "pc"` or `"phone"`; the coordinator
  removes it once the step is done or expired. A step due within 24 hours is Urgent on its own (`export_dashboard.py`).
- The daily run: deadlines today or tomorrow get one notification at the end of the run, all in one message.
