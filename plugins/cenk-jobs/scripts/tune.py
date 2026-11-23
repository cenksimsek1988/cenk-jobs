"""Tune the saved searches (the tune-search skill): candidate searches compared over one fixed window. A candidate is a
set of saved-search rows with title rules, run as a filter over one pool of postings per round; the person's fit model
decides which candidate finds the most high fits. No model reads a search; the fit check runs once per job.

python -I tune.py start [--days <n>]
    the run's folder, apply/tune/<YYYY-MM-DD>/ with run.json: the window (now minus n days, default 7, fixed for every
    round), the counted fit model (FIT_MODEL), the token budget (TUNE_TOKENS, default 35000000) and the cache of raw
    answers (TUNE_CACHE, default cenk-tune/<date> in the system's temp folder). A second start on the same day keeps
    that run.
python -I tune.py round <n> [--offline]
    reads round-<n>.json in the run's folder ({"candidates": [{"name", "rows": [saved-search rows], "rules": title
    rules, or null for the person's own, "row_terms": "filter" or "search", optional}]}), reads every row once (a
    cached answer costs no call, so rounds share them) and runs each candidate over the window's postings as
    collect_postings.py reads its rows: terms, every place, title rules, the other-language title rule, the LinkedIn
    remote text rule. Past records grade what they know: the tracker's stored fit (graded again under today's rules),
    its skipped and closed jobs, this run's fit results, an excluded employer. Prints one line per candidate; writes
    pool-<n>.jsonl and cands-<n>.json. --offline: cached answers only.
python -I tune.py fit <n> [--recheck]
    the jobs of round n that no record grades, and earlier ones whose fit check failed, as a search file in fit/<n>/,
    with the run script that holds its args (workflow_args.py --script, an APPLY=list run on Sonnet): run it with the
    Workflow tool's scriptPath. --recheck: the jobs the screen graded high that the counted model has not checked, on
    that model (fit/<n>r/). Refused when its estimate passes the budget left.
python -I tune.py score <n> <journal> [<journal> ...] [--recheck]
    each fit result of the journals kept whole by posting (fit-results.json; the screen's and the counted model's
    apart, --recheck for the latter), then round n's table again, its best candidate and the stop rule: 3 rounds in a
    row without a new best on the counted model.
python -I tune.py winner <n> <candidate> [--apply]
    what the candidate changes: its rows as the saved searches (a saved script row with the same search keeps its id
    and history; one the candidate lacks is turned off), its title rules as SEARCH_RULES (the old file kept beside it
    as .before-tune-<date>.json, once a day), the high fits no tracker job holds, added (track.py add --file) with
    their own fit results attached, the counted model's first (track.py sync of new-high-fits.jsonl, a company-shape
    tracker): each then stands as a pending high fit. A dry run without --apply; --apply writes it and deletes the
    cache.
python -I tune.py clean
    deletes the cache of raw answers.
Calls: a network call waits 3 s after the last one to its host, 6 s on LinkedIn; a run makes at most 600 LinkedIn and
650 Himalayas calls (seen 23 Nov 2026: refused after about 650 and 700), and a refusal stops that source for the
round. Tokens: a fit run's estimate is its employers times the model's cost of one fit check (Sonnet 38k, measured 23
Nov; Opus 100k; Opus at max effort 225k). The counted model is FIT_MODEL: the screen (Sonnet) checks every job, the
counted model re-checks the screen's highs (seen 23 Nov: Sonnet graded 44 high, Opus kept 10). A job is one
employer and title, however many links it has; a posting found by several rows counts for each candidate that holds
one of them. Add --env <job-search.env> anywhere to pick the env file.
"""
import collections
import datetime
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import choices  # noqa: E402
import collect_postings as cp  # noqa: E402
import employerlib as el  # noqa: E402
import jsenv  # noqa: E402
import recordlib  # noqa: E402
import reposts  # noqa: E402
from trackerlib import (as_result, companies, expand_row, is_company_shape, job_urls, pay_for, pay_table,  # noqa: E402
                        terms)

FIT_COST = {"sonnet": 38000, "opus": 100000, "opus-max": 225000}
LIMITS = {"linkedin": 600, "himalayas": 650}  # network calls a run, by source
PACE = {"linkedin": 6.0}  # seconds between two calls to one host; others GAP
GAP = 3.0
SCREEN = "sonnet"
KEY_FIELDS = ("source", "board", "query", "place", "mode", "tech", "tag")
GRADES = ("high", "normal", "long-shot", "weak")
WEEKLY = ("greenhouse", "lever", "ashby", "smartrecruiters", "workable", "workable-search")  # as searches.py add
TABLE = ("candidate", "postings", "jobs", "excluded", "other-language title", "known", "checked", "to check",
         "LinkedIn unread", "high (screen)", "high (counted)", "normal", "long-shot", "weak", "skip")


def row_key(row):
    """One search, however it was saved: its source and what it asks. Example: a LinkedIn row's source, query, place
    and mode."""
    return json.dumps({k: str(row.get(k) or "").strip() for k in KEY_FIELDS}, sort_keys=True)


def link_key(url):
    """One job's link however it was copied (as track.py add --file): no scheme, www, fragment or trailing slash,
    lower case; a LinkedIn job link also without its query."""
    u = str(url or "").split("#")[0].strip()
    if re.search(r"(?i)^https?://([a-z0-9-]+\.)*linkedin\.com/jobs/view/", u):
        u = u.split("?")[0]
    return re.sub(r"^https?://(www\.)?", "", u.rstrip("/").lower())


def family(url):
    """The source a link's calls count for: linkedin, himalayas, else its host."""
    host = urllib.parse.urlparse(url).netloc.lower()
    return "linkedin" if "linkedin.com" in host else "himalayas" if "himalayas.app" in host else host


def cache_key(url):
    """A raw answer's file name: the link without LinkedIn's moving time window (f_TPR), so every round reads the
    window the first call read."""
    key = re.sub(r"([?&])f_TPR=[^&]*(&|$)", r"\1", url).rstrip("?&")
    return hashlib.sha1(key.encode("utf-8")).hexdigest() + ".txt"


def pid_of(url):
    """A posting's id, as collect_postings.py gives it."""
    return "P" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]


def write_json(path, data, indent=1):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=indent)
    os.replace(path + ".tmp", path)


def read_json(path, default=None):
    if not os.path.isfile(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class Run:
    """The run's folder and its run.json."""

    def __init__(self, env, folder):
        self.env, self.folder = env, folder
        self.path = os.path.join(folder, "run.json")
        self.data = read_json(self.path)
        if self.data is None:
            sys.exit(f"no tune run in {folder}: tune.py start")

    @staticmethod
    def latest(env):
        base = os.path.join(env.home, "apply", "tune")
        days = sorted(d for d in (os.listdir(base) if os.path.isdir(base) else [])
                      if os.path.isfile(os.path.join(base, d, "run.json")))
        if not days:
            sys.exit(f"no tune run under {base}: tune.py start")
        return Run(env, os.path.join(base, days[-1]))

    def save(self):
        write_json(self.path, self.data)

    def file(self, name):
        return os.path.join(self.folder, name)

    @property
    def start(self):
        return datetime.datetime.fromisoformat(self.data["window_start"])

    @property
    def model(self):
        return self.data["model"]


def start(env, days):
    today = datetime.date.today().isoformat()
    folder = os.path.join(env.home, "apply", "tune", today)
    if os.path.isfile(os.path.join(folder, "run.json")):
        print(f"{folder.replace(os.sep, '/')}: the run of {today} goes on")
        return
    raw = (env.get("TUNE_TOKENS") or "35000000").strip()
    if not raw.isdigit():
        sys.exit(f"TUNE_TOKENS is a number of tokens: got {raw!r}")
    model = choices.value(env, "FIT_MODEL")[0]
    begin = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat(timespec="minutes")
    cache = env.path("TUNE_CACHE") if env.get("TUNE_CACHE") else os.path.join(tempfile.gettempdir(), "cenk-tune", today)
    os.makedirs(folder, exist_ok=True)
    write_json(os.path.join(folder, "run.json"), {
        "window_start": begin, "model": model, "budget": int(raw), "spent": 0, "cache": cache.replace(os.sep, "/"),
        "calls": {}, "fit_runs": [], "journals": [], "rounds": {}})
    print(f"{folder.replace(os.sep, '/')}: window from {begin}, counted model {model}, budget {int(raw)} tokens; "
          "write round-1.json there (tune-search skill, step 2)")


# --- reading: raw answers cached by link, paced and counted by source --------------------------------------------
def install_cache(run, offline):
    """collect_postings reads through a cache: a cached answer is read from disk with no wait; a new one waits its
    host's gap, counts against the run's limit and is saved. offline: a missing answer is an error."""
    raw_dir = os.path.join(run.data["cache"], "raw")
    os.makedirs(raw_dir, exist_ok=True)
    real_get, last = cp.get, {}

    def get(url):
        path = os.path.join(raw_dir, cache_key(url))
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                return fh.read()
        if offline:
            raise OSError(f"not cached: {url}")
        fam = family(url)
        calls = run.data["calls"]
        if calls.get(fam, 0) >= LIMITS.get(fam, 10 ** 9):
            raise OSError(f"{fam}: the run's {LIMITS[fam]} calls are used")
        wait = PACE.get(fam, GAP) - (time.monotonic() - last.get(fam, -1e9))
        if wait > 0:
            time.sleep(wait)
        try:
            text = real_get(url)
        finally:
            last[fam] = time.monotonic()
            calls[fam] = calls.get(fam, 0) + 1
            run.save()  # the count survives a stop mid-round, so the next round keeps to the limit
        # LinkedIn's sign-in wall and an empty answer are read again next time, never kept as the answer.
        if text.strip() and not (fam == "linkedin" and "authwall" in text):
            with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
            os.replace(path + ".tmp", path)
        return text
    cp.get = get
    cp.paced_fetch = lambda source, url: cp.fetch(url)  # the pacing is the cache's, per host


class Context:
    """What a round reads once: the person's places, terms, rules and fit settings; the tracker's jobs by link and by
    employer and title; this run's fit results; the employer checks."""

    def __init__(self, env, run):
        self.env, self.run = env, run
        cp.ENV = env
        self.regions = cp.load_places(env)
        self.role_terms = terms(env.get("ROLE_TERMS"))
        self.rules = cp.title_rules(env)
        self.row_terms = (env.get("ROW_TERMS") or "").strip().lower()
        self.fit = choices.fit_settings(env)
        self.results = read_json(run.file("fit-results.json"), {})
        self.texts_dir = os.path.join(run.data["cache"], "texts")
        os.makedirs(self.texts_dir, exist_ok=True)
        self.queue = cp.LinkedInQueue(False)  # no waits of its own: the cache paces LinkedIn
        self.remote, self.linkedin_stopped, self.keys, self.excluded, self.known_of = {}, "", {}, {}, {}
        self.checks_problem = ""  # the first employer check that could not be read, named once
        with open(env.path("TRACKER"), encoding="utf-8") as fh:
            tracker = json.load(fh)
        self.by_link, self.by_job = {}, {}
        for company, job in companies(tracker):
            name = job.get("company") or company.get("name", "")
            for u in job_urls(job):
                self.by_link.setdefault(link_key(u), job)
            title = job.get("title") or (job.get("prep") or {}).get("title", "")
            for k in self.employer_keys(name):
                self.by_job.setdefault((k, reposts.title_key(title)), job)
        self.rule_set = el.rules(env)
        self.employers = el.checks_file(env).get("employers", {}) if env.get("EMPLOYER_CHECKS") else {}

    def employer_keys(self, name):
        if name not in self.keys:
            self.keys[name] = sorted(reposts.employer_keys(self.env, name, {})) or [str(name or "").lower()]
        return self.keys[name]

    def job_of(self, post):
        """(employer key, title key): one job, however many links it has."""
        return f"{self.employer_keys(post['company'])[0]}|{' '.join(sorted(reposts.title_key(post['title'])))}"

    def text_path(self, post):
        return os.path.join(self.texts_dir, post["id"] + ".md")

    def remote_text(self, post):
        """yes, no or unread: whether a LinkedIn posting's own text speaks of remote work (its guest page, cached).
        A refusal (429) or the run's last call stops LinkedIn's texts for the round; a page that is gone is a no."""
        if post["id"] in self.remote:
            return self.remote[post["id"]]
        if self.linkedin_stopped:
            return "unread"
        try:
            text = cp.job_text(post["url"], None, self.queue)
        except (cp.Refused, OSError, ValueError) as problem:
            gone = isinstance(problem, cp.Refused) and problem.code in (404, 410)
            if gone:
                self.remote[post["id"]] = "no"
                return "no"
            if (isinstance(problem, cp.Refused) and problem.code == 429) or "calls are used" in str(problem):
                self.linkedin_stopped = str(problem)
                print(f"LinkedIn texts stop for this round ({problem}): the postings that need one count as unread")
            return "unread"
        if text is None:
            state = "no"
        else:
            plain = html.unescape(re.sub(r"<[^>]+>", " ", text))
            state = "yes" if cp.REMOTE_WORDS.search(plain) else "no"
            cp.keep_text(post["url"], text)
            if post["url"] in cp.TEXTS and not os.path.isfile(self.text_path(post)):
                cp.save_text(self.text_path(post), post, cp.TEXTS[post["url"]])
        self.remote[post["id"]] = state
        return state

    def employer_out(self, name):
        if name not in self.excluded:
            try:
                view = el.check_view(self.env, name, self.rule_set, employers=self.employers)
                self.excluded[name] = view["verdict"] == "exclude"
            except SystemExit as problem:
                if not self.checks_problem:
                    self.checks_problem = str(problem)
                    print(f"an employer check cannot be read ({problem}): an employer whose check cannot be read "
                          "counts as not excluded")
                self.excluded[name] = False
        return self.excluded[name]

    def graded(self, fit):
        """A stored fit graded again under today's rules, every grade kept (no setting cuts it): high, normal,
        long-shot, weak, unread or skip."""
        out = choices.regraded(fit, "normal", self.fit, 999)
        if out.get("grade") == "unread":
            return "unread"
        return (out.get("grade") or "skip") if out.get("action") == "apply" else "skip"

    def known(self, post):
        """The tracker's grade of the posting's job, or "": its stored fit graded again, its skip or close. Read once
        per posting (a split tracker's detail file costs a read)."""
        if post["id"] not in self.known_of:
            self.known_of[post["id"]] = self._known(post)
        return self.known_of[post["id"]]

    def _known(self, post):
        job = self.by_link.get(link_key(post["url"]))
        if job is None:
            for k in self.employer_keys(post["company"]):
                job = self.by_job.get((k, reposts.title_key(post["title"])))
                if job is not None:
                    break
        if job is None:
            return ""
        if job.get("status") == "excluded":
            return "excluded"
        prep = expand_row(self.env.path("TRACKER"), job).get("prep") or {}
        if prep.get("requirements") is not None or prep.get("gaps") is not None:
            return self.graded(prep)
        if job.get("status") in ("skipped", "closed", "declined"):
            return "skip"
        return job.get("grade") if job.get("grade") in GRADES else ""


def read_round(run, ctx, cands, offline):
    """The pool: every row of the round's candidates read once; the window's postings, each with every row that
    returned it. Prints one line per row read."""
    install_cache(run, offline)
    begin, rows = run.start, {}
    since = begin.date().isoformat()
    for c in cands:
        for r in c.get("rows") or []:
            if r.get("source") not in cp.BOARDS + cp.FEEDS + ("linkedin",):
                sys.exit(f"candidate {c.get('name')}: a row's source is no source collect_postings.py reads: "
                         f"{r.get('source')!r}")
            rows.setdefault(row_key(r), r)
    pool, stopped = {}, {}
    for key, row in sorted(rows.items(), key=lambda kv: cp.rank(kv[1])):
        source, site = row["source"], row.get("site") or row["source"]
        fam = "linkedin" if source == "linkedin" else "himalayas" if source.startswith("himalayas") else source
        words = terms(row.get("query")) or ctx.role_terms
        if fam in stopped or not words:
            print(f"not read: {site} | {row.get('query', '')} ({stopped.get(fam) or 'no terms and no ROLE_TERMS'})")
            continue
        try:
            texts = cp.answers(row, None, ctx.queue, begin, words)
        except (cp.Refused, OSError, ValueError) as problem:
            if fam in ("linkedin", "himalayas") and ("429" in str(problem) or "calls are used" in str(problem)):
                stopped[fam] = str(problem)  # refused or out of calls: the source rests for this round
            print(f"not read: {site} | {row.get('query', '')} ({problem})")
            continue
        n = 0
        for t, c, p, d, u in (x for text in texts for x in cp.parse(source, row.get("board", ""), text)):
            if not u or not t or (d and d < since):
                continue
            post = pool.setdefault(pid_of(u), {"id": pid_of(u), "url": u, "title": t,
                                               "company": cp.employer_of(row, c), "place": p,
                                               "places": cp.PLACES_OF.get(u, []), "date": d, "rows": [],
                                               "found_by": cp.found_by(row)})
            if key not in post["rows"]:
                post["rows"].append(key)
                n += 1
            if u in cp.TEXTS and not os.path.isfile(ctx.text_path(post)):
                cp.save_text(ctx.text_path(post), post, cp.TEXTS[u])
        print(f"read: {site} | {row.get('query', '')}: {n} postings in the window")
    return pool


def compile_rules(raw):
    """A candidate's title rules as collect_postings.py reads a SEARCH_RULES file."""
    try:
        return {k: re.compile(raw[k], re.I) for k in cp.RULE_KEYS if raw.get(k)}
    except (TypeError, AttributeError, re.error) as problem:
        sys.exit(f"a candidate's rules: not readable as title rules: {problem}")


def run_candidate(cand, pool, ctx):
    """(found, other-language, LinkedIn unread): the candidate's postings, as collect_postings.py would read them."""
    rules = ctx.rules if cand.get("rules") is None else compile_rules(cand["rules"])
    term_rules = {} if str(cand.get("row_terms") or ctx.row_terms).lower() == "filter" else rules
    by_key = {row_key(r): r for r in cand.get("rows") or []}
    found, other, unread = [], [], []
    for post in pool.values():
        result = ""
        for row in [by_key[k] for k in post["rows"] if k in by_key]:
            place = next((x for x in [post["place"]] + post["places"]
                          if cp.wanted(row, post["title"], x, ctx.role_terms, ctx.regions, term_rules)), None)
            if place is None or cp.title_out(post["title"], rules):
                continue
            if choices.other_language({"title": post["title"]}, ctx.fit):
                result = result or "other"
                continue
            if cp.remote_gate(row, place):
                state = ctx.remote_text(post)
                if state != "yes":
                    result = result or ("unread" if state == "unread" else "")
                    continue
            result = "found"
            break
        {"found": found, "other": other, "unread": unread}.get(result, []).append(post["id"])
    return found, other, unread


def job_grades(ctx, posts):
    """(screen grade, counted grade, how) of one job's postings: excluded, a record's grade, this run's results, or
    "to check". A record counts for both; this run's screen result for the screen; the counted model's re-check for
    the counted grade (the screen's, when the screen is the counted model)."""
    if any(ctx.employer_out(p["company"]) for p in posts):
        return "excluded", "excluded", "excluded"
    known = [g for g in (ctx.known(p) for p in posts) if g]
    if "excluded" in known:
        return "excluded", "excluded", "excluded"
    order = {g: i for i, g in enumerate(GRADES + ("skip", "unread"))}
    if known:
        g = sorted(known, key=lambda x: order.get(x, 9))[0]
        return g, g, "known"
    screen = [ctx.graded(ctx.results[p["id"]][SCREEN]) for p in posts if SCREEN in ctx.results.get(p["id"], {})]
    if not screen:
        return "to check", "", "none"
    s = sorted(screen, key=lambda x: order.get(x, 9))[0]
    model = ctx.run.model
    if model == SCREEN:
        return s, s, "checked"
    counted = [ctx.graded(ctx.results[p["id"]][model]) for p in posts if model in ctx.results.get(p["id"], {})]
    return s, (sorted(counted, key=lambda x: order.get(x, 9))[0] if counted else ""), "checked"


def table(run, ctx, n, pool, found_sets):
    """One line per candidate, the best first; returns {name: row} and writes cands-<n>.json."""
    out = {}
    for name, (found, other, unread) in found_sets.items():
        jobs = collections.OrderedDict()
        for i in found:
            jobs.setdefault(ctx.job_of(pool[i]), []).append(pool[i])
        n_ = collections.Counter()
        for posts in jobs.values():
            screen, counted, how = job_grades(ctx, posts)
            n_[how] += 1
            n_["g:" + screen] += 1
            if counted == "high":
                n_["counted"] += 1
        other_jobs = {ctx.job_of(pool[i]) for i in other}
        out[name] = {"candidate": name, "postings": len(found), "jobs": len(jobs), "excluded": n_["excluded"],
                     "other-language title": len(other_jobs), "known": n_["known"], "checked": n_["checked"],
                     "to check": n_["none"], "LinkedIn unread": len(unread), "high (screen)": n_["g:high"],
                     "high (counted)": n_["counted"], "normal": n_["g:normal"], "long-shot": n_["g:long-shot"],
                     "weak": n_["g:weak"], "skip": n_["g:skip"] + n_["g:unread"],
                     "found": found, "other": other, "unread": unread}
    write_json(run.file(f"cands-{n}.json"), out)
    rows = sorted(out.values(), key=lambda r: (-r["high (counted)"], -r["high (screen)"], r["jobs"]))
    print("| " + " | ".join(TABLE) + " |")
    print("|" + "---|" * len(TABLE))
    for r in rows:
        print("| " + " | ".join(str(r[k]) for k in TABLE) + " |")
    return out


def load_pool(run, n):
    path = run.file(f"pool-{n}.jsonl")
    if not os.path.isfile(path):
        sys.exit(f"no pool for round {n}: tune.py round {n}")
    with open(path, encoding="utf-8") as fh:
        return {p["id"]: p for p in (json.loads(line) for line in fh if line.strip())}


def round_cmd(env, n, offline):
    run = Run.latest(env)
    spec = read_json(run.file(f"round-{n}.json"))
    if not spec or not spec.get("candidates"):
        sys.exit(f"{run.file(f'round-{n}.json')}: no candidates ({{\"candidates\": [{{\"name\", \"rows\"}}]}})")
    names = [c.get("name") for c in spec["candidates"]]
    if not all(names) or len(set(names)) != len(names):
        sys.exit("every candidate needs its own name")
    ctx = Context(env, run)
    pool = read_round(run, ctx, spec["candidates"], offline)
    with open(run.file(f"pool-{n}.jsonl"), "w", encoding="utf-8", newline="\n") as fh:
        for p in pool.values():
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    found = {c["name"]: run_candidate(c, pool, ctx) for c in spec["candidates"]}
    print(f"round {n}: {len(pool)} postings in the window from {run.data['window_start']}; calls so far "
          + (", ".join(f"{k} {v}" for k, v in sorted(run.data["calls"].items())) or "none"))
    run.save()
    table(run, ctx, n, pool, found)


def found_sets(run, n):
    cands = read_json(run.file(f"cands-{n}.json"))
    if cands is None:
        sys.exit(f"no candidates' results for round {n}: tune.py round {n}")
    return {k: (v["found"], v["other"], v["unread"]) for k, v in cands.items()}


def fit_cmd(env, n, recheck):
    run = Run.latest(env)
    ctx, pool = Context(env, run), load_pool(run, n)
    sets = found_sets(run, n)
    model = run.model if recheck else SCREEN
    if recheck and model == SCREEN:
        sys.exit(f"the counted model is {SCREEN}, the screen's own: no re-check")
    jobs = collections.OrderedDict()
    for found, _, _ in sets.values():
        for i in found:
            jobs.setdefault(ctx.job_of(pool[i]), {})[i] = pool[i]
    todo = []
    for posts in jobs.values():
        screen, counted, how = job_grades(ctx, list(posts.values()))
        want = (screen == "high" and how == "checked" and counted == "") if recheck else screen == "to check"
        if want:
            # The posting with the longest saved text speaks for the job; a LinkedIn one last.
            size = lambda p: os.path.getsize(ctx.text_path(p)) if os.path.isfile(ctx.text_path(p)) else 0  # noqa: E731
            todo.append(max(posts.values(), key=lambda p: (size(p), "linkedin" not in p["url"])))
    if not todo:
        print(f"round {n}: nothing to {'re-check' if recheck else 'check'}")
        return
    pays = pay_table(env)[1]
    by_employer = collections.OrderedDict()
    for p in todo:
        job = {"id": p["id"], "title": p["title"], "url": p["url"], "location": p["place"], "date": p["date"],
               "found_by": p["found_by"]}
        if (p["found_by"].split(":") + [""])[1] in cp.DISCOVERY_ONLY:
            job.update(apply_url="", apply_note="apply on the employer's own careers page (this site's posting pages "
                                                "are blocked)")
        else:
            job["apply_url"] = p["url"]
        if os.path.isfile(ctx.text_path(p)):
            job["text_file"] = ctx.text_path(p).replace(os.sep, "/")
        pay = pay_for(pays, p["place"])
        if pay:
            job["pay"] = pay
        by_employer.setdefault(p["company"] or "(no employer named)", []).append(job)
    estimate = len(by_employer) * FIT_COST.get(model, FIT_COST["opus"])
    folder = run.file(os.path.join("fit", f"{n}{'r' if recheck else ''}"))
    script = os.path.join(folder, "run.js")
    # The same fit run written again before any of its results came back (its script not run yet, or its run lost)
    # replaces its own estimate; a run with results stays spent, so the next run for its failed checks adds to it.
    again = [r for r in run.data["fit_runs"] if r.get("script") == script.replace(os.sep, "/")
             and not any(r.get("model") in ctx.results.get(p, {}) for p in r.get("postings", []))]
    run.data["spent"] -= sum(r.get("estimate", 0) for r in again)
    run.data["fit_runs"] = [r for r in run.data["fit_runs"] if r not in again]
    left = run.data["budget"] - run.data["spent"]
    if estimate > left:
        sys.exit(f"round {n}: {len(by_employer)} employers on {model} are about {estimate} tokens, {left} left of "
                 f"TUNE_TOKENS={run.data['budget']}: the run stops here with its best so far")
    os.makedirs(folder, exist_ok=True)
    search = os.path.join(folder, "search.json")
    write_json(search, {"companies": [{"name": k, "jobs": v} for k, v in by_employer.items()]})
    res = subprocess.run([sys.executable, "-I", os.path.join(HERE, "workflow_args.py"), "--search", search, "--list",
                          "--fit-model", model, "--script", script, "--tag", f"tune{n}{'r' if recheck else ''}",
                          "--env", env.file], capture_output=True, text=True, encoding="utf-8")
    if res.returncode:
        sys.exit(f"workflow_args.py failed: {res.stderr.strip()[-300:]}")
    run.data["spent"] += estimate
    run.data["fit_runs"].append({"round": n, "model": model, "employers": len(by_employer), "estimate": estimate,
                                 "postings": [p["id"] for p in todo], "script": script.replace(os.sep, "/")})
    run.save()
    print(res.stdout.strip())
    print(f"round {n}: {len(todo)} jobs at {len(by_employer)} employers on {model}, about {estimate} tokens "
          f"({run.data['spent']} of {run.data['budget']} spent); run the Workflow tool with scriptPath "
          f"{script.replace(os.sep, '/')}, then tune.py score {n} <its journal>{' --recheck' if recheck else ''}")


def journal_results(path):
    """{job id: the fit check's job object} from a run's journal: every prep-fit: result, read as track.py sync
    reads it (trackerlib.as_result). A result that holds no jobs is counted and named in one line."""
    with open(path, encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    labels = {r.get("agentId"): r.get("label", "") for r in rows if r.get("type") == "started"}
    out, unreadable = {}, 0
    for r in rows:
        if r.get("type") != "result" or not str(labels.get(r.get("agentId"), "")).startswith("prep-fit:"):
            continue
        value = as_result(r.get("result"))
        if not isinstance(value, dict):
            unreadable += 1
            continue
        for job in value.get("jobs", []):
            if isinstance(job, dict) and job.get("id"):
                out[job["id"]] = job
    if unreadable:
        print(f"{path}: {unreadable} fit result(s) not readable as a job list: their jobs stay to check")
    return out


def best_line(run):
    """The best round so far and the rounds since, on the counted model; 3 without a new best end the run."""
    best, since, which = -1, 0, ""
    for k in sorted(run.data["rounds"], key=int):
        r = run.data["rounds"][k]
        if r["count"] > best:
            best, since, which = r["count"], 0, f"round {k}, {r['name']}"
        else:
            since += 1
    stop = "; stop: 3 rounds in a row without a new best" if since >= 3 else ""
    return f"best so far: {best} high on {run.model} ({which}); rounds since without a new best: {since}{stop}"


def score_cmd(env, n, journals, recheck):
    run = Run.latest(env)
    model = run.model if recheck else SCREEN
    results = read_json(run.file("fit-results.json"), {})
    got = 0
    for path in journals:
        for job_id, job in journal_results(path).items():
            results.setdefault(job_id, {})[model] = job
            got += 1
        entry = {"path": os.path.abspath(path).replace(os.sep, "/"), "model": model}
        if entry not in run.data["journals"]:
            run.data["journals"].append(entry)
    write_json(run.file("fit-results.json"), results)
    ctx, pool = Context(env, run), load_pool(run, n)
    print(f"round {n}: {got} fit results on {model} kept")
    out = table(run, ctx, n, pool, found_sets(run, n))
    top = max(out.values(), key=lambda r: (r["high (counted)"], -r["jobs"]))
    run.data["rounds"][str(n)] = {"name": top["candidate"], "count": top["high (counted)"],
                                  "screen": top["high (screen)"]}
    run.save()
    print(f"round {n} best: {top['candidate']}, {top['high (counted)']} high on {run.model}")
    print(best_line(run))


def winner_cmd(env, n, name, apply):
    run = Run.latest(env)
    spec = read_json(run.file(f"round-{n}.json")) or {}
    cand = next((c for c in spec.get("candidates") or [] if c.get("name") == name), None)
    if cand is None:
        sys.exit(f"round {n} has no candidate {name!r}")
    today = datetime.date.today().isoformat()
    data, base = recordlib.load(env, "searches", {
        "_about": "Saved searches: read from alert emails, or checked on a schedule (searches.py).", "searches": []})
    rows = data["searches"]
    saved = collections.defaultdict(list)  # a search saved twice: every copy follows the winner
    for r in rows:
        if r.get("method") == "script":
            saved[row_key(r)].append(r)
    want = {row_key(r): r for r in cand.get("rows") or []}
    add = [k for k in want if k not in saved]
    off = [r for k, rs in saved.items() if k not in want for r in rs if not r.get("off")]
    back = [r for k in want for r in saved.get(k, []) if r.get("off")]
    ctx, pool = Context(env, run), load_pool(run, n)
    found = found_sets(run, n)[name][0]
    jobs = collections.OrderedDict()
    for i in found:
        jobs.setdefault(ctx.job_of(pool[i]), []).append(pool[i])
    new_highs = []
    for posts in jobs.values():
        screen, counted, how = job_grades(ctx, posts)
        if counted == "high" and how == "checked" and not any(ctx.known(p) or link_key(p["url"]) in ctx.by_link
                                                                for p in posts):
            # The posting the fit check read holds the result: it goes in, so the result attaches by its id.
            new_highs.append(next((p for p in posts if run.model in ctx.results.get(p["id"], {})),
                                  next((p for p in posts if SCREEN in ctx.results.get(p["id"], {})), posts[0])))
    rules_path = env.path("SEARCH_RULES") if env.get("SEARCH_RULES") else os.path.join(env.home, "apply",
                                                                                       "search-rules.json")
    print(f"winner {name} (round {n}): {len(want)} rows: {len(want) - len(add)} saved already ({len(back)} turned on "
          f"again), {len(add)} new; {len(off)} saved script rows turned off; title rules "
          + ("kept" if cand.get("rules") is None else f"replaced ({rules_path.replace(os.sep, '/')})")
          + f"; {len(new_highs)} high fits no tracker job holds, added with their fit results")
    if not apply:
        print(f"dry run: nothing was changed (tune.py winner {n} \"{name}\" --apply does it)")
        return
    next_id = max([r.get("id", 0) for r in rows], default=0)
    for k in add:
        r = want[k]
        next_id += 1
        rows.append({"id": next_id, "site": r.get("site") or r["source"], "query": r.get("query", ""), "alert": False,
                     "gmail": "", "every_days": int(r.get("every_days") or (7 if r["source"] in WEEKLY else 1)),
                     "added": today, "last_checked": "", "last_found": None, "method": "script",
                     **{f: r[f] for f in KEY_FIELDS + ("employer",) if f != "query" and r.get(f)}})
    for r in off:
        r["off"] = True
        r["note"] = "; ".join(x for x in (r.get("note"), f"off: tune-search {today}") if x)
    for r in back:
        r.pop("off", None)
    recordlib.save(env, "searches", data, base, "tune.py", indent=1)
    print(f"saved searches: {len(add)} added, {len(off)} turned off, {len(back)} turned on again")
    if cand.get("rules") is not None:
        compile_rules(cand["rules"])
        backup = f"{os.path.splitext(rules_path)[0]}.before-tune-{today}.json"
        if os.path.isfile(rules_path) and not os.path.isfile(backup):  # a second --apply keeps the person's own
            shutil.copyfile(rules_path, backup)
        write_json(rules_path, cand["rules"])
        print(f"title rules: {rules_path.replace(os.sep, '/')} (the old file beside it, .before-tune-{today}.json)")
    if new_highs:
        path = run.file("new-high-fits.json")
        by_employer = collections.OrderedDict()
        for p in new_highs:
            by_employer.setdefault(p["company"] or "(no employer named)", []).append(
                {"id": p["id"], "title": p["title"], "url": p["url"], "location": p["place"], "date": p["date"],
                 "found_by": p["found_by"]})
        write_json(path, {"companies": [{"name": k, "jobs": v} for k, v in by_employer.items()]})
        # Their own results alone, the counted model's first, as one journal: sync attaches them by job id and
        # touches no other employer (a whole run's journals would re-apply other results and checks).
        journal = run.file("new-high-fits.jsonl")
        with open(journal, "w", encoding="utf-8", newline="\n") as fh:
            for i, (employer, posts) in enumerate(by_employer.items()):
                fits = [ctx.results[p["id"]].get(run.model) or ctx.results[p["id"]][SCREEN] for p in posts]
                fh.write(json.dumps({"type": "started", "agentId": f"tune{i}", "label": "prep-fit:" + employer})
                         + "\n")
                fh.write(json.dumps({"type": "result", "agentId": f"tune{i}", "result": {"company": employer,
                                                                                         "jobs": fits}},
                                    ensure_ascii=False) + "\n")
        with open(env.path("TRACKER"), encoding="utf-8") as fh:
            company_shape = is_company_shape(json.load(fh))
        steps = [["add", "--file", path]]
        if company_shape:
            steps.append(["sync", journal])
        else:
            print(f"their fit results stay in {journal.replace(os.sep, '/')}: a flat tracker takes no sync")
        for cmd in steps:
            res = subprocess.run([sys.executable, "-I", os.path.join(HERE, "track.py"), *cmd, "--env", env.file],
                                 capture_output=True, text=True, encoding="utf-8")
            print(res.stdout.strip()[-1500:])
            if res.returncode:
                sys.exit(f"track.py {cmd[0]} failed: {res.stderr.strip()[-300:]}")
    clean_cmd(env)


def clean_cmd(env):
    run = Run.latest(env)
    cache = run.data["cache"]
    if os.path.isdir(cache):
        shutil.rmtree(cache)
        print(f"deleted the cache of raw answers: {cache}")
    else:
        print(f"no cache at {cache}")


def main():
    args = sys.argv[1:]
    env_arg = None
    if "--env" in args:
        i = args.index("--env")
        if i + 1 >= len(args):
            sys.exit("--env takes the path of a job-search.env")
        env_arg = args[i + 1]
        del args[i:i + 2]
    if not args or args[0] not in ("start", "round", "fit", "score", "winner", "clean"):
        sys.exit(__doc__)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    env = jsenv.load(env_arg, __file__)
    cmd, rest = args[0], args[1:]
    flags = [a for a in rest if a.startswith("--")]
    plain = [a for a in rest if not a.startswith("--")]
    if cmd == "start":
        days = 7
        if "--days" in rest:
            i = rest.index("--days")
            days = int(rest[i + 1]) if i + 1 < len(rest) and rest[i + 1].isdigit() else sys.exit("--days takes a number")
        start(env, days)
        return
    if cmd == "clean":
        clean_cmd(env)
        return
    if not plain or not plain[0].isdigit():
        sys.exit(f"{cmd} takes the round's number first")
    n = int(plain[0])
    if cmd == "round":
        round_cmd(env, n, "--offline" in flags)
    elif cmd == "fit":
        fit_cmd(env, n, "--recheck" in flags)
    elif cmd == "score":
        if len(plain) < 2:
            sys.exit("score <n> <journal> [...]: the fit run's journal")
        score_cmd(env, n, plain[1:], "--recheck" in flags)
    elif cmd == "winner":
        if len(plain) < 2:
            sys.exit("winner <n> <candidate> [--apply]")
        winner_cmd(env, n, plain[1], "--apply" in flags)


if __name__ == "__main__":
    main()
