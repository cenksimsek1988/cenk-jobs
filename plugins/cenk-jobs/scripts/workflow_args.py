"""The args of workflows/screen-and-prepare.js, built by script: small enough to pass in the Workflow call.

    workflow_args.py --search <outDir>/search.json [--lookup <file>] [--tag <tag>] [--person "<name>"]
        writes <outDir>/args.json and prints its size and one line per employer left out. Beside it: rules.json (the
        person's employer rules, read by the agents), and the record parts screen.json, facts.json, fit.json
        (career_view.py), and jobs/<employer>.json, one per employer with a unique name, which its entry names
        (jobs_file) and its fit check reads. --lookup: employer_lookup.py --out's file: "exclude" leaves the employer out, "undecided"
        passes it with quick and its lookup line.

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
    opts = {}
    for flag in ("--env", "--search", "--lookup", "--tag", "--person"):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                sys.exit(f"{flag} takes a value")
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    if args or not opts.get("--search"):
        sys.exit(__doc__)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    env = jsenv.load(opts.get("--env"), __file__)
    search = os.path.abspath(opts["--search"])
    out_dir = os.path.dirname(search)
    slash = lambda p: p.replace(os.sep, "/")  # noqa: E731
    with open(search, encoding="utf-8") as fh:
        found = json.load(fh).get("companies", [])
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

    tag = opts.get("--tag") or datetime.datetime.now().strftime("r%m%d%H%M")
    result = {
        "person": opts.get("--person") or env.get("PERSON_NAME", ""),
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
    path = os.path.join(out_dir, "args.json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(result, fh, ensure_ascii=False, separators=(",", ":"))
    for line in left:
        print("left out: " + line)
    print(f"{slash(path)}: {os.path.getsize(path)} bytes, {len(passed)} employers, {len(left)} left out")


if __name__ == "__main__":
    main()
