"""The free employer lookup: public data (Wikidata) for an employer never checked, before any model is used.

python -I employer_lookup.py <name> [<name> ...] [--file <search file>] [--record] [--out <file>] [--from <dir>]
    one line per employer: name | verdict | why | Wikidata item | seconds. Verdicts:
      exclude      a finding the person's rules exclude (example: its industry is the arms industry and they exclude
                   direct defence ties): the job stops before any token is spent
      go on        a finding that does not exclude, or the item was found with nothing that touches a rule
      undecided    no single item matches the name, or a fact needs the person's own rules (example: its country is
                   a state category's state): the cheap check decides, if a posting fits
      known        the employer is in the records already: nothing is fetched
    An employer looked up before (the cache) gets its earlier verdict without a request.
    --file: the employers of a search file (collect_postings.py --out). --record: write each finding with its source
    into EMPLOYER_CHECKS (employer.py record) and every lookup into the cache, EMPLOYERS_DIR/public-lookup.json, so no
    employer is looked up twice. --out: the verdicts as JSON for the workflow. --from <dir>: Wikidata's answers from
    <dir>/<name>.json ({search, entity, labels}) instead of the web, for tests.
Wikidata throttled one request a second (three 429s in 30 requests, 15 Nov 2026): the script waits 2 seconds between
requests and 30 seconds after a 429 and tries again; a second 429 puts the employer at the end of the queue after a
pause of 60 seconds (--wait <seconds>), at most 5 pauses a run; only then is the rest "undecided: not looked up"
(seen: one 429 left 29 of 55 employers unlooked). A name holding " | " is printed with " / ". About 3 requests per employer: about
6 seconds, so about 3 minutes for a run of 30 postings; run it during the search, before the funnel.
What it reads: the item's industry (P452), country (P17), country of origin (P495), parent (P749) and owner (P127).
What it finds: defence by the industry or the item's description (arms, defence, military, weapons, munitions),
a direct tie; a state category's state as the item's country (where it is headquartered) or country of origin
(where it was founded), a direct tie by the plugin's levels. The person's settings then decide: an exclusion stops
the job here. A finding the settings do not exclude, in a category with the person's own notes (example: "Western
arms producers are excluded"), is left to the cheap check, since only a model reads the notes. Everything else
stays unknown: the lookup never writes "clear".
Add --env <job-search.env> anywhere to pick the env file.
"""
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import employerlib as el  # noqa: E402
import jsenv  # noqa: E402

API = "https://www.wikidata.org/w/api.php?"
UA = {"User-Agent": "cenk-jobs-plugin/0.34 (employer lookup; one request every 2 seconds)"}
DEFENCE = re.compile(r"(?i)\b(arms|armaments?|defen[cs]e|military|weapons?|munitions?)\b")
SUFFIX = re.compile(r"\.(io|com|ai|co|net|org|de|it|es|fr)$")
last_call = [0.0]


class Throttled(Exception):
    pass


throttled_once = set()
PAUSES = 5


def ask(params):
    wait = 2.0 - (time.monotonic() - last_call[0])
    if wait > 0:
        time.sleep(wait)
    url = API + urllib.parse.urlencode({**params, "format": "json"})
    for attempt in (1, 2):
        last_call[0] = time.monotonic()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as problem:
            if problem.code != 429 or attempt == 2:
                raise Throttled(f"HTTP {problem.code}") from problem
            time.sleep(30)
    return {}


def plain(name):
    """The name as the employer check compares it: no web suffix, legal form, punctuation or part in brackets."""
    whole = re.sub(r"\([^)]*\)", " ", SUFFIX.sub("", name.lower().strip()))
    return " ".join(sorted(el.keys(whole), key=len, reverse=True)[:1]) or whole.strip()


def facts_of(name, from_dir):
    """(item id, label, description, {industry, country, origin, parent, owner: [labels]}, exact) or None when no
    item matches. exact: the item's name is the employer's name (web suffix and legal form aside); otherwise it is
    the only item whose name starts with the employer's name, and the result only informs the cheap check."""
    if from_dir:
        # Tests: <name>.throttle answers 429 to the first request for that name in a run.
        if os.path.isfile(os.path.join(from_dir, re.sub(r"[^A-Za-z0-9]+", "-", name) + ".throttle")) \
                and name not in throttled_once:
            throttled_once.add(name)
            raise Throttled("HTTP 429")
        path = os.path.join(from_dir, re.sub(r"[^A-Za-z0-9]+", "-", name) + ".json")
        if not os.path.isfile(path):
            return None
        with open(path, encoding="utf-8") as fh:
            saved = json.load(fh)
        return saved["id"], saved["label"], saved.get("description", ""), saved.get("facts", {}), saved.get("exact", True)
    base = plain(name)
    hits = ask({"action": "query", "list": "search", "srsearch": f"{base} haswbstatement:P452", "srlimit": 5})
    ids = [h["title"] for h in hits.get("query", {}).get("search", [])]
    if not ids:
        return None
    items = ask({"action": "wbgetentities", "ids": "|".join(ids), "props": "labels|descriptions|claims",
                 "languages": "en"}).get("entities", {})
    label = lambda e: (e.get("labels", {}).get("en") or {}).get("value", "")  # noqa: E731
    exact = [i for i in ids if plain(label(items.get(i, {}))) == base]
    starts = [i for i in ids if re.match(re.escape(base) + r"\b", label(items.get(i, {})).lower())]
    pick = exact[:1] or (starts if len(starts) == 1 else [])
    if not pick:
        return None
    item = items.get(pick[0])
    if not item:
        return None
    claims = item.get("claims", {})
    refs = {key: [c["mainsnak"]["datavalue"]["value"]["id"] for c in claims.get(prop, [])
                  if c.get("mainsnak", {}).get("datavalue")]
            for key, prop in (("industry", "P452"), ("country", "P17"), ("origin", "P495"), ("parent", "P749"),
                              ("owner", "P127"))}
    wanted = sorted({q for qs in refs.values() for q in qs})[:50]
    names = ask({"action": "wbgetentities", "ids": "|".join(wanted), "props": "labels", "languages": "en"}).get(
        "entities", {}) if wanted else {}
    facts = {k: [label(names.get(q, {})) or q for q in qs] for k, qs in refs.items() if qs}
    return pick[0], label(item), (item.get("descriptions", {}).get("en") or {}).get("value", ""), facts, bool(exact)


def judge(env, name, found, rule_set):
    """(verdict, why, checks to record) from the facts against the person's rules."""
    if not found:
        return "undecided", "no single Wikidata item matches the name", {}
    qid, label, description, facts, exact = found
    source = f"https://www.wikidata.org/wiki/{qid}"
    checks = {}
    defence = [x for x in facts.get("industry", []) if DEFENCE.search(x)] or (
        [description] if DEFENCE.search(description) else [])
    if defence:
        checks["defence"] = {"status": "flagged", "level": "direct", "source_url": source,
                             "fact": f"Wikidata ({label}): {'; '.join(defence)[:200]}"}
    # Founded in a state or headquartered there: a direct tie to that state (the plugin's levels).
    for cat, s in rule_set["categories"].items():
        state = str(s.get("state") or "")
        hits = [f"{how} {p}" for how, key in (("headquartered in", "country"), ("founded in", "origin"))
                for p in facts.get(key, []) if state and p.lower() == state.lower()]
        if hits:
            checks[cat] = {"status": "flagged", "level": "direct", "source_url": source,
                           "fact": f"Wikidata ({label}): {'; '.join(hits)}"}
    if not exact:
        # Only a prefix match ("Gamma" and "Gamma Defence Systems"): never a finding of its own, only a lead.
        lead = "; ".join(f"{c}: {k['fact']}" for c, k in checks.items()) or "nothing that touches a rule"
        return "undecided", f"not certain it is the same employer: Wikidata {qid} ({label}): {lead}"[:300], {}
    if not checks:
        return "go on", f"Wikidata ({label}): nothing that touches a rule", checks
    why = "; ".join(f"{c}: {k['fact']}" for c, k in checks.items())[:300]
    if el.decide(env, name, checks, rule_set)[0] == "exclude":
        return "exclude", why, checks
    # Not excluded by the settings, but the person's own notes for that category may exclude it: a model reads them.
    if any(str(rule_set["categories"].get(c, {}).get("notes") or "").strip() for c in checks):
        return "undecided", why + " | the person's notes for the category decide", checks
    return "go on", why, checks


def main():
    args = sys.argv[1:]
    opts = {}
    for flag in ("--env", "--file", "--out", "--from", "--wait"):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                sys.exit(f"{flag} takes a value")
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    record = "--record" in args
    names = [a for a in args if a != "--record"]
    env = jsenv.load(opts.get("--env"), __file__)
    if opts.get("--file"):
        with open(opts["--file"], encoding="utf-8") as fh:
            names += [c["name"] for c in json.load(fh).get("companies", [])]
    if not names:
        sys.exit(__doc__)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    cache_path = os.path.join(el.employers_dir(env), "public-lookup.json") if el.employers_dir(env) else ""
    cache = {}
    if cache_path and os.path.isfile(cache_path):
        with open(cache_path, encoding="utf-8") as fh:
            cache = json.load(fh)
    rule_set = el.rules(env)
    out, throttled, pauses = {}, "", 0
    try:
        wait = float(opts.get("--wait", 60))
    except ValueError:
        sys.exit("--wait takes seconds")
    queue = list(dict.fromkeys(names))
    while queue:
        name = queue.pop(0)
        start = time.monotonic()
        view = el.check_view(env, name, rule_set)
        if view["verdict"] == "exclude":
            out[name] = {"verdict": "exclude", "why": "in the list: " + "; ".join(view["reasons"])[:200]}
        elif not view.get("never_checked"):
            out[name] = {"verdict": "known", "why": "in the records"}
        elif name in cache:
            # Looked up before: no request; the saved facts are judged again under today's rules and notes, so a
            # changed setting counts, and an undecided one still gets its cheap check.
            saved = cache[name]
            found = tuple(saved["found"]) if saved.get("found") else None
            verdict, why, checks = judge(env, name, found, rule_set)
            out[name] = {"verdict": verdict, "why": f"looked up {saved.get('date', '')}: {why}", "item": found[0] if found else ""}
            if record:
                for cat, check in checks.items():
                    el.record(env, name, {cat: check})
        elif throttled:
            out[name] = {"verdict": "undecided", "why": f"not looked up: Wikidata {throttled}"}
        else:
            try:
                found = facts_of(name, opts.get("--from"))
            except Throttled as problem:
                if pauses < PAUSES:
                    # Wikidata asks to slow down: a pause, and this employer goes again after the others.
                    pauses += 1
                    time.sleep(wait)
                    queue.append(name)
                    continue
                throttled = str(problem)
                out[name] = {"verdict": "undecided", "why": f"not looked up: Wikidata {problem}"}
            except (OSError, ValueError) as problem:
                out[name] = {"verdict": "undecided", "why": f"not looked up: Wikidata {problem}"}
            else:
                verdict, why, checks = judge(env, name, found, rule_set)
                out[name] = {"verdict": verdict, "why": why, "item": found[0] if found else ""}
                if record:
                    for cat, check in checks.items():
                        el.record(env, name, {cat: check})
                    cache[name] = {"date": datetime.date.today().isoformat(), "found": list(found) if found else None,
                                   **out[name]}
        out[name]["seconds"] = round(time.monotonic() - start, 1)
        print(" | ".join(str(x).replace(" | ", " / ") for x in (name, out[name]["verdict"], out[name]["why"],
                                                                 out[name].get("item", ""), f"{out[name]['seconds']} s")))
    if record and cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path + ".tmp", "w", encoding="utf-8", newline="\n") as fh:
            json.dump(cache, fh, ensure_ascii=False, indent=1)
        os.replace(cache_path + ".tmp", cache_path)
    if opts.get("--out"):
        with open(opts["--out"], "w", encoding="utf-8", newline="\n") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
    counts = {}
    for v in out.values():
        counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
    print(f"{len(out)} employers: " + ", ".join(f"{n} {k}" for k, n in sorted(counts.items())))


if __name__ == "__main__":
    main()
