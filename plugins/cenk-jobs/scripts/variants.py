"""Variants: which model and effort each step of a run uses, rotated over runs to compare their token cost, and the
good-fit count each run is judged by. Off until the person turns it on.

python -I variants.py current            the variant for this run: the one after the last run's in the rotation, or
                                         "default" when variants are off or not set up
python -I variants.py models [<name>]    {step: {model, effort}} of that variant (default: this run's) as JSON, for
                                         screen-and-prepare.js's args.models; "{}" for default
python -I variants.py count [--days 7]   for each finished run at least <days> days old and not counted yet: its
                                         good-fit jobs, logged once as a "run-result" row (variant, good_fit)
python -I variants.py show               each variant's runs, good-fit jobs and the runs still to count
The file: VARIANTS in job-search.env, default apply/variants.json:
  {"on": true, "rotation": ["a", "b"], "variants": {"a": {"fit": {"model": "sonnet", "effort": "low"}},
   "b": {"fit": {"model": "haiku", "effort": "low"}}}}
Steps: fit, screen, verify, judge, form, writer, review, review_plain (screen-and-prepare.js), main (the scheduled
run's own session: `schedule` sets that task's model). A step a variant leaves out uses the default.
A run's variant is logged with it: `usage.py log run started "<how>" variant=<name>`.
A good-fit job of a run: a job whose history moves it from found to to-apply, needs-person, account-needed or
submitted on one of the run's dates, and that is not now skipped or excluded, nor declined before it was sent. A
posting that closed still counts: the fit was right. Example: 3 good-fit jobs for the run of 2026-11-17, variant b.
Add --env <job-search.env> anywhere to pick the env file.
"""
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jsenv  # noqa: E402
from trackerlib import flat_jobs  # noqa: E402

STEPS = ("fit", "screen", "verify", "judge", "form", "writer", "review", "review_plain", "main")
PASSED = ("to-apply", "needs-person", "account-needed", "submitted")
DROPPED = ("skipped", "excluded")


def load_json(path, default):
    if not os.path.isfile(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def variants_file(env):
    return env.path("VARIANTS") if env.get("VARIANTS") else os.path.join(env.home, "apply", "variants.json")


def usage_rows(env):
    path = env.path("USAGE_LOG") if env.get("USAGE_LOG") else os.path.join(env.home, "apply", "usage-log.jsonl")
    if not os.path.isfile(path):
        return path, []
    with open(path, encoding="utf-8") as fh:
        return path, [json.loads(line) for line in fh if line.strip()]


def runs(rows):
    """[(start, end, variant)]: each run from its "started" row to its ok, failed or stopped row."""
    out, start = [], None
    for r in rows:
        if r.get("step") != "run":
            continue
        if r.get("result") == "started":
            start = r
        elif start:
            out.append((start["time"], r["time"], start.get("variant") or "default"))
            start = None
    return out


def current(conf, rows):
    rotation = [v for v in conf.get("rotation") or [] if v in (conf.get("variants") or {})]
    if not conf.get("on") or not rotation:
        return "default"
    used = [r.get("variant") for r in rows if r.get("step") == "run" and r.get("result") == "started"]
    last = next((v for v in reversed(used) if v in rotation), None)
    return rotation[(rotation.index(last) + 1) % len(rotation)] if last else rotation[0]


def good_fit(jobs, start, end):
    days = {(datetime.date.fromisoformat(start[:10]) + datetime.timedelta(days=n)).isoformat()
            for n in range((datetime.date.fromisoformat(end[:10]) - datetime.date.fromisoformat(start[:10])).days + 1)}
    count = 0
    for job in jobs:
        history = job.get("history") or []
        passed = next((h for h in history if h.get("status") in PASSED), None)
        if not passed or passed.get("date", "")[:10] not in days:
            continue
        status = job.get("status", "")
        sent = any(h.get("status") == "submitted" for h in history)
        if status in DROPPED or (status == "declined" and not sent):
            continue
        count += 1
    return count


def main():
    args = sys.argv[1:]
    env_arg = None
    if "--env" in args:
        i = args.index("--env")
        if i + 1 >= len(args):
            sys.exit("--env takes the path of a job-search.env")
        env_arg = args[i + 1]
        del args[i:i + 2]
    if not args or args[0] not in ("current", "models", "count", "show"):
        sys.exit(__doc__)
    env = jsenv.load(env_arg, __file__)
    conf = load_json(variants_file(env), {})
    log_path, rows = usage_rows(env)
    if args[0] == "current":
        print(current(conf, rows))
    elif args[0] == "models":
        name = args[1] if len(args) > 1 else current(conf, rows)
        if name != "default" and name not in (conf.get("variants") or {}):
            sys.exit(f"no variant {name!r} in {variants_file(env)}")
        steps = (conf.get("variants") or {}).get(name, {})
        unknown = [s for s in steps if s not in STEPS]
        if unknown:
            sys.exit(f"unknown step(s) {', '.join(unknown)}: steps are {', '.join(STEPS)}")
        print(json.dumps(steps))
    elif args[0] == "count":
        days = int(args[args.index("--days") + 1]) if "--days" in args else 7
        with open(env.path("TRACKER"), encoding="utf-8") as fh:
            jobs = flat_jobs(json.load(fh))
        counted = {r.get("run") for r in rows if r.get("step") == "run-result"}
        today = datetime.date.today()
        new = []
        for start, end, variant in runs(rows):
            if start in counted or (today - datetime.date.fromisoformat(end[:10])).days < days:
                continue
            n = good_fit(jobs, start, end)
            new.append({"time": datetime.datetime.now().replace(microsecond=0).isoformat(), "step": "run-result",
                        "result": "ok", "run": start, "variant": variant, "good_fit": n})
            print(f"run {start[:16]} variant {variant}: {n} good-fit jobs")
        if new:
            with open(log_path, "a", encoding="utf-8", newline="\n") as fh:
                for r in new:
                    fh.write(json.dumps(r) + "\n")
        print(f"{len(new)} run(s) counted")
    else:
        results = [r for r in rows if r.get("step") == "run-result"]
        by = {}
        for r in results:
            by.setdefault(r.get("variant", "default"), []).append(r.get("good_fit", 0))
        for name, counts in sorted(by.items()):
            print(f"{name}: {len(counts)} runs, good-fit jobs {counts}")
        waiting = [s for s, e, v in runs(rows) if s not in {r.get("run") for r in results}]
        print(f"this run: {current(conf, rows)} | runs still to count: {len(waiting)}")


if __name__ == "__main__":
    main()
