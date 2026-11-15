"""How many tokens the job search used, per run and per kind of agent, from this computer's Claude Code transcripts
of the main folder. Numbers only: it never prints or keeps message text, names or descriptions, and sends nothing.

python -I token_report.py [--days 14] [--json <file>]
    one line per run in the usage log (its variant, minutes, W of the main session and of its agents, good-fit jobs
    once counted, W per good-fit job), then one line per agent kind (count, W per agent, model).
    --json: the same numbers as one JSON file, for a person who wants to share them with the plugin's developer.
W: one fresh input token of the largest model, weighted by cost: cache write 1.25, cache read 0.1, output 5; model
price Opus 1, Sonnet 0.6, Haiku 0.2 (a comparison scale, not a bill).
Transcripts: <CLAUDE_CONFIG_DIR, else ~/.claude>/projects/<the main folder's path with every sign other than a
letter or digit as "-">/. Agents: <session>/subagents/**/agent-*.jsonl, their kind from the agent's meta file.
Add --env <job-search.env> anywhere to pick the env file.
"""
import collections
import datetime
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jsenv  # noqa: E402
from variants import runs, usage_rows  # noqa: E402

PRICE = (("haiku", 0.2), ("sonnet", 0.6))


def price(model):
    return next((p for name, p in PRICE if name in (model or "")), 1.0)


def weight(usage, model):
    u = usage
    return price(model) * ((u.get("input_tokens") or 0) + 1.25 * (u.get("cache_creation_input_tokens") or 0)
                           + 0.1 * (u.get("cache_read_input_tokens") or 0) + 5 * (u.get("output_tokens") or 0))


def messages(path):
    """[(time, model, usage)] of a transcript's assistant messages, the last copy of each message id."""
    seen = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"assistant"' not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            m = d.get("message") or {} if d.get("type") == "assistant" else {}
            if m.get("usage") and m.get("id"):
                seen[m["id"]] = (d.get("timestamp") or "", m.get("model") or "", m["usage"])
    return list(seen.values())


def local(t):
    try:
        return datetime.datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
    except ValueError:
        return None


def projects_dir(env):
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    return os.path.join(base, "projects", re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(env.home)))


def main():
    args = sys.argv[1:]
    opts = {}
    for flag in ("--env", "--days", "--json"):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                sys.exit(f"{flag} takes a value")
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    if args:
        sys.exit(__doc__)
    env = jsenv.load(opts.get("--env"), __file__)
    since = datetime.datetime.now() - datetime.timedelta(days=int(opts.get("--days") or 14))
    folder = projects_dir(env)
    if not os.path.isdir(folder):
        sys.exit(f"no transcripts for this main folder on this computer ({folder})")
    main_msgs, agent_msgs, kinds = [], [], collections.defaultdict(list)
    for path in glob.glob(os.path.join(folder, "*.jsonl")):
        main_msgs += messages(path)
        session = path[:-6]
        for a in glob.glob(os.path.join(session, "subagents", "**", "agent-*.jsonl"), recursive=True):
            kind = "workflow agent" if "workflows" in a.replace("\\", "/") else "agent"
            try:
                with open(a[:-6] + ".meta.json", encoding="utf-8") as fh:
                    kind = json.load(fh).get("agentType") or kind
            except (OSError, ValueError):
                pass
            ms = [x for x in messages(a) if (local(x[0]) or since) >= since]
            agent_msgs += ms
            if ms:
                kinds[kind].append(ms)
    _, rows = usage_rows(env)
    good = {r.get("run"): r.get("good_fit") for r in rows if r.get("step") == "run-result"}
    out = {"runs": [], "agents": []}
    for start, end, variant in runs(rows):
        s, e = local(start), local(end)
        if not s or not e or e < since:
            continue
        inside = lambda t: (lambda x: x is not None and s <= x <= e)(local(t))  # noqa: E731
        mw = sum(weight(u, m) for t, m, u in main_msgs if inside(t))
        aw = sum(weight(u, m) for t, m, u in agent_msgs if inside(t))
        g = good.get(start)
        row = {"start": start[:16], "variant": variant, "minutes": round((e - s).total_seconds() / 60),
               "main_w": round(mw), "agents_w": round(aw), "good_fit": g,
               "w_per_good_fit": round((mw + aw) / g) if g else None}
        out["runs"].append(row)
        print(f"run {row['start']} {variant:10} {row['minutes']:4} min  main {mw/1e6:7.2f}M  agents {aw/1e6:6.2f}M  "
              f"good-fit {g if g is not None else '-':>3}  per good-fit "
              + (f"{row['w_per_good_fit']/1e6:6.2f}M W" if row["w_per_good_fit"]
                 else "     - (counted 7 days after the run)" if g is None else "     - (no good fit)"))
    for kind, lst in sorted(kinds.items(), key=lambda kv: -len(kv[1])):
        w = sum(weight(u, m) for ms in lst for t, m, u in ms)
        models = collections.Counter(re.sub(r"^claude-", "", ms[0][1]) for ms in lst)
        out["agents"].append({"kind": kind, "count": len(lst), "w_per_agent": round(w / len(lst)), "models": dict(models)})
        print(f"agent {kind:28} {len(lst):4}  {w/len(lst)/1e3:9.0f}k W each  {dict(models)}")
    total_main = sum(weight(u, m) for t, m, u in main_msgs if (local(t) or since) >= since)
    total_agents = sum(weight(u, m) for t, m, u in agent_msgs)
    print(f"last {opts.get('--days') or 14} days: main sessions {total_main/1e6:.1f}M W, agents {total_agents/1e6:.1f}M W")
    out["totals"] = {"days": int(opts.get("--days") or 14), "main_w": round(total_main), "agents_w": round(total_agents)}
    if opts.get("--json"):
        with open(opts["--json"], "w", encoding="utf-8", newline="\n") as fh:
            json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
