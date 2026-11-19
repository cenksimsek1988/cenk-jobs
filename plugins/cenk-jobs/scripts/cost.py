"""What the job search costs against a Claude plan, from the static table data/plan-costs.json and this computer's
transcripts. Numbers only: it never prints message text and sends nothing.

python -I cost.py table [<plan>]
    each step's W (low-high, its source) and its share of the plan's week; a steady week against the target share
    of a Pro week. Plan: pro | max5 | max20 (max counts as max5); default PLAN, else every plan. Shares print as
    "unknown" while pro_week_w is null (no calibration week yet).
python -I cost.py calibrate [<plan>]
    W per 1% of the 7-day limit, from the status line's log (PLAN_USAGE_LOG, written by statusline.py --log) and the
    W of every transcript on this computer in between; then the plan's week and Pro's week in W. Needs a rise of 5
    points or more within one reset period.
python -I cost.py context
    the main folder's coordinator session ("Job search coordinator", the newest): its context and the day it
    started, then "hand off" when it started before today or its context is over COORDINATOR_CONTEXT (default
    200000 tokens), else "keep". Example: "coordinator context 340k, started 2026-11-06: hand off".
Add --env <job-search.env> anywhere to pick the env file. Exit 0; 1 when nothing can be read.
"""
import datetime
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jsenv  # noqa: E402
from token_report import local, messages, projects_dir, weight  # noqa: E402

TABLE = os.path.join(os.path.dirname(HERE), "data", "plan-costs.json")
TITLE = "Job search coordinator"
MIN_RISE = 5


def load_table():
    with open(TABLE, encoding="utf-8") as fh:
        return json.load(fh)


def plan_of(name, plans):
    name = "max5" if name == "max" else name
    return name if name in plans else None


def mw(w):
    return f"{w / 1e6:.1f}M" if w >= 1e6 else f"{w / 1e3:.0f}k"


def share(low, high, week):
    return f"{100 * low / week:.1f}-{100 * high / week:.1f}% of a week" if week else "share unknown"


def table(env, plan):
    t = load_table()
    plans = t["plans"]
    chosen = [plan_of(plan, plans)] if plan_of(plan, plans) else list(plans)
    pro = t.get("pro_week_w")
    print(f"Pro week: {mw(pro) + ' W' if pro else 'unknown'} ({t.get('pro_week_source', '')})")
    for p in chosen:
        week = pro * plans[p] if pro else None
        print(f"{p}:")
        for step, (low, high, source) in t["steps"].items():
            print(f"  {step:17} {mw(low)}-{mw(high)} W  {share(low, high, week)}  ({source})")
        low = sum(n * t["steps"][s][0] for s, n in t["steady_week"].items())
        high = sum(n * t["steps"][s][1] for s, n in t["steady_week"].items())
        print(f"  steady week       {mw(low)}-{mw(high)} W  {share(low, high, week)}  "
              f"({', '.join(f'{n} {s}' for s, n in t['steady_week'].items())})")
    target = t["target"] * pro if pro else None
    print(f"target: a steady week within {round(100 * t['target'])}% of a Pro week"
          + (f" ({mw(target)} W)" if target else " (unknown until calibrated)"))


def log_rows(env):
    path = env.path("PLAN_USAGE_LOG") if env.get("PLAN_USAGE_LOG") else os.path.join(env.home, "apply",
                                                                                   "plan-usage-log.jsonl")
    rows = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                    rows.append((datetime.datetime.fromisoformat(r["at"]), float(r["seven_day"]),
                                 str(r.get("resets_at", ""))))
                except (ValueError, KeyError, TypeError):
                    continue
    except OSError:
        sys.exit(f"no status line log at {path}: statusline.py install prints the setting with --log")
    return path, rows


def all_weight(start, end):
    """W of every transcript on this computer (every project, agents included) between start and end."""
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    total = 0.0
    for path in glob.glob(os.path.join(base, "projects", "**", "*.jsonl"), recursive=True):
        try:
            if datetime.datetime.fromtimestamp(os.path.getmtime(path)) < start:
                continue
        except OSError:
            continue
        for t, m, u in messages(path):
            at = local(t)
            if at is not None and start <= at <= end:
                total += weight(u, m)
    return total


def calibrate(env, plan):
    t = load_table()
    path, rows = log_rows(env)
    periods = {}
    for at, pct, reset in rows:
        periods.setdefault(reset, []).append((at, pct))
    best = None
    for reset, pts in periods.items():
        pts.sort()
        rise = pts[-1][1] - pts[0][1]
        if rise >= MIN_RISE and (best is None or rise > best[2]):
            best = (pts[0][0], pts[-1][0], rise)
    if not best:
        print(f"not enough yet: {len(rows)} rows in {path}; needs a rise of {MIN_RISE} points in one reset period")
        return
    start, end, rise = best
    w = all_weight(start, end)
    per = w / rise
    print(f"W per 1% of the week: {mw(per)} ({mw(w)} W over {rise:.0f} points, {start:%Y-%m-%d %H:%M} to "
          f"{end:%Y-%m-%d %H:%M})")
    print(f"this plan's week: {mw(100 * per)} W. A low figure: use on other devices and claude.ai counts toward the "
          "plan but is not in these transcripts.")
    p = plan_of(plan, t["plans"])
    if p:
        print(f"Pro week: {mw(100 * per / t['plans'][p])} W (from {p}, a low figure), the value for pro_week_w "
              "in data/plan-costs.json")
    else:
        print("Pro week: name the plan (cost.py calibrate pro|max5|max20)")


def context(env):
    folder = projects_dir(env)
    paths = sorted(glob.glob(os.path.join(folder, "*.jsonl")), key=os.path.getmtime, reverse=True)
    for path in paths:
        title, first, last = "", None, None
        try:
            fh = open(path, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"custom-title"' not in line and '"assistant"' not in line and first is not None:
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if first is None and d.get("timestamp"):
                    first = local(d["timestamp"])
                if d.get("type") == "custom-title":
                    title = d.get("customTitle") or title
                u = (d.get("message") or {}).get("usage") if d.get("type") == "assistant" else None
                if u:
                    last = u
        if title != TITLE:
            continue
        ctx = sum((last or {}).get(k) or 0 for k in ("input_tokens", "cache_read_input_tokens",
                                                     "cache_creation_input_tokens"))
        try:
            limit = int(env.get("COORDINATOR_CONTEXT") or 200000)
        except ValueError:
            print(f"COORDINATOR_CONTEXT={env.get('COORDINATOR_CONTEXT')} is not a number: using 200000",
                  file=sys.stderr)
            limit = 200000
        old = first is not None and first.date() < datetime.date.today()
        print(f"coordinator context {ctx // 1000}k, started {first.date() if first else 'unknown'}: "
              + ("hand off" if old or ctx > limit else "keep"))
        return
    sys.exit(f"no session titled {TITLE!r} in {folder}")


def main():
    sys.stdout.reconfigure(errors="replace")
    args = sys.argv[1:]
    explicit = None
    if "--env" in args:
        i = args.index("--env")
        if i + 1 >= len(args):
            sys.exit("--env takes a value")
        explicit = args[i + 1]
        del args[i:i + 2]
    if not args or args[0] not in ("table", "calibrate", "context") or len(args) > 2:
        sys.exit(__doc__)
    env = jsenv.load(explicit, __file__)
    plan = args[1] if len(args) > 1 else (env.get("PLAN") or "")
    if args[0] == "table":
        table(env, plan)
    elif args[0] == "calibrate":
        calibrate(env, plan)
    else:
        context(env)


if __name__ == "__main__":
    main()
