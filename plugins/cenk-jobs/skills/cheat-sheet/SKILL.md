---
name: cheat-sheet
description: "Show a hiring step's keyword cheat sheet as one page beside the call: no scrolling, the call link on top, sized for its spot on the screen. Use for 'open my cheat sheet', 'cheat sheet for the interview', 'kopya kağıdımı aç'. Not the prep itself: /cenk-jobs:prepare writes it."
---

# Cheat sheet: one page for the call

Read `../../RULES.md` first. The page is built from the step's `cheat-sheet.md`, which `/cenk-jobs:prepare` writes:
keyword lines only, never scripted sentences. This skill changes no record and sends nothing. It reads no web page:
the page is a local file the script writes; to check it once open, `get_page_text`, never a screenshot.

## Steps

1. The time first: check the step's date and time against now and name the step. Example: "Now 13:40. Acme technical
   interview, today 14:00." Several steps today: ask which one.
2. No `cheat-sheet.md` in the step's folder, or one older than the posting or the records it was written from: write
   or correct it first (`prepare`, "Prep notes").
3. Where the page goes on the screen: read `CHEAT_SHEET_SPOT` in `job-search.env`. Not set: ask once. "Where will the
   page sit: the top or bottom half, the left or right side, or a corner?" The answer is kept there and reused; the
   person changes it by saying so.
4. Build and open it: `cheat_sheet.py <job id> [step=<n>] [spot=<spot>] --open`. It writes `cheat-sheet-wide.html`
   in the step's folder and opens it in a new window of the person's Chrome. Example: `cheat_sheet.py J1 spot=corner
   --open`. Chrome not found: give the file's path as text, marked "open in Chrome".
5. Say in one line what is on the page and that they move the window to the spot. The page shrinks its text until it
   fits and shows the size on top; "still too long" there: shorten `cheat-sheet.md` with the person and build again.

## The page

- Columns by the spot: top or bottom half 3, left or right side 1, a corner 2.
- The top line: the step, the employer, the date, and the call link from the step's `link` in `PIPELINE`.
- A heading in `cheat-sheet.md` starts a block; every other line is one keyword line. Example: `## Numbers`, then
  `- 12 engineers, 3 teams`.
- Pay figures never go on the page (RULES.md, "Honesty and what Claude never does").
