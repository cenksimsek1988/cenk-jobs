"""Reposts: a posting whose employer and title match a role the person already applied to, or declined.

    reposts.py <search file>     one line per repost: <posting id> | <company> | <title> | repost of <job id>
                                 (the search file: {companies: [{name, jobs: [{id, title}]}]})

The employer matches by its lookup keys (employerlib.keys: legal forms and brackets dropped, each bracket part a key
of its own) and by the person's saved names (names.json aliases). The title matches as a set of words: case, word
order, punctuation and gender tags such as "(m/f/d)" do not count; seniority words do.
Example: "Senior Software Engineer (m/f/d)" sent at "Acme (Parent)" makes "Software Engineer - Senior" at "Acme" a
repost; "Staff Software Engineer" there is not one.
A job counts as applied to when its tracker status is submitted or declined, or it has an applied date.
collect_postings.py --out leaves reposts out of the funnel. Add --env <job-search.env> anywhere to pick the env file.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import employerlib as el  # noqa: E402
import jsenv  # noqa: E402
from trackerlib import companies  # noqa: E402

TAGS = re.compile(r"(?i)\(?\b[mfwdx]\s*/\s*[mfwdx](\s*/\s*[mfwdx])?\b\)?|\ball genders\b")
FILLER = {"and", "the", "of", "for", "in", "at", "a", "an", "to", "with"}


def title_key(title):
    """The title's words as a set, without gender tags, punctuation or filler words."""
    words = re.findall(r"[a-z0-9+#]+", TAGS.sub(" ", str(title or "")).lower())
    return frozenset(w for w in words if w not in FILLER)


def employer_keys(env, name, employers):
    """Every key the employer is known by: its own keys and those of the saved entry it matches (names.json)."""
    out = set(el.keys(name or ""))
    entry, _, how, _ = el.own_match(env, name or "", employers)
    if entry and how in ("exact", "group"):
        out |= el.keys(entry)
    return out


class Index:
    """The roles applied to, by employer key and title key."""

    def __init__(self, env, tracker):
        self.env = env
        self.employers = el.checks_file(env).get("employers", {}) if env.get("EMPLOYER_CHECKS") else {}
        self.applied = {}
        for company, job in companies(tracker):
            if job.get("status") in ("submitted", "declined") or job.get("applied"):
                name = job.get("company") or company.get("name", "")
                tk = title_key(job.get("title") or (job.get("prep") or {}).get("title", ""))
                for k in employer_keys(env, name, self.employers):
                    self.applied.setdefault((k, tk), job["id"])

    def repost_of(self, company, title):
        """The id of the job this posting repeats, or ""."""
        tk = title_key(title)
        for k in employer_keys(self.env, company, self.employers):
            if (k, tk) in self.applied:
                return self.applied[(k, tk)]
        return ""


def main():
    args = sys.argv[1:]
    explicit = None
    if "--env" in args:
        i = args.index("--env")
        explicit = args[i + 1] if i + 1 < len(args) else sys.exit("--env takes the path of a job-search.env")
        del args[i:i + 2]
    if len(args) != 1:
        sys.exit(__doc__)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    env = jsenv.load(explicit, __file__)
    with open(env.path("TRACKER"), encoding="utf-8") as fh:
        index = Index(env, json.load(fh))
    with open(args[0], encoding="utf-8") as fh:
        found = json.load(fh).get("companies", [])
    for c in found:
        for j in c.get("jobs", []):
            of = index.repost_of(c.get("name", ""), j.get("title", ""))
            if of:
                print(" | ".join((j.get("id", ""), c.get("name", ""), j.get("title", ""), "repost of " + of)))


if __name__ == "__main__":
    main()
