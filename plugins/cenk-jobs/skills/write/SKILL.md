---
name: write
description: "Write one free text for an application with the person: the company and role, their matching background and gaps, then a draft in their voice, revised together. Use for 'write this essay with me', 'help me answer this question', 'let's write my motivation text', 'birlikte yazalım'. Fills no form."
---

# Write: one free text, with the person

Read `../../RULES.md` first: "Honesty and what Claude never does" holds the rules on drafts and AI that this skill
follows. One text per run: an essay or a motivation answer on a form, or a letter the person writes themselves. It
runs in its own session, on the main session's model (/cenk-jobs:coordinate, "Essays round"). It fills no form and
sends nothing: the apply session fills the approved text, by `ASK_FIRST`.
The person asked for this draft, so it is written whatever `draft_answers` says; that setting decides only drafts
nobody asked for.

## Steps

1. The job and the question: `track.py show <id>`, the question's exact words and its limit. Example: "Acme,
   Backend Engineer: 'Why Acme?' (at most 1,000 characters)". The posting still open (`fetch_jd.py <link>`); closed:
   say so and stop.
2. The employer's AI rule, in one line, before anything else: quoted from the posting or the form, or "none found".
   The person decides; under a rule against AI the job waits for them. Example: "The form says 'answers must be your
   own work, without AI tools': write it yourself, or go on?"
3. The company and the role in at most 6 lines: what it makes, its size, remote work and culture, the role's work,
   the hiring steps. Sources: the posting, the employer's records (`employer.py check "<name>"`) and at most 3 web
   pages, each line with its source. Employee reviews only after the person's yes, looked up once (RULES.md,
   "Employer rules").
4. The person's related background (`career_view.py facts`): matching skills, experience, education and side
   activities, one line each in the posting's words; then the gaps against its must-haves, plainly. Example: "Gap:
   no Kubernetes in production (a must-have); Docker Compose at Acme".
5. "Why this role for you?", asked after steps 3 and 4: the person's own reasons are the strongest part of the text,
   and at first they may not know the company.
6. A question that asks for examples (example: "something digital you made"): what it looks for, in the posting's
   words; a fit rating for each item the person names (strong, fair, weak); leave out political, illegal and
   childhood items, and ones they only took part in.
7. A starting draft in their voice: calm and experienced, no essay words, no praise of the employer's product,
   within the limit. A gap goes mid-paragraph, never last; the text ends on a strength. Example: "I led two
   migrations like yours", not "I am passionate about your innovative platform". A person who writes it themselves
   gets this feedback on their text instead of a draft.
8. Revise with them: after the first full draft, only the changed sentences. Their wording wins; in text they wrote,
   fix only English and grammar. Before each round of approvals, check again that the posting is open.

## Facts

- Every fact comes from `career_view.py facts` or from what the person says in this session. A claim no source
  supports stays out. Example: "they don't track online hours" becomes "fully remote since the start" when only
  that is sourced.
- A number the person recalls with no record behind it never goes into the text (RULES.md).
- Never read the interview study notes here (RULES.md).
- A new fact about the person goes into the profile at once (`profilelib.py set`, RULES.md "Keep learning about the
  person"); any other new fact is a fact line in the handoff, for the master record.

## End

- An approved answer: its text alone in `handoffs/<short name>.answer.md` (UTF-8); the handoff names the job, the
  question and that file. The coordinator records it with `questions.py answer <question id> --file <that file>`
  (after `questions.py add job "<question>" job=<id>` when the Questions page never asked it).
- An approved letter: its body in `LETTER_BODIES_DIR` as `<job id>.txt` (paragraphs split by a blank line, from the
  greeting to the sign-off line); its PDF is built on the day it is sent (`make_letter_pdf.py`).
- Then the handoff (/cenk-jobs:coordinate, "The handoff every sub-session ends with"), and say what was done:
  the text approved or still open, and where it is.
