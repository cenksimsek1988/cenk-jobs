# Programs: checks and install lines

Read by /cenk-jobs:setup, step 1, and by a session whose health check names a missing program.

- Check each program:

  | Program | What it is for | Check |
  |---|---|---|
  | Python 3.10+ | runs every script | `python --version` (Windows also `py --version`) |
  | Google Chrome | prints CVs and letters to PDF; Claude in Chrome applies in it | `check_setup.py` |
  | Google Drive for desktop | keeps the main folder in Drive and on the computer | `check_setup.py` |
  | pypdf | reads the person's PDFs as text (old CVs, documents) and checks each CV built | `python -I -c "import pypdf"` |
  | Poppler (`pdftoppm`) | lets Claude see PDF pages as images (a scanned diploma, a CV's layout) | `pdftoppm -v` |

- Install every one the person does not refuse, from the official source, with its line below. Say that an install
  accepts the program's own licence (Poppler: GPL; Chrome and Drive: Google's terms).

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
  the browser with `find` or `read_page` (`max_chars` 5000); never a screenshot.
