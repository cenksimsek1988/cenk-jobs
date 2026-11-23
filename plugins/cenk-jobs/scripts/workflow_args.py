"""The args of workflows/screen-and-prepare.js, built by script: small enough to pass in the Workflow call.

    workflow_args.py --search <outDir>/search.json [--lookup <file>] [--tag <tag>] [--person "<name>"]
        [--screen "<employer>" ...]
    workflow_args.py --screen "<employer>" [--screen "<employer>" ...] --out <dir>
        the full employer check before a first hiring step (RULES/employers.md): each named employer gets screen; one
        with no new posting in the run is screen_only (no fit check). An employer track.py sync has marked screened
        prints "screened on <date>: <name>" and is left out while that date is at most SCREEN_AGE_DAYS (90) old; an
        excluded one is listed as left out. An employer with new postings in the run gets the full check too, never
        only a due second check.
        writes <outDir>/args.json and prints its size and one line per employer left out. Beside it: rules.json (the
        person's employer rules, read by the agents), and the record parts screen.json, facts.json, fit.json
        (career_view.py), and jobs/<employer>.json, one per employer with a unique name, which its entry names
        (jobs_file) and its fit check reads. --lookup: employer_lookup.py --out's file: "exclude" leaves the employer out, "undecided"
        passes it with quick and its lookup line.
    workflow_args.py --search <file> --list [--fit-model sonnet|opus|opus-max] [--script <run.js>]
        --list: a list run (APPLY=list: the fit check only; no letters, no drafts, each step's own model); --fit-model:
        the fit check's model for this run; --script: also the run script, the workflow's own text with these args
        written in and a counts-only return, for the Workflow tool's scriptPath (0.49.0, tune-search: the args of
        hundreds of employers are too long to type into the call, and a workflow script reads no file).

Per employer of the search file it runs employer.py check's view: "exclude" leaves it out; a second check due passes
it with screen, known and own (those categories); its verdict and ties go with it. The rest comes from the scripts the
coordinator ran by hand before: choices.py workflow, variants.py order and models, career_view.py cvs, the setting
draft_answers. The full rules go to the agents as a file; the args keep only what the script itself decides with
(each category's label, action, indirect, custom flag and notes). Example: 102 employers make about 8 KB, where the
args with the rules and every known check inline made 45 KB.
Add --env <job-search.env> anywhere to pick the env file.
"""
import datetime
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import choices  # noqa: E402
import employerlib as el  # noqa: E402
import jsenv  # noqa: E402
from trackerlib import companies as tracker_jobs  # noqa: E402

KEEP = ("label", "action", "indirect", "custom", "notes")
SCREEN_AGE_DAYS = 90  # a full check before a hiring step older than this runs again (approved 20 Nov 2026)


def jobs_files(out_dir, found):
    """One file per employer of the search file, <outDir>/jobs/<name>.json, each name unique whatever the case (a
    clash adds -2, -3): {employer: path}. Each fit check reads only its own employer's postings.
    Example: "Acme (Parent) GmbH" -> jobs/Acme-Parent-GmbH.json."""
    folder = os.path.join(out_dir, "jobs")
    os.makedirs(folder, exist_ok=True)
    taken, out = set(), {}
    for c in found:
        base = re.sub(r"[^A-Za-z0-9]+", "-", c.get("name", "")).strip("-") or "employer"
        name, n = base, 1
        while name.lower() in taken:
            n += 1
            name = f"{base}-{n}"
        taken.add(name.lower())
        path = os.path.join(folder, name + ".json")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"name": c.get("name", ""), "jobs": c.get("jobs", [])}, fh, ensure_ascii=False, indent=1)
        out[c.get("name", "")] = path.replace(os.sep, "/")
    return out


def run(env, script, *more):
    res = subprocess.run([sys.executable, "-I", os.path.join(HERE, script), *more, "--env", env.file],
                         capture_output=True, text=True, encoding="utf-8")
    if res.returncode:
        sys.exit(f"{script} {' '.join(more[:1])} failed: {res.stderr.strip()[-300:]}")
    return res.stdout


def draft_answers(env):
    try:
        import profilelib as pl
        return str(pl.setting(pl.load(env), "draft_answers", "no")).lower() == "yes"
    except Exception as problem:  # noqa: BLE001 - no readable profile: the setting counts as unset, so "no"
        print(f"draft_answers not read ({problem}): drafts off for this run", file=sys.stderr)
        return False


def main():
    args = sys.argv[1:]
    opts, screens = {}, []
    while "--screen" in args:
        i = args.index("--screen")
        if i + 1 >= len(args):
            sys.exit("--screen takes an employer's name")
        screens.append(args[i + 1])
        del args[i:i + 2]
    for flag in ("--env", "--search", "--lookup", "--tag", "--person", "--out", "--fit-model", "--script"):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                sys.exit(f"{flag} takes a value")
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    listed = "--list" in args
    if listed:
        args.remove("--list")
    if opts.get("--fit-model") and opts["--fit-model"] not in choices.KEYS["FIT_MODEL"][0]:
        sys.exit(f"--fit-model is one of {', '.join(choices.KEYS['FIT_MODEL'][0])}: got {opts['--fit-model']!r}")
    if args or not (opts.get("--search") or (screens and opts.get("--out"))):
        sys.exit(__doc__)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    env = jsenv.load(opts.get("--env"), __file__)
    slash = lambda p: p.replace(os.sep, "/")  # noqa: E731
    if opts.get("--search"):
        search = os.path.abspath(opts["--search"])
        out_dir = os.path.dirname(search)
        with open(search, encoding="utf-8") as fh:
            found = json.load(fh).get("companies", [])
    else:
        search, out_dir, found = "", os.path.abspath(opts["--out"]), []
        os.makedirs(out_dir, exist_ok=True)
    lookup = {}
    if opts.get("--lookup"):
        with open(opts["--lookup"], encoding="utf-8") as fh:
            lookup = json.load(fh)

    rule_set = el.rules(env)
    rules_file = os.path.join(out_dir, "rules.json")
    with open(rules_file, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rule_set, fh, ensure_ascii=False, indent=1)
    compact = {"categories": {c: {k: v for k, v in (s or {}).items() if k in KEEP and v not in ("", None, False)}
                              for c, s in rule_set.get("categories", {}).items()}}
    parts = {}
    for scope in ("screen", "facts", "fit"):
        parts[scope] = os.path.join(out_dir, scope + ".json")
        run(env, "career_view.py", scope, "--out", parts[scope])
    cvs = json.loads(run(env, "career_view.py", "cvs") or "[]")

    with open(env.path("TRACKER"), encoding="utf-8") as fh:
        tracker = json.load(fh)
    applied = {}
    for company, job in tracker_jobs(tracker):
        if job.get("status") == "submitted" or job.get("applied"):
            for k in el.keys(job.get("company") or company.get("name", "")):
                applied.setdefault(k, []).append(job.get("title", ""))

    employers = el.checks_file(env).get("employers", {}) if env.get("EMPLOYER_CHECKS") else {}
    files = jobs_files(out_dir, found)
    passed, known, left = [], {}, []
    for c in found:
        name = c.get("name", "")
        view = el.check_view(env, name, rule_set, employers=employers)
        free = lookup.get(name) or {}
        if view["verdict"] == "exclude" or free.get("verdict") == "exclude":
            left.append(f"{name} | exclude | " + "; ".join(view["reasons"] or [free.get("why", "")])[:200])
            continue
        entry = {"name": name, "jobs_file": files[name]}
        if view["verdict"] and not view["never_checked"]:
            entry["verdict"] = view["verdict"]
        if view["recheck"]:
            entry.update(screen=True, known=True, own=view["recheck"])
            known[name] = {"checks": view["checks"]}
        if free.get("verdict") == "undecided":
            entry.update(quick=True, lookup=str(free.get("why", ""))[:240])
        titles = sorted({t for k in el.keys(name) for t in applied.get(k, [])})
        if titles:
            entry["applied_jobs"] = titles[:10]
        passed.append(entry)

    # The full check before a first hiring step (--screen): once per employer, by the date track.py sync keeps.
    screened = {c.get("name"): c.get("screened") for c in tracker.get("companies", [])}
    for name in screens:
        when = str(screened.get(name) or "")[:10]
        try:
            age = (datetime.date.today() - datetime.date.fromisoformat(when)).days if when else None
        except ValueError:
            age = None  # an unreadable date: the check runs again
        if age is not None and age <= SCREEN_AGE_DAYS:
            print(f"screened on {when}: {name}")
            continue
        view = el.check_view(env, name, rule_set, employers=employers)
        if view["verdict"] == "exclude":
            left.append(f"{name} | exclude | " + "; ".join(view["reasons"])[:200])
            continue
        entry = next((e for e in passed if e["name"] == name), None)
        if entry:
            # Its new postings are fit-checked first, then the full check runs: without "known", a due second check
            # ("own") runs after the screen instead of in its place.
            entry["screen"] = True
            entry.pop("known", None)
            continue
        # No new posting: only the screen runs (screen_only), with what the records already hold as its starting point.
        entry = {"name": name, "screen": True, "screen_only": True}
        if view["verdict"] and not view["never_checked"]:
            entry["verdict"] = view["verdict"]
        if view["checks"]:
            known[name] = {"checks": view["checks"]}
        passed.append(entry)

    import profilelib as pl
    tag = opts.get("--tag") or datetime.datetime.now().strftime("r%m%d%H%M")
    result = {
        "person": opts.get("--person") or pl.person(env)["name"],
        "masterRecord": slash(env.path("MASTER_RECORD")), "envFile": slash(os.path.abspath(env.file)),
        "scripts": slash(HERE), "python": slash(sys.executable),
        "searchFile": slash(search), "outDir": slash(out_dir),
        "bodiesDir": slash(env.path("LETTER_BODIES_DIR")), "lettersDir": slash(env.path("LETTERS_DIR")), "tag": tag,
        "screenRecord": slash(parts["screen"]), "factsRecord": slash(parts["facts"]), "fitRecord": slash(parts["fit"]),
        "rulesFile": slash(rules_file), "employerRules": compact, "known": known,
        "cvs": cvs, "order": (run(env, "variants.py", "order").split() or ["employer-first"])[0],
        "models": json.loads(run(env, "variants.py", "models") or "{}"),
        "draftAnswers": draft_answers(env), **choices.workflow_args(env), "companies": passed,
    }
    clues = env.path("FIT_CLUES") if env.get("FIT_CLUES") else os.path.join(env.home, "apply", "fit-clues.md")
    if os.path.isfile(clues):
        result["fitClues"] = slash(clues)  # feedback.py clues: earlier replies, read by the fit check
    if listed:
        result.update(apply="list", letters="never", draftAnswers=False, models={})
    if opts.get("--fit-model"):
        result["fitModel"] = opts["--fit-model"]
    path = os.path.join(out_dir, "args.json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(result, fh, ensure_ascii=False, separators=(",", ":"))
    for line in left:
        print("left out: " + line)
    print(f"{slash(path)}: {os.path.getsize(path)} bytes, {len(passed)} employers, {len(left)} left out")
    if opts.get("--script"):
        with open(os.path.join(HERE, "..", "workflows", "screen-and-prepare.js"), encoding="utf-8") as fh:
            funnel = fh.read()
        marker = "\nconst A = args\n"
        if marker not in funnel:
            sys.exit("workflows/screen-and-prepare.js has no line 'const A = args': no run script written")
        text = funnel.replace(marker, "\nconst A = " + json.dumps(dict(result, countsOnly=True), ensure_ascii=True)
                              + "\n", 1)
        with open(opts["--script"], "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print(f"{slash(os.path.abspath(opts['--script']))}: the run script, {len(text)} characters, args written in")


if __name__ == "__main__":
    main()
