"""Create a new person's job-search main folder and its job-search.env. Never overwrites anything.

Usage: python -I init_career_folder.py "<main folder, e.g. G:/My Drive/Career/job-search>" "<Full Name>"
Creates in the main folder:
  job-search.env               every folder and file name the scripts use (edit the values, never the scripts)
  documents-inbox/             the person drops all their documents here as they are; Claude sorts them
  career-records/career.json   the master record: every fact, decision and form answer, as JSON
  CVs/versions/                one JSON per CV version; build_cv.py prints them to PDF into CVs/
  certificates/ diplomas/ portfolio/   the person's documents (portfolio: e.g. an architect's project catalogue)
  job-applications/{pending,approved,rejected,not-applied}/   one folder per application
  apply/targets.json, apply/pipeline.json, apply/letters/, apply/bodies/   tracker, hiring stages, cover letters
  career-records/employer-rules.json, apply/employer-checks.json   employer rules (defaults) and the person's checks
The scripts stay in the plugin; the main folder holds only the person's own files.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if len(sys.argv) < 3:
    sys.exit(__doc__)
home = os.path.abspath(sys.argv[1])
name = " ".join(sys.argv[2:])
made = []

for d in ("documents-inbox", "career-records", os.path.join("career-records", "previous-documents"),
          os.path.join("CVs", "versions"), "certificates", "diplomas", "portfolio",
          os.path.join("apply", "letters"), os.path.join("apply", "bodies"),
          *(os.path.join("job-applications", s) for s in ("pending", "approved", "rejected", "closed", "declined", "not-applied"))):
    path = os.path.join(home, d)
    if not os.path.isdir(path):
        os.makedirs(path)
        made.append(path)

SKELETON = {
    "meta": {"about": "The person's master record: every fact, decision and form answer. Facts come only from the "
                      "person or their documents; a claim nobody confirmed has \"status\": \"pending\" and never goes "
                      "on a CV. Add each new fact at once, dated, as one fact line (no narrative, no quoted chat); "
                      "a decision is a value and a date."},
    "profile": {"name": name, "headline": "", "email": "", "phone": "", "linkedin": "", "location": "",
                "citizenship": [], "work_authorisation": "", "languages": []},
    "experience": [], "education": [], "certificates": [], "skills": {}, "volunteering": [], "interests": [],
    "portfolio": [],
    "references": {"_about": "Referees the person named, each {name, role, relation, contact, agreed_on}; only with "
                             "the person's word that the referee agreed. Never contacted by Claude."},
    "form_answers": {"_about": "Answers the person gave for application forms; add each new one with its date."},
    "preferences": {"locations": [], "work_modes": [], "pay": {"private": True, "rules": []},
                    "interview_scheduling": []},
    "employer_rules": [], "cv_rules": [], "decisions": [], "open_questions": [],
    "learnings": [], "sources": [],
}
FILES = {
    os.path.join(home, "career-records", "career.json"): SKELETON,
    os.path.join(home, "apply", "targets.json"): {
        "_about": "One row per job: id, company, title, url, location, work_mode, cv, letter, status, applied, note, "
                  "history. Statuses: found, pending, to-apply, account-needed, needs-person, needs-captcha, "
                  "submitted, skipped, excluded, failed, closed (posting closed before sending), declined (the person chose "
                  "not to apply).",
        "jobs": []},
    os.path.join(home, "apply", "logins.json"): {
        "_about": "Login state: connectors and job-site sign-ins. Written by Claude at each health check (logins.py).",
        "logins": []},
    os.path.join(home, "apply", "pipeline.json"): {
        "_about": "Hiring stage per sent job (key = job id). stage: approved | rejected | closed | declined (missing = pending). "
                  "approved: steps in order, each {date, time, name, with, how, due, link, mail} (link: the step's "
                  "own page; mail: the Gmail link of the email that set it); same_as: another job id whose "
                  "process this one shares; reminder. rejected and closed: date and reason. declined: date, why "
                  "(ethics | relocation | pay | other) and reason."},
    os.path.join(home, "apply", "employer-checks.json"): {
        "_about": "The person's own employer checks per category (employer.py): {employers: {name: {checks, verdict, "
                  "decisions}}}.",
        "employers": {}},
    # The person's employer rules start as the plugin's defaults: every category "warn and ask".
    os.path.join(home, "career-records", "employer-rules.json"):
        json.load(open(os.path.join(HERE, "..", "templates", "employer-rules.json"), encoding="utf-8")),
}
for path, content in FILES.items():
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        made.append(path)

env_path = os.path.join(home, "job-search.env")
if not os.path.exists(env_path):
    template = open(os.path.join(HERE, "..", "templates", "job-search.env.template"), encoding="utf-8").read()
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(template.replace("{name}", name).replace("{name_upper}", name.upper())
                .replace("{home}", home.replace(os.sep, "/")))
    made.append(env_path)

print("\n".join(["Created:"] + made) if made else "Nothing to create: the folders already exist.")
print(f"\nNext: put all your documents (CVs, cover letters, diplomas, certificates, references, portfolio) as they are\n"
      f"in {os.path.join(home, 'documents-inbox')}, or tell Claude where they are; then tell Claude you have finished.")
