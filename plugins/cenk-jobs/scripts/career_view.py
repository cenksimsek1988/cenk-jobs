"""One part of the master record, so a job reads what it needs instead of the whole file.

python -I career_view.py screen [--out <file>]   the employer rules and the person's decisions: for screening an employer
python -I career_view.py facts [--out <file>]    what a letter or a form may use: profile (CV wording), experience,
                                                 skills, education, where they will work, pay rule, form answers, CV
                                                 rules, never-claim lists; from the person's profile (profilelib.py):
                                                 person (name, pronouns, contact, location, languages, links,
                                                 nationality, work authorisation), employment, and the names in
                                                 the setting form_facts. Never private or contacts.
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


env_arg, out = option("--env"), option("--out")
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
