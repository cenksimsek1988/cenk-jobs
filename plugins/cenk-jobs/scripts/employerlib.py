"""Employer rules, the shared blacklist and the person's own employer checks; used by employer.py, usage.py and
track.py.

Categories (templates/employer-rules.json): israel, defence, animal_cruelty, climate, sexism, human_rights,
working_conditions, sanctions, plus the person's own filters (a category with "custom": true in their rules).
A check is {status, level, fact, source_url, checked}:
  status  flagged (a crime-level finding with its source) | clear (checked, nothing found) | unknown (not checked)
  level   direct (the employer, its corporate group or its majority owner) | indirect (a minority investor, an
          investor's other holdings, a partner or a customer)
What a flagged check does comes from the person's EMPLOYER_RULES: action for a direct tie (never | ask | apply),
indirect for an indirect one (ask | warn | apply). The defaults are "ask" for both: warn and ask first.

Files:
  data/blacklist.json   in the plugin: the shared list, {employers: [{name, aliases, checks: {category: check}}]},
                        built by the developer from users' reports (employer.py merge). Users only read it.
  EMPLOYER_RULES        the person's settings, a copy of templates/employer-rules.json (defaults when not set).
  EMPLOYER_CHECKS       the person's own results: {employers: {name: {checks: {category: check}, verdict,
                        verdict_date, decisions: [{date, verdict, category}]}}}. Their own checks win over the
                        shared list's. A decision is a value and a date, never a quote (older entries may hold
                        "words"; they are read, never written).
"""
import datetime
import json
import os
import re

PLUGIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLACKLIST = os.path.join(PLUGIN, "data", "blacklist.json")
DEFAULT_RULES = os.path.join(PLUGIN, "templates", "employer-rules.json")
# The shared categories; only these go into the shared blacklist. A person's own filters add to them in their rules.
CATEGORIES = ("israel", "defence", "animal_cruelty", "climate", "sexism", "human_rights", "working_conditions",
              "sanctions")
STATUSES = ("flagged", "clear", "unknown")
LEVELS = ("direct", "indirect")
ACTIONS = ("never", "ask", "apply")
INDIRECT_ACTIONS = ("ask", "warn", "apply")
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
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def keys(name):
    """Lookup keys for an employer name: the name without punctuation and legal forms, plus each part in brackets
    ("Amazon (AWS)" -> "amazon aws", "amazon", "aws")."""
    out = set()
    parts = [name] + re.findall(r"\(([^)]*)\)", name) + [re.sub(r"\([^)]*\)", " ", name)]
    for part in parts:
        k = re.sub(r"[^a-z0-9]+", " ", part.lower().replace(".", ""))  # "N.V." -> "nv"
        k = re.sub(r"\s+", " ", LEGAL.sub(" ", k)).strip()
        if len(k) >= 2:
            out.add(k)
    return out


def env_path(env, key):
    return env.path(key) if env.get(key) else ""


def rules(env):
    """The person's rules, with any missing category filled from the defaults."""
    default = load_json(DEFAULT_RULES, {})
    own = load_json(env_path(env, "EMPLOYER_RULES"), {})
    merged = dict(default, **{k: v for k, v in own.items() if k != "categories"})
    merged["categories"] = {c: dict(default.get("categories", {}).get(c, {}), **own.get("categories", {}).get(c, {}))
                            for c in CATEGORIES}
    # The person's own filters (example: gambling) count like the shared categories, for them only.
    merged["categories"].update({c: s for c, s in own.get("categories", {}).items()
                                 if c not in CATEGORIES and s.get("custom")})
    return merged


def categories(env):
    """Every category the person's rules check: the shared ones, then their own filters."""
    return list(rules(env)["categories"])


def blacklist():
    return load_json(BLACKLIST, {"employers": []})


def checks_file(env):
    return load_json(env_path(env, "EMPLOYER_CHECKS"), {"employers": {}})


def find_entry(entries, name):
    """The entry of a {name: entry} dict or [{name, aliases}] list that matches the name, else None."""
    wanted = keys(name)
    items = entries.items() if isinstance(entries, dict) else [(e.get("name", ""), e) for e in entries]
    for entry_name, entry in items:
        names = [entry_name] + list(entry.get("aliases", []))
        if any(wanted & keys(n) for n in names):
            return entry_name, entry
    return None, None


def on_never_list(name, names):
    """A never-apply name matches the employer's name, a part of it in brackets, or any of them that starts with it as
    whole words: "Acme" matches "Acme Cloud Services" (and "Nova" also "Nova Path", another company). always_ok
    stays exact, so a trusted name never lets a different company through."""
    mine = keys(name)
    return any(m == k or m.startswith(k + " ") for n in names for k in keys(n) for m in mine)


def lookup(env, name):
    """Every known check for an employer: {category: dict(check, origin=shared|own)}; own results win."""
    out = {}
    _, shared = find_entry(blacklist().get("employers", []), name)
    for cat, check in (shared or {}).get("checks", {}).items():
        out[cat] = dict(check, origin="shared")
    _, own = find_entry(checks_file(env).get("employers", {}), name)
    for cat, check in (own or {}).get("checks", {}).items():
        if cat not in out or check.get("status") != "unknown":
            out[cat] = dict(check, origin="own")
    return out


def excluding(env, name, rule_set=None):
    """What makes the person's rules exclude an employer: [{category, origin, level}], empty when they do not.
    origin: list (their never_apply list), decision (their answer to an ask), shared (a finding from the shared
    blacklist) or own (their own check)."""
    r = rule_set or rules(env)
    if on_never_list(name, r.get("never_apply", [])):
        return [{"category": "", "origin": "list"}]
    if any(keys(name) & keys(n) for n in r.get("always_ok", [])):
        return []
    _, own = find_entry(checks_file(env).get("employers", {}), name)
    if (own or {}).get("decisions"):
        last = own["decisions"][-1]
        return [{"category": last.get("category", ""), "origin": "decision"}] if last["verdict"] == "exclude" else []
    out = []
    for cat, check in lookup(env, name).items():
        if check.get("status") != "flagged" or cat not in r["categories"]:
            continue
        setting = r["categories"][cat]
        level = check.get("level", "direct")
        if (setting.get("action", "ask") if level == "direct" else setting.get("indirect", "ask")) == "never":
            out.append({"category": cat, "origin": check.get("origin", "own"), "level": level})
    return out


def decide(env, name, checks, rule_set=None):
    """(verdict, reasons) from the person's rules: exclude | ask | apply. A 'warn' reason comes with apply."""
    r = rule_set or rules(env)
    if on_never_list(name, r.get("never_apply", [])):
        return "exclude", ["on the person's never_apply list"]
    if any(keys(name) & keys(n) for n in r.get("always_ok", [])):
        return "apply", ["on the person's always_ok list"]
    _, own = find_entry(checks_file(env).get("employers", {}), name)
    if (own or {}).get("decisions"):
        last = own["decisions"][-1]
        why = f" ({last['category']})" if last.get("category") else ""
        return last["verdict"], [f"the person decided {last['verdict']} on {last['date']}{why}"]
    verdict, reasons = "apply", []
    for cat, check in checks.items():
        if check.get("status") != "flagged" or cat not in r["categories"]:
            continue
        setting = r["categories"][cat]
        level = check.get("level", "direct")
        act = setting.get("action", "ask") if level == "direct" else setting.get("indirect", "ask")
        label = setting.get("label", cat)
        reasons.append(f"{act}: {label} ({level}): {check.get('fact', '')[:160]}")
        if act == "never":
            verdict = "exclude"
        elif act == "ask" and verdict != "exclude":
            verdict = "ask"
    return verdict, reasons


def record(env, name, checks=None, verdict=None, decided=False, category=None):
    """Write checks (and a verdict, or with decided=True the person's decision) for an employer into EMPLOYER_CHECKS."""
    path = env_path(env, "EMPLOYER_CHECKS")
    if not path:
        raise SystemExit("EMPLOYER_CHECKS is not set in job-search.env")
    data = checks_file(env)
    found, entry = find_entry(data["employers"], name)
    entry = entry or {"checks": {}}
    known = categories(env) if checks else []
    for cat, check in (checks or {}).items():
        if cat not in known:
            raise SystemExit(f"unknown category {cat!r}: one of {', '.join(known)}")
        check = {k: v for k, v in check.items() if k != "origin" and v not in (None, "")}
        check.setdefault("checked", today())
        # An "unknown" never replaces a result someone already found (flagged or clear).
        if entry["checks"].get(cat) and check.get("status") == "unknown":
            continue
        entry["checks"][cat] = check
    if verdict:
        entry["verdict"] = verdict
        entry["verdict_date"] = today()
    if decided:
        decision = {"date": today(), "verdict": verdict}
        if category:
            decision["category"] = category
        entry.setdefault("decisions", []).append(decision)
    data["employers"][found or name] = entry
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
