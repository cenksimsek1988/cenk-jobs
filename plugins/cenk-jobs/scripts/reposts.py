"""Reposts: a posting whose employer and title match a role the person already applied to, or declined.

    reposts.py <search file>     one line per repost: <posting id> | <company> | <title> | repost of <job id>
                                 (the search file: {companies: [{name, jobs: [{id, title}]}]})

The employer matches by its lookup keys (employerlib.keys: legal forms and brackets dropped, each bracket part a key
of its own) and by the person's saved names (names.json aliases). The title matches as a set of words: case, word
order, punctuation and gender tags such as "(m/f/d)" do not count; seniority words do.
Example: "Senior Software Engineer (m/f/d)" sent at "Acme (Parent)" makes "Software Engineer - Senior" at "Acme" a
repost; "Staff Software Engineer" there is not one.
A job counts as applied to when its tracker status is submitted or declined, or it has an applied date.
collect_postings.py --out leaves reposts out of the funnel, and a posting whose employer and title match a job the
funnel skipped for fit in the last 30 days (the fit cache). Add --env <job-search.env> anywhere to pick the env file.
"""
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import employerlib as el  # noqa: E402
import jsenv  # noqa: E402
from trackerlib import companies  # noqa: E402

FIT_CACHE_DAYS = 30  # a fit skip this recent stands for the same employer and title found again
TAGS = re.compile(r"(?i)\(?\b[mfwdx]\s*/\s*[mfwdx](\s*/\s*[mfwdx])?\b\)?|\ball genders\b")
FILLER = {"and", "the", "of", "for", "in", "at", "a", "an", "to", "with"}


def title_key(title):
    """The title's words as a set, without gender tags, punctuation or filler words."""
    words = re.findall(r"[a-z0-9+#]+", TAGS.sub(" ", str(title or "")).lower())
    return frozenset(w for w in words if w not in FILLER)


def repeat_pairs(jobs, pipeline):
    """[(first id, later job)]: a sent job (submitted, or in PIPELINE) whose employer key and title words match an
    earlier sent one, in applied order. jobs: trackerlib.flat_jobs rows. The dashboard flags the later job
    ("re-application of"); records.py check (dupes) names a pair whose later job has no repeat_of=<first id>."""
    seen, out = {}, []
    sent = [j for j in jobs if j.get("status") == "submitted" or j["id"] in (pipeline or {})]
    for j in sorted(sent, key=lambda j: (str(j.get("applied") or "")[:10], j["id"])):
        keys = sorted(el.keys(j.get("company") or ""))
        k = (keys[0] if keys else "", title_key(j.get("title", "")))
        if k[0] and k[1] and k in seen:
            out.append((seen[k], j))
        else:
            seen.setdefault(k, j["id"])
    return out


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
        self.applied, self.fit_skipped = {}, {}
        since = (datetime.date.today() - datetime.timedelta(days=FIT_CACHE_DAYS)).isoformat()
        for company, job in companies(tracker):
            last = (job.get("history") or [{}])[-1]
            note = last.get("note") or last.get("outcome") or ""  # the older tracker shape keeps it in "outcome"
            if job.get("status") == "skipped" and str(note).startswith("fit:") \
                    and str(last.get("date", ""))[:10] >= since:
                name = job.get("company") or company.get("name", "")
                for k in employer_keys(env, name, self.employers):
                    self.fit_skipped.setdefault((k, title_key(job.get("title", ""))), job["id"])
            if job.get("status") in ("submitted", "declined") or job.get("applied"):
                name = job.get("company") or company.get("name", "")
                tk = title_key(job.get("title") or (job.get("prep") or {}).get("title", ""))
                for k in employer_keys(env, name, self.employers):
                    self.applied.setdefault((k, tk), job["id"])

    def fit_skip_of(self, company, title):
        """The id of a job with this employer and title the funnel skipped for fit in the last FIT_CACHE_DAYS days,
        or "": the same posting on another board or a new link is not screened again."""
        tk = title_key(title)
        for k in employer_keys(self.env, company, self.employers):
            if (k, tk) in self.fit_skipped:
                return self.fit_skipped[(k, tk)]
        return ""

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
