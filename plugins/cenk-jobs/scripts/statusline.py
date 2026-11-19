"""The plan's usage share for the run report, opt-in: Claude Code gives it only to a status line script.

    statusline.py --out <file> [--log <file>] [--then "<command>"]
        the status line itself: reads Claude Code's JSON on stdin, writes rate_limits (5 hours, 7 days) to <file>
        and prints "5h 23% · 7d 41%"; with --log, adds a row (at, seven_day, resets_at) to the calibration log
        whenever the 7-day share changes (cost.py calibrate); with --then, runs the person's own status line
        command on the same input and prints its line instead
    statusline.py install [--env <job-search.env>]
        copies this script into the main folder (apply/statusline.py) and prints the statusLine setting to add to
        the person's Claude Code settings; written there only after their yes
    statusline.py read [--env <job-search.env>]
        one line for the run report, from PLAN_USAGE: "Plan used: 5 hours 23% (resets 21:00), 7 days 41%";
        nothing when the file is missing or older than a day

Example: `statusline.py read` prints `Plan used: 5 hours 23% (resets 21:00), 7 days 41% (resets Mon 09:00)`.
"""
import datetime
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WINDOWS = (("five_hour", "5 hours", "5h"), ("seven_day", "7 days", "7d"))


def when(value):
    """resets_at as local time: epoch seconds or an ISO string."""
    try:
        t = (datetime.datetime.fromtimestamp(float(value)) if isinstance(value, (int, float)) or str(value).isdigit()
             else datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone().replace(tzinfo=None))
    except (TypeError, ValueError, OSError):
        return ""
    return t.strftime("%H:%M") if t.date() == datetime.date.today() else t.strftime("%a %H:%M")


def log_week(path, week):
    """One row in the calibration log when the 7-day share or its reset changed since the last row."""
    row = {"seven_day": week.get("used_percentage"), "resets_at": week.get("resets_at")}
    if row["seven_day"] is None:
        return
    last = {}
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        last = json.loads(lines[-1]) if lines else {}
    except (OSError, ValueError):
        pass
    if last.get("seven_day") == row["seven_day"] and last.get("resets_at") == row["resets_at"]:
        return
    try:
        with open(path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps({"at": datetime.datetime.now().isoformat(timespec="seconds"), **row}) + "\n")
    except OSError as e:
        print(f"statusline: cannot write {path}: {e.strerror}", file=sys.stderr)


def status(opts):
    raw = sys.stdin.read()
    try:
        limits = (json.loads(raw) or {}).get("rate_limits") or {}
    except ValueError:
        limits = {}
    found = {k: limits[k] for k, _, _ in WINDOWS if isinstance(limits.get(k), dict)}
    if found and opts.get("--out"):
        tmp = opts["--out"] + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"at": datetime.datetime.now().isoformat(timespec="seconds"), **found}, fh)
            os.replace(tmp, opts["--out"])
        except OSError as e:  # the line still shows; the reason goes to stderr, never a traceback per refresh
            print(f"statusline: cannot write {opts['--out']}: {e.strerror}", file=sys.stderr)
    if found.get("seven_day") and opts.get("--log"):
        log_week(opts["--log"], found["seven_day"])
    if opts.get("--then"):
        out = subprocess.run(opts["--then"], input=raw, capture_output=True, text=True, shell=True)
        sys.stdout.write(out.stdout)
        return
    print(" · ".join(f"{short} {round(found[k].get('used_percentage', 0))}%" for k, _, short in WINDOWS if k in found))


def main():
    sys.stdout.reconfigure(errors="replace")  # the middle dot on a cp1252 console
    args = sys.argv[1:]
    opts = {}
    for flag in ("--out", "--log", "--then", "--env"):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                sys.exit(f"{flag} takes a value")
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    if not args:
        return status(opts)
    sys.path.insert(0, HERE)
    import jsenv
    env = jsenv.load(opts.get("--env"), __file__)
    target = env.path("PLAN_USAGE") if env.get("PLAN_USAGE") else os.path.join(env.home, "apply", "plan-usage.json")
    if args[0] == "install":
        copy = os.path.join(env.home, "apply", "statusline.py")
        os.makedirs(os.path.dirname(copy), exist_ok=True)
        shutil.copyfile(os.path.abspath(__file__), copy)
        python = (env.get("PYTHON") or "python").replace("\\", "/")
        log = (env.path("PLAN_USAGE_LOG") if env.get("PLAN_USAGE_LOG")
               else os.path.join(env.home, "apply", "plan-usage-log.jsonl"))
        cmd = (f'"{python}" -I "{copy.replace(os.sep, "/")}" --out "{target.replace(os.sep, "/")}" '
               f'--log "{log.replace(os.sep, "/")}"')
        print(json.dumps({"statusLine": {"type": "command", "command": cmd}}, indent=1))
        print("An existing statusLine command: keep it with --then \"<that command>\" at the end.")
    elif args[0] == "read":
        if not os.path.isfile(target):
            return
        try:
            with open(target, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"statusline read: {target} is unreadable: {e}", file=sys.stderr)
            return
        try:
            age = datetime.datetime.now() - datetime.datetime.fromisoformat(data.get("at", ""))
        except ValueError:
            return
        if age > datetime.timedelta(days=1):
            return
        parts = []
        for key, name, _ in WINDOWS:
            w = data.get(key) or {}
            if "used_percentage" in w:
                reset = when(w.get("resets_at"))
                parts.append(f"{name} {round(w['used_percentage'])}%" + (f" (resets {reset})" if reset else ""))
        if parts:
            print("Plan used: " + ", ".join(parts))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
