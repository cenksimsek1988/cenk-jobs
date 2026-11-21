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
    APPLY_FITS      normal | high            auto-send high and normal fits (at most one kind of soft gap), or only
                                             high (none)
    LONG_SHOTS_PER_DAY 0 | <n>               long-shots and weak fits (two or more kinds of soft gaps) auto-sent a day,
                                             after the high and normal ones; 0: none, they stay listed for the
                                             person
    FIT_MODEL       sonnet | opus | opus-max the fit check's model: Sonnet (about 60k tokens an employer), Opus at
                                             medium effort (about 100k), which reads the requirements closer, or
                                             Opus at max effort (about 150-300k, estimated)
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
    "FIT_MODEL": (("sonnet", "opus", "opus-max"), "sonnet"),
    "EMAILED_CODES": (("off", "on"), "off"),
    "OPTIONAL_FIELDS": (("off", "fill"), "off"),
    "PLAN": (("pro", "max5", "max20", "max", "other", ""), ""),
}
SUGGEST = {"pro": {"APPLY": "list", "LETTERS": "never", "SEARCH_DAYS": "Mon"}, "max5": {}, "max20": {}, "max": {}, "other": {}}
# The gap kinds that never skip a job (0.46.0); any other kind ("hard") does. One list: the workflow gets it as
# args.fit.soft (workflow_args), so the two graders never drift.
SOFT = ("missing_must_have", "pay_below", "seniority", "stack", "domain", "scope", "relocation")


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


# The fit settings' defaults: a requirement's weight by its place in the posting (the score, kept as information
# since 0.46.0), the score bands (read by feedback.py's analysis only), the channel notes, and the soft gap kinds.
# The person's own values: FIT_SETTINGS (default apply/fit-settings.json), as in templates/fit-settings-example.json.
FIT_DEFAULTS = {"weights": {"title": 4, "must_years": 3, "must": 2, "nice": 1},
                "grades": {"high": 80, "normal": 65, "long_shot": 50}, "channel_notes": {}, "soft": list(SOFT)}
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
    return {"writerModel": get("WRITER_MODEL"), "fitModel": get("FIT_MODEL"), "employerCheck": get("EMPLOYER_CHECK"),
            "apply": get("APPLY"), "applyFits": get("APPLY_FITS"), "longShots": int(get("LONG_SHOTS_PER_DAY") or 0),
            "letters": get("LETTERS"), "askFirst": ask_first(env), "fit": fit_settings(env)}


def setting_cut(note, env):
    """The key of the setting whose cut skipped a fit, when the person's settings no longer make it, else "".
    Example: "fit: not a high fit (APPLY_FITS=high): Go" with APPLY_FITS=normal -> "APPLY_FITS"; a hard gap -> ""."""
    note = str(note or "")
    if "(APPLY_FITS=high)" in note and value(env, "APPLY_FITS")[0] != "high":
        return "APPLY_FITS"
    room = value(env, "LONG_SHOTS_PER_DAY")[0]
    if "LONG_SHOTS_PER_DAY=0" in note and room.isdigit() and int(room) > 0:
        return "LONG_SHOTS_PER_DAY"
    return ""


def gap_count(gaps):
    """The soft gap kinds, counted (the 19 Nov reply analysis' gap groups): each kind 1, however many gaps it holds;
    a domain kind with a gap of no adjacent real fact (closest "none" or empty) 2. Example: Go and Kubernetes
    missing -> 1 (stack); Go missing and a payments domain with no adjacent fact -> 3."""
    none = any(g.get("kind") == "domain" and str(g.get("closest") or "").strip().lower() in ("", "none") for g in gaps)
    return len({g.get("kind") for g in gaps}) + (1 if none else 0)


def grade(job, apply_fits="normal", settings=None, long_shots=0):
    """(grade, reason): high, normal, long-shot, weak or unread; a reason means the job is a skip, listed with it.

    A hard gap (place, work mode, eligibility, a required language, a security clearance, pay far under the rule) is
    a skip with grade "". A posting not read in full is "unread", a skip that waits for the next run's fit check with
    the posting text. Else the kinds of soft gaps decide (0.46.0; 19 Nov reply analysis: 72% of rejections had two
    or more gap groups, 31% of invitations): 0 high, 1 normal, 2 long-shot, 3 or more weak (gap_count). A long-shot or
    a weak fit goes on only within LONG_SHOTS_PER_DAY (0: a skip, listed for the person); a normal fit with
    APPLY_FITS=high is a skip. A read posting with no must-haves and no requirements counts one kind ("no
    evidence"): never high. The weighted score stays on the job as information (graded). Example: two stack gaps ->
    ("normal", ""); a domain gap with no adjacent fact -> ("long-shot", "long-shot: 2 soft gap kinds
    (LONG_SHOTS_PER_DAY=0): <what>")."""
    gaps = job.get("gaps")
    if job.get("action") != "apply" or (gaps is None and job.get("requirements") is None):
        return job.get("grade", ""), ""
    gaps = gaps or []
    soft = (settings or FIT_DEFAULTS).get("soft") or SOFT
    what = "; ".join(str(g.get("what", "")) for g in gaps)
    if any(g.get("kind") not in soft for g in gaps):
        return "", "a hard gap: " + what
    if job.get("read", "full") != "full":
        return "unread", "unread: the posting text was not read; the next run checks it again"
    n = gap_count(gaps)
    reqs = [r for r in job.get("requirements") or [] if isinstance(r, dict)]
    if isinstance(job.get("must_haves"), list) and not job["must_haves"] and not reqs and not n:
        n, what = 1, "no evidence: no must-haves read"  # a read posting with nothing checked is never high
    g = "high" if n == 0 else "normal" if n == 1 else "long-shot" if n == 2 else "weak"
    if g in ("long-shot", "weak") and not long_shots:
        return g, f"{g}: {n} soft gap kinds (LONG_SHOTS_PER_DAY=0): {what}"
    if g == "normal" and apply_fits == "high":
        return g, f"not a high fit (APPLY_FITS=high): {what}"
    return g, ""


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
