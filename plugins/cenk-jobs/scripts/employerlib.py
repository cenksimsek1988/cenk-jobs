"""Employer rules, the shared blacklist and the person's own employer checks; used by employer.py, usage.py and
track.py.

Categories (templates/employer-rules.json): israel, defence, animal_cruelty, climate, sexism, human_rights,
working_conditions, sanctions, plus the person's own filters (a category with "custom": true in their rules).
A check is {status, level, fact, source_url, checked}:
  status  flagged (a crime-level finding with its source) | clear (checked, nothing found) | unknown (not checked)
  level   direct (the employer, its corporate group or its majority owner) | indirect (a minority investor, an
          investor's other holdings, a partner or a customer)
What a flagged check does comes from the person's EMPLOYER_RULES: action for a direct tie (exclude | discuss |
allow), indirect for an indirect one (discuss | warn | allow). The default is "discuss" for both: Claude shows the
finding and the person decides (allow or exclude).
An employer may also hold "environment": what employee reviews say, {rating, scale, reviews, complaints, source_url,
checked}, apart from the categories: it is shown to the person and never changes a verdict. "reviews": 0 means someone
looked and found none, so nobody looks again.

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


def blacklist():
    return load_json(BLACKLIST, {"employers": []})


def checks_file(env):
    return load_json(env_path(env, "EMPLOYER_CHECKS"), {"employers": {}})


def find_entry(entries, name):
    """The entry of a {name: entry} dict or [{name, aliases}] list that matches the name, else None. An exact match
    wins; then an entry marked "group": true matches every name that starts with its own (its units: "Acme" covers
    "Acme Cloud Services")."""
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


def decision_for(env, name):
    """The person's last decision for an employer: its own entry's, else that of a group entry covering it ("Acme",
    "group": true, covers "Acme Cloud" even when that has an entry of its own)."""
    employers = checks_file(env).get("employers", {})
    _, own = find_entry(employers, name)
    if (own or {}).get("decisions"):
        return own["decisions"][-1]
    for entry_name, entry in employers.items():
        if entry.get("group") and entry.get("decisions") and covered_by(name, [entry_name] + list(entry.get("aliases", []))):
            return entry["decisions"][-1]
    return None


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
    _, mine = find_entry((checks_file(env) if own is None else own).get("employers", {}), name)
    _, theirs = find_entry((blacklist() if shared is None else shared).get("employers", []), name)
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
    for cat, check in lookup(env, name).items():
        if check.get("status") != "flagged" or cat not in r["categories"]:
            continue
        setting = r["categories"][cat]
        level = check.get("level", "direct")
        if (setting.get("action", "discuss") if level == "direct" else setting.get("indirect", "discuss")) == "exclude":
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
        entry_name, entry = find_entry(employers, name)
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
                if (entry.get("checks", {}).get(cat) or {}).get("fact"):
                    return entry["checks"][cat]
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
            level = k.get("level", "direct")
            why.append(labels.get(cat, cat) + (" (indirect)" if level == "indirect" else ""))
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
        level = check.get("level", "direct")
        act = setting.get("action", "discuss") if level == "direct" else setting.get("indirect", "discuss")
        label = setting.get("label", cat)
        reasons.append(f"{act}: {label} ({level}): {check.get('fact', '')[:160]}")
        if act == "exclude":
            verdict = "exclude"
        elif act == "discuss" and verdict != "exclude":
            verdict = "discuss"
    return verdict, reasons


def record(env, name, checks=None, verdict=None, decided=False, category=None, group=False, environment=None):
    """Write checks (and a verdict, or with decided=True the person's decision) for an employer into EMPLOYER_CHECKS.
    group=True: the entry also covers every name that starts with its own (the group's units).
    environment: an environment_finding(), which replaces the saved one (reviews 0 never replaces a rating) and gets
    today's date."""
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
