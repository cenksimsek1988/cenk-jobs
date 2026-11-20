---
name: cheat-sheet
description: "Show a hiring step's keyword sheet as one page beside the call: no scrolling, the call link on top, on the screen the call is not on. Use for 'open my cheat sheet', 'open the keyword sheet', 'cheat sheet for the interview', 'kopya kağıdımı aç'. Not the prep itself: /cenk-jobs:prepare writes it."
---

# Cheat sheet: one page for the call

Read `../../RULES.md` first. A step has two sheets, both written by `/cenk-jobs:prepare`: `cheat-sheet.md`, the study
sheet read before the call, and `keywords.md`, the keyword sheet for the call (a few words per line). The page is
built from `keywords.md`. This skill changes no record and sends nothing. It reads no web page: the page is a local
file the script writes; to check it once open, `get_page_text`, never a screenshot.

## Steps

The page opens in the same turn as the request, even mid-call: no link to click, no question first. Questions come
after it is open.

1. The time first: check the step's date and time against now and name the step. Example: "Now 13:40. Acme technical
   interview, today 14:00." Several steps today: open the nearest one, then ask.
2. No `keywords.md` in the step's folder, or one older than its `cheat-sheet.md`: write it from `cheat-sheet.md` first
   (`prepare`, "Prep notes"). No `cheat-sheet.md` either: write both.
3. Build and open it: `cheat_sheet.py <job id> [step=<n>] --open`. It writes `cheat-sheet-wide.html` in the step's
   folder and opens it in its own Chrome window, placed at the spot (`CHEAT_SHEET_SPOT`, default top) on a monitor
   other than the call's (`CALL_MONITOR`). Example: `cheat_sheet.py J1 --open`. Chrome not found: give the file's
   path as text, marked "open in Chrome".
4. Then, only what is not set yet, once each: which monitor holds the call (`cheat_sheet.py --monitors` lists them;
   the answer: `call=<n>`), and where the page sits (top or bottom half, left or right side, the top-right corner:
   `spot=<spot>`). Each answer is kept in `job-search.env` and reused; build again with it. Example: "The call is on
   monitor 2" -> `cheat_sheet.py J1 call=2 --open`.
5. Say in one line what is on the page. The page shrinks its text until it fits and shows the size on top; "still too
   long" there: shorten `keywords.md` with the person and build again.

## The page

- Columns by the spot: top or bottom half 3, left or right side 1, the corner 2.
- The top line: the step, the employer, the date, and the call link from the step's `link` in `PIPELINE`.
- A heading in `keywords.md` starts a block, shown with a coloured heading band; every other line is one keyword
  line, large and high in contrast. Example: `## Numbers`, then `- 12 eng / 3 teams`.
- Pay figures never go on the page (RULES.md, "Honesty and what Claude never does").
