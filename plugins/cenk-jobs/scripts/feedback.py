"""Employer replies as feedback for the fit check: one line per job in FEEDBACK_LOG (default
apply/reply-feedback.jsonl), read back as clues and compared with the fit scores. Scripts only: no model.

python -I feedback.py add <job id> invitation|rejection|silence [not_fit="<what did not fit>"]
    one line for the job: the date, the outcome, the CV variant, the role type (from the title), the fit's score,
    grade and reason (from the tracker), and what did not fit (from the reply and the posting). A job's newer line
    replaces its older one. Example: feedback.py add J12 rejection not_fit="payments domain; Kotlin main language"
python -I feedback.py silent [--days 14] [--add]
    submitted jobs with no reply line after that many days since the application; --add writes a silence line each.
python -I feedback.py clues
    writes FIT_CLUES (default apply/fit-clues.md): replies by role type and by CV variant, and the recent
    rejections' not-fit lines. The fit check reads it as clues, never as a reason to skip a job.
python -I feedback.py analyse
    replies by score band (5 points) and by grade, and proposed FIT_SETTINGS grade changes; it changes nothing.
    Proposals: a band at or above "normal" with 5+ replies and no invitation -> raise "normal" past it; a band
    under "normal" with 5+ replies and an invitation rate at least the normal band's -> lower "normal" to it.
Add --env <job-search.env> anywhere to pick the env file. Exit 1 on bad arguments or an unknown job id.
"""
import collections
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import choices  # noqa: E402
import jsenv  # noqa: E402
from trackerlib import companies, expand_row  # noqa: E402

OUTCOMES = ("invitation", "rejection", "silence")
MIN_REPLIES = 5
# Role type from the title, first match wins (the 19 Nov reply analysis' groups).
ROLE_TYPES = (
    ("head-director", r"\b(head|director|vp|vice president)\b"),
    ("staff-principal", r"\b(staff|principal|distinguished)\b"),
    ("senior-em", r"\b(senior|group|sr\.?)\s+(engineering\s+)?manager\b|\bmanager\s+(ii|2|of managers)\b"),
    ("em", r"\bmanager\b"),
    ("architect", r"\barchitect\b"),
    ("team-tech-lead", r"\blead\b"),
    ("senior-ic", r"."),
)


def role_type(title):
    for name, pattern in ROLE_TYPES:
        if re.search(pattern, title or "", re.I):
            return name
    return "senior-ic"


def log_path(env):
    return env.path("FEEDBACK_LOG") if env.get("FEEDBACK_LOG") else os.path.join(env.home, "apply",
                                                                                 "reply-feedback.jsonl")


def read_log(env):
    """{job id: line}, the newest line per job."""
    out = {}
    try:
        with open(log_path(env), encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("job"):
                    out[row["job"]] = row
    except OSError:
        pass
    return out


def write_log(env, rows):
    path = log_path(env)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for row in sorted(rows.values(), key=lambda r: (r.get("date", ""), r["job"])):
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def tracker_jobs(env):
    path = env.path("TRACKER")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return {j["id"]: (c.get("name", ""), expand_row(path, j)) for c, j in companies(data) if j.get("id")}


def line_of(job_id, company, job, outcome, not_fit):
    prep = job.get("prep") or {}
    return {"date": datetime.date.today().isoformat(), "job": job_id, "company": company,
            "title": job.get("title") or prep.get("title") or "", "outcome": outcome,
            "variant": prep.get("variant") or job.get("variant") or "", "role_type": role_type(job.get("title")),
            "score": prep.get("score"), "grade": prep.get("grade") or job.get("grade") or "",
            "fit_reason": prep.get("reason") or "", "not_fit": not_fit, "applied": job.get("applied") or ""}


def add(env, rest):
    if len(rest) < 2 or rest[1] not in OUTCOMES:
        sys.exit("add takes <job id> invitation|rejection|silence [not_fit=\"...\"]")
    not_fit = next((r.split("=", 1)[1] for r in rest[2:] if r.startswith("not_fit=")), "")
    jobs = tracker_jobs(env)
    if rest[0] not in jobs:
        sys.exit(f"{rest[0]}: not in the tracker")
    rows = read_log(env)
    company, job = jobs[rest[0]]
    rows[rest[0]] = line_of(rest[0], company, job, rest[1], not_fit)
    write_log(env, rows)
    print(f"feedback {rest[0]}: {rest[1]} ({rows[rest[0]]['role_type']}, {rows[rest[0]]['variant'] or 'no variant'})")


def silent(env, rest):
    days = 14
    if "--days" in rest:
        i = rest.index("--days")
        if i + 1 >= len(rest) or not rest[i + 1].isdigit():
            sys.exit("--days takes a number")
        days = int(rest[i + 1])
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    rows = read_log(env)
    quiet = [(i, c, j) for i, (c, j) in tracker_jobs(env).items()
             if j.get("status") == "submitted" and str(j.get("applied") or "9999") <= cutoff and i not in rows]
    for i, c, j in quiet:
        print(f"{i} | {c} | {j.get('title', '')} | applied {j.get('applied')}")
        if "--add" in rest:
            rows[i] = line_of(i, c, j, "silence", "")
    if "--add" in rest and quiet:
        write_log(env, rows)
    print(f"silent past {days} days: {len(quiet)}" + (" (silence lines written)" if "--add" in rest and quiet else ""))


def counts(rows, key):
    table = collections.defaultdict(collections.Counter)
    for r in rows:
        table[r.get(key) or "-"][r["outcome"]] += 1
    return table


def clues(env):
    rows = list(read_log(env).values())
    path = env.path("FIT_CLUES") if env.get("FIT_CLUES") else os.path.join(env.home, "apply", "fit-clues.md")
    out = [f"# Earlier replies ({len(rows)}), as clues for the fit check, never a reason to skip", ""]
    for key, label in (("role_type", "role type"), ("variant", "CV variant")):
        out.append(f"## By {label}: invitation / rejection / silence")
        for name, c in sorted(counts(rows, key).items(), key=lambda kv: -sum(kv[1].values())):
            out.append(f"- {name}: {c['invitation']} / {c['rejection']} / {c['silence']}")
        out.append("")
    recent = [r for r in sorted(rows, key=lambda r: r.get("date", ""), reverse=True)
              if r["outcome"] == "rejection" and r.get("not_fit")][:20]
    out.append("## Recent rejections: what did not fit")
    out += [f"- {r['role_type']}, {r.get('variant') or 'no variant'}: {r['not_fit']}" for r in recent] or ["- none yet"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")
    print(f"{path}: {len(rows)} replies, {len(recent)} not-fit lines")


def rate(c):
    n = sum(c.values())
    return c["invitation"] / n if n else 0.0


def analyse(env):
    rows = [r for r in read_log(env).values() if isinstance(r.get("score"), (int, float))]
    bands = choices.fit_settings(env)["grades"]
    by_band = collections.defaultdict(collections.Counter)
    for r in rows:
        by_band[int(r["score"]) // 5 * 5][r["outcome"]] += 1
    print(f"replies with a score: {len(rows)}")
    print("band    | invitation | rejection | silence")
    for b in sorted(by_band, reverse=True):
        c = by_band[b]
        print(f"{b:3}-{b + 4:<3} | {c['invitation']:10} | {c['rejection']:9} | {c['silence']:7}")
    for g, c in sorted(counts(rows, "grade").items()):
        print(f"grade {g}: {c['invitation']} / {c['rejection']} / {c['silence']}")
    normal = collections.Counter()
    for b, c in by_band.items():
        if bands["normal"] <= b < bands["high"]:
            normal.update(c)
    proposals = []
    for b in sorted(by_band):
        c, n = by_band[b], sum(by_band[b].values())
        if n < MIN_REPLIES:
            continue
        if bands["normal"] <= b < bands["high"] and not c["invitation"]:
            proposals.append(f"raise normal from {bands['normal']} to {b + 5}: {n} replies at {b}-{b + 4}, no invitation")
        if b < bands["normal"] and sum(normal.values()) and rate(c) >= rate(normal) and c["invitation"]:
            proposals.append(f"lower normal from {bands['normal']} to {b}: {b}-{b + 4} invited {rate(c):.0%}, "
                             f"the normal band {rate(normal):.0%}")
    for p in proposals or ["no change proposed (too few replies or no clear band)"]:
        print("proposal: " + p)


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
    if not args or args[0] not in ("add", "silent", "clues", "analyse"):
        sys.exit(__doc__)
    env = jsenv.load(explicit, __file__)
    cmd, rest = args[0], args[1:]
    if cmd == "add":
        add(env, rest)
    elif cmd == "silent":
        silent(env, rest)
    elif cmd == "clues":
        clues(env)
    else:
        analyse(env)


if __name__ == "__main__":
    main()
