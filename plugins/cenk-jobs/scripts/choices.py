"""The person's cost choices in job-search.env: one key per choice, asked at setup, changed any time by saying so.

    choices.py show                 every choice with its value, and "(default)" where the file sets none
    choices.py workflow             the choices the screen-and-prepare workflow takes, as JSON args
    choices.py set KEY=value ...    checks each value and writes it into job-search.env (setup and the person's word)
    choices.py suggest pro|max5|max20|other
                                    the defaults setup proposes for that plan; never written without the person's yes
    choices.py grade <prepared-jobs.json>
                                    each job's score and grade (high, normal, long-shot, weak, unread, or skip with
                                    the reason)
    choices.py fit                  the fit settings in use (FIT_SETTINGS, default apply/fit-settings.json, over the
                                    defaults), as JSON

Keys (default first):
    WRITER_MODEL    opus | sonnet            letters and free text by Opus, or by the cheaper model with its review
    EMPLOYER_CHECK  cheap | free             the cheap model check where the free lookup cannot decide, or none
    APPLY           auto | list              fill and send, or only a list of fitting jobs with links
    APPLY_FITS      normal | high            auto-send high and normal fits (score 65 or more), or only high (80)
    LONG_SHOTS_PER_DAY 0 | <n>               long-shots (score 50-64) auto-sent a day, after the high and normal
                                             ones; 0: none, they stay listed for the person
    LETTERS         asked | always | never   a letter where the form has or may have a field (an optional field
                                             gets it too), always, or never
    EMAILED_CODES   off | on                 on: the session reads an application's emailed code or confirmation
                                             link in Gmail (the form just submitted, its own sender, 15 minutes);
                                             sign-in and sign-up codes, CAPTCHAs and passwords stay the person's
    OPTIONAL_FIELDS off | fill               fill: salutation, gender, demographics and EEO from the profile; off:
                                             blank, or "prefer not to say" where required. Mail opt-ins stay off
    ASK_FIRST       send,free_text           the steps that wait for the person (send, free_text, interview);
                                             empty: all alone. Without the key: free_text, and send when
                                             APPLY_MODE=review (what a folder from before 0.35.0 did)
    CALENDAR        auto | self              Claude books slots and keeps the calendar, or only records the date
    MAX_NEW_PER_RUN 30 | <n> | unlimited     postings one run takes into the funnel
    SESSION_MODEL   sonnet | opus | haiku | (empty)   the model new sub-sessions start with; empty: sonnet
                                             (essays and study always take the main session's model)
    PLAN            pro | max5 | max20 | other   only to suggest defaults; never decides alone (max: an older max5)
Essays (`show` names it): "auto" is ASK_FIRST without free_text, "ask" with it; no key of its own.
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
    "LONG_SHOTS_PER_DAY": (None, "0"),
    "SESSION_MODEL": (("sonnet", "opus", "haiku", ""), "sonnet"),
    "EMAILED_CODES": (("off", "on"), "off"),
    "OPTIONAL_FIELDS": (("off", "fill"), "off"),
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
    if key == "LONG_SHOTS_PER_DAY":
        return None if value.isdigit() else f"LONG_SHOTS_PER_DAY is a number: got {value!r}"
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


# The fit score's defaults (19 Nov reply analysis): a requirement's weight by its place in the posting, and the
# grade bands. The person's own values: FIT_SETTINGS (default apply/fit-settings.json), as in
# templates/fit-settings-example.json.
FIT_DEFAULTS = {"weights": {"title": 4, "must_years": 3, "must": 2, "nice": 1},
                "grades": {"high": 80, "normal": 65, "long_shot": 50}, "channel_notes": {}}
LEVEL_MATCH = {"hands_on": 1.0, "adjacent": 0.5, "absent": 0.0}


def fit_settings(env):
    """The fit settings: the person's file over the defaults, key by key."""
    path = env.path("FIT_SETTINGS") if env.get("FIT_SETTINGS") else os.path.join(env.home, "apply",
                                                                                 "fit-settings.json")
    own = {}
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as fh:
                own = json.load(fh)
        except ValueError as problem:
            sys.exit(f"{path}: not readable as JSON: {problem}")
    return {k: ({**v, **(own.get(k) or {})} if isinstance(v, dict) else own.get(k, v))
            for k, v in FIT_DEFAULTS.items()}


def match_of(req):
    """A requirement's match, 0 to 1: years held / years asked (capped at 1) when years are asked, else its level
    (hands_on 1, adjacent 0.5, absent 0)."""
    try:
        asked = float(req.get("years_asked") or 0)
        if asked > 0:
            return min(float(req.get("years_held") or 0) / asked, 1.0)
    except (TypeError, ValueError):
        pass
    return LEVEL_MATCH.get(req.get("level"), 0.0)


def score(job, settings=None):
    """The weighted requirement score, 0-100, or None without requirements: sum(weight x match) / sum(weights).
    Example: the title skill held (4 x 1) and a must-have with 5 of 10 years (3 x 0.5): 5.5 / 7 -> 79."""
    weights = (settings or FIT_DEFAULTS)["weights"]
    reqs = [r for r in job.get("requirements") or [] if isinstance(r, dict)]
    total = sum(float(weights.get(r.get("place"), 0)) for r in reqs)
    if not total:
        return None
    return round(100 * sum(float(weights.get(r.get("place"), 0)) * match_of(r) for r in reqs) / total)


def workflow_args(env):
    get = lambda k: value(env, k)[0]  # noqa: E731
    return {"writerModel": get("WRITER_MODEL"), "employerCheck": get("EMPLOYER_CHECK"), "apply": get("APPLY"),
            "applyFits": get("APPLY_FITS"), "longShots": int(get("LONG_SHOTS_PER_DAY") or 0),
            "letters": get("LETTERS"), "askFirst": ask_first(env), "fit": fit_settings(env)}


def grade(job, apply_fits="normal", settings=None, long_shots=0):
    """(grade, reason): high, normal, long-shot, weak or unread; a reason means the job is a skip, listed with it.

    A hard gap (place, work mode, eligibility, a required language, a security clearance) is a skip with grade "".
    A posting not read in full is "unread", a skip that waits for the next run's fit check with the posting text.
    Else the score's band (FIT_SETTINGS grades): 80+ high, 65-79 normal, 50-64 long-shot, under 50 weak (a skip,
    listed for the person). A normal fit with APPLY_FITS=high, and a long-shot with LONG_SHOTS_PER_DAY=0, is a skip
    too. A job without requirements (before 0.41.0) is graded from its gaps: none high, one soft normal, more weak.
    Example: requirements scoring 72 -> ("normal", ""); scoring 40 -> ("weak", "weak fit: score 40")."""
    gaps = job.get("gaps")
    if job.get("action") != "apply" or (gaps is None and job.get("requirements") is None):
        return job.get("grade", ""), ""
    gaps = gaps or []
    what = "; ".join(str(g.get("what", "")) for g in gaps)
    if any(g.get("kind") not in SOFT for g in gaps):
        return "", "a hard gap: " + what
    # Before the score: a posting read in part or not at all may have no requirements, hence no score.
    if job.get("read", "full") != "full":
        return "unread", "unread: the posting text was not read; the next run checks it again"
    s = score(job, settings)
    if s is not None:
        bands = (settings or FIT_DEFAULTS)["grades"]
        g = ("high" if s >= bands["high"] else "normal" if s >= bands["normal"]
             else "long-shot" if s >= bands["long_shot"] else "weak")
        if g == "weak":
            return g, f"weak fit: score {s}"
        if g == "long-shot" and not long_shots:
            return g, f"long-shot: score {s} (LONG_SHOTS_PER_DAY=0)"
        if g == "normal" and apply_fits == "high":
            return g, f"not a high fit (APPLY_FITS=high): score {s}"
        return g, ""
    soft = len(gaps)
    if soft > 1:
        return "weak", "weak fit: " + what
    if soft == 1 and apply_fits == "high":
        return "normal", "not a high fit (APPLY_FITS=high): " + what
    return ("high" if soft == 0 else "normal"), ""


def graded(job, apply_fits="normal", settings=None, long_shots=0):
    """The job with its grade and score; a job below the person's level becomes a skip with the reason."""
    g, why = grade(job, apply_fits, settings, long_shots)
    out = dict(job, grade=g)
    s = score(job, settings)
    if s is not None:
        out["score"] = s
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
        env = jsenv.load(explicit, __file__)
        level, settings = value(env, "APPLY_FITS")[0], fit_settings(env)
        long_shots = int(value(env, "LONG_SHOTS_PER_DAY")[0] or 0)
        with open(rest[0], encoding="utf-8") as fh:
            for j in json.load(fh).get("jobs", []):
                g = graded(j, level, settings, long_shots)
                print(" | ".join((str(j.get("id", "")), g.get("action", ""), g.get("grade") or "-",
                                  str(g.get("score", "-")), g.get("reason", ""))))
        return
    env = jsenv.load(explicit, __file__)
    if cmd == "fit":
        print(json.dumps(fit_settings(env)))
        return
    if cmd == "show":
        for key in KEYS:
            val, own = value(env, key)
            older = key == "ASK_FIRST" and "ASK_FIRST" not in env
            print(f"{key}={val}" + ("" if own else "  (older folder: from APPLY_MODE)" if older else "  (default)"))
        # Essays are no key of their own: ASK_FIRST with free_text asks first, without it writes alone.
        print(f"essays: {'ask' if 'free_text' in ask_first(env) else 'auto'}  (ASK_FIRST free_text)")
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
