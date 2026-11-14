"""The keyword cheat sheet of one hiring step as a single page for the call: no scrolling, the call link on top.

python -I cheat_sheet.py <job id> [step=<n>] [spot=top|bottom|left|right|corner] [--open]
    writes cheat-sheet-wide.html in the step's folder, from that folder's cheat-sheet.md, and prints its path.
    step=<n>: the step's number in PIPELINE (1 is the first); without it, the first step that is not done, not
    cancelled and dated today or later, else the last one.
    spot=: where the page sits on the screen; it sets the columns: top or bottom half 3, left or right side 1, a
    corner 2. Given once, it is written to CHEAT_SHEET_SPOT in job-search.env and used from then on (default: top).
    --open: opens the page in a new Chrome window (CHROME in job-search.env, else the usual install paths).
cheat-sheet.md: a heading line ("# ", "## ") starts a block; every other line is a keyword line ("- " and "* " are
dropped, **bold** stays bold). The page shrinks its own text until it fits the window and shows the size on top.
Example: cheat_sheet.py J1 spot=corner --open
Add --env <job-search.env> anywhere to pick the env file.
"""
import datetime
import html
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jsenv  # noqa: E402
from trackerlib import flat_jobs, pipeline_entry, step_done  # noqa: E402

SPOTS = {"top": 3, "bottom": 3, "left": 1, "right": 1, "corner": 2}
STAGE_DIRS = ("approved", "pending", "rejected", "closed", "declined", "not-applied")
JOB_ID = re.compile(r"^- \*\*Job id:\*\* (\S+)", re.M)
BOLD = re.compile(r"\*\*(.+?)\*\*")
TEMPLATE = os.path.join(HERE, "..", "templates", "cheat-sheet", "index.html")
CHROME_PATHS = (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def job_folder(root, job_id):
    """The application folder whose overview.md names this job id: the first one, in the stages' order."""
    for stage in STAGE_DIRS:
        base = os.path.join(root, stage)
        for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
            overview = os.path.join(base, name, "overview.md")
            if os.path.isfile(overview):
                with open(overview, encoding="utf-8") as f:
                    found = JOB_ID.search(f.read())
                if found and found.group(1) == job_id:
                    return os.path.join(base, name)
    return ""


def pick_step(steps, wanted, today):
    """The step's number (1..): the one asked for, else the next one not done or cancelled, else the last."""
    if wanted:
        if not (wanted.isascii() and wanted.isdigit()) or not 1 <= int(wanted) <= len(steps):
            sys.exit(f"step is a number from 1 to {len(steps)}")
        return int(wanted)
    coming = [n for n, s in enumerate(steps, 1)
              if not s.get("cancelled") and not step_done(s) and max(str(s.get("date") or "")[:10],
                                                                    str(s.get("due") or "")[:10]) >= today]
    return coming[0] if coming else len(steps)


def step_dir(folder, n):
    """The step's own folder ("NN <date> <name>", as build_app_folders.py names it)."""
    prefix = f"{n:02d} "
    hits = [d for d in sorted(os.listdir(folder)) if d.startswith(prefix) and os.path.isdir(os.path.join(folder, d))]
    return os.path.join(folder, hits[0]) if hits else ""


def blocks_of(text):
    """[(title, [line, ...])] from the cheat sheet's Markdown; lines before the first heading form a block of their own."""
    blocks = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            blocks.append((line.lstrip("#").strip(), []))
            continue
        if not blocks:
            blocks.append(("", []))
        blocks[-1][1].append(re.sub(r"^[-*]\s+", "", line))
    return [(title, lines) for title, lines in blocks if title or lines]


def rich(text):
    """Escaped for the page; **bold** becomes <b>."""
    return BOLD.sub(r"<b>\1</b>", html.escape(text))


def set_env_key(path, key, value):
    """Write one KEY=value line into job-search.env: its line replaced, or added at the end."""
    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    hit = [i for i, line in enumerate(lines) if line.strip().startswith(key + "=")]
    for i in hit:
        lines[i] = f"{key}={value}"
    if not hit:
        lines.append(f"{key}={value}")
    with open(path + ".tmp", "w", encoding="utf-8", newline="") as f:
        f.write(eol.join(lines) + eol)
    os.replace(path + ".tmp", path)


def chrome_of(env):
    chrome = env.get("CHROME")
    if chrome and os.path.exists(chrome):
        return chrome
    return next((c for c in CHROME_PATHS if os.path.exists(c)), None) or shutil.which("google-chrome") \
        or shutil.which("chrome")


def main():
    args = sys.argv[1:]
    env_arg = None
    if "--env" in args:
        i = args.index("--env")
        if i + 1 >= len(args):
            sys.exit("--env takes the path of a job-search.env")
        env_arg = args[i + 1]
        del args[i:i + 2]
    show = "--open" in args
    args = [a for a in args if a != "--open"]
    if not args or "=" in args[0]:
        sys.exit(__doc__)
    job_id, pairs = args[0], dict(a.split("=", 1) for a in args[1:] if "=" in a)
    if set(pairs) - {"step", "spot"} or len(pairs) != len(args) - 1:
        sys.exit("expected step=<n> and spot=<" + "|".join(SPOTS) + ">")
    env = jsenv.load(env_arg, __file__)
    spot = pairs.get("spot") or env.get("CHEAT_SHEET_SPOT") or "top"
    if spot not in SPOTS:
        sys.exit(f"spot is one of {', '.join(SPOTS)}: got {spot!r}")

    with open(env.path("TRACKER"), encoding="utf-8") as f:
        job = next((j for j in flat_jobs(json.load(f)) if j["id"] == job_id), None)
    if job is None:
        sys.exit(f"{job_id} is not in the tracker")
    pipeline = {}
    if env.get("PIPELINE") and os.path.isfile(env.path("PIPELINE")):
        with open(env.path("PIPELINE"), encoding="utf-8") as f:
            pipeline = json.load(f)
    steps = pipeline_entry(pipeline, job_id).get("steps") or []
    if not steps:
        sys.exit(f"{job_id} has no hiring step in PIPELINE")
    n = pick_step(steps, pairs.get("step"), datetime.date.today().isoformat())
    step = steps[n - 1]
    folder = job_folder(env.path("APPLICATIONS_DIR"), job_id)
    where = step_dir(folder, n) if folder else ""
    source = os.path.join(where, "cheat-sheet.md") if where else ""
    if not source or not os.path.isfile(source):
        sys.exit(f"no cheat-sheet.md for step {n} of {job_id}: /cenk-jobs:prepare writes it into the step's folder"
                 + (f" ({where})" if where else " (build_app_folders.py creates the folder)"))
    with open(source, encoding="utf-8") as f:
        blocks = blocks_of(f.read())
    if not blocks:
        sys.exit(f"{source} holds no keyword line")

    when = " ".join(x for x in (str(step.get("date") or "")[:16].replace("T", " "), str(step.get("time") or "")) if x)
    title = f"{job.get('company', '')} - {step.get('name', 'Step')}".strip(" -")
    top = [f"<b>{html.escape(step.get('name', 'Step'))}</b>", f"<span>{html.escape(job.get('company', ''))}</span>"]
    top += [f"<span>{html.escape(when)}</span>"] if when else []
    link = str(step.get("link") or "")
    if re.match(r"https?://", link):
        top.append(f'<a href="{html.escape(link, quote=True)}" rel="noopener noreferrer">{html.escape(link)}</a>')
    body = "\n".join(
        '    <div class="block">' + (f"<h2>{rich(t)}</h2>" if t else "") + "".join(f"<p>{rich(x)}</p>" for x in lines)
        + "</div>" for t, lines in blocks)
    with open(TEMPLATE, encoding="utf-8") as f:
        page = f.read()
    parts = {"TITLE": html.escape(title), "COLUMNS": str(SPOTS[spot]), "TOP": "".join(top), "BLOCKS": body}
    page = re.sub(r"__(TITLE|COLUMNS|TOP|BLOCKS)__", lambda m: parts[m.group(1)], page)
    out = os.path.join(where, "cheat-sheet-wide.html")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    if pairs.get("spot") and env.get("CHEAT_SHEET_SPOT") != spot:
        set_env_key(env.file, "CHEAT_SHEET_SPOT", spot)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    print(out)
    print(f"step {n}: {step.get('name', 'Step')}" + (f", {when}" if when else "") + f" | spot {spot}, "
          f"{SPOTS[spot]} column{'' if SPOTS[spot] == 1 else 's'} | {len(blocks)} blocks, "
          f"{sum(len(x) for _, x in blocks)} lines | the page shows its text size on top")
    if show:
        chrome = chrome_of(env)
        if not chrome:
            sys.exit("Chrome not found: set CHROME in job-search.env, or open the file in Chrome by hand")
        subprocess.Popen([chrome, "--new-window", pathlib.Path(out).resolve().as_uri()])
        print("opened in a new Chrome window: move it to the spot")


if __name__ == "__main__":
    main()
