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
    choices.py fit --set work_languages=Java,Kotlin
                                    the main programming languages (and platforms, such as Android) the person has
                                    used at work, into the fit settings file (made when missing); a role in none of
                                    them is a skip (other_language). Empty clears it

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
    LETTERS         asked | always | never   a letter where the form shows a cover-letter field (an optional one
                                             too), also where a file field takes one, or never; a form not read
                                             (Easy Apply) gets one only once open and showing a field
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
from trackerlib import scope_of, terms, title_has  # noqa: E402

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
# The main programming languages (0.46.8), name: [pattern, flags ("i": any case)]. A role whose job title, or whose
# must-haves, name only languages the person has not used at work is a hard gap at every level (other_language).
# One list: the workflow gets it as args.fit.languages and Python compiles it with re.ASCII, so both graders match
# alike (spaces as [ \t], since JS's \s takes more). Plain C and R are left out: one letter matches too much. Example:
# "Lead Golang Engineer" names Go; "Go-to-market", "Go the extra mile" and "JavaScript" name neither Go nor Java. A
# must-have that starts with "Go" or "Swift" as an everyday word still matches: the fit check's hands-on level and a
# work language in the title or the must-haves keep such a role.
LANGUAGES = {
    "Go": [r"\bGo\b(?!-|[ \t]+(?:to|live|above|beyond|the)\b)|\b[Gg][Oo][Ll][Aa][Nn][Gg]\b", ""],
    "C#/.NET": [r"\bC#|\.NET\b|\b[Dd]ot[Nn]et\b", ""],
    "Python": [r"\bpython\b", "i"],
    "Rust": [r"\bRust\b", ""],
    "Java": [r"\bjava\b(?!\s*script)", "i"],
    "Kotlin": [r"\bkotlin\b", "i"],
    "Scala": [r"\bscala\b", "i"],
    "Groovy": [r"\bgroovy\b", "i"],
    "Clojure": [r"\bclojure\b", "i"],
    "C++": [r"C\+\+", ""],
    "Ruby": [r"\bruby\b", "i"],
    "PHP": [r"\bphp\b", "i"],
    "JavaScript": [r"\bjavascript\b|\bnode\.?js\b", "i"],
    "TypeScript": [r"\btypescript\b", "i"],
    "Swift": [r"\bSwift\b", ""],
    "Objective-C": [r"\bobjective-c\b", "i"],
    "Dart": [r"\bDart\b", ""],
    "Elixir": [r"\belixir\b", "i"],
    "Erlang": [r"\berlang\b", "i"],
    "Haskell": [r"\bhaskell\b", "i"],
    "F#": [r"\bF#", ""],
    "OCaml": [r"\bocaml\b", "i"],
    "Perl": [r"\bperl\b", "i"],
    "Lua": [r"\bLua\b", ""],
}
# The platforms a job title can name (0.47.0), in the same form: a title that names only platforms or languages the
# person has not used at work is an other-language role too. The title only: a must-have that names a platform
# ("integrations with Salesforce") never counts. Seen 23 Nov: 12 Android, SAP, Salesforce and frontend titles graded
# weak or long-shot for a Java record, and long-shots can be sent. Example: "Senior Android Engineer" names Android;
# "Java Developer (Android)" names Java too and stays a fit. A web framework is no platform here: "Senior React
# Developer" goes to the fit check, and so does React Native (the person's choice, 23 Nov); Flutter is a mobile
# platform like Android and iOS (0.48.0).
PLATFORMS = {
    "Android": [r"\bandroid\b", "i"],
    "iOS": [r"\biOS\b", ""],
    "Flutter": [r"\bflutter\b", "i"],
    "SAP": [r"\bSAP\b|\bABAP\b", ""],
    "Salesforce": [r"\bsalesforce\b", "i"],
    "ServiceNow": [r"\bservice[ \t-]?now\b", "i"],
    "Frontend": [r"\bfront[ \t-]?end\b", "i"],
}
# A place in hires_in that names a region, not one country: the hires_in rule is about countries, so such an entry
# always passes (a model may list "Europe" where the posting hires across it). ASCII, as the workflow's twin.
WIDE_PLACE = re.compile(r"\b(worldwide|anywhere|global(ly)?|international(ly)?|europe(an union)?|eu|eea|emea|latam|"
                        r"apac|americas|north america|asia|africa|middle east)\b", re.I | re.ASCII)


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
# since 0.46.0), the score bands (read by feedback.py's analysis only), the channel notes, the soft gap kinds, the
# main programming languages and platforms, and the person's work languages (empty: the fit check's hands-on levels
# tell). The person's own values: FIT_SETTINGS (default apply/fit-settings.json), as in
# templates/fit-settings-example.json. fit_settings adds "scope", the person's places (place_scope), never a file key.
FIT_DEFAULTS = {"weights": {"title": 4, "must_years": 3, "must": 2, "nice": 1},
                "grades": {"high": 80, "normal": 65, "long_shot": 50}, "channel_notes": {}, "soft": list(SOFT),
                "languages": LANGUAGES, "platforms": PLATFORMS, "work_languages": []}
LEVEL_MATCH = {"hands_on": 1.0, "adjacent": 0.5, "absent": 0.0}


def fit_path(env):
    return env.path("FIT_SETTINGS") if env.get("FIT_SETTINGS") else os.path.join(env.home, "apply", "fit-settings.json")


def set_work_languages(env, value):
    """work_languages into the person's fit settings file, made when missing; its other keys stay. Each name must
    be a main language (LANGUAGES) or platform (PLATFORMS). Example: "Java,Kotlin" -> {"work_languages": ["Java",
    "Kotlin"], ...}; "Java,android" -> ["Java", "Android"]."""
    given = [x.strip() for x in value.split(",") if x.strip()]
    fit = fit_settings(env)
    langs, plats = fit["languages"], fit["platforms"]
    named = lambda x: languages_in(x, langs) + languages_in(x, plats, "platforms")  # noqa: E731
    unknown = [x for x in given if not named(x)]
    if unknown:
        sys.exit(f"not a main language: {', '.join(unknown)} (the languages: {', '.join(langs)}; the platforms: "
                 f"{', '.join(plats)})")
    names = []  # the list's own names: "golang" is stored as "Go"
    for x in given:
        names += [n for n in named(x) if n not in names]
    path = fit_path(env)
    own = {}
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as fh:
                own = json.load(fh)
        except ValueError as problem:
            sys.exit(f"{path}: not readable as JSON: {problem}")
    own["work_languages"] = names
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(own, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(path + ".tmp", path)
    print(f"work_languages={','.join(names)} in {path}")


def fit_settings(env):
    """The fit settings: the person's file over the defaults, key by key, and "scope": the person's places
    (place_scope), for the hires_in rule."""
    path = fit_path(env)
    own = {}
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as fh:
                own = json.load(fh)
        except ValueError as problem:
            sys.exit(f"{path}: not readable as JSON: {problem}")
    if not isinstance(own, dict) or any(not isinstance(own.get(k) or {}, dict)
                                        for k, v in FIT_DEFAULTS.items() if isinstance(v, dict)):
        sys.exit(f"{path}: an object whose weights, grades, channel_notes, languages and platforms are objects")
    out = {k: ({**v, **(own.get(k) or {})} if isinstance(v, dict) else own.get(k, v))
           for k, v in FIT_DEFAULTS.items()}
    bad = [f"{key} {name}" for key in ("languages", "platforms") for name, entry in out[key].items()
           if not (isinstance(entry, list) and len(entry) == 2 and all(isinstance(x, str) for x in entry))]
    if bad or not isinstance(out["work_languages"], list):
        sys.exit(f"{path}: " + (f"{', '.join(bad)}: each is [pattern, flags], two strings" if bad else
                                "work_languages is a list of names"))
    out["scope"] = place_scope(env)
    return out


def place_scope(env):
    """The person's places, for the hires_in rule (hires_elsewhere): the places taken in any work mode and the remote
    regions (the master record's search scope over PLACES and REMOTE_REGIONS in job-search.env, as
    collect_postings.py reads them), and the places ruled out (NOT_PLACES), each in lower case. Example: {"places":
    ["rome"], "regions": ["italy", "eu"], "not_places": ["turin"]}."""
    regions, places = scope_of(env)
    return {"places": places if places is not None else terms(env.get("PLACES")),
            "regions": regions if regions is not None else terms(env.get("REMOTE_REGIONS")),
            "not_places": terms(env.get("NOT_PLACES"))}


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
    Example: "fit: not a high fit (APPLY_FITS=high): Go" with APPLY_FITS=normal -> "APPLY_FITS"; a hard gap -> "".
    Only the fit check's own message counts, with or without "fit: " before it (the run writes both; seen 21 Nov: 46
    of 64 without); a note the person wrote that names a setting does not."""
    note = re.sub(r"^fit:\s*", "", str(note or "").strip())
    if note.startswith("not a high fit (APPLY_FITS=high)") and value(env, "APPLY_FITS")[0] != "high":
        return "APPLY_FITS"
    room = value(env, "LONG_SHOTS_PER_DAY")[0]
    if (re.match(r"(long-shot|weak): \d+ soft gap", note) and "(LONG_SHOTS_PER_DAY=0)" in note
            and room.isdigit() and int(room) > 0):
        return "LONG_SHOTS_PER_DAY"
    return ""


def gap_count(gaps):
    """The soft gap kinds, counted (the 19 Nov reply analysis' gap groups): each kind 1, however many gaps it holds;
    a domain kind with a gap of no adjacent real fact (closest "none" or empty) 2. Example: Go and Kubernetes
    missing -> 1 (stack); Go missing and a payments domain with no adjacent fact -> 3."""
    none = any(g.get("kind") == "domain" and str(g.get("closest") or "").strip().lower() in ("", "none") for g in gaps)
    return len({g.get("kind") for g in gaps}) + (1 if none else 0)


_PATTERNS = {}


def languages_in(text, langs, kind="languages"):
    """The main programming languages (or, with the platforms list, the platforms) a text names, in the order of
    langs (the fit settings' languages or platforms). Example: "Go/Golang and Python" -> ["Go", "Python"]."""
    found = []
    for name, (pattern, flags) in langs.items():
        key = (pattern, flags)
        if key not in _PATTERNS:
            try:
                _PATTERNS[key] = re.compile(pattern, re.ASCII | (re.I if "i" in str(flags or "") else 0))
            except re.error as problem:
                sys.exit(f"fit settings: {kind} {name!r}: not a valid pattern: {problem}")
        if _PATTERNS[key].search(str(text or "")):
            found.append(name)
    return found


def other_language(job, settings=None):
    """Why a fit is an other-language role, "" when it is none (0.46.8; seen 21-22 Nov: four Go roles graded normal
    to weak and sent to a Java record): the job title names main languages or platforms and none of them is a work
    language, or the must-haves name languages, none a work language, while neither the title nor another must-have
    asks one. Platforms count in the title only (0.47.0). Work languages: the fit settings' work_languages; without
    them this rule is off and the fit check marks such a role a hard gap by its own reading (the fit prompt). Seen: a
    "lead level" title requirement naming Golang graded hands-on, so the fit check's levels cannot stand in for the
    list. A hands-on must-have ("Go or similar") never counts: the fit check found the person meets it. Nice-to-haves
    never count. Example: "Lead Golang Engineer" for work_languages ["Java"] -> "other-language role (title: Go): no
    work use in the record"; "Senior Android Engineer" -> "... (title: Android) ..."; a Java role whose must-haves
    also ask Python -> ""."""
    settings = settings or FIT_DEFAULTS
    langs, plats = settings.get("languages") or {}, settings.get("platforms") or {}
    named = ", ".join(str(x) for x in settings.get("work_languages") or [])
    work = set(languages_in(named, langs)) | set(languages_in(named, plats, "platforms")) if langs else set()
    if not work:
        return ""
    reqs = [r for r in job.get("requirements") or [] if isinstance(r, dict)]
    title_text = " | ".join([str(job.get("title") or "")] + [str(r.get("text") or "") for r in reqs
                                                              if r.get("place") == "title"])
    title = languages_in(title_text, langs) + languages_in(title_text, plats, "platforms")
    parts = ["title: " + ", ".join(title)] if title and not work & set(title) else []
    ok, asked = bool(work & set(title)), []
    for r in reqs:
        if r.get("place") not in ("must_years", "must"):
            continue
        found = languages_in(r.get("text"), langs)
        if work & set(found):
            ok = True
        elif found and r.get("level") != "hands_on":
            asked += [x for x in found if x not in asked]
    if asked and not ok:
        parts.append("must-haves: " + ", ".join(asked))
    return f"other-language role ({'; '.join(parts)}): no work use in the record" if parts else ""


def hires_elsewhere(job, settings=None):
    """Why a fit hires only outside the person's places, "" when it does not (0.47.0; seen 23 Nov: one fit model
    graded high 9 roles open only to remote workers in one other country, another called them a hard gap): the fit
    check lists the countries a remote worker must live in (hires_in, the posting's words; [] when it names none),
    and none is one of the person's places or remote regions, or each is a place ruled out: the collector's place
    rule, so the person's own country counts only when their places or regions name it (setup asks for cities and
    countries). A region entry (Europe, EMEA, Worldwide, Anywhere) always passes. Off without the person's places
    and regions (the fit settings' scope). Example: hires_in ["Poland"] for remote regions ["italy", "eu"] -> "hires
    only in Poland, outside the person's places"; ["Poland", "Italy"] -> ""; ["Europe"] -> ""."""
    scope = (settings or {}).get("scope") or {}
    wanted = [str(x) for x in list(scope.get("places") or []) + list(scope.get("regions") or [])]
    hires = job.get("hires_in") if isinstance(job.get("hires_in"), list) else []
    hires = [str(x).strip() for x in hires if str(x).strip()]
    if not wanted or not hires:
        return ""
    banned = [str(x) for x in scope.get("not_places") or []]
    if any(WIDE_PLACE.search(x) or (title_has(x, wanted) and not title_has(x, banned)) for x in hires):
        return ""
    return f"hires only in {', '.join(hires)}, outside the person's places"


def grade(job, apply_fits="normal", settings=None, long_shots=0):
    """(grade, reason): high, normal, long-shot, weak or unread; a reason means the job is a skip, listed with it.

    A hard gap (place, work mode, eligibility, a required language, a security clearance, pay far under the rule, an
    other-language role: other_language, where the title alone suffices; a posting that hires only outside the
    person's places: hires_elsewhere) is a skip with grade "". A
    posting not read in full is "unread", a skip that waits for the next run's fit check with
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
    other = other_language(job, settings) or hires_elsewhere(job, settings)
    if other:
        return "", "a hard gap: " + other
    if job.get("read", "full") != "full":
        return "unread", "unread: the posting text was not read; the next run checks it again"
    n = gap_count(gaps)
    reqs = [r for r in job.get("requirements") or [] if isinstance(r, dict)]
    if isinstance(job.get("must_haves"), list) and not job["must_haves"] and not reqs and not n:
        n, what = 1, "no evidence: no must-haves read"  # a read posting with nothing checked is never high
    # A stack the job title names that the record shows no use of counts as two kinds: at least a long-shot (0.46.6;
    # seen 21 Nov: a C#/.NET role graded normal for a Java record).
    title_absent = [str(r.get("text") or "").strip() for r in reqs
                    if r.get("place") == "title" and r.get("level") == "absent" and str(r.get("text") or "").strip()]
    if title_absent:
        n = max(n + 1, 2)
        what = "; ".join(x for x in (what, "the title asks " + ", ".join(title_absent) + ", not held") if x)
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


# The skip reasons grade() itself writes ("fit: " before them in a tracker note): such a skip was an "apply" of the
# fit check, cut by the grade.
OWN_SKIP = re.compile(r"^(fit:\s*)?(a hard gap: |unread: |(long-shot|weak): \d+ soft gap|not a high fit \()")


def regraded(prep, apply_fits="normal", settings=None, long_shots=0):
    """A stored fit (a tracker row's prep) graded again under today's rules (track.py regrade, reopen; tune-search
    reuses it): the grade's own cut undone, then graded. A skip the fit check made itself (a closed posting) stays.
    A fit from before 0.46.0 has no gap kinds: only the other-language rule grades it again, its grade stays.
    Example: a fit stored "normal" on 21 Nov whose title asks Go, for a Java record -> action "skip", reason "a hard
    gap: other-language role (title: Go): no work use in the record"."""
    prep = dict(prep or {})
    # The cut's message replaced the fit check's reason line: it goes with the cut.
    fit = dict(prep, action="apply", reason="") \
        if prep.get("action") == "skip" and OWN_SKIP.match(str(prep.get("reason") or "")) else prep
    if fit.get("action") != "apply":
        return prep
    if "gaps" not in fit:
        other = other_language(fit, settings)
        return dict(fit, action="skip", grade="", reason="a hard gap: " + other) if other else prep
    return graded(fit, apply_fits, settings, long_shots)


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
        if rest[:1] == ["--set"]:
            key, sep, val = (rest[1] if len(rest) > 1 else "").partition("=")
            if key != "work_languages" or not sep or len(rest) > 2:
                sys.exit("fit --set takes work_languages=<names, comma-separated>: the other fit settings are the "
                         "file's own keys")
            set_work_languages(env, val)
            return
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
