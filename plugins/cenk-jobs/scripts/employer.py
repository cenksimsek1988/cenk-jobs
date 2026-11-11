"""Employer checks: the shared blacklist, the person's own results and their rules (see employerlib.py).

python -I employer.py check "<name>" ["<name>" ...] [--full]
                                                        what is known per category (shared list and own results),
                                                        what the person's rules say, and the verdict: exclude |
                                                        discuss | allow. Run it before screening a new employer.
                                                        match: exact | group | possible | none; possible: the saved
                                                        employers the name may be (a possible match is "discuss"
                                                        until alias or alias --not settles it). Opens only that
                                                        employer's checks.json; --full adds environment and history.
                                                        recheck: categories whose second check against the person's
                                                        own rules (their notes) is due; "allow" is "discuss" until
                                                        it is done
python -I employer.py own "<name>" <category> <direct|indirect|none> [why="..."]
                                                        the second check of a finding under the person's own rules
                                                        (their notes): the level for them and the rule it meets,
                                                        beside the finding, which stays as found; none = not counted
python -I employer.py recheck-running                   every employer with a running application (sent, not
                                                        rejected, closed or declined), judged again: prints those
                                                        whose verdict moved to exclude or discuss, or whose second
                                                        check is due, and saves each moved verdict
python -I employer.py rules                             the person's rules as they apply: their file filled from the
                                                        plugin's (levels, state category, what); for the workflow
python -I employer.py alias "<saved name>" "<other name>"   the other name finds the saved employer from now on
                                                        (its keys go into names.json); refused when one of its
                                                        keys already points to another employer
python -I employer.py alias --not "<a>" "<b>"           a and b are different employers: never offered again
python -I employer.py split [--apply]                   move each employer's checks, history and environment into
                                                        EMPLOYERS_DIR/<name>/ files and write names.json; a dry run
                                                        (counts and bytes) without --apply; with it, a backup first,
                                                        every entry proved equal, and only then the summary replaced
python -I employer.py record "<name>" <category> <flagged|clear|unknown> [level=direct|indirect] [fact="..."]
                             [source=<url>]              write one category result (a flagged one needs source=)
python -I employer.py environment "<name>" reviews=<n> [rating=<x>] [scale=5] [complaints="a; b"] [source=<url>]
                                                        save what employee reviews say (replaces the saved one, with
                                                        today's date); reviews=0: looked and found none, which
                                                        never replaces a saved rating
python -I employer.py decide "<name>" <exclude|allow> [<category>] [--group]
                                                        the person's answer to a "discuss": the value and the date,
                                                        with the category it was about (no quote); --group: the
                                                        decision covers the group's units too ("Acme": "Acme Cloud")
python -I employer.py repair-clear [--apply]            an israel or defence "clear" with no fact or source
                                                        becomes "unknown"; prints the counts, and with --apply writes them after a backup
python -I employer.py import-tracker                    fill EMPLOYER_CHECKS from an older {companies: [...]} tracker's
                                                        screening verdicts, hits and ties (adds, never overwrites)
python -I employer.py merge <report.json> [...] [--only-excluded] [--only-flagged] [--only-hits]
                             [--into <blacklist.json>]  for the plugin's developer: merge users' usage reports into
                                                        the shared data/blacklist.json (--only-hits: leave out
                                                        checks imported from an older tracker's weaker ties)
python -I employer.py merge --from-checks [--into <blacklist.json>]
                                                        for the plugin's developer: merge their own EMPLOYER_CHECKS
                                                        (every sourced finding, direct and indirect; never their
                                                        decisions) into the shared list
Categories: israel (a state category), defence, animal_cruelty, climate, sexism, human_rights, working_conditions,
sanctions, and the person's own filters ("custom": true in their EMPLOYER_RULES; another state has "state").
The summary file EMPLOYER_CHECKS keeps per employer the verdict, decisions and a status per category; the facts sit
in the employer's detail files (employerlib.py describes the layout). EMPLOYERS_DIR (job-search.env) is their folder.
Add --env <job-search.env> anywhere to pick the env file (merge needs none).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import employerlib as el  # noqa: E402
import jsenv  # noqa: E402
from trackerlib import expand_company, flat_jobs, json_indent  # noqa: E402

args = sys.argv[1:]
env_arg = None
if "--env" in args:
    i = args.index("--env")
    env_arg = args[i + 1]
    del args[i:i + 2]
group_flag = "--group" in args
args = [a for a in args if a != "--group"]
apply_flag = "--apply" in args
args = [a for a in args if a != "--apply"]
full_flag = "--full" in args
args = [a for a in args if a != "--full"]
not_flag = "--not" in args
args = [a for a in args if a != "--not"]
IMPORTED_UNKNOWN = "imported from an older tracker: no fact or source recorded"
if not args or args[0] not in ("check", "record", "environment", "decide", "repair-clear", "import-tracker", "merge",
                               "alias", "split", "own", "recheck-running", "rules"):
    sys.exit(__doc__)
cmd = args[0]


def pairs(items):
    out = {}
    for item in items:
        if "=" not in item:
            sys.exit(f"expected key=value, got {item!r}")
        k, v = item.split("=", 1)
        out[k] = v
    return out


def merge(reports, into, only_excluded, only_flagged, only_hits):
    data = el.load_json(into, {"employers": []})
    data["_about"] = ("The shared employer blacklist of the cenk-jobs plugin: per employer and category, a sourced "
                      "check (flagged, or clear when someone checked and found nothing). Built from users' usage "
                      "reports by employer.py merge; it holds no person's data. A flagged check needs its source. An "
                      "'environment' block holds what employee reviews say (rating, number of reviews, complaint "
                      "topics, source, date); it never decides anything.")
    data["categories"] = list(el.CATEGORIES)
    added = changed = 0
    for path in reports:
        report = path if isinstance(path, dict) else el.load_json(path, {})
        for emp in report.get("employers", []):
            if only_excluded and emp.get("verdict") != "exclude":
                continue
            checks = {c: k for c, k in emp.get("checks", {}).items()
                      if c in el.CATEGORIES and k.get("status") in ("flagged", "clear")
                      and (k.get("status") == "clear" or k.get("source_url"))
                      and (not only_flagged or k.get("status") == "flagged")
                      and (not only_hits or k.get("basis", "hit") == "hit")}
            # A filter on the checks asks for those checks only, so it leaves the employee reviews out too.
            environment = None
            if emp.get("environment") and not (only_flagged or only_hits):
                try:
                    environment = el.environment_from_report(emp["environment"])
                except (ValueError, TypeError, AttributeError) as problem:
                    print(f"left out the employee reviews of {emp['name']}: {problem}")
            if not checks and not environment:
                continue
            _, entry = el.find_entry(data["employers"], emp["name"])
            if entry is None:
                entry = {"name": emp["name"], "aliases": [], "checks": {}, "reports": 0}
                data["employers"].append(entry)
                added += 1
            entry["reports"] = entry.get("reports", 0) + 1
            for cat, new in checks.items():
                new = {k: new[k] for k in ("status", "level", "fact", "source_url", "checked", "basis") if new.get(k)}
                old = entry["checks"].get(cat)
                if not old:
                    entry["checks"][cat] = new
                elif new["status"] == "flagged" and (old["status"] == "clear" or (
                        old.get("level") != "direct" and new.get("level") == "direct")):
                    entry["checks"][cat] = new
                elif new["status"] == old["status"] and new.get("checked", "") > old.get("checked", ""):
                    entry["checks"][cat] = dict(old, checked=new["checked"]) if new["status"] == "clear" else new
                elif new["status"] == "clear" and old["status"] == "flagged":
                    old["clear_reports"] = old.get("clear_reports", 0) + 1
                else:
                    continue
                changed += 1
            if environment and el.environment_rank(environment) > el.environment_rank(entry.get("environment") or {}):
                entry["environment"] = environment
                changed += 1
            entry["updated"] = el.today()
    data["employers"].sort(key=lambda e: e["name"].lower())
    data["updated"] = el.today()
    el.save_json(into, data)
    print(f"{into}: {len(data['employers'])} employers ({added} new), {changed} category checks added or changed")


if cmd == "merge":
    rest = [a for a in args[1:] if not a.startswith("--")]
    into = el.BLACKLIST
    if "--into" in args:
        into = args[args.index("--into") + 1]
        rest.remove(into)
    if "--from-checks" in args:
        # The developer's own checks, shaped like a usage report: the checks only, never their decisions, and every
        # part of their name in a fact replaced (seen: a fact naming the developer, 6 Nov 2026).
        dev_env = jsenv.load(env_arg, __file__)
        parts = {p for k in ("PERSON_NAME", "NAME_ON_CV") for w in (dev_env.get(k) or "").split() if len(w) >= 3
                 for p in (w, w.translate(jsenv.ASCII))}
        person = re.compile(r"(?i)(?<![\w-])(" + "|".join(map(re.escape, sorted(parts))) + r")(?![\w-])") if parts else None

        def unnamed(check):
            return dict(check, fact=person.sub("the person", check.get("fact", ""))) if person else check
        rest.append({"employers": [{"name": name, "verdict": entry.get("verdict"),
                                    "checks": {c: unnamed(k) for c, k in entry.get("checks", {}).items()},
                                    "environment": entry.get("environment")}
                                   for name, entry in el.merged_entries(dev_env)]})
    if not rest:
        sys.exit("merge needs at least one report file, or --from-checks")
    merge(rest, into, "--only-excluded" in args, "--only-flagged" in args, "--only-hits" in args)
    sys.exit(0)

env = jsenv.load(env_arg, __file__)
if cmd == "check":
    rule_set = el.rules(env)
    employers = el.checks_file(env).get("employers", {})  # the summary, read once for every name
    out = [el.check_view(env, name, rule_set, full_flag, employers) for name in args[1:]]
    print(json.dumps(out, ensure_ascii=False, indent=1))
elif cmd == "rules":
    print(json.dumps(el.rules(env), ensure_ascii=False, indent=1))
elif cmd == "own":
    if len(args) < 4:
        sys.exit(__doc__)
    if args[2] not in el.categories(env):
        sys.exit(f"category must be one of {', '.join(el.categories(env))}")
    check = el.set_own(env, args[1], args[2], args[3], pairs(args[4:]).get("why", ""))
    print(args[1], args[2], "found", check.get("level", "direct"), "-> for the person", check["own_level"])
elif cmd == "recheck-running":
    tracker_path = env.path("TRACKER") if env.get("TRACKER") else ""
    pipeline_path = env.path("PIPELINE") if env.get("PIPELINE") else ""
    rows = el.recheck_running(env, flat_jobs(el.load_json(tracker_path, {})), el.load_json(pipeline_path, {}))
    print(json.dumps(rows, ensure_ascii=False, indent=1) if rows else "nothing moved: no running application needs the person")
elif cmd == "alias":
    if len(args) != 3:
        sys.exit(__doc__)
    if not_flag:
        n = el.not_same(env, args[1], args[2])
        print(f"{args[1]} and {args[2]} are different employers: {n} key pair(s) recorded in names.json")
    else:
        name, added = el.alias(env, args[1], args[2])
        print(f"{args[2]} now finds {name} (keys: {', '.join(added)})")
elif cmd == "split":
    path = env.path("EMPLOYER_CHECKS")
    data = el.load_json(path, {"employers": {}})
    summaries, files, names, pairs, st = el.plan_split(env, data)
    if not st["moved"]:
        print(f"nothing to split: {st['entries']} entries, none with checks or an environment left in the summary")
        sys.exit(0)
    print(f"{st['moved']} of {st['entries']} entries to split into {st['files']} files "
          f"({st['detail_bytes']} bytes); {os.path.basename(path)} {st['before_bytes']} -> {st['after_bytes']} bytes; "
          f"names.json {st['keys']} keys ({st['collisions']} shared by two entries, first entry wins)")
    if not apply_flag:
        print("dry run: nothing written; add --apply to split")
        sys.exit(0)
    backup = el.apply_split(env, path, data, (summaries, files, names, pairs, st))
    print(f"split; every entry proved equal to its original; backup {backup}")
elif cmd == "record":
    if len(args) < 4:
        sys.exit(__doc__)
    name, cat, status = args[1], args[2], args[3]
    extra = pairs(args[4:])
    if status not in el.STATUSES:
        sys.exit(f"status must be one of {', '.join(el.STATUSES)}")
    if status == "flagged" and not extra.get("source"):
        sys.exit("a flagged check needs source=<url>")
    level = extra.get("level", "direct")
    if level not in el.LEVELS:
        sys.exit(f"level must be one of {', '.join(el.LEVELS)}")
    el.record(env, name, {cat: {"status": status, "level": level, "fact": extra.get("fact", ""),
                                "source_url": extra.get("source", "")}})
    print(name, cat, status, level)
elif cmd == "environment":
    if len(args) < 3:
        sys.exit(__doc__)
    extra = pairs(args[2:])
    try:
        finding = el.environment_finding(extra.get("reviews", ""), extra.get("rating"), extra.get("scale", 5),
                                         extra.get("complaints", ""), extra.get("source", ""))
    except ValueError as problem:
        sys.exit(str(problem))
    entry = el.record(env, args[1], environment=finding)
    print(args[1], json.dumps(entry["environment"], ensure_ascii=False))
    if not finding.get("reviews") and entry["environment"].get("reviews"):
        print("kept the saved rating: reviews=0 never replaces one")
elif cmd == "decide":
    if len(args) < 3 or args[2] not in el.DECISIONS:
        sys.exit(__doc__)
    category = args[3] if len(args) > 3 else None
    if category and category not in el.categories(env):
        sys.exit(f"category must be one of {', '.join(el.categories(env))}")
    el.record(env, args[1], verdict=args[2], decided=True, category=category, group=group_flag)
    # An older {companies: [...]} tracker keeps a verdict per company: the person's decision replaces it there. A decision
    # on one category: "exclude" still excludes the employer; "allow" replaces only a "discuss", since another category
    # may still exclude it.
    path = env.path("TRACKER")
    tracker = el.load_json(path, {})
    for company in tracker.get("companies", []):
        old = company.get("verdict")
        replaces = old != args[2] and (not category or args[2] == "exclude" or old == "discuss")
        if replaces and el.keys(company.get("name", "")) & el.keys(args[1]):
            company["verdict"] = args[2]
            company["decided"] = {"date": el.today(), **({"category": category} if category else {})}
            with open(path + ".tmp", "w", encoding="utf-8") as f:
                json.dump(tracker, f, ensure_ascii=False, indent=json_indent(path))
            os.replace(path + ".tmp", path)
            break
    print(args[1], "->", args[2])
elif cmd == "repair-clear":
    path = env.path("EMPLOYER_CHECKS")
    data = el.load_json(path, {"employers": {}})
    counts, employers, changed = {}, set(), {}
    for name, summary in data.get("employers", {}).items():
        # a split entry whose status map shows no clear israel or defence check needs no detail file opened
        if summary.get("details") and not any((summary.get("status") or {}).get(c) == "clear" for c in ("israel", "defence")):
            continue
        entry = el.expand_entry(env, summary, ("checks", "environment", "history"))
        for cat in ("israel", "defence"):  # the only categories the older import-tracker wrote as "clear"
            check = (entry.get("checks") or {}).get(cat) or {}
            if check.get("status") == "clear" and not check.get("fact") and not check.get("source_url"):
                counts[cat] = counts.get(cat, 0) + 1
                employers.add(name)
                check.update(status="unknown", fact="no fact or source was recorded for this check")
                changed[name] = entry
    print(f"{len(employers)} employers;", ", ".join(f"{c}: {n}" for c, n in sorted(counts.items())) or "nothing to repair")
    if apply_flag and employers:
        el.apply_repair(env, path, data, changed)
        print("written, with a backup beside it")
elif cmd == "import-tracker":
    tracker = el.load_json(env.path("TRACKER"), {})
    if "companies" not in tracker:
        sys.exit("import-tracker reads the older {companies: [...]} tracker, which this TRACKER is not")
    have = el.checks_file(env).get("employers", {})
    imported = 0
    for company in tracker["companies"]:
        verdict = company.get("verdict")
        if verdict not in ("exclude", "allow", "clear"):
            continue
        company = expand_company(env.path("TRACKER"), company)  # a split tracker keeps hits and ties in a detail file
        found = {}
        # basis "hit": a finding the earlier screen judged exclusion-level; "tie": one of its weaker ties.
        hits = [(h.get("criterion", ""), h.get("finding", ""), h.get("source_url", ""), "hit")
                for h in company.get("hits") or []]
        ties = [("", t, "", "tie") for k, v in company.items() if k.startswith("ties") for t in (v or [])]
        for criterion, finding, source, basis in hits + ties:
            if not criterion and el.NOT_A_FLAG.search(finding[:80]):
                continue
            cat, level = el.classify(criterion, finding)
            if not cat:
                continue
            if not source:
                urls = [w for w in finding.split() if w.startswith("http")]
                source = urls[0].rstrip(",;.)") if urls else ""
            if not source:
                continue
            old = found.get(cat)
            # A hit beats a tie, and then a direct finding an indirect one.
            rank = (basis == "hit", level == "direct")
            if old and (old["basis"] == "hit", old["level"] == "direct") >= rank:
                continue
            found[cat] = {"status": "flagged", "level": level, "fact": finding[:500], "source_url": source,
                          "basis": basis}
        for cat in ("israel", "defence"):  # the earlier screening kept no fact or source for these: nobody can tell
            found.setdefault(cat, {"status": "unknown", "fact": IMPORTED_UNKNOWN})
        _, own = el.find_own(env, company["name"], have)
        new = {c: k for c, k in found.items() if c not in el.entry_checks(env, own or {})}
        if new:
            el.record(env, company["name"], new, verdict="exclude" if verdict == "exclude" else "allow")
            imported += 1
    print(f"imported checks for {imported} employers into {env.path('EMPLOYER_CHECKS')}")
