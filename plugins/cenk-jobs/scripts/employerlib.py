"""Employer rules, the shared blacklist and the person's own employer checks; used by employer.py, usage.py and
track.py.

Categories (templates/employer-rules.json): israel (a state category: "state": "Israel"), defence, animal_cruelty,
climate, sexism, human_rights, working_conditions, sanctions, plus the person's own filters (a category with
"custom": true in their rules; another state is one with "state").
A check is {status, level, fact, source_url, checked} as found, plus the second check's own_level, own_why,
own_checked and own_rules (the fingerprint of the notes it was judged against) when the person's rules for the
category (its notes) judged it:
  status     flagged (a crime-level finding with its source) | clear (checked, nothing found) | unknown (not checked)
  level      direct | indirect, by the plugin's levels for the category (its levels, else the general ones)
  own_level  direct | indirect | none: the level under the person's own rules; none = not counted for them. It never
             leaves the person's files (the usage report and merge copy only the fields as found).
What a flagged check does comes from the person's EMPLOYER_RULES: action for a direct tie (exclude | discuss |
allow), indirect for an indirect one (discuss | warn | allow). The default is "discuss" for both: Claude shows the
finding and the person decides (allow or exclude). The level that counts is own_level when there is one (level_of).
An employer may also hold "environment": what employee reviews say, {rating, scale, reviews, complaints, source_url,
checked}, apart from the categories: it is shown to the person and never changes a verdict. "reviews": 0 means someone
looked and found none, so nobody looks again.

Files:
  data/blacklist.json   in the plugin: the shared list, {employers: [{name, aliases, checks: {category: check}}]},
                        built by the developer from users' reports (employer.py merge). Users only read it.
  EMPLOYER_RULES        the person's settings, a copy of templates/employer-rules.json (defaults when not set).
  EMPLOYER_CHECKS       the person's own summary: {employers: {name: entry}}. Their own checks win over the shared
                        list's. A decision is a value and a date, never a quote (older entries may hold "words"; they
                        are read, never written).
  EMPLOYERS_DIR         beside EMPLOYER_CHECKS ("employers" by default): names.json and one folder per employer.

The layout, top-down (only this module knows it): names.json {names: {lookup key: entry name}, not_same: [[key, key]]}
refers to the summary; the summary entry {verdict, verdict_date, group, aliases, decisions, status: {category:
"flagged direct" | "flagged indirect" | "clear" | "unknown"}, details: {scope: "employers/<name>/<scope>.json"}} refers
to a detail file per scope: checks.json (each category's check without history), environment.json (the employee-
review finding), history.json ({category: earlier checks}). An entry with no "details" keeps everything inline
(a file not split yet, another install). A reader opens only the files of the one employer and scope it needs.
  expand_entry(env, entry, scopes)   the entry with its scopes merged back (the entry as before the split)
  split_entry(entry) / write_entry   the summary entry and its detail files; the one writer
  own_match(env, name)               (entry name, entry, how, possible): how is exact | group | possible | none
"""
import copy
import datetime
import difflib
import hashlib
import json
import os
import re
import shutil

from trackerlib import file_name, write_detail, write_json

PLUGIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLACKLIST = os.path.join(PLUGIN, "data", "blacklist.json")
DEFAULT_RULES = os.path.join(PLUGIN, "templates", "employer-rules.json")
# The shared categories; only these go into the shared blacklist. A person's own filters add to them in their rules.
CATEGORIES = ("israel", "defence", "animal_cruelty", "climate", "sexism", "human_rights", "working_conditions",
              "sanctions")
STATUSES = ("flagged", "clear", "unknown")
LEVELS = ("direct", "indirect")
OWN_LEVELS = ("direct", "indirect", "none")
FOUND_FIELDS = ("status", "level", "fact", "source_url", "basis")  # a check as found; a change makes a history item
OWN_FIELDS = ("own_level", "own_why", "own_checked", "own_rules")  # the second check's: the person's only, never shared
ENDED = ("rejected", "closed", "declined")  # PIPELINE stages after which an application no longer runs
ACTIONS = ("exclude", "discuss", "allow")
INDIRECT_ACTIONS = ("discuss", "warn", "allow")
DECISIONS = ("exclude", "allow")
ENVIRONMENT_FIELDS = ("rating", "scale", "reviews", "complaints", "source_url", "checked")
MAX_COMPLAINTS = 6
MAX_COMPLAINT_LENGTH = 60  # a topic of a few words: the shared list never holds review text
SOURCE_URL = re.compile(r"https?://\S{1,500}")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
LEGAL = re.compile(r"\b(inc|incorporated|ltd|limited|llc|plc|gmbh|ag|bv|nv|sa|spa|srl|sas|sarl|oy|oyj|ab|as|asa|"
                   r"aps|kg|co|corp|corporation|company|se|group|holding|holdings)\b")


def today():
    return datetime.date.today().isoformat()


def load_json(path, default):
    if not path or not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def keys(name):
    """Lookup keys for an employer name: the name without punctuation and legal forms, plus each part in brackets
    ("Amazon (AWS)" -> "amazon aws", "amazon", "aws"). A name that would reduce below 2 characters keeps its legal
    form ("A Co" -> "a co")."""
    out = set()
    parts = [name] + re.findall(r"\(([^)]*)\)", name) + [re.sub(r"\([^)]*\)", " ", name)]
    for i, part in enumerate(parts):
        plain = re.sub(r"[^a-z0-9]+", " ", part.lower().replace(".", ""))  # "N.V." -> "nv"
        k = re.sub(r"\s+", " ", LEGAL.sub(" ", plain)).strip()
        if len(k) < 2 and (i == 0 or i == len(parts) - 1):  # the whole name, not a part in brackets
            k = re.sub(r"\s+", " ", plain).strip()
        if len(k) >= 2:
            out.add(k)
    return out


def env_path(env, key):
    return env.path(key) if env.get(key) else ""


def rules(env):
    """The person's rules, with any missing category filled from the defaults. The levels, the state category's
    definition and each shared category's what and levels are always the plugin's: a finding is recorded as found, so
    the shared blacklist means the same for everyone; the person's own rules are their notes (the second check)."""
    default = load_json(DEFAULT_RULES, {})
    own = load_json(env_path(env, "EMPLOYER_RULES"), {})
    merged = dict(default, **{k: v for k, v in own.items() if k != "categories"})
    for key in ("levels", "state_category"):
        if key in default:
            merged[key] = default[key]
    state = merged.get("state_category") or {}
    merged["categories"] = {}
    for c in CATEGORIES:
        plugin = default.get("categories", {}).get(c, {})
        s = {k: v for k, v in dict(plugin, **own.get("categories", {}).get(c, {})).items() if k not in ("what", "levels")}
        merged["categories"][c] = dict(s, **{k: plugin[k] for k in ("what", "levels") if k in plugin})
    # The person's own filters (example: gambling) count like the shared categories, for them only.
    merged["categories"].update({c: dict(s) for c, s in own.get("categories", {}).items()
                                 if c not in CATEGORIES and isinstance(s, dict) and s.get("custom")})
    # A state category (israel, or one the person named) takes its what and levels from the state category.
    for s in merged["categories"].values():
        if s.get("state"):
            s.update({k: copy.deepcopy(state[k]) for k in ("what", "levels") if k in state})
    # A value the rules do not know (a typo, an older name such as "never") counts as "discuss": the person decides,
    # and nothing is applied to on a setting nobody understood.
    for s in merged["categories"].values():
        if s.get("action", "discuss") not in ACTIONS:
            s["action"] = "discuss"
        if s.get("indirect", "discuss") not in INDIRECT_ACTIONS:
            s["indirect"] = "discuss"
    return merged


def categories(env):
    """Every category the person's rules check: the shared ones, then their own filters."""
    return list(rules(env)["categories"])


def level_of(check):
    """The level that counts for the person: the second check's own_level when there is one, else the level as found."""
    own = check.get("own_level")
    return own if own in OWN_LEVELS else (check.get("level") or "direct")


def act_for(setting, level):
    """What a category setting does with a tie of this level: exclude | discuss | warn | allow."""
    return setting.get("action", "discuss") if level == "direct" else setting.get("indirect", "discuss")


def notes_key(rule_set, cat):
    """The fingerprint of a category's notes (the person's own rules): sha256 of the text with its spaces collapsed,
    12 hex characters. A second check stores it as own_rules; another fingerprint now means the notes changed."""
    notes = " ".join(str((rule_set["categories"].get(cat) or {}).get("notes") or "").split())
    return hashlib.sha256(notes.encode("utf-8")).hexdigest()[:12]


def own_fields(rule_set, cat, own_level, why=""):
    """A second check's fields for one category: own_level, own_why, today's own_checked and own_rules."""
    return {"own_level": own_level, "own_why": why, "own_checked": today(), "own_rules": notes_key(rule_set, cat)}


def second_check_due(rule_set, cat, check):
    """Whether a finding needs the second check against the person's own rules: it is flagged, the category has notes,
    and it has no own_level yet, or one judged against other notes (own_rules is not the notes' fingerprint now)."""
    setting = rule_set["categories"].get(cat) or {}
    if check.get("status") != "flagged" or not str(setting.get("notes") or "").strip():
        return False
    return check.get("own_level") not in OWN_LEVELS or check.get("own_rules") != notes_key(rule_set, cat)


def blacklist():
    return load_json(BLACKLIST, {"employers": []})


def checks_file(env):
    """The person's summary file as stored: {employers: {name: entry}}, entries not expanded (see expand_entry)."""
    return load_json(env_path(env, "EMPLOYER_CHECKS"), {"employers": {}})


# --- the layout: names.json, the summary, one folder per employer ------------------------------------------------------
NAMES_FILE = "names.json"
DETAIL_PATH = re.compile(r"^employers/[A-Za-z0-9._-]+/(checks|environment|history)\.json$")
SCOPES = ("checks", "environment", "history")
SIMILAR = 0.85  # two lookup keys this alike (difflib ratio) are a possible match
MAX_POSSIBLE = 5
NAMES_ABOUT = ("Lookup table of the cenk-jobs employer records (employer.py): every lookup key of every saved "
               "employer name and alias maps to its entry in EMPLOYER_CHECKS; not_same lists key pairs that are "
               "different employers, so they are never offered as a possible match again.")


def employers_dir(env):
    """EMPLOYERS_DIR, else 'employers' beside EMPLOYER_CHECKS; "" when EMPLOYER_CHECKS is not set."""
    if env.get("EMPLOYERS_DIR"):
        return env.path("EMPLOYERS_DIR")
    path = env_path(env, "EMPLOYER_CHECKS")
    return os.path.join(os.path.dirname(path), "employers") if path else ""


def _signature(path):
    try:
        st = os.stat(path)
    except OSError:
        return None
    return st.st_mtime_ns, st.st_size


_FILES = {}


def _read_cached(path):
    """A JSON file read once per change (by modified time and size); None when it does not exist. Callers never change
    what it returns."""
    sig = _signature(path)
    if sig is None:
        return None
    hit = _FILES.get(path)
    if hit and hit[0] == sig:
        return hit[1]
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    _FILES[path] = (sig, data)
    return data


def detail_path(env, rel, scope):
    """The absolute path of a details link. Only 'employers/<name>/<scope>.json' is accepted, so a link set by hand
    never reads or writes another file."""
    if not (isinstance(rel, str) and DETAIL_PATH.match(rel) and rel.endswith(f"/{scope}.json")
            and rel.split("/")[1] not in (".", "..")
            and not rel.split("/")[1].endswith(".")):
        raise SystemExit(f"not an employer detail file path for {scope}: {rel!r}")
    base = employers_dir(env)
    if not base:
        raise SystemExit("EMPLOYER_CHECKS is not set in job-search.env")
    return os.path.normpath(os.path.join(base, rel[len("employers/"):]))


def names_path(env):
    base = employers_dir(env)
    return os.path.join(base, NAMES_FILE) if base else ""


def load_names(env):
    """(names {key: entry name}, not_same {frozenset of two keys}) from names.json; empty when it does not exist."""
    path = names_path(env)
    data = _read_cached(path) if path else None
    if not isinstance(data, dict):
        return {}, set()
    return (dict(data.get("names") or {}),
            {frozenset(p) for p in data.get("not_same") or [] if isinstance(p, list) and len(p) == 2})


def save_names(env, names, not_same):
    path = names_path(env)
    write_json(path, {"_about": NAMES_ABOUT, "names": dict(sorted(names.items())),
                      "not_same": sorted(sorted(p) for p in not_same)}, 1)
    _FILES.pop(path, None)


def entry_keys(name, entry):
    """Every lookup key of an entry: its name's and its aliases'."""
    return {k for n in [name] + list(entry.get("aliases") or []) for k in keys(n)}


class _Index:
    """The lookup keys of the person's entries and how a name matches them. Built from names.json (when there is one)
    and the entries' own names and aliases, so a hand-added entry is found too."""

    def __init__(self, employers, names, not_same):
        self.employers = employers
        self.pos = {n: i for i, n in enumerate(employers)}
        self.not_same = not_same
        self.key_to = {k: n for k, n in names.items() if n in employers}
        for n, e in employers.items():
            for k in entry_keys(n, e):
                self.key_to.setdefault(k, n)
        self.groups = [(n, entry_keys(n, e)) for n, e in employers.items() if e.get("group")]
        self.memo = {}

    def match(self, name):
        """(entry name, how, possible): exact (a key of the name is a key of an entry), group (a group entry covers the
        name), possible (see _possible; entry name None) or none."""
        if name in self.memo:
            return self.memo[name]
        wanted = keys(name)
        exact = {self.key_to[k] for k in wanted if k in self.key_to}
        if exact:
            out = (min(exact, key=self.pos.get), "exact", [])
        else:
            cover = [n for n, ks in self.groups if any(m == k or m.startswith(k + " ") for k in ks for m in wanted)]
            if cover:
                out = (min(cover, key=self.pos.get), "group", [])
            else:
                possible = self._possible(wanted)
                out = (None, "possible" if possible else "none", possible)
        self.memo[name] = out
        return out

    def _possible(self, wanted):
        """Entries with a key that holds all words of a key of the name as whole words, or the other way round, or is
        at least SIMILAR alike; pairs in not_same left out. Sorted by name, at most MAX_POSSIBLE."""
        found = set()
        sm = difflib.SequenceMatcher(autojunk=False)
        for wk in sorted(wanted):
            ww = set(wk.split())
            sm.set_seq2(wk)
            for ck, owner in self.key_to.items():
                if owner in found or ck == wk or frozenset((wk, ck)) in self.not_same:
                    continue
                cw = set(ck.split())
                if ww <= cw or cw <= ww:
                    found.add(owner)
                    continue
                sm.set_seq1(ck)
                if sm.real_quick_ratio() >= SIMILAR and sm.quick_ratio() >= SIMILAR and sm.ratio() >= SIMILAR:
                    found.add(owner)
        return [{"name": n, "verdict": self.employers[n].get("verdict", "")} for n in sorted(found)[:MAX_POSSIBLE]]


_INDEX = {}


def own_index(env, employers):
    """The _Index of an employers dict, rebuilt when the dict or names.json changed."""
    sig = (_signature(names_path(env)), len(employers))
    if _INDEX.get("employers") is not employers or _INDEX.get("sig") != sig:
        names, not_same = load_names(env)
        _INDEX.update(employers=employers, sig=sig, index=_Index(employers, names, not_same))
    return _INDEX["index"]


def own_match(env, name, employers=None):
    """(entry name, summary entry, how, possible) for the person's own entries: how is exact | group | possible |
    none; the entry only for exact and group; possible: [{name, verdict}] only when how is possible."""
    employers = checks_file(env).get("employers", {}) if employers is None else employers
    entry_name, how, possible = own_index(env, employers).match(name)
    return entry_name, employers.get(entry_name), how, possible


def find_own(env, name, employers=None):
    """(entry name, summary entry) of the person's entry that has the name (exact, else a group's), else (None, None)."""
    entry_name, entry, _, _ = own_match(env, name, employers)
    return entry_name, entry


def find_entry(entries, name):
    """The entry of a [{name, aliases}] list (the shared blacklist) or a {name: entry} dict that matches the name, else
    None. An exact match wins; then an entry marked "group": true matches every name that starts with its own (its
    units: "Acme" covers "Acme Cloud Services"). The person's own entries go through find_own."""
    wanted = keys(name)
    items = list(entries.items()) if isinstance(entries, dict) else [(e.get("name", ""), e) for e in entries]
    for entry_name, entry in items:
        names = [entry_name] + list(entry.get("aliases", []))
        if any(wanted & keys(n) for n in names):
            return entry_name, entry
    for entry_name, entry in items:
        if entry.get("group") and covered_by(name, [entry_name] + list(entry.get("aliases", []))):
            return entry_name, entry
    return None, None


def covered_by(name, names):
    """A group's name covers the employer's name, a part of it in brackets, or any of them that starts with it as
    whole words: "Acme" covers "Acme Cloud Services" (and "Nova" also "Nova Path", another company)."""
    mine = keys(name)
    return any(m == k or m.startswith(k + " ") for n in names for k in keys(n) for m in mine)


def status_text(check):
    """A check's line in the summary's status map: 'flagged direct' | 'flagged indirect' | 'clear' | 'unknown'."""
    status = check.get("status") if isinstance(check, dict) else None
    if status == "flagged":
        return "flagged " + str(check.get("level") or "direct")
    return status if status in ("clear", "unknown") else "unknown"


def split_entry(entry):
    """(summary entry, {scope: data}) of a merged entry. The summary keeps everything but the checks and the
    environment, and gets a status map; checks.json holds the checks without their history, history.json
    {category: history}, environment.json the finding. A scope with nothing to hold, or an empty value, stays inline
    in the summary, so expand_entry gives the entry back exactly."""
    summary = {k: v for k, v in entry.items() if k not in ("checks", "environment")}
    parts = {}
    checks = entry.get("checks")
    if isinstance(checks, dict) and checks:
        held, history = {}, {}
        for cat, check in checks.items():
            if isinstance(check, dict) and check.get("history"):
                check = dict(check)
                history[cat] = check.pop("history")
            held[cat] = check
        parts["checks"] = held
        if history:
            parts["history"] = history
        summary["status"] = {cat: status_text(c) for cat, c in checks.items()}
    elif "checks" in entry:
        summary["checks"] = checks
    if entry.get("environment"):
        parts["environment"] = entry["environment"]
    elif "environment" in entry:
        summary["environment"] = entry["environment"]
    return copy.deepcopy(summary), copy.deepcopy(parts)


def _scope_file(env, entry, scope):
    """The content of an entry's detail file for a scope; None when the entry links none; {} for a missing history."""
    rel = (entry.get("details") or {}).get(scope)
    if not rel:
        return None
    data = _read_cached(detail_path(env, rel, scope))
    if data is None:
        if scope == "history":
            return {}
        raise SystemExit(f"the entry links {rel}, which does not exist in {employers_dir(env)}")
    return data


def expand_entry(env, entry, scopes=("checks", "environment")):
    """A copy of a summary entry with the given scopes merged back from its detail files, opening only those files.
    An entry without "details" is returned as it is (without the checks' history unless "history" is asked for)."""
    split = bool(entry.get("details"))
    out = copy.deepcopy({k: v for k, v in entry.items() if not (split and k in ("details", "status"))})
    if not split:
        if "history" not in scopes:
            for check in (out.get("checks") or {}).values():
                if isinstance(check, dict):
                    check.pop("history", None)
        return out
    for scope in ("checks", "environment"):
        if scope in scopes:
            data = _scope_file(env, entry, scope)
            if data is not None:
                out[scope] = copy.deepcopy(data)
    if "history" in scopes:
        for cat, history in (_scope_file(env, entry, "history") or {}).items():
            if isinstance(out.get("checks", {}).get(cat), dict):
                out["checks"][cat]["history"] = copy.deepcopy(history)
    return out


def entry_checks(env, entry, facts=True, history=False):
    """The checks of a summary entry: {category: check}. facts="flagged": a category the summary says is not flagged
    comes as {status} only, and a split entry with none flagged opens no file."""
    if entry.get("details") and facts == "flagged":
        status = entry.get("status") or {}
        if not any(str(s).startswith("flagged") for s in status.values()):
            return {c: {"status": str(s).split()[0]} for c, s in status.items()}
    return (expand_entry(env, entry, ("checks", "history") if history else ("checks",)).get("checks") or {})


def entry_environment(env, entry):
    """The saved working-environment finding of a summary entry, else None; opens only environment.json."""
    return expand_entry(env, entry, ("environment",)).get("environment") or None


def merged_entries(env, scopes=("checks", "environment")):
    """[(name, merged entry)] of every entry, for a command that needs all of them (the usage report, merge). Opens the
    detail files of every entry: nothing else should."""
    return [(n, expand_entry(env, e, scopes)) for n, e in checks_file(env).get("employers", {}).items()]


def _folder_of(entry):
    for rel in (entry.get("details") or {}).values():
        if isinstance(rel, str) and DETAIL_PATH.match(rel):
            return rel.rsplit("/", 1)[0]
    return ""


def _folders_used(employers):
    return {f.split("/", 1)[1].lower() for f in (_folder_of(e) for e in employers.values()) if f}


def split_mode(data):
    """Whether the file is split: any entry has details. New entries then get detail files too."""
    return any(isinstance(e, dict) and e.get("details") for e in data.get("employers", {}).values())


def write_entry(env, data, name, entry):
    """Store a merged entry in data["employers"][name] (the caller saves the summary file afterwards). In a split file
    the entry is split: its detail files are written first (only the ones that changed), and names.json gets the
    entry's keys. Otherwise it stays inline."""
    employers = data["employers"]
    old = employers.get(name) or {}
    if not (old.get("details") or split_mode(data)):
        employers[name] = entry
        return
    summary, parts = split_entry(entry)
    folder = _folder_of(old) or "employers/" + file_name(name, _folders_used(employers))
    links = {}
    for scope in SCOPES:
        rel = f"{folder}/{scope}.json"
        path = detail_path(env, rel, scope)
        if scope in parts:
            write_detail(path, parts[scope])
            _FILES.pop(path, None)
            links[scope] = rel
        elif (old.get("details") or {}).get(scope) and os.path.exists(path):
            os.remove(path)
            _FILES.pop(path, None)
    if links:
        summary["details"] = links
    employers[name] = summary
    names, not_same = load_names(env)
    wanted = {k: name for k in entry_keys(name, summary) if k not in names}
    if wanted or not os.path.exists(names_path(env)):
        save_names(env, dict(names, **wanted), not_same)


def plan_split(env, data):
    """(summary file content, {rel: detail}, names, stats) for the entries not split yet that have something to move
    (checks or an environment). Writes nothing."""
    employers = data.get("employers", {})
    used = _folders_used(employers)
    summaries, files, moved = {}, {}, 0
    for name, entry in employers.items():
        if entry.get("details") or not (entry.get("checks") or entry.get("environment")):
            summaries[name] = entry
            continue
        folder = "employers/" + file_name(name, used)
        summary, parts = split_entry(entry)
        summary["details"] = {scope: f"{folder}/{scope}.json" for scope in parts}
        files.update({f"{folder}/{scope}.json": part for scope, part in parts.items()})
        summaries[name] = summary
        moved += 1
    names, pairs = load_names(env)
    names = dict(names)
    collisions = 0
    for name, entry in summaries.items():
        for k in entry_keys(name, entry):
            if names.setdefault(k, name) != name:
                collisions += 1
    out = dict(data, employers=summaries)
    size = lambda d: len(json.dumps(d, ensure_ascii=False, indent=1).encode("utf-8"))
    stats = {"entries": len(employers), "moved": moved, "files": len(files), "keys": len(names),
             "collisions": collisions, "detail_bytes": sum(size(d) for d in files.values()),
             "before_bytes": size(data), "after_bytes": size(out)}
    return out, files, names, pairs, stats


def split_proof(env, original, summaries):
    """The name of the first entry moved by this run whose merged view (read back from disk) is not the original
    entry, else None. Entries that already had details are skipped."""
    for name, entry in original.items():
        if entry.get("details"):  # split by an earlier run: this run did not move it
            continue
        if expand_entry(env, summaries[name], SCOPES) != entry:
            return name
    return None


def backup_checks(path, kind):
    """Copy a file to '<path>.before-<kind>-<today>.json' (numbered when that exists); returns the backup's path."""
    backup, n = f"{path}.before-{kind}-{today()}.json", 1
    while os.path.exists(backup):
        n += 1
        backup = f"{path}.before-{kind}-{today()}-{n}.json"
    shutil.copy2(path, backup)
    return backup


def apply_split(env, path, data, plan):
    """Write a plan_split plan: a backup first, the detail files, the proof read back from disk, and only then names.json
    and the summary. On a mismatch SystemExit names the entry and the summary is left as it was. Returns the backup."""
    summaries, files, names, pairs, _ = plan
    backup = backup_checks(path, "split")
    for rel, detail in files.items():
        write_detail(detail_path(env, rel, rel.rsplit("/", 1)[1][:-5]), detail)
    _FILES.clear()
    bad = split_proof(env, data["employers"], summaries["employers"])
    if bad is not None:
        raise SystemExit(f"the merged view of {bad!r} differs from the original: the summary and names.json are "
                         f"unchanged (detail files were written beside it; the backup is {backup})")
    save_names(env, names, pairs)
    save_json(path, summaries)
    return backup


def apply_repair(env, path, data, changed):
    """Write repair-clear's changed merged entries ({name: entry}): the summary backed up, and each split employer's
    checks.json beside itself, then the entries and the summary."""
    shutil.copy2(path, f"{path}.before-repair-{today()}.json")
    for name, entry in changed.items():
        old = data["employers"][name]
        if (old.get("details") or {}).get("checks"):
            detail = detail_path(env, old["details"]["checks"], "checks")
            shutil.copy2(detail, f"{detail}.before-repair-{today()}.json")
        write_entry(env, data, name, entry)
    save_json(path, data)


def decision_for(env, name):
    """The person's last decision for an employer: its own entry's, else that of a group entry covering it ("Acme",
    "group": true, covers "Acme Cloud" even when that has an entry of its own). Reads the summary only."""
    employers = checks_file(env).get("employers", {})
    _, own = find_own(env, name, employers)
    if (own or {}).get("decisions"):
        return own["decisions"][-1]
    for entry_name, entry in employers.items():
        if entry.get("group") and entry.get("decisions") and covered_by(name, [entry_name] + list(entry.get("aliases", []))):
            return entry["decisions"][-1]
    return None


def lookup(env, name, facts=True, history=False, employers=None):
    """Every known check for an employer: {category: dict(check, origin=shared|own)}; own results win. Opens only that
    employer's checks.json (and history.json with history=True). facts="flagged": see entry_checks."""
    out = {}
    _, shared = find_entry(blacklist().get("employers", []), name)
    for cat, check in (shared or {}).get("checks", {}).items():
        out[cat] = dict(check, origin="shared")
    _, own = find_own(env, name, employers)
    for cat, check in entry_checks(env, own or {}, facts, history).items():
        if cat not in out or check.get("status") != "unknown":
            out[cat] = dict(check, origin="own")
    return out


def check_view(env, name, rule_set=None, full=False, employers=None):
    """What employer.py check prints for a name: {name, match, matched, verdict, reasons, checks, unknown, recheck,
    has_environment, possible}; full adds the environment finding and each check's history. A possible match with no
    exact or group match turns an "allow" into "discuss" ("possible match: <name> (<verdict>)"): never a silent allow.
    recheck: the categories whose second check is due (second_check_due; none once the person decided); while one is
    due, an "allow" is "discuss" too."""
    rule_set = rule_set or rules(env)
    employers = checks_file(env).get("employers", {}) if employers is None else employers
    entry_name, entry, how, possible = own_match(env, name, employers)
    checks = lookup(env, name, history=full, employers=employers)
    verdict, reasons, recheck = decide_due(env, name, checks, rule_set)
    for p in possible:
        reasons.append(f"possible match: {p['name']} ({p['verdict'] or 'no verdict'})")
    if possible and verdict == "allow":
        verdict = "discuss"
    shared = find_entry(blacklist().get("employers", []), name)[1] or {}
    saved = bool((entry or {}).get("details", {}).get("environment") or (entry or {}).get("environment"))
    out = {"name": name, "match": how, "matched": entry_name or "", "verdict": verdict, "reasons": reasons,
           "checks": checks,
           "unknown": [c for c in rule_set["categories"] if checks.get(c, {}).get("status", "unknown") == "unknown"],
           "recheck": recheck, "has_environment": saved or bool(shared.get("environment")), "possible": possible}
    if full:
        out["environment"] = environment_of(env, name, own={"employers": employers})
    return out


def recheck_of(env, name, checks, rule_set):
    """The categories of an employer whose second check is due; none when the person decided on the employer."""
    if decision_for(env, name):
        return []
    return [c for c, k in checks.items() if c in rule_set["categories"] and second_check_due(rule_set, c, k)]


def decide_due(env, name, checks, rule_set=None):
    """(verdict, reasons, due): decide(), and while a second check is due (due: its categories) an "allow" is
    "discuss": never an allow on a level the person's own rules have not judged yet. Every verdict goes through it:
    check_view, recheck_running and track.py sync."""
    rule_set = rule_set or rules(env)
    verdict, reasons = decide(env, name, checks, rule_set)
    due = recheck_of(env, name, checks, rule_set)
    if due:
        reasons = reasons + ["second check due: " + ", ".join(due)]
        if verdict == "allow":
            verdict = "discuss"
    return verdict, reasons, due


def pipeline_row(pipeline, job_id):
    """A job's PIPELINE row; a row marked same_as follows that row."""
    p = pipeline.get(job_id) or {}
    return (pipeline.get(p["same_as"]) or p) if p.get("same_as") else p


def set_own(env, name, cat, own_level, why=""):
    """Record the second check of one category: own_level (direct | indirect | none), own_why (the rule it meets) and
    today's date beside the finding, which stays as found. A finding only the shared list holds is copied into the
    person's own record first. Returns the check written."""
    if own_level not in OWN_LEVELS:
        raise SystemExit(f"own level must be one of {', '.join(OWN_LEVELS)}")
    found = lookup(env, name).get(cat)
    if not found or found.get("status") != "flagged":
        raise SystemExit(f"{name} has no finding in {cat}: a second check judges a finding")
    check = {k: v for k, v in found.items() if k not in ("origin", "history")}
    check.update(own_fields(rules(env), cat, own_level, why))
    record(env, name, {cat: check})
    return check


def running(jobs, pipeline):
    """{employer: [job]} of the applications sent and still running: tracker status submitted (or a PIPELINE row), and
    a PIPELINE stage that is not rejected, closed or declined (a row marked same_as follows that row)."""
    out = {}
    for job in jobs:
        p = pipeline_row(pipeline, job.get("id"))
        if (job.get("status") == "submitted" or job.get("id") in pipeline) and p.get("stage") not in ENDED:
            out.setdefault(job.get("company", ""), []).append(job)
    return out


def recheck_running(env, jobs, pipeline, write=True):
    """Every employer with a running application, judged again under the person's current rules and records:
    [{employer, saved, now, reasons, recheck, jobs: [{id, title, stage}]}] for those that need the person or a second
    check: the verdict moved to exclude or discuss, or a second check is due. A moved verdict is saved (write), so the
    next run lists it only when it moves again; a move to allow is saved without a line."""
    rule_set = rules(env)
    employers = checks_file(env).get("employers", {})
    out = []
    for name, jobs_of in sorted(running(jobs, pipeline).items()):
        if not name:
            continue
        entry_name, entry = find_own(env, name, employers)
        checks = lookup(env, name, employers=employers)
        verdict, reasons, recheck = decide_due(env, name, checks, rule_set)
        saved = (entry or {}).get("verdict") or "allow"  # a sent application was allowed when it was sent
        if verdict != saved and write:
            record(env, entry_name or name, verdict=verdict)
            employers = checks_file(env).get("employers", {})
        if (verdict != saved and verdict in ("exclude", "discuss")) or recheck:
            out.append({"employer": name, "saved": saved, "now": verdict, "reasons": reasons, "recheck": recheck,
                        "jobs": [{"id": j.get("id", ""), "title": j.get("title", ""),
                                  "stage": pipeline_row(pipeline, j.get("id")).get("stage", "sent")} for j in jobs_of]})
    return out


def whole_keys(name):
    """The keys of the whole name only, never of a part in brackets: "Acme Mobile (Examplia)" -> "acme mobile",
    "acme mobile examplia" (not "examplia", which may be another employer's name)."""
    return keys(re.sub(r"\([^)]*\)", " ", name)) | keys(name.replace("(", " ").replace(")", " "))


def alias(env, saved, other):
    """Add another name's lookup keys to names.json for a saved entry, so that name finds it. Returns the entry name
    and the keys added. SystemExit with a message when the saved name is not an entry or a key belongs to another."""
    employers = checks_file(env).get("employers", {})
    index = own_index(env, employers)
    name, how, _ = index.match(saved)
    if how != "exact":
        raise SystemExit(f"{saved!r} is not a saved employer name (match: {how}); alias needs the saved name")
    wanted = whole_keys(other)
    if not wanted:
        raise SystemExit(f"{other!r} has no lookup key")
    for k in sorted(wanted):
        owner = index.key_to.get(k)
        if owner and owner != name:
            raise SystemExit(f"the key {k!r} of {other!r} already points to {owner!r}, not {name!r}: nothing changed")
        near = [p["name"] for p in index._possible({k}) if p["name"] != name]
        if near:
            raise SystemExit(f"the key {k!r} of {other!r} is a possible match of {near[0]!r}: settle {near[0]!r} first "
                             f"(alias or alias --not): nothing changed")
    names, not_same = load_names(env)
    added = sorted(k for k in wanted | entry_keys(name, employers[name]) if names.get(k) != name)
    save_names(env, dict(names, **{k: name for k in added}), not_same)
    return name, sorted(wanted)


def not_same(env, a, b):
    """Record that two names are different employers, so neither is offered as a possible match of the other. Returns
    the key pairs added."""
    employers = checks_file(env).get("employers", {})
    index = own_index(env, employers)
    ka, kb = whole_keys(a), whole_keys(b)
    if not ka or not kb:
        raise SystemExit("both names need a lookup key")
    ma, mb = index.match(a), index.match(b)
    if ma[1] == mb[1] == "exact" and ma[0] == mb[0]:
        raise SystemExit(f"{a!r} and {b!r} are the same saved employer: nothing changed")
    names, pairs = load_names(env)
    new = {frozenset((x, y)) for x in ka for y in kb if x != y} - pairs
    save_names(env, names, pairs | new)
    return len(new)


def environment_finding(reviews, rating=None, scale=5, complaints="", source_url=""):
    """A working-environment finding from employee reviews; ValueError when it is not one. complaints: a list or a
    ';'-separated string of topics ("micromanagement; high turnover"). reviews 0: looked and found none."""
    if not str(reviews).isdigit():
        raise ValueError("reviews=<how many reviews> is required: a whole number, 0 when none were found")
    if int(reviews) == 0:
        return {"reviews": 0}
    if rating in (None, "") or not SOURCE_URL.fullmatch(str(source_url)):
        raise ValueError("a finding with reviews needs rating= and source=<url>")
    rating, scale = float(rating), float(scale)
    if not 0 < rating <= scale:
        raise ValueError(f"rating {rating:g} is not between 0 and {scale:g}")
    topics = [t.strip() for t in (complaints.split(";") if isinstance(complaints, str) else complaints) if t.strip()]
    if len(topics) > MAX_COMPLAINTS or any(len(t) > MAX_COMPLAINT_LENGTH for t in topics):
        raise ValueError(f"complaints are at most {MAX_COMPLAINTS} topics of a few words, never review text")
    finding = {"rating": rating, "scale": scale, "reviews": int(reviews), "source_url": source_url}
    return dict(finding, complaints=topics) if topics else finding


def environment_from_report(block):
    """A usage report's environment block, held to environment_finding's limits, with its date. Raises ValueError,
    TypeError or AttributeError when it does not pass: a report is foreign text that reaches every person's Claude."""
    checked = block.get("checked")
    if not (isinstance(checked, str) and DATE.fullmatch(checked) and checked <= today()):
        raise ValueError("its date is not a date up to today")
    finding = environment_finding(block.get("reviews", ""), block.get("rating"), block.get("scale", 5),
                                  block.get("complaints") or [], block.get("source_url") or "")
    return dict(finding, checked=checked)


def replaces_environment(old, new):
    """Whether a new finding takes the place of the saved one: "no reviews found" never replaces a rating."""
    return bool(new.get("reviews")) or not (old or {}).get("reviews")


def environment_rank(finding):
    """Orders the findings for one employer: any rating beats "no reviews found", then the newer date."""
    return bool(finding.get("reviews")), finding.get("checked", "")


def environment_of(env, name, shared=None, own=None):
    """The saved working-environment finding for an employer with origin=own|shared, else None: of the person's own and
    the shared list's, a rating before "no reviews found", then the newer, their own on a tie. shared, own: those two
    files, if already read."""
    _, mine = find_own(env, name, (checks_file(env) if own is None else own).get("employers", {}))
    _, theirs = find_entry((blacklist() if shared is None else shared).get("employers", []), name)
    mine = {"environment": entry_environment(env, mine)} if mine else None  # opens only that employer's environment.json
    found = [dict(e["environment"], origin=origin) for e, origin in ((mine, "own"), (theirs, "shared"))
             if (e or {}).get("environment")]
    return max(found, key=environment_rank, default=None)


def excluding(env, name, rule_set=None):
    """What makes the person's rules exclude an employer: [{category, origin, level}], empty when they do not.
    origin: decision (their answer: exclude), shared (a finding from the shared blacklist) or own (their own check)."""
    r = rule_set or rules(env)
    last = decision_for(env, name)
    if last:
        return [{"category": last.get("category", ""), "origin": "decision"}] if last["verdict"] == "exclude" else []
    out = []
    for cat, check in lookup(env, name, facts="flagged").items():
        if check.get("status") != "flagged" or cat not in r["categories"]:
            continue
        level = level_of(check)
        if level != "none" and act_for(r["categories"][cat], level) == "exclude":
            out.append({"category": cat, "origin": check.get("origin", "own"), "level": level})
    return out


def excluded_list(env, jobs, pipeline=None):
    """The person's one list of excluded employers, one row each, for the dashboard's Excluded tab: every employer
    their rules or decisions exclude, and every employer of a job the tracker excluded or the person withdrew from on
    their rules. jobs: the tracker's flat job list; pipeline: PIPELINE's {job id: stage}.
    Row: {id, employer, how (Excluded|Withdrawn), by, why, fact, source, since, jobs, n, names (every name the
    employer goes by in the records)}."""
    global blacklist, checks_file
    shared, own = blacklist(), checks_file(env)
    saved = blacklist, checks_file
    blacklist, checks_file = (lambda: shared), (lambda e: own)  # read each file once, not once per employer
    try:
        return _excluded_list(env, jobs, pipeline or {}, own.get("employers", {}))
    finally:
        blacklist, checks_file = saved


def _excluded_list(env, jobs, pipeline, employers):
    r = rules(env)
    labels = {c: s.get("label", c) for c, s in r["categories"].items()}
    rows = {}

    def row_for(name):
        entry_name, entry = find_own(env, name, employers)
        key = entry_name or name
        row = rows.setdefault(key, {"group": bool((entry or {}).get("group")), "jobs": [], "withdrawn": False,
                                    "note": "", "reason": "", "names": [key]})
        if name and name not in row["names"]:
            row["names"].append(name)
        return row

    for job in jobs:
        p = pipeline.get(job.get("id")) or {}
        if p.get("same_as"):
            p = pipeline.get(p["same_as"]) or p
        withdrawn = p.get("stage") == "declined" and p.get("why") == "ethics"
        if job.get("status") != "excluded" and not withdrawn:
            continue
        row = row_for(job.get("company", ""))
        row["jobs"].append(job.get("title") or job["id"])
        row["withdrawn"] = row["withdrawn"] or withdrawn
        row["note"] = row["note"] or (job.get("outcome") or "").removeprefix("employer excluded: ")
        row["reason"] = row["reason"] or (p.get("reason") or "" if withdrawn else "")
    for name in employers:
        if excluding(env, name, r):
            row_for(name)

    def group_check(name, cat):
        # A group's unit: the finding may be recorded under the group's own name ("Acme" for "Acme Cloud").
        for entry_name, entry in employers.items():
            if entry_name != name and entry.get("group") and covered_by(name, [entry_name] + list(entry.get("aliases", []))):
                found = entry_checks(env, entry).get(cat) or {}
                if found.get("fact"):
                    return found
        return {}

    out = []
    for name, row in rows.items():
        found = excluding(env, name, r)
        checks = lookup(env, name)
        flagged = [c for c, k in checks.items() if k.get("status") == "flagged"]
        last = decision_for(env, name) or {}
        if found and found[0]["origin"] == "decision":
            by, wanted, since = "your decision", [found[0]["category"]] if found[0]["category"] else flagged, last.get("date", "")
        elif found:
            by, wanted, since = "your rules", [f["category"] for f in found], ""
        else:
            by, wanted, since = "when screened", flagged, ""
        why, facts, sources = [], [], []
        for cat in wanted:
            k = checks.get(cat) if (checks.get(cat) or {}).get("fact") else group_check(name, cat) or checks.get(cat) or {}
            level = level_of(k)
            why.append(labels.get(cat, cat) + {"indirect": " (indirect)", "none": " (not a tie by your rules)"}.get(level, ""))
            if k.get("fact"):
                facts.append(k["fact"])
            if k.get("source_url") and k["source_url"] not in sources:
                sources.append(k["source_url"])
            since = since or k.get("checked", "")
        fact = " · ".join(facts) or row["reason"] or row["note"] or "No finding recorded yet: Claude checks it at the next run."
        titles = row["jobs"]
        out.append({"id": name, "employer": name + (" and its group" if row["group"] else ""),
                    "how": "Withdrawn" if row["withdrawn"] else "Excluded", "by": by,
                    "why": "; ".join(why) or "by your rules when the job was screened", "fact": fact,
                    "source": sources[0] if sources else "", "since": since,
                    "jobs": "; ".join(titles[:5]) + (f" and {len(titles) - 5} more" if len(titles) > 5 else ""),
                    "n": len(titles), "names": row["names"]})
    # Withdrawn first (the person had applied), then by name.
    return sorted(out, key=lambda x: (x["how"] != "Withdrawn", x["employer"].lower()))


def decide(env, name, checks, rule_set=None):
    """(verdict, reasons) from the person's rules: exclude | discuss | allow. A 'warn' reason comes with allow."""
    r = rule_set or rules(env)
    last = decision_for(env, name)
    if last:
        why = f" ({last['category']})" if last.get("category") else ""
        return last["verdict"], [f"the person decided {last['verdict']} on {last['date']}{why}"]
    verdict, reasons = "allow", []
    for cat, check in checks.items():
        if check.get("status") != "flagged" or cat not in r["categories"]:
            continue
        setting = r["categories"][cat]
        label = setting.get("label", cat)
        level, found = level_of(check), check.get("level") or "direct"
        if level == "none":
            reasons.append(f"not counted: {label}: not a tie by your rules: {check.get('own_why', '')[:160]}")
            continue
        act = act_for(setting, level)
        how = level if level == found else f"{level} by your rules, found {found}"
        reasons.append(f"{act}: {label} ({how}): {check.get('fact', '')[:160]}")
        if act == "exclude":
            verdict = "exclude"
        elif act == "discuss" and verdict != "exclude":
            verdict = "discuss"
    return verdict, reasons


def record(env, name, checks=None, verdict=None, decided=False, category=None, group=False, environment=None):
    """Write checks (and a verdict, or with decided=True the person's decision) for an employer into EMPLOYER_CHECKS.
    group=True: the entry also covers every name that starts with its own (the group's units).
    environment: an environment_finding(), which replaces the saved one (reviews 0 never replaces a rating) and gets
    today's date. A check that replaces a different one keeps the old as a history item with "until". In a split file
    the checks go to the employer's checks.json, the history to history.json, the environment to environment.json and
    the status map to the summary (write_entry). Returns the merged entry."""
    path = env_path(env, "EMPLOYER_CHECKS")
    if not path:
        raise SystemExit("EMPLOYER_CHECKS is not set in job-search.env")
    data = checks_file(env)
    data.setdefault("employers", {})
    found, summary = find_own(env, name, data["employers"])
    entry = expand_entry(env, summary, SCOPES) if summary else {}
    entry.setdefault("checks", {})
    known = categories(env) if checks else []
    for cat, check in (checks or {}).items():
        if cat not in known:
            raise SystemExit(f"unknown category {cat!r}: one of {', '.join(known)}")
        check = {k: v for k, v in check.items() if k != "origin" and v not in (None, "")}
        check.setdefault("checked", today())
        old = entry["checks"].get(cat)
        # An "unknown" never replaces a result someone already found (flagged or clear).
        if old and check.get("status") == "unknown":
            continue
        if old and any(old.get(k) != check.get(k) for k in FOUND_FIELDS):
            # A new finding: the second check of the old one does not carry over (it is due again).
            earlier = {k: v for k, v in old.items() if k != "history"}
            check["history"] = list(old.get("history") or []) + [dict(earlier, until=today())]
        elif old:
            # The same finding again: it keeps its history and its second check, unless a new one comes with it.
            if old.get("history"):
                check["history"] = old["history"]
            if "own_level" not in check:
                check.update({k: old[k] for k in OWN_FIELDS if k in old})
        entry["checks"][cat] = check
    if environment and replaces_environment(entry.get("environment"), environment):
        entry["environment"] = dict(environment, checked=today())
    if verdict:
        entry["verdict"] = verdict
        entry["verdict_date"] = today()
    if group:
        entry["group"] = True
    if decided:
        decision = {"date": today(), "verdict": verdict}
        if category:
            decision["category"] = category
        entry.setdefault("decisions", []).append(decision)
    write_entry(env, data, found or name, entry)
    save_json(path, data)
    return entry


# Older trackers kept free-text screening hits; these map them to categories (for employer.py import-tracker).
CODES = {"A": ("defence", "direct"), "B": ("israel", "direct"), "U1": ("israel", "direct"), "U2": ("israel", "indirect"),
         "U3": ("israel", "indirect"), "U4": ("israel", "direct"), "U5": ("defence", "indirect")}
WORDS = [("israel", re.compile(r"(?i)israel|\bidf\b|settlement|who profits|\bbds\b|occupied|apartheid|gaza|tel aviv")),
         ("defence", re.compile(r"(?i)\barms?\b|defen[cs]e|military|weapon|munition|missile|fighter jet")),
         ("animal_cruelty", re.compile(r"(?i)animal|\bfur\b|vivisection")),
         ("climate", re.compile(r"(?i)climate|pollut|deforest|greenwash|emission|fossil")),
         ("sexism", re.compile(r"(?i)sexis|gender pay|sexual harass|sex discrim")),
         ("human_rights", re.compile(r"(?i)human rights|forced labou?r|uyghur|surveillance")),
         ("working_conditions", re.compile(r"(?i)union.bust|unpaid wage|labou?r abuse|unsafe work|sweatshop"))]
NOT_A_FLAG = re.compile(r"(?i)\b(not met|not the|borderline|possible|allegation|past|closed|eu level|sister|"
                        r"unverified|no tie|none found|not found)\b")


def classify(criterion, finding):
    """(category, level) for an older free-text hit, or (None, None) when it names no category or is not a flag."""
    head = (criterion or "").strip()
    if NOT_A_FLAG.search(head):
        return None, None
    m = re.match(r"([ABU])(\d)?", head)
    if m:
        code = m.group(1) + (m.group(2) or "") if m.group(1) == "U" else m.group(1)
        if code in CODES:
            return CODES[code]
    text = head + " " + (finding or "")
    for cat, pattern in WORDS:
        if pattern.search(text):
            indirect = re.search(r"(?i)minority|investor|other holdings|partner|customer|lender|creditor", text)
            return cat, "indirect" if indirect else "direct"
    return None, None
