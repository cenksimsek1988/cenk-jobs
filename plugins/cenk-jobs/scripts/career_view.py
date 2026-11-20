"""One part of the master record, so a job reads what it needs instead of the whole file.

python -I career_view.py screen [--out <file>]   the employer rules and the person's decisions: for screening an employer
python -I career_view.py fit [--out <file>]      what the fit check needs, about a third of facts: profile,
                                                 employment timeline, education, skills, languages, where they will
                                                 work, pay rule, availability, and the person's languages, location
                                                 and work authorisation from their profile
python -I career_view.py facts [--out <file>]    what a letter or a form may use: profile (CV wording), experience,
                                                 skills, education, where they will work, pay rule, form answers, CV
                                                 rules, never-claim lists; from the person's profile (profilelib.py):
                                                 person (name, pronouns, contact, location, languages, links,
                                                 nationality, work authorisation), employment, and the names in
                                                 the setting form_facts. Never private or contacts.
python -I career_view.py cvs [--out <file>]     the CV versions for the workflow's cvs: [{variant, file, use}], only
                                                 those whose PDF exists in CVS_DIR (each missing one is named on
                                                 stderr: build it with build_cv.py)
python -I career_view.py pay "<city>" [--set "<figure>"]
                                                 the person's pay figure for that city from PAY_TABLE (private;
                                                 default apply/pay-by-city.json); --set adds it, worked out once from
                                                 the pay rule. collect_postings.py gives each posting its city's figure.
python -I career_view.py scope [--set <key>=<a,b> ...]
                                                 the search scope (preferences.locations.search_scope): remote_regions
                                                 stands for REMOTE_REGIONS and any_mode_places for PLACES in the search
                                                 scripts, each when set. --set writes the keys given, only with the
                                                 person's yes; an empty value removes that key. Example: scope --set
                                                 remote_regions=EU,Worldwide any_mode_places=Springfield
Prints the JSON, or with --out writes it and prints the path and size. Add --env <job-search.env> to pick the env file.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jsenv  # noqa: E402
import profilelib as pl  # noqa: E402

SCOPES = {
    "screen": ("preferences.employer_rules", "decisions"),
    "fit": ("profile", "employment_timeline", "education", "skills", "languages", "preferences.locations",
            "preferences.work_modes", "preferences.pay", "preferences.availability"),
    "facts": ("profile", "employment_timeline", "experience", "education", "certificates", "skills", "languages",
              "preferences.locations", "preferences.work_modes", "preferences.pay", "preferences.availability",
              "form_answers", "cv_rules"),
}
# The only person keys in the facts view: agents read it and write prepared answers and letters, so a value here would
# be copied. Address, birth date and any key added later stay out.
PERSON_SHOWN = ("name", "pronouns", "email", "phone", "location", "languages", "links", "nationality",
                "work_authorisation")
args = sys.argv[1:]


def option(name):
    if name not in args:
        return None
    i = args.index(name)
    value = args[i + 1]
    del args[i:i + 2]
    return value


env_arg, out, set_to = option("--env"), option("--out"), option("--set")
if len(args) == 2 and args[0] == "pay":
    # One city's pay figure from PAY_TABLE; --set adds or changes it (worked out once from the pay rule).
    from trackerlib import pay_table
    env = jsenv.load(env_arg, __file__)
    path, table = pay_table(env)
    if set_to is not None:
        for key in [k for k in table if k.lower() == args[1].lower()]:
            del table[key]  # one key per city, whatever its case
        table[args[1]] = set_to
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(table, f, ensure_ascii=False, indent=1)
    figure = next((v for k, v in table.items() if k.lower() == args[1].lower()), "")
    print(figure or f"no figure for {args[1]}: work it out from the pay rule, then --set it")
    sys.exit(0)
if args and args[0] == "scope":
    # The scope a person states reaches the scripts only through these two keys (seen 20 Nov: never written, so 89 of
    # 103 postings of one run were out of scope).
    from trackerlib import json_indent
    SCOPE_KEYS = ("remote_regions", "any_mode_places")
    env = jsenv.load(env_arg, __file__)
    path = env.path("MASTER_RECORD")
    if not os.path.isfile(path):
        sys.exit(f"{path}: no master record (MASTER_RECORD in job-search.env)")
    if args[1:] and set_to is None:
        sys.exit("scope alone prints the scope; scope --set <key>=<a,b> ... writes it")
    with open(path, encoding="utf-8") as f:
        record = json.load(f)
    pairs = [set_to] + args[1:] if set_to is not None else []
    prefs = record.setdefault("preferences", {})
    if pairs:
        given = dict(p.split("=", 1) for p in pairs if "=" in p)
        if len(given) != len(pairs) or set(given) - set(SCOPE_KEYS):
            sys.exit("scope --set takes " + " ".join(k + "=<a,b>" for k in SCOPE_KEYS))
        if isinstance(prefs.get("locations"), list):
            # An older record keeps its places as a list: they stay, as locations.places.
            prefs["locations"] = {"places": prefs["locations"]}
            print("preferences.locations was a list: kept as preferences.locations.places")
        scope = prefs.setdefault("locations", {}).setdefault("search_scope", {})
        for key, value in given.items():
            values = [v.strip() for v in value.split(",") if v.strip()]
            if values:
                scope[key] = values
            else:
                scope.pop(key, None)
        indent = json_indent(path)
        with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as f:
            json.dump(record, f, ensure_ascii=False, indent=indent)
            f.write("\n")
        os.replace(path + ".tmp", path)
    locations = prefs.get("locations")
    scope = (locations.get("search_scope") if isinstance(locations, dict) else None) or {}
    fallback = {"remote_regions": "REMOTE_REGIONS", "any_mode_places": "PLACES"}
    for key in SCOPE_KEYS:
        print(f"{key}: " + (", ".join(scope[key]) if scope.get(key) else f"not set ({fallback[key]} in job-search.env "
                                                                          "counts)"))
    sys.exit(0)
if args == ["cvs"]:
    import glob
    from build_cv import pdf_name
    env = jsenv.load(env_arg, __file__)
    found = []
    for path in sorted(glob.glob(os.path.join(env.path("CV_VERSIONS_DIR"), "*.json"))):
        name = os.path.basename(path)
        if " " not in os.path.splitext(name)[0]:
            continue  # not "<n> <Variant>.json"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        pdf = env.path("CVS_DIR", pdf_name(name, data.get("name") or env.get("PERSON_NAME", "")))
        if not os.path.isfile(pdf):
            print(f"no PDF for {name}: build it with build_cv.py; left out", file=sys.stderr)
            continue
        found.append({"variant": os.path.splitext(name)[0].split(" ", 1)[1], "file": pdf.replace(os.sep, "/"),
                      "use": data.get("use") or data.get("title", "")})
    text = json.dumps(found, ensure_ascii=False, indent=1)
    if out:
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(out, len(text.encode("utf-8")), "bytes")
    else:
        print(text)
    sys.exit(0)
if len(args) != 1 or args[0] not in SCOPES:
    sys.exit(__doc__)
scope = args[0]
env = jsenv.load(env_arg, __file__)
with open(env.path("MASTER_RECORD"), encoding="utf-8") as f:
    record = json.load(f)
view = {"_about": f"The {scope} part of the master record. Facts only."}
for key in SCOPES[scope]:
    source, target = record, view
    *parents, leaf = key.split(".")
    for parent in parents:
        source = source.get(parent, {})
        target = target.setdefault(parent, {})
    if leaf in source:
        target[leaf] = source[leaf]
if scope == "fit":
    profile = pl.load(env)
    if profile["exists"] and not profile["error"]:
        person = profile["data"].get("person") or {}
        view["person"] = {k: v for k, v in person.items() if k in ("languages", "location", "nationality",
                                                                   "work_authorisation")}
if scope == "facts":  # every list of things never to claim, wherever the person's record keeps one
    view.update({k: v for k, v in record.items() if re.search(r"never|not_known", k)})
    profile = pl.load(env)
    if profile["exists"] and not profile["error"]:
        person = profile["data"].get("person") or {}
        view["person"] = {k: v for k, v in person.items() if k in PERSON_SHOWN}
        if profile["data"].get("employment"):
            view["employment"] = profile["data"]["employment"]
        view["form_facts"] = pl.form_facts(profile)[0]
    else:
        print("No readable profile: the facts view has no person facts. "
              + (pl.missing_message(profile) if not profile["exists"] else f"{profile['path']}: {profile['error']}"),
              file=sys.stderr)
text = json.dumps(view, ensure_ascii=False, separators=(",", ":"))
if out:
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(out, len(text.encode()), "bytes")
else:
    print(text)
