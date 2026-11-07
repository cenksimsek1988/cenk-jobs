"""Usage log and the usage report the person may share with the plugin's developer (only with their yes).

python -I usage.py log <step> <ok|failed|stopped> ["<note>"]   one line per routine step (health check, gmail,
                                                               search, screen, apply, folders, dashboard, prep, ...);
                                                               the note stays local, it never goes into a report;
                                                               step "run" with started, then ok|failed|stopped,
                                                               marks a whole run (the dashboard shows it)
python -I usage.py due                                         "due" when USAGE_SHARING=yes and no report was drafted
                                                               in the last 7 days; "ask" when USAGE_SHARING is not set
python -I usage.py report [--out <file>]                       write the report JSON (default: next to USAGE_LOG) and
                                                               print the email text for the developer
python -I usage.py mark-drafted                                record that this week's report email was drafted
python -I usage.py stats                                       print the employer_rules block below, for the person
                                                               (works whatever USAGE_SHARING says; sends nothing)

The report holds no personal data: never the person's name, contact details, accounts, CV or letter text, notes,
pay figures or addresses (masked if they appear). It holds:
  applications  how many were sent each week (and the average), by platform and by status
  outcomes      per sent application: employer, role, platform, sent date, stage, the hiring steps reached with their
                dates, the first "yes" (the first step) and the days it took, or the rejection date
  sites         each connector and job site with its login state (no account names)
  employers     every employer checked, with its verdict and each category's result (flagged with the fact and
                source, clear, or left out when unknown); flagged employers are reported whatever the person decided
  employer_rules  jobs turned down because of the employer rules: excluded before applying, withdrawn after
                applying (before or after a hiring step) and waiting on the person's answer to a "discuss", each
                by category and by where the finding came from (shared list, own check, decision);
                the person's own filters count as "custom"
  steps         how often each routine step ran and how it ended
The email goes to DEVELOPER_EMAIL as a Gmail draft; the person reads it and sends it.
Add --env <job-search.env> anywhere to pick the env file.
"""
import collections
import datetime
import json
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import employerlib as el  # noqa: E402
import jsenv  # noqa: E402
from trackerlib import applied_on, flat_jobs, no_pay, note_key, site_of  # noqa: E402

DEVELOPER_EMAIL = "cenk.plugins.reports@gmail.com"
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"\+\d[\d ()-]{7,}\d")  # international numbers only, so dates and amounts stay
PROFILE = re.compile(r"(?i)linkedin\.com/in/[\w%-]+|github\.com/[\w-]+")
args = sys.argv[1:]
env_arg = None
if "--env" in args:
    i = args.index("--env")
    env_arg = args[i + 1]
    del args[i:i + 2]
if not args or args[0] not in ("log", "due", "report", "mark-drafted", "stats"):
    sys.exit(__doc__)
env = jsenv.load(env_arg, __file__)
LOG = env.path("USAGE_LOG") if env.get("USAGE_LOG") else os.path.join(env.home, "apply", "usage-log.jsonl")
now = datetime.datetime.now().replace(microsecond=0)


def events():
    if not os.path.exists(LOG):
        return []
    with open(LOG, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def ensure_install():
    """An install id lets the developer tell one person's weekly reports apart from another's without a name."""
    if not any(e.get("event") == "install" for e in events()):
        append_line({"time": now.isoformat(), "event": "install", "id": uuid.uuid4().hex[:12]})


def append(row):
    ensure_install()
    append_line(row)


def append_line(row):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def masker():
    """A function that removes the person's identity from a string."""
    exact = [env.get(k, "") for k in ("PERSON_NAME", "NAME_ON_CV", "GMAIL_ACCOUNT", "CALENDAR_ACCOUNT",
                                      "DRIVE_ACCOUNT")]
    exact += [p.strip() for p in env.get("CONTACT_LINE", "").split("·")]
    exact = sorted({e for e in exact if len(e) >= 4}, key=len, reverse=True)
    # Each part of the name on its own, with its ASCII spelling ("Öztürk" and "Ozturk"), as a whole word: hyphens
    # count as part of a word, so a name inside "name-jobs" stays.
    parts = {p for k in ("PERSON_NAME", "NAME_ON_CV") for w in env.get(k, "").split() if len(w) >= 3
             for p in (w, w.translate(jsenv.ASCII))}
    name = re.compile(r"(?i)(?<![\w-])(" + "|".join(map(re.escape, sorted(parts))) + r")(?![\w-])") if parts else None
    pairs = []
    if env.get("REDACT_FILE") and os.path.exists(env.path("REDACT_FILE")):
        with open(env.path("REDACT_FILE"), encoding="utf-8") as f:
            for line in f:
                if "=>" in line and not line.lstrip().startswith("#"):
                    pattern, repl = line.rstrip("\n").split("=>", 1)
                    pairs.append((re.compile(pattern.strip()), "[private]"))

    def mask(text):
        for e in exact:
            text = text.replace(e, "[private]")
        for pattern, repl in pairs:
            text = pattern.sub(repl, text)
        if name:
            text = name.sub("[the person]", text)
        return PROFILE.sub("[private]", PHONE.sub("[private]", EMAIL.sub("[private]", text)))
    return mask


def scrub(value, mask, pay=False):
    if isinstance(value, str):
        value = mask(value)
        return no_pay(value) if pay else value
    if isinstance(value, list):
        return [scrub(v, mask, pay) for v in value]
    if isinstance(value, dict):
        return {k: scrub(v, mask, pay) for k, v in value.items()}
    return value


def week(day):
    y, w, _ = datetime.date.fromisoformat(day).isocalendar()
    return f"{y}-W{w:02d}"


RULE_STAGES = ("excluded", "submitted", "skipped", "closed", "declined", "failed")


def turned_down(jobs, pipeline):
    """Jobs the employer rules turned down: before applying, withdrawn after applying, and waiting on a discuss."""
    rule_set = el.rules(env)
    custom = {c for c, s in rule_set["categories"].items() if s.get("custom")}
    memo = {}

    def why(company):
        if company not in memo:
            memo[company] = el.excluding(env, company, rule_set)
        return memo[company]

    def label(found):
        if found["origin"] == "unknown":
            return "unknown"  # the tracker says excluded, but the rules no longer exclude the employer
        if found["category"] in custom:
            return "custom"
        return found["category"] or ("named_list" if found["origin"] == "list" else "unspecified")

    def block():
        return {"jobs": 0, "by_category": collections.Counter(), "by_origin": collections.Counter()}

    before, after, discuss = block(), block(), block()
    after.update(before_a_step=0, after_a_step=0)
    for job in jobs:
        company = job.get("company", "")
        p = pipeline.get(job.get("id")) or {}
        if p.get("same_as"):
            p = pipeline.get(p["same_as"]) or p
        sent = job.get("status") == "submitted" or bool(p)
        if p.get("stage") == "declined" and p.get("why") == "ethics":
            target = after
            target["after_a_step" if p.get("steps") else "before_a_step"] += 1
            found = why(company)
            if p.get("category"):
                found = [{"category": p["category"], "origin": found[0]["origin"] if found else "decision"}]
        elif job.get("status") == "excluded" and not sent:
            target, found = before, why(company)
        elif not sent and job.get("status") not in RULE_STAGES:
            if el.decide(env, company, el.lookup(env, company), rule_set)[0] != "discuss":
                continue
            target = discuss
            found = []
            for c, k in el.lookup(env, company).items():
                s = rule_set["categories"].get(c)
                if k.get("status") != "flagged" or s is None:
                    continue
                act = s.get("action", "discuss") if k.get("level", "direct") == "direct" else s.get("indirect", "discuss")
                if act == "discuss":
                    found.append({"category": c, "origin": k.get("origin", "own")})
        else:
            continue
        target["jobs"] += 1
        for f in found or [{"category": "", "origin": "unknown"}]:
            target["by_category"][label(f)] += 1
            target["by_origin"][f["origin"]] += 1
    out = {}
    for key, b in (("excluded_before_applying", before), ("withdrawn_after_applying", after),
                   ("waiting_on_discuss", discuss)):
        out[key] = dict(b, by_category=dict(b["by_category"].most_common()),
                        by_origin=dict(b["by_origin"].most_common()))
    return out


def rules_line(block):
    def part(b):
        cats = ", ".join(f"{c} {n}" for c, n in b["by_category"].items())
        return f"{b['jobs']}" + (f" ({cats})" if cats else "")
    return (f"Turned down because of the employer rules: {part(block['excluded_before_applying'])} before "
            f"applying, {part(block['withdrawn_after_applying'])} withdrawn after applying; "
            f"{part(block['waiting_on_discuss'])} waiting on the person's answer.")


def report():
    tracker = el.load_json(env.path("TRACKER"), {})
    pipeline = el.load_json(env.path("PIPELINE"), {})
    logins = el.load_json(env.path("LOGINS") if env.get("LOGINS") else "", {"logins": []})
    note = note_key(tracker)
    jobs = flat_jobs(tracker)
    sent = [(j, applied_on(j, note)) for j in jobs if j.get("status") == "submitted" or j.get("id") in pipeline]
    sent = [(j, d) for j, d in sent if d]
    weeks = collections.Counter(week(d) for _, d in sent)
    if sent:
        first = min(datetime.date.fromisoformat(d) for _, d in sent)
        span = max(1, ((now.date() - first).days // 7) + 1)
    else:
        span = 0
    outcomes, yes = [], 0
    for job, day in sorted(sent, key=lambda x: x[1]):
        p = pipeline.get(job["id"]) or {}
        if p.get("same_as"):
            p = pipeline.get(p["same_as"]) or p
        steps = [{"name": s.get("name", ""), "date": s.get("date", "")} for s in p.get("steps", [])]
        row = {"employer": job.get("company", ""), "role": job.get("title", ""),
               "platform": job.get("platform") or site_of(job.get("apply_url")), "sent": day,
               "stage": p.get("stage", "pending"), "steps": steps}
        dated = sorted(s["date"] for s in steps if s["date"])
        if p.get("stage") == "approved" or steps:
            yes += 1
            row["first_yes"] = dated[0] if dated else ""
            if dated:
                row["days_to_first_yes"] = (datetime.date.fromisoformat(dated[0]) -
                                            datetime.date.fromisoformat(day)).days
        if p.get("stage") in ("rejected", "closed", "declined"):
            row[f"{p['stage']}_on"] = p.get("date", "")
        if p.get("stage") == "declined":
            row["declined_why"] = p.get("why", "other")
            if p.get("category"):
                row["declined_category"] = p["category"]
        outcomes.append(row)
    checks = el.checks_file(env).get("employers", {})
    employers = []
    for name, entry in sorted(checks.items()):
        cats = {c: {k: v for k, v in chk.items() if k in ("status", "level", "fact", "source_url", "checked", "basis")}
                for c, chk in entry.get("checks", {}).items() if chk.get("status") in ("flagged", "clear")}
        employers.append({"name": name, "verdict": entry.get("verdict", ""), "checks": cats})
    log = events()
    steps = collections.Counter((e.get("step"), e.get("result")) for e in log if e.get("step"))
    install = next((e["id"] for e in log if e.get("event") == "install"), "")
    mask = masker()
    out = {
        "plugin": "cenk-jobs", "report_date": now.date().isoformat(), "install_id": install,
        "applications": scrub({
            "sent_total": len(sent), "weeks": dict(sorted(weeks.items())), "weeks_counted": span,
            "average_per_week": round(len(sent) / span, 1) if span else 0,
            "by_platform": dict(collections.Counter((j.get("platform") or site_of(j.get("apply_url")) or "unknown")
                                                     for j, _ in sent).most_common()),
            # An older tracker may name the person in a status ("needs-jane"): every such status counts as needs-person.
            "by_status": dict(collections.Counter(
                "needs-person" if s.startswith("needs-") and s != "needs-captcha" else s
                for s in (j.get("status", "") for j in jobs)).most_common()),
            "first_yes": yes, "first_yes_rate": round(yes / len(sent), 3) if sent else 0,
            "rejected": sum(1 for o in outcomes if o["stage"] == "rejected"),
            "closed": sum(1 for o in outcomes if o["stage"] == "closed"),
            "declined": sum(1 for o in outcomes if o["stage"] == "declined"),
        }, mask, pay=True),
        "outcomes": scrub(outcomes, mask, pay=True),
        "sites": scrub([{"kind": r.get("kind", ""), "name": r.get("name") or r.get("id", ""),
                         "status": r.get("status", "")} for r in logins.get("logins", [])], mask),
        "employers": scrub(employers, mask),
        "employer_rules": turned_down(jobs, pipeline),
        "steps": [{"step": s, "result": r, "count": n} for (s, r), n in sorted(steps.items())],
    }
    return out


def email_text(rep):
    a = rep["applications"]
    flagged = collections.Counter(c for e in rep["employers"] for c, k in e["checks"].items()
                                  if k.get("status") == "flagged")
    failed = [s for s in rep["steps"] if s["result"] not in ("ok", "started")]
    lines = [f"cenk-jobs usage report {rep['report_date']} (install {rep['install_id']})", "",
             f"Applications sent: {a['sent_total']}, about {a['average_per_week']} a week over {a['weeks_counted']} weeks.",
             f"First yes (a first hiring step): {a['first_yes']} ({round(a['first_yes_rate'] * 100)}%); "
             f"rejected: {a['rejected']}; closed (not a rejection): {a['closed']}; declined by the person: "
             f"{a['declined']}.",
             f"Employers checked: {len(rep['employers'])}; flagged by category: "
             + (", ".join(f"{c} {n}" for c, n in flagged.most_common()) or "none") + ".",
             rules_line(rep["employer_rules"]),
             "Steps that did not end ok: " + (", ".join(f"{s['step']} {s['result']} x{s['count']}" for s in failed)
                                              or "none") + ".",
             "", "The full report (JSON) follows. It holds no name, contact, CV, pay or address.", "",
             json.dumps(rep, ensure_ascii=False, indent=1)]
    return "\n".join(lines)


cmd = args[0]
if cmd == "log":
    if len(args) < 3:
        sys.exit(__doc__)
    append({"time": now.isoformat(), "step": args[1], "result": args[2], "note": args[3] if len(args) > 3 else ""})
    print("logged", args[1], args[2])
elif cmd == "due":
    sharing = env.get("USAGE_SHARING", "").lower()
    if sharing not in ("yes", "no"):
        print("ask: USAGE_SHARING is not set; ask the person once whether usage reports may go to the developer")
    elif sharing == "no":
        print("not due: the person said no to usage reports")
    else:
        last = max((e["time"] for e in events() if e.get("event") == "report-drafted"), default="")
        due = not last or (now - datetime.datetime.fromisoformat(last)).days >= 7
        print("due" if due else f"not due: last report drafted {last[:10]}")
elif cmd == "report":
    ensure_install()
    rep = report()
    out = args[args.index("--out") + 1] if "--out" in args else os.path.join(
        os.path.dirname(LOG), f"usage-report-{rep['report_date']}.json")
    el.save_json(out, rep)
    print(f"To: {DEVELOPER_EMAIL}")
    print(f"Subject: cenk-jobs usage report {rep['report_date']} ({rep['install_id']})")
    print(f"Report file: {out}")
    print()
    print(email_text(rep))
elif cmd == "mark-drafted":
    append({"time": now.isoformat(), "event": "report-drafted"})
    print("report drafted", now.date().isoformat())
elif cmd == "stats":
    block = turned_down(flat_jobs(el.load_json(env.path("TRACKER"), {})), el.load_json(env.path("PIPELINE"), {}))
    print(rules_line(block))
    print(json.dumps(block, ensure_ascii=False, indent=1))
