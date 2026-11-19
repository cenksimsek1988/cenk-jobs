"""The person's cost choices in job-search.env: one key per choice, asked at setup, changed any time by saying so.

    choices.py show                 every choice with its value, and "(default)" where the file sets none
    choices.py workflow             the choices the screen-and-prepare workflow takes, as JSON args
    choices.py set KEY=value ...    checks each value and writes it into job-search.env (setup and the person's word)
    choices.py suggest pro|max5|max20|other
                                    the defaults setup proposes for that plan; never written without the person's yes
    choices.py grade <prepared-jobs.json>
                                    each job's grade from its gaps (high, normal, or skip with the reason)

Keys (default first):
    WRITER_MODEL    opus | sonnet            letters and free text by Opus, or by the cheaper model with its review
    EMPLOYER_CHECK  cheap | free             the cheap model check where the free lookup cannot decide, or none
    APPLY           auto | list              fill and send, or only a list of fitting jobs with links
    APPLY_FITS      normal | high            apply to good fits (no gap or one soft gap), or only to high (no gap)
    LETTERS         asked | always | never   a letter where the form has or may have a field, always, or never
    ASK_FIRST       send,free_text           the steps that wait for the person (send, free_text, interview);
                                             empty: all alone. Without the key: free_text, and send when
                                             APPLY_MODE=review (what a folder from before 0.35.0 did)
    CALENDAR        auto | self              Claude books slots and keeps the calendar, or only records the date
    MAX_NEW_PER_RUN 30 | <n> | unlimited     postings one run takes into the funnel
    SESSION_MODEL   sonnet | opus | haiku | (empty)   the model new sub-sessions start with; empty: the main
                                             session's own (essays and study always take it)
    PLAN            pro | max5 | max20 | other   only to suggest defaults; never decides alone (max: an older max5)
Example: `choices.py set APPLY_FITS=high LETTERS=never` writes both lines, each replacing the key's old line.
Add --env <job-search.env> anywhere to pick the env file.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jsenv  # noqa: E402

STEPS = ("send", "free_text", "interview")
KEYS = {
    "WRITER_MODEL": (("opus", "sonnet"), "opus"),
    "EMPLOYER_CHECK": (("cheap", "free"), "cheap"),
    "APPLY": (("auto", "list"), "auto"),
    "APPLY_FITS": (("normal", "high"), "normal"),
    "LETTERS": (("asked", "always", "never"), "asked"),
    "ASK_FIRST": (None, "send,free_text"),
    "CALENDAR": (("auto", "self"), "auto"),
    "MAX_NEW_PER_RUN": (None, "30"),
    "SESSION_MODEL": (("sonnet", "opus", "haiku", ""), "sonnet"),
    "PLAN": (("pro", "max5", "max20", "max", "other", ""), ""),
}
SUGGEST = {"pro": {"APPLY": "list", "LETTERS": "never", "SEARCH_DAYS": "Mon"}, "max5": {}, "max20": {}, "max": {}, "other": {}}
SOFT = ("missing_must_have", "pay_below", "seniority")


def problem(key, value):
    """Why a value is not valid for the key, or None."""
    allowed, _ = KEYS[key]
    if allowed:
        return None if value in allowed else f"{key} is one of {', '.join(allowed)}: got {value!r}"
    if key == "ASK_FIRST":
        bad = [s for s in value.split(",") if s.strip() and s.strip() not in STEPS]
        return f"ASK_FIRST takes {', '.join(STEPS)}, comma-separated: got {', '.join(bad)}" if bad else None
    return None if value == "unlimited" or value.isdigit() else f"MAX_NEW_PER_RUN is a number or unlimited: got {value!r}"


def value(env, key):
    """(value, from_file): the file's value, else the default. ASK_FIRST without its key follows APPLY_MODE."""
    if key in env and (env[key] or key == "ASK_FIRST"):
        return env[key].strip().lower().replace(" ", ""), True
    if key == "ASK_FIRST":  # a folder set up before 0.35.0 keeps what it did: drafts wait for approval; send alone
        return ("send,free_text" if env.get("APPLY_MODE", "").strip().lower() == "review" else "free_text"), False
    return KEYS[key][1], False


def ask_first(env):
    return [s for s in value(env, "ASK_FIRST")[0].split(",") if s in STEPS]


def workflow_args(env):
    get = lambda k: value(env, k)[0]  # noqa: E731
    return {"writerModel": get("WRITER_MODEL"), "employerCheck": get("EMPLOYER_CHECK"), "apply": get("APPLY"),
            "applyFits": get("APPLY_FITS"), "letters": get("LETTERS"), "askFirst": ask_first(env)}


def grade(job, apply_fits="normal"):
    """(grade, reason): high (no gap), normal (one soft gap), or "" with the reason the job is skipped.

    A soft gap: one must-have missing, pay up to 10% under the target, or seniority one step off. A hard gap or two
    soft gaps: skipped. The person reads only "high" and "normal"; a weaker fit is skipped as a weak fit.
    Example: gaps [{"kind": "pay_below", "what": "5% under"}] -> ("normal", "")."""
    gaps = job.get("gaps")
    if job.get("action") != "apply" or gaps is None:
        return job.get("grade", ""), ""
    what = "; ".join(str(g.get("what", "")) for g in gaps)
    if any(g.get("kind") not in SOFT for g in gaps):
        return "", "a hard gap: " + what
    soft = len(gaps)
    if soft > 1:
        return "", "weak fit: " + what
    if soft == 1 and apply_fits == "high":
        return "", "not a high fit (APPLY_FITS=high): " + what
    return ("high" if soft == 0 else "normal"), ""


def graded(job, apply_fits="normal"):
    """The job with its grade; a job below the person's level becomes a skip with the reason."""
    g, why = grade(job, apply_fits)
    out = dict(job, grade=g)
    if why:
        out.update(action="skip", reason=why)
    return out


def write(env, pairs):
    """Each KEY=value into the env file: the key's line replaced where it has one, else appended."""
    with open(env.file, encoding="utf-8", newline="") as fh:
        text = fh.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    for key, val in pairs:
        line = f"{key}={val}"
        pattern = re.compile(rf"^{key}=.*$", re.M)
        if pattern.search(text):
            text = pattern.sub(lambda _: line, text, count=1)
        else:
            text = text.rstrip("\r\n") + nl + line + nl
    with open(env.file, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def main():
    args = sys.argv[1:]
    explicit = None
    if "--env" in args:
        i = args.index("--env")
        if i + 1 >= len(args):
            sys.exit("--env takes the path of a job-search.env")
        explicit = args[i + 1]
        del args[i:i + 2]
    if not args:
        sys.exit(__doc__)
    cmd, rest = args[0], args[1:]
    if cmd == "grade":
        if not rest:
            sys.exit("grade takes a prepared-jobs JSON file")
        level = value(jsenv.load(explicit, __file__), "APPLY_FITS")[0]
        with open(rest[0], encoding="utf-8") as fh:
            for j in json.load(fh).get("jobs", []):
                g = graded(j, level)
                print(" | ".join((str(j.get("id", "")), g.get("action", ""), g.get("grade") or "-", g.get("reason", ""))))
        return
    env = jsenv.load(explicit, __file__)
    if cmd == "show":
        for key in KEYS:
            val, own = value(env, key)
            older = key == "ASK_FIRST" and "ASK_FIRST" not in env
            print(f"{key}={val}" + ("" if own else "  (older folder: from APPLY_MODE)" if older else "  (default)"))
    elif cmd == "workflow":
        print(json.dumps(workflow_args(env)))
    elif cmd == "suggest":
        if not rest or rest[0] not in SUGGEST:
            sys.exit("suggest takes pro, max5, max20 or other")
        # SEARCH_DAYS is set through /cenk-jobs:schedule, with the task itself, never with `set`.
        merged = {k: KEYS[k][1] for k in KEYS if k != "PLAN"} | SUGGEST[rest[0]] | {"PLAN": rest[0]}
        for key, val in merged.items():
            print(f"{key}={val}")
    elif cmd == "set":
        pairs = []
        for item in rest:
            key, sep, val = item.partition("=")
            key, val = key.strip().upper(), val.strip().lower().replace(" ", "")
            if not sep or key not in KEYS:
                sys.exit(f"set takes KEY=value with KEY one of {', '.join(KEYS)}: got {item!r}")
            why = problem(key, val)
            if why:
                sys.exit(why)
            pairs.append((key, val))
        if not pairs:
            sys.exit("set takes at least one KEY=value")
        write(env, pairs)
        for key, val in pairs:
            print(f"set {key}={val}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
