#!/bin/sh
# Tests for the cenk-jobs scripts, on a made-up job search in a throwaway folder: one PASS or FAIL line per check.
# Why: the tracker's split into summary rows and detail files, the employer decisions and the small scripts must keep
# working on both tracker shapes, and no check may ever touch a real record.
# Usage: sh tests/run.sh          (PYTHON=<python> sh tests/run.sh to pick the interpreter)
# Exit 0: every check passed. 1: at least one failed. 2: the tests could not start.
# Safety: every script runs with --env <throwaway folder>/<home>/job-search.env and JOB_SEARCH_ENV points there too,
# from a working folder inside the throwaway folder, so no real job-search.env can be found. The folder is removed on exit.
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
S="$HERE/../plugins/cenk-jobs/scripts"
[ -f "$S/track.py" ] || { echo "cannot find the scripts beside $HERE" >&2; exit 2; }

PY=${PYTHON:-}
if [ -z "$PY" ]; then
    for cand in python3 python; do
        if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import sys" >/dev/null 2>&1; then PY=$cand; break; fi
    done
fi
[ -n "$PY" ] || { echo "no python found: set PYTHON" >&2; exit 2; }

T=$(mktemp -d) || exit 2
trap 'rm -rf "$T"' EXIT INT TERM HUP
# Windows programs need the C:/ form of a Git Bash path; elsewhere cygpath does not exist.
win() { cygpath -m "$1" 2>/dev/null || echo "$1"; }
T=$(win "$T")
S=$(win "$(cd "$S" && pwd)")
cd "$T" || exit 2

PASSED=0
FAILED=0
pass() { PASSED=$((PASSED + 1)); echo "PASS $1"; }
fail() { FAILED=$((FAILED + 1)); echo "FAIL $1"; }
# check "<name>" <command ...>: PASS when the command exits 0; on FAIL its first lines follow, indented.
check() {
    name=$1
    shift
    if "$@" >"$T/last.out" 2>&1; then pass "$name"; else fail "$name"; head -n 6 "$T/last.out" | sed 's/^/     /'; fi
}

# A helper for the checks: values in JSON files, the split round trip, flat_jobs. Path syntax: a.b.0.c, id=J1 picks
# the list item whose id is J1.
cat >"$T/q.py" <<'PYEOF'
import copy
import json
import os
import sys

sys.path.insert(0, os.environ["SCRIPTS"])
import trackerlib as tl  # noqa: E402
import employerlib as el  # noqa: E402


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def walk(data, path):
    for key in [k for k in path.split(".") if k]:
        if isinstance(data, list):
            if "=" in key:
                name, value = key.split("=", 1)
                data = next(x for x in data if str(x.get(name)) == value)
            else:
                data = data[int(key)]
        else:
            data = data[key]
    return data


def strip_details(tracker):
    tracker = copy.deepcopy(tracker)
    for c in tracker.get("companies", []):
        c.pop("details", None)
        for j in c.get("jobs", []):
            j.pop("details", None)
    for j in tracker.get("jobs", []):
        j.pop("details", None)
    return tracker


cmd = sys.argv[1]
if cmd == "roundtrip":  # q.py roundtrip <original> <split tracker>
    original, split = load(sys.argv[2]), sys.argv[3]
    merged = tl.expand(load(split), split)
    sys.exit(0 if strip_details(merged) == original else 1)
if cmd == "flat":  # q.py flat <original> <split tracker>: the same rows, but for what moved into the details
    drop = ("prep", "history", "earlier", "details", "prep_apply_url")
    one = [{k: v for k, v in r.items() if k not in drop} for r in tl.flat_jobs(load(sys.argv[2]))]
    two = [{k: v for k, v in r.items() if k not in drop} for r in tl.flat_jobs(load(sys.argv[3]))]
    sys.exit(0 if one and one == two else 1)
if cmd == "lookupkeys":  # q.py lookupkeys "<name>" a,b: the lookup keys of the name are exactly these
    sys.exit(0 if sorted(el.keys(sys.argv[2])) == sorted(sys.argv[3].split(",")) else 1)
if cmd == "keys":  # q.py keys <file> a,b,c: the top-level keys are exactly these
    sys.exit(0 if sorted(load(sys.argv[2])) == sorted(sys.argv[3].split(",")) else 1)
if cmd == "nostatus":  # q.py nostatus <file> <path to checks> <status>: no check has this status
    sys.exit(0 if all(c.get("status") != sys.argv[4] for c in walk(load(sys.argv[2]), sys.argv[3]).values()) else 1)
# q.py <file> <path> eq|ne|len|absent|present [value]
path, node, op = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    value, found = walk(load(path), node), True
except (KeyError, IndexError, StopIteration):
    value, found = None, False
if op == "absent":
    sys.exit(0 if not found else 1)
if op == "present":
    sys.exit(0 if found else 1)
want = sys.argv[4]
if op == "eq":
    sys.exit(0 if found and str(value) == want else 1)
if op == "ne":
    sys.exit(0 if found and str(value) != want else 1)
if op == "len":
    sys.exit(0 if found and len(value) == int(want) else 1)
sys.exit(2)
PYEOF
SCRIPTS=$S
export SCRIPTS
q() { "$PY" -I "$T/q.py" "$@"; }

# --- the made-up fixture -------------------------------------------------------------------------------------------
PAD=$(awk 'BEGIN { for (i = 0; i < 150; i++) printf "padding " }')

# mkhome <dir> <tracker shape: old|flat>: a job search folder for Jane Doe, with the older {companies} tracker or the flat one.
mkhome() {
    h=$1
    mkdir -p "$h/apply" "$h/career-records"
    cat >"$h/job-search.env" <<EOF
PERSON_NAME=Jane Doe
NAME_ON_CV=JANE DOE
CONTACT_LINE=jane@example.com
RECORDS_DIR=career-records
CVS_DIR=CVs
CV_VERSIONS_DIR=CVs/versions
CERTIFICATES_DIR=certificates
APPLICATIONS_DIR=job-applications
LETTERS_DIR=apply/letters
LETTER_BODIES_DIR=apply/bodies
MASTER_RECORD=career-records/career.json
PERSONAL_RECORD=career-records/personal.json
TRACKER=apply/targets.json
PIPELINE=apply/pipeline.json
LOGINS=apply/logins.json
QUESTIONS=apply/questions.json
SEARCHES=apply/searches.json
EMPLOYER_CHECKS=apply/employer-checks.json
EOF
    echo '{}' >"$h/apply/pipeline.json"
    echo '{"logins": []}' >"$h/apply/logins.json"
    cat >"$h/career-records/career.json" <<EOF
{"profile": {"name": "Jane Doe"}, "skills": ["Java"], "languages": ["English"],
 "preferences": {"employer_rules": {"note": "made up"}, "locations": ["Rome"], "pay": {"min": 1}},
 "decisions": [], "form_answers": {"notice_period": "1 month"}, "cv_rules": [], "never_claim": ["a PhD"],
 "private_extra": "not for letters"}
EOF
    if [ "$2" = old ]; then
        cat >"$h/apply/targets.json" <<EOF
{"companies": [
 {"name": "Acme Corp", "verdict": "allow", "origin": "search",
  "hits": [{"criterion": "A", "finding": "Acme builds weapons", "source_url": "https://example.com/f"}],
  "not_counted": ["Acme sponsors a club"], "ties_for_jane": ["Acme has a partner firm"],
  "jobs": [{"id": "J1", "title": "Engineer", "url": "https://example.com/j1", "status": "pending", "applied": "",
            "outcome": "added", "history": [{"date": "2026-11-01", "status": "found", "outcome": "added"}],
            "prep": {"id": "J1", "title": "Senior Engineer", "apply_url": "https://example.com/apply/1",
                     "platform": "Workday", "needs_jane": ["Phone number"],
                     "answers": [{"question": "Notice period", "answer": "1 month"}], "reason": "fits ${PAD}"}}]},
 {"name": "Beta Ltd", "verdict": "exclude", "hits": [],
  "jobs": [{"id": "J2", "title": "Analyst", "url": "https://www.linkedin.com/jobs/view/1234567890/?trackingId=abc",
            "status": "excluded", "outcome": "employer excluded", "apply_url": "https://example.com/a2",
            "prep": {"id": "J2", "apply_url": "https://example.com/other2"}}]},
 {"name": "Gamma Inc", "verdict": "discuss",
  "jobs": [{"id": "J3", "title": "Designer", "url": "https://example.com/j3", "status": "found", "outcome": ""}]},
 {"name": "Epsilon Co", "verdict": "allow",
  "jobs": [{"id": "E1", "title": "Tester", "url": "https://example.com/e1", "status": "found", "outcome": ""}]}
]}
EOF
    else
        cat >"$h/apply/targets.json" <<EOF
{"jobs": [
 {"id": "F1", "company": "Acme Corp", "title": "Developer", "url": "https://example.com/f1", "status": "needs-person",
  "note": "waiting for a phone number", "history": [{"date": "2026-11-01", "status": "found", "note": "added"}]},
 {"id": "F2", "company": "Beta Ltd", "title": "Analyst", "url": "https://www.linkedin.com/jobs/view/1234567890/?trackingId=abc",
  "status": "found", "note": ""}
]}
EOF
    fi
}

# Every script gets its env file explicitly; JOB_SEARCH_ENV is only the second line of defence.
use() { H=$1; ENVF="$H/job-search.env"; JOB_SEARCH_ENV=$ENVF; export JOB_SEARCH_ENV; }
track() { "$PY" -I "$S/track.py" "$@" --env "$ENVF"; }
employer() { "$PY" -I "$S/employer.py" "$@" --env "$ENVF"; }
questions() { "$PY" -I "$S/questions.py" "$@" --env "$ENVF"; }
searches() { "$PY" -I "$S/searches.py" "$@" --env "$ENVF"; }
backup_of() { ls "$1"/apply/targets.json.before-split-*.json 2>/dev/null | head -n 1; }

mkhome "$T/old" old
mkhome "$T/flat" flat
use "$T/old"
check "safety: the env file is inside the throwaway folder" sh -c '
    case "$1" in "$2"/*) exit 0 ;; *) exit 1 ;; esac' _ "$ENVF" "$T"

# --- split: the dry run ----------------------------------------------------------------------------------------------
cp -R "$T/old" "$T/split"
use "$T/split"
cp "$H/apply/targets.json" "$T/original.json"
track split >"$T/dry.out" 2>&1
check "split dry run: prints counts and bytes" grep -q "bytes: tracker" "$T/dry.out"
check "split dry run: changes nothing" sh -c 'cmp -s "$1" "$2" && [ ! -d "$3/apply/details" ] && [ -z "$(ls "$3"/apply/*.before-split-* 2>/dev/null)" ]' \
    _ "$T/original.json" "$H/apply/targets.json" "$H"

# --- split --apply -----------------------------------------------------------------------------------------------------
check "split --apply: exits 0" track split --apply
check "split --apply: one detail file per job and company with something to move" sh -c \
    '[ -f "$1/apply/details/jobs/J1.json" ] && [ -f "$1/apply/details/jobs/J2.json" ] && [ -f "$1/apply/details/companies/Acme-Corp.json" ] && [ ! -f "$1/apply/details/jobs/J3.json" ] && [ ! -f "$1/apply/details/companies/Epsilon-Co.json" ]' _ "$H"
check "split --apply: a backup of the tracker is kept" sh -c 'cmp -s "$1" "$2"' _ "$T/original.json" "$(backup_of "$H")"
check "split --apply: the tracker is smaller" sh -c '[ "$(wc -c <"$1")" -lt "$(wc -c <"$2")" ]' _ "$H/apply/targets.json" "$T/original.json"
check "split --apply: the summary row has no prep or history, and names its detail" sh -c '
    "$1" -I "$2/q.py" "$3" companies.0.jobs.0.prep absent && "$1" -I "$2/q.py" "$3" companies.0.jobs.0.history absent &&
    "$1" -I "$2/q.py" "$3" companies.0.jobs.0.details eq details/jobs/J1.json' _ "$PY" "$T" "$H/apply/targets.json"
check "split --apply: the row alone holds the resolved title, link, platform and needs" sh -c '
    for kv in "title eq Senior Engineer" "apply_url eq https://example.com/apply/1" "platform eq Workday" "needs.0 eq Phone number"; do
        k=${kv%% *}; rest=${kv#* }; "$1" -I "$2/q.py" "$3" "companies.0.jobs.0.$k" "${rest%% *}" "${rest#* }" || exit 1
    done' _ "$PY" "$T" "$H/apply/targets.json"
check "split --apply: the detail's prep drops what the row says" sh -c '
    "$1" -I "$2/q.py" "$3" prep.id absent && "$1" -I "$2/q.py" "$3" prep.title absent &&
    "$1" -I "$2/q.py" "$3" prep.apply_url absent && "$1" -I "$2/q.py" "$3" prep.platform absent' _ "$PY" "$T" "$H/apply/details/jobs/J1.json"
check "split --apply: the merged view of every row equals the original" q roundtrip "$T/original.json" "$H/apply/targets.json"
check "split --apply: flat_jobs gives the same rows as before" q flat "$T/original.json" "$H/apply/targets.json"
check "split --apply: flat_jobs opens no detail file" sh -c '
    mv "$1/apply/details" "$1/apply/details.hidden" && "$2" -I -c "
import json, sys
sys.path.insert(0, sys.argv[1])
import trackerlib
rows = trackerlib.flat_jobs(json.load(open(sys.argv[2], encoding=\"utf-8\")))
sys.exit(0 if len(rows) == 4 else 1)" "$3" "$1/apply/targets.json"; code=$?
    mv "$1/apply/details.hidden" "$1/apply/details"; exit $code' _ "$H" "$PY" "$S"

# --- split twice -------------------------------------------------------------------------------------------------------
cp "$H/apply/targets.json" "$T/split1.json"
track split --apply >"$T/twice.out" 2>&1
check "split twice: says there is nothing to split" grep -q "nothing to split" "$T/twice.out"
check "split twice: the tracker is unchanged and no second backup is made" sh -c \
    'cmp -s "$1" "$2" && [ "$(ls "$3"/apply/targets.json.before-split-* | wc -l)" -eq 1 ]' _ "$T/split1.json" "$H/apply/targets.json" "$H"

cp -R "$T/split" "$T/split-fresh"  # the tracker as just split, for the checks below that must not see sync's changes

# --- show ----------------------------------------------------------------------------------------------------------------
track show J1 >"$T/show.out" 2>&1
check "show: the summary row and the path of its detail" sh -c 'grep -q "details/jobs/J1.json" "$1" && ! grep -q "\"prep\"" "$1" && grep -q "\"company\": \"Acme Corp\"" "$1"' _ "$T/show.out"
track show J1 --full >"$T/full.out" 2>&1
check "show --full: the merged view holds prep, history and the answers" sh -c 'grep -q "\"prep\"" "$1" && grep -q "\"history\"" "$1" && grep -q "Notice period" "$1" && grep -q "Phone number" "$1"' _ "$T/full.out"
check "brief: reads the prep from the detail" sh -c '"$1" -I "$2/track.py" brief J1 --env "$3" | grep -q "NEED: Phone number"' _ "$PY" "$S" "$ENVF"

# --- the person's own commands on a split tracker ---------------------------------------------------------------------
check "questions answer on a split tracker: the answer goes into the detail's prep" sh -c '
    "$1" -I "$2/questions.py" add job "Why Acme?" job=J1 --env "$3" >/dev/null &&
    "$1" -I "$2/questions.py" answer job-j1-why-acme "Because it fits" --env "$3" >/dev/null &&
    "$1" -I "$4/q.py" "$5/apply/details/jobs/J1.json" "prep.answers.question=Why Acme?.answer" eq "Because it fits" &&
    "$1" -I "$4/q.py" "$5/apply/targets.json" companies.0.jobs.0.prep absent' _ "$PY" "$S" "$ENVF" "$T" "$H"
check "set on a split tracker: the history goes into the detail file" sh -c '
    "$1" -I "$2/track.py" set J1 submitted "sent in the test" --env "$3" >/dev/null &&
    "$1" -I "$4/q.py" "$5/apply/details/jobs/J1.json" history len 2 &&
    "$1" -I "$4/q.py" "$5/apply/details/jobs/J1.json" history.status=submitted.outcome eq "sent in the test" &&
    "$1" -I "$4/q.py" "$5/apply/targets.json" companies.0.jobs.0.history absent &&
    "$1" -I "$4/q.py" "$5/apply/targets.json" companies.0.jobs.0.status eq submitted &&
    "$1" -I "$4/q.py" "$5/apply/targets.json" companies.0.jobs.0.applied ne ""' _ "$PY" "$S" "$ENVF" "$T" "$H"

cat >"$T/journal.jsonl" <<'EOF'
{"type": "started", "agentId": "a1", "label": "excl-screen:Acme Corp"}
{"type": "result", "agentId": "a1", "result": {"verdict": "allow", "hits": [], "ties": ["Acme sponsors a sports club"]}}
{"type": "started", "agentId": "a2", "label": "prep-jobs:Acme Corp"}
{"type": "result", "agentId": "a2", "result": {"jobs": [{"id": "J1", "action": "apply", "platform": "Greenhouse", "title": "Senior Engineer", "apply_url": "https://example.com/apply/1", "needs": ["Phone number"], "reason": "fits"}]}}
EOF
check "sync on a split tracker: the prep goes into the detail file" sh -c '
    "$1" -I "$2/track.py" sync "$6" --env "$3" >/dev/null &&
    "$1" -I "$4/q.py" "$5/apply/details/jobs/J1.json" prep.action eq apply &&
    "$1" -I "$4/q.py" "$5/apply/details/jobs/J1.json" prep.platform absent &&
    "$1" -I "$4/q.py" "$5/apply/targets.json" companies.0.jobs.0.prep absent &&
    "$1" -I "$4/q.py" "$5/apply/targets.json" companies.0.jobs.0.platform eq Greenhouse' _ "$PY" "$S" "$ENVF" "$T" "$H" "$T/journal.jsonl"
check "sync on a split tracker: ties go into the company's detail, the older ties_for key stays" sh -c '
    "$1" -I "$2/q.py" "$3/apply/details/companies/Acme-Corp.json" ties.0 eq "Acme sponsors a sports club" &&
    "$1" -I "$2/q.py" "$3/apply/details/companies/Acme-Corp.json" ties_for_jane.0 eq "Acme has a partner firm" &&
    "$1" -I "$2/q.py" "$3/apply/targets.json" companies.0.hits absent' _ "$PY" "$T" "$H"
check "sync on a split tracker: still every row of the tracker" sh -c '
    "$1" -I "$2/q.py" "$3/apply/targets.json" companies len 4 && "$1" -I "$2/q.py" "$3/apply/targets.json" companies.0.jobs len 1' _ "$PY" "$T" "$H"

# --- the application folders are the same before and after the split -------------------------------------------------------
cp -R "$T/old" "$T/build-flat"
cp -R "$T/old" "$T/build-split"
use "$T/build-flat"
"$PY" -I "$S/build_app_folders.py" --env "$ENVF" >"$T/build1.out" 2>&1
use "$T/build-split"
track split --apply >/dev/null 2>&1
"$PY" -I "$S/build_app_folders.py" --env "$ENVF" >"$T/build2.out" 2>&1
check "build_app_folders: runs on both" sh -c 'grep -q "applications" "$1" && grep -q "applications" "$2"' _ "$T/build1.out" "$T/build2.out"
check "build_app_folders: every file is the same on the split tracker" sh -c 'diff -r "$1/job-applications" "$2/job-applications" && [ -f "$1/job-applications/not-applied/README.md" ]' _ "$T/build-flat" "$T/build-split"

# --- employer decisions on the older tracker -----------------------------------------------------------------------------
cp -R "$T/old" "$T/decide"
use "$T/decide"
employer decide "Acme Corp" exclude >/dev/null 2>&1
check "decide exclude: an allow becomes exclude in the older tracker" q "$H/apply/targets.json" companies.name=Acme\ Corp.verdict eq exclude
employer decide "Beta Ltd" allow israel >/dev/null 2>&1
check "decide allow on a category: an exclude stays" q "$H/apply/targets.json" companies.name=Beta\ Ltd.verdict eq exclude
employer decide "Gamma Inc" allow israel >/dev/null 2>&1
check "decide allow on a category: a discuss becomes allow" q "$H/apply/targets.json" companies.name=Gamma\ Inc.verdict eq allow
check "decide: the decision is recorded without a quote" q "$H/apply/employer-checks.json" employers.Gamma\ Inc.decisions.0.category eq israel

cp -R "$T/split-fresh" "$T/decide-split"
use "$T/decide-split"
cp "$H/apply/targets.json" "$T/before-decide.json"
employer decide "Epsilon Co" exclude >/dev/null 2>&1
check "decide on a split tracker: the verdict changes and the details stay linked" sh -c '
    "$1" -I "$2/q.py" "$3/apply/targets.json" "companies.name=Epsilon Co.verdict" eq exclude &&
    "$1" -I "$2/q.py" "$3/apply/targets.json" "companies.name=Acme Corp.details" eq details/companies/Acme-Corp.json &&
    [ -f "$3/apply/details/companies/Acme-Corp.json" ]' _ "$PY" "$T" "$H"

# --- import-tracker: no fact means unknown, never clear ---------------------------------------------------------------------
cp -R "$T/old" "$T/import"
use "$T/import"
employer import-tracker >/dev/null 2>&1
check "import-tracker: an employer with no fact gets unknown, never clear" sh -c '
    "$1" -I "$2/q.py" "$3/apply/employer-checks.json" "employers.Epsilon Co.checks.israel.status" eq unknown &&
    "$1" -I "$2/q.py" "$3/apply/employer-checks.json" "employers.Epsilon Co.checks.defence.status" eq unknown &&
    "$1" -I "$2/q.py" nostatus "$3/apply/employer-checks.json" "employers.Epsilon Co.checks" clear' _ "$PY" "$T" "$H"
check "import-tracker: a sourced hit becomes a flagged check" q "$H/apply/employer-checks.json" employers.Acme\ Corp.checks.defence.status eq flagged
cp -R "$T/split-fresh" "$T/import-split"
use "$T/import-split"
employer import-tracker >/dev/null 2>&1
check "import-tracker on a split tracker: reads the hits from the company's detail" q "$H/apply/employer-checks.json" employers.Acme\ Corp.checks.defence.status eq flagged

# --- repair-clear ------------------------------------------------------------------------------------------------------------
cp -R "$T/old" "$T/repair"
use "$T/repair"
cat >"$H/apply/employer-checks.json" <<'EOF'
{"employers": {"Delta Inc": {"checks": {"israel": {"status": "clear", "checked": "2026-11-01"},
                                         "defence": {"status": "clear", "fact": "annual report lists no arms", "source_url": "https://example.com/r"}}}}}
EOF
cp "$H/apply/employer-checks.json" "$T/checks-before.json"
employer repair-clear >"$T/repair1.out" 2>&1
check "repair-clear without --apply: counts the check and changes nothing" sh -c 'grep -q "1 employers; israel: 1" "$1" && cmp -s "$2" "$3/apply/employer-checks.json" && [ -z "$(ls "$3"/apply/*.before-repair-* 2>/dev/null)" ]' _ "$T/repair1.out" "$T/checks-before.json" "$H"
employer repair-clear --apply >"$T/repair2.out" 2>&1
check "repair-clear --apply: the clear without a fact becomes unknown" q "$H/apply/employer-checks.json" employers.Delta\ Inc.checks.israel.status eq unknown
check "repair-clear --apply: a sourced clear stays" q "$H/apply/employer-checks.json" employers.Delta\ Inc.checks.defence.status eq clear
check "repair-clear --apply: leaves a backup of the file as it was" sh -c 'cmp -s "$1" "$(ls "$2"/apply/employer-checks.json.before-repair-*.json | head -n 1)"' _ "$T/checks-before.json" "$H"

# --- employers: names, possible matches, alias, and the split into detail files -------------------------------------------
# mkemployers <dir>: a home with three made-up employers; "Examplia Internet GmbH" is excluded and has a history and a review.
mkemployers() {
    cp -R "$T/old" "$1"
    cat >"$1/apply/employer-checks.json" <<'EOF'
{"_about": "made up", "employers": {
 "Examplia Internet GmbH": {"checks": {
    "israel": {"status": "flagged", "level": "direct", "fact": "Examplia Internet supplies an army", "source_url": "https://example.com/n1",
               "checked": "2026-11-01", "history": [{"status": "clear", "fact": "nothing found", "checked": "2026-10-01", "until": "2026-11-01"}]},
    "defence": {"status": "clear", "fact": "annual report lists no arms", "source_url": "https://example.com/r", "checked": "2026-11-01"}},
  "verdict": "exclude", "verdict_date": "2026-11-01", "decisions": [{"date": "2026-11-02", "verdict": "exclude", "category": "israel"}],
  "environment": {"rating": 3.5, "scale": 5, "reviews": 40, "source_url": "https://example.com/rev", "checked": "2026-11-01"}},
 "A Co": {"checks": {}, "verdict": "allow", "verdict_date": "2026-11-01"},
 "Acme Corp": {"checks": {"climate": {"status": "clear", "fact": "no finding", "source_url": "https://example.com/a", "checked": "2026-11-01"}},
               "verdict": "allow", "verdict_date": "2026-11-01"}}}
EOF
}
check "keys: a name that would reduce below 2 characters keeps its legal form" q lookupkeys "A Co" "a co"
check "keys: legal forms are still dropped" q lookupkeys "Examplia Internet GmbH" "examplia internet"

mkemployers "$T/emp"
use "$T/emp"
employer check "A Co" >"$T/c-aco.json" 2>&1
check "check: a one-letter name matches itself exactly" sh -c '"$1" -I "$2/q.py" "$3" 0.match eq exact && "$1" -I "$2/q.py" "$3" 0.verdict eq allow' _ "$PY" "$T" "$T/c-aco.json"
employer check "Examplia" >"$T/c-examplia.json" 2>&1
check "check: a short name is a possible match of the saved full name, and never an allow" sh -c '
    "$1" -I "$2/q.py" "$3" 0.match eq possible && "$1" -I "$2/q.py" "$3" 0.verdict eq discuss &&
    "$1" -I "$2/q.py" "$3" "0.possible.0.name" eq "Examplia Internet GmbH" && "$1" -I "$2/q.py" "$3" "0.possible.0.verdict" eq exclude &&
    "$1" -I "$2/q.py" "$3" 0.reasons.0 eq "possible match: Examplia Internet GmbH (exclude)"' _ "$PY" "$T" "$T/c-examplia.json"
employer check "Zeta Works" >"$T/c-zeta.json" 2>&1
check "check: an unrelated name has match none and verdict allow" sh -c '"$1" -I "$2/q.py" "$3" 0.match eq none && "$1" -I "$2/q.py" "$3" 0.verdict eq allow && "$1" -I "$2/q.py" "$3" 0.possible len 0' _ "$PY" "$T" "$T/c-zeta.json"

cp -R "$T/emp" "$T/emp-alias"
use "$T/emp-alias"
employer alias "Examplia Internet GmbH" "Examplia" >/dev/null 2>&1
employer check "Examplia" >"$T/c-examplia2.json" 2>&1
check "alias: the short name is then an exact match and excluded" sh -c '"$1" -I "$2/q.py" "$3" 0.match eq exact && "$1" -I "$2/q.py" "$3" 0.verdict eq exclude && "$1" -I "$2/q.py" "$3" 0.matched eq "Examplia Internet GmbH"' _ "$PY" "$T" "$T/c-examplia2.json"
check "alias: names.json maps the new key to the saved entry" q "$H/apply/employers/names.json" names.examplia eq "Examplia Internet GmbH"
cp "$H/apply/employers/names.json" "$T/names-before.json"
check "alias: a key that points to another employer is refused and nothing changes" sh -c '
    ! "$1" -I "$2/employer.py" alias "A Co" "Examplia" --env "$3" >"$4" 2>&1 && grep -q "already points to" "$4" && cmp -s "$5" "$6/apply/employers/names.json"' \
    _ "$PY" "$S" "$ENVF" "$T/alias-refused.out" "$T/names-before.json" "$H"

cp -R "$T/emp" "$T/emp-not"
use "$T/emp-not"
employer alias --not "Examplia" "Examplia Internet GmbH" >/dev/null 2>&1
employer check "Examplia" >"$T/c-examplia3.json" 2>&1
check "alias --not: the pair is never offered again" sh -c '"$1" -I "$2/q.py" "$3" 0.match eq none && "$1" -I "$2/q.py" "$3" 0.verdict eq allow' _ "$PY" "$T" "$T/c-examplia3.json"

cp -R "$T/emp" "$T/emp-split"
use "$T/emp-split"
employer check "Examplia Internet GmbH" "Acme Corp" "A Co" >"$T/before-split.json" 2>&1
cp "$H/apply/employer-checks.json" "$T/emp-original.json"
employer split >"$T/esplit-dry.out" 2>&1
check "employer split dry run: prints counts and bytes" grep -q "bytes" "$T/esplit-dry.out"
check "employer split dry run: changes nothing" sh -c 'cmp -s "$1" "$2/apply/employer-checks.json" && [ ! -d "$2/apply/employers" ] && [ -z "$(ls "$2"/apply/*.before-split-* 2>/dev/null)" ]' _ "$T/emp-original.json" "$H"
check "employer split --apply: exits 0" employer split --apply
check "employer split --apply: a backup of the file as it was, and names.json" sh -c '
    cmp -s "$1" "$(ls "$2"/apply/employer-checks.json.before-split-*.json | head -n 1)" && [ -f "$2/apply/employers/names.json" ]' _ "$T/emp-original.json" "$H"
check "employer split --apply: one folder per employer with something to hold, a file per scope" sh -c '
    d="$1/apply/employers/Examplia-Internet-GmbH"; [ -f "$d/checks.json" ] && [ -f "$d/history.json" ] && [ -f "$d/environment.json" ] &&
    [ -f "$1/apply/employers/Acme-Corp/checks.json" ] && [ ! -f "$1/apply/employers/Acme-Corp/history.json" ] && [ ! -d "$1/apply/employers/A-Co" ]' _ "$H"
check "employer split --apply: the summary holds status and links, no facts" sh -c '
    f="$2/apply/employer-checks.json"; "$1" -I "$3/q.py" "$f" "employers.Examplia Internet GmbH.status.israel" eq "flagged direct" &&
    "$1" -I "$3/q.py" "$f" "employers.Examplia Internet GmbH.status.defence" eq clear &&
    "$1" -I "$3/q.py" "$f" "employers.Examplia Internet GmbH.details.checks" eq employers/Examplia-Internet-GmbH/checks.json &&
    "$1" -I "$3/q.py" "$f" "employers.Examplia Internet GmbH.checks" absent && "$1" -I "$3/q.py" "$f" "employers.Examplia Internet GmbH.environment" absent &&
    "$1" -I "$3/q.py" "$f" "employers.A Co.details" absent && "$1" -I "$3/q.py" "$f" "employers.Examplia Internet GmbH.decisions.0.category" eq israel &&
    ! grep -q "supplies an army" "$f"' _ "$PY" "$H" "$T"
check "employer split --apply: checks.json holds no history, history.json holds it" sh -c '
    d="$2/apply/employers/Examplia-Internet-GmbH"; "$1" -I "$3/q.py" "$d/checks.json" israel.history absent &&
    "$1" -I "$3/q.py" "$d/history.json" israel.0.until eq 2026-11-01' _ "$PY" "$H" "$T"
cp "$H/apply/employer-checks.json" "$T/emp-split1.json"
employer split --apply >"$T/esplit-twice.out" 2>&1
check "employer split twice: says there is nothing to split, changes nothing, no second backup" sh -c '
    grep -q "nothing to split" "$1" && cmp -s "$2" "$3/apply/employer-checks.json" && [ "$(ls "$3"/apply/employer-checks.json.before-split-* | wc -l)" -eq 1 ]' _ "$T/esplit-twice.out" "$T/emp-split1.json" "$H"
employer check "Examplia Internet GmbH" "Acme Corp" "A Co" >"$T/after-split.json" 2>&1
check "check after the split: the same verdict, facts and match as before" cmp -s "$T/before-split.json" "$T/after-split.json"
mv "$H/apply/employers/Examplia-Internet-GmbH/history.json" "$T/history.hidden"
employer check "Examplia Internet GmbH" >"$T/after-nohist.json" 2>&1
check "check after the split: works with history.json removed, and never opens it" sh -c '"$1" -I "$2/q.py" "$3" 0.verdict eq exclude && "$1" -I "$2/q.py" "$3" 0.checks.israel.fact eq "Examplia Internet supplies an army"' _ "$PY" "$T" "$T/after-nohist.json"
mv "$T/history.hidden" "$H/apply/employers/Examplia-Internet-GmbH/history.json"
employer check "Examplia Internet GmbH" --full >"$T/after-full.json" 2>&1
check "check --full: adds the environment and the history" sh -c '"$1" -I "$2/q.py" "$3" 0.environment.reviews eq 40 && "$1" -I "$2/q.py" "$3" 0.checks.israel.history.0.until eq 2026-11-01' _ "$PY" "$T" "$T/after-full.json"
check "check: without --full no environment and no history" sh -c '"$1" -I "$2/q.py" "$3" 0.environment absent && "$1" -I "$2/q.py" "$3" 0.checks.israel.history absent && "$1" -I "$2/q.py" "$3" 0.has_environment eq True' _ "$PY" "$T" "$T/after-split.json"

employer record "Examplia Internet GmbH" defence flagged level=direct fact="Examplia Internet also builds drones" source=https://example.com/n2 >/dev/null 2>&1
check "record on a split file: the check goes into checks.json and the status into the summary" sh -c '
    d="$2/apply/employers/Examplia-Internet-GmbH"; "$1" -I "$3/q.py" "$d/checks.json" defence.status eq flagged &&
    "$1" -I "$3/q.py" "$d/checks.json" defence.fact eq "Examplia Internet also builds drones" &&
    "$1" -I "$3/q.py" "$2/apply/employer-checks.json" "employers.Examplia Internet GmbH.status.defence" eq "flagged direct" &&
    "$1" -I "$3/q.py" "$2/apply/employer-checks.json" "employers.Examplia Internet GmbH.checks" absent' _ "$PY" "$H" "$T"
check "record on a split file: the replaced check goes into history.json" q "$H/apply/employers/Examplia-Internet-GmbH/history.json" defence.0.status eq clear
employer record "Orion Ltd" israel clear fact="no tie found" source=https://example.com/o >/dev/null 2>&1
check "record on a split file: a new employer gets its folder and its keys in names.json" sh -c '
    [ -f "$2/apply/employers/Orion-Ltd/checks.json" ] && "$1" -I "$3/q.py" "$2/apply/employers/names.json" names.orion eq "Orion Ltd"' _ "$PY" "$H" "$T"

cp -R "$T/emp" "$T/emp-inline"
use "$T/emp-inline"
employer record "Acme Corp" defence clear fact="no arms" source=https://example.com/b >/dev/null 2>&1
check "an unsplit file still works: record keeps the checks inline and makes no folder" sh -c '
    "$1" -I "$3/q.py" "$2/apply/employer-checks.json" "employers.Acme Corp.checks.defence.status" eq clear &&
    "$1" -I "$3/q.py" "$2/apply/employer-checks.json" "employers.Acme Corp.details" absent && [ ! -d "$2/apply/employers" ]' _ "$PY" "$H" "$T"

cp -R "$T/emp-split" "$T/emp-bad"
use "$T/emp-bad"
echo '{"israel": {"status": "clear", "fact": "OUTSIDE-FILE-READ"}}' >"$H/apply/outside.json"
sed 's#"checks": "employers/Examplia-Internet-GmbH/checks.json"#"checks": "../outside.json"#' "$H/apply/employer-checks.json" >"$H/apply/edited.json" && mv "$H/apply/edited.json" "$H/apply/employer-checks.json"
check "a details path outside employers/ is refused, and the file is never read" sh -c '
    ! "$1" -I "$2/employer.py" check "Examplia Internet GmbH" --env "$3" >"$4" 2>&1 && grep -q "not an employer detail file path" "$4" && ! grep -q OUTSIDE-FILE-READ "$4"' _ "$PY" "$S" "$ENVF" "$T/bad.out"
echo '{"israel": {"status": "clear", "fact": "OUTSIDE-FILE-READ"}}' >"$H/apply/checks.json"
sed 's#"checks": "../outside.json"#"checks": "employers/../checks.json"#' "$H/apply/employer-checks.json" >"$H/apply/edited.json" && mv "$H/apply/edited.json" "$H/apply/employer-checks.json"
check "a details path through a '..' folder is refused too" sh -c '! "$1" -I "$2/employer.py" check "Examplia Internet GmbH" --env "$3" >"$4" 2>&1 && ! grep -q OUTSIDE-FILE-READ "$4"' _ "$PY" "$S" "$ENVF" "$T/bad2.out"

cp -R "$T/emp-split" "$T/emp-partial"
use "$T/emp-partial"
"$PY" -I -c 'import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
d["employers"]["Zephyr Ltd"] = {"checks": {"israel": {"status": "clear", "fact": "no tie", "source_url": "https://example.com/z", "checked": "2026-11-01"}}, "verdict": "allow"}
json.dump(d, open(p, "w", encoding="utf-8"))' "$H/apply/employer-checks.json"
check "employer split on a partly split file: exits 0, moves the new entry, keeps the old one" sh -c '
    "$1" -I "$2/employer.py" split --apply --env "$3" >/dev/null 2>&1 && [ -f "$4/apply/employers/Zephyr-Ltd/checks.json" ] &&
    "$1" -I "$5/q.py" "$4/apply/employer-checks.json" "employers.Examplia Internet GmbH.details.checks" eq employers/Examplia-Internet-GmbH/checks.json &&
    "$1" -I "$5/q.py" "$4/apply/employer-checks.json" "employers.Zephyr Ltd.checks" absent' _ "$PY" "$S" "$ENVF" "$H" "$T"

use "$T/emp"
check "alias with a bracketed name writes only the whole-name keys" sh -c '
    "$1" -I "$2/employer.py" alias "Acme Corp" "Acme Mobile (Examplia)" --env "$3" >/dev/null 2>&1 &&
    "$1" -I "$4/q.py" "$5/apply/employers/names.json" "names.acme mobile" eq "Acme Corp" && "$1" -I "$4/q.py" "$5/apply/employers/names.json" names.examplia absent' _ "$PY" "$S" "$ENVF" "$T" "$H"
employer check "Examplia" >"$T/c-ex-after.json" 2>&1
check "alias with a bracketed name: the bracket part is still only a possible match of the other employer" q "$T/c-ex-after.json" 0.match eq possible
use "$T/emp-alias"
rm -f "$H/apply/employers/names.json"
check "alias refuses a key that is a possible match of another employer, and writes nothing" sh -c '
    ! "$1" -I "$2/employer.py" alias "Acme Corp" "Examplia" --env "$3" >"$4" 2>&1 && grep -q "settle .Examplia Internet GmbH. first" "$4" && [ ! -e "$5/apply/employers/names.json" ]' _ "$PY" "$S" "$ENVF" "$T/alias-near.out" "$H"

cp -R "$T/emp-split" "$T/emp-names"
use "$T/emp-names"
L=Examplia-Worldwide-Consulting-And-Software-Development-Services-Europe
employer record "$L Alpha" israel clear fact="no tie" source=https://example.com/l1 >/dev/null 2>&1
employer record "$L Beta" israel clear fact="no tie" source=https://example.com/l2 >/dev/null 2>&1
employer record "NUL" israel clear fact="no tie" source=https://example.com/n >/dev/null 2>&1
check "two long names that differ only after the cut get two folders" sh -c '[ "$(ls "$1/apply/employers" | grep -c "^Examplia-Worldwide")" -eq 2 ]' _ "$H"
check "a reserved Windows name gets a writable folder" sh -c '[ -f "$1/apply/employers/NUL-x/checks.json" ]' _ "$H"
check "no folder name ends in a dot" sh -c '[ -z "$(ls "$1/apply/employers" | grep "[.]$")" ]' _ "$H"

# --- employer levels: the plugin's levels, the second check against the person's own rules, running applications ------------
cp -R "$T/old" "$T/lv"
use "$T/lv"
echo "EMPLOYER_RULES=apply/employer-rules.json" >>"$H/job-search.env"
cat >"$H/apply/employer-rules.json" <<'EOF'
{"categories": {"defence": {"what": "OLD WHAT", "action": "exclude", "indirect": "warn",
                            "notes": "a defence product sold with no customer named counts as sold to armed forces"},
                "israel": {"label": "Ties to Israel", "what": "OLD WHAT", "action": "discuss", "indirect": "allow"}},
 "changes": []}
EOF
cat >"$H/apply/employer-checks.json" <<'EOF'
{"employers": {
 "Acme Corp": {"checks": {"defence": {"status": "flagged", "level": "indirect", "fact": "Acme sells its planning tool to an army",
                                      "source_url": "https://example.com/d1", "checked": "2026-11-01"}},
               "verdict": "allow", "verdict_date": "2026-11-01"},
 "Delta Inc": {"checks": {"defence": {"status": "flagged", "level": "direct", "fact": "Delta builds drones",
                                      "source_url": "https://example.com/d2", "checked": "2026-11-01"}},
               "verdict": "allow", "verdict_date": "2026-11-01"}}}
EOF
cat >"$H/apply/targets.json" <<'EOF'
{"jobs": [{"id": "R1", "company": "Acme Corp", "title": "Engineer", "url": "https://example.com/r1", "status": "submitted"},
          {"id": "R2", "company": "Delta Inc", "title": "Analyst", "url": "https://example.com/r2", "status": "submitted"}]}
EOF
echo '{"R2": {"stage": "rejected", "date": "2026-11-05"}}' >"$H/apply/pipeline.json"
# setrule <field> <value>: the person changes one field of their defence category
setrule() {
    "$PY" -I -c 'import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
d["categories"]["defence"][sys.argv[2]] = sys.argv[3]
json.dump(d, open(p, "w", encoding="utf-8"))' "$H/apply/employer-rules.json" "$1" "$2"
}
employer rules >"$T/lv-rules.json" 2>&1
check "rules: a shared category's what and levels are the plugin's, not the person's copy" sh -c '
    "$1" -I "$2/q.py" "$3" categories.defence.what ne "OLD WHAT" && "$1" -I "$2/q.py" "$3" categories.defence.levels.none present' _ "$PY" "$T" "$T/lv-rules.json"
check "rules: israel is a state category with the state levels" sh -c '
    "$1" -I "$2/q.py" "$3" categories.israel.state eq Israel && "$1" -I "$2/q.py" "$3" categories.israel.levels.none present &&
    "$1" -I "$2/q.py" "$3" categories.israel.what ne "OLD WHAT" && "$1" -I "$2/q.py" "$3" categories.israel.label eq "Ties to Israel"' _ "$PY" "$T" "$T/lv-rules.json"
check "rules: the person's actions and notes stay theirs" sh -c '
    "$1" -I "$2/q.py" "$3" categories.defence.action eq exclude && "$1" -I "$2/q.py" "$3" categories.defence.notes present' _ "$PY" "$T" "$T/lv-rules.json"
employer check "Acme Corp" >"$T/lv-c1.json" 2>&1
check "check: a finding in a category with notes has its second check due" q "$T/lv-c1.json" 0.recheck.0 eq defence
check "check: while a second check is due, an indirect tie set to warn is discuss, never allow" q "$T/lv-c1.json" 0.verdict eq discuss
employer own "Acme Corp" defence direct why="unnamed defence customers count as armed forces" >/dev/null 2>&1
F="$H/apply/employer-checks.json"
check "own: the level for the person sits beside the finding, which stays as found" sh -c '
    "$1" -I "$2/q.py" "$3" "employers.Acme Corp.checks.defence.own_level" eq direct &&
    "$1" -I "$2/q.py" "$3" "employers.Acme Corp.checks.defence.level" eq indirect' _ "$PY" "$T" "$F"
employer check "Acme Corp" >"$T/lv-c2.json" 2>&1
check "own: the verdict uses the person's level (direct, set to exclude), and nothing is due" sh -c '
    "$1" -I "$2/q.py" "$3" 0.verdict eq exclude && "$1" -I "$2/q.py" "$3" 0.recheck len 0' _ "$PY" "$T" "$T/lv-c2.json"
employer record "Acme Corp" defence flagged level=indirect fact="Acme sells its planning tool to an army" source=https://example.com/d1 >/dev/null 2>&1
check "record: the same finding again keeps its second check" q "$F" "employers.Acme Corp.checks.defence.own_level" eq direct
employer record "Acme Corp" defence flagged level=indirect fact="Acme sells a planning tool to two armies" source=https://example.com/d3 >/dev/null 2>&1
check "record: a new finding drops the old second check, so it is due again" sh -c '
    "$1" -I "$2/q.py" "$3" "employers.Acme Corp.checks.defence.own_level" absent &&
    "$1" -I "$2/q.py" "$3" "employers.Acme Corp.checks.defence.history.0.own_level" eq direct' _ "$PY" "$T" "$F"
employer own "Acme Corp" defence none why="a general product" >/dev/null 2>&1
employer check "Acme Corp" >"$T/lv-c3.json" 2>&1
check "own none: the finding is not counted for the person" sh -c '
    "$1" -I "$2/q.py" "$3" 0.verdict eq allow && grep -q "not counted" "$3"' _ "$PY" "$T" "$T/lv-c3.json"
check "own: the second check keeps the fingerprint of the notes it judged against" q "$F" "employers.Acme Corp.checks.defence.own_rules" len 12
setrule indirect allow
setrule notes "a defence product  sold with no customer named counts as sold to armed forces"
employer check "Acme Corp" >"$T/lv-c4.json" 2>&1
check "a change to a category's indirect setting, or to the spaces in its notes, leaves its second check as it is" q "$T/lv-c4.json" 0.recheck len 0
setrule notes "a defence product sold with no customer named counts as sold to its armed forces"
employer check "Acme Corp" >"$T/lv-c5.json" 2>&1
check "a change to a category's notes makes its second check due again" q "$T/lv-c5.json" 0.recheck.0 eq defence
employer recheck-running >"$T/lv-r1.json" 2>&1
check "recheck-running: lists a running application whose second check is due; an ended one never" sh -c '
    "$1" -I "$2/q.py" "$3" 0.employer eq "Acme Corp" && "$1" -I "$2/q.py" "$3" 0.recheck.0 eq defence &&
    "$1" -I "$2/q.py" "$3" "" len 1' _ "$PY" "$T" "$T/lv-r1.json"
check "recheck-running: while the second check is due the saved verdict is discuss" q "$F" "employers.Acme Corp.verdict" eq discuss
employer own "Acme Corp" defence direct why="unnamed defence customers count as armed forces" >/dev/null 2>&1
employer recheck-running >"$T/lv-r2.json" 2>&1
check "recheck-running: a verdict that moved to exclude is listed with its running job" sh -c '
    "$1" -I "$2/q.py" "$3" 0.now eq exclude && "$1" -I "$2/q.py" "$3" 0.saved eq discuss && "$1" -I "$2/q.py" "$3" 0.jobs.0.id eq R1' _ "$PY" "$T" "$T/lv-r2.json"
check "recheck-running: the moved verdict is saved" q "$F" "employers.Acme Corp.verdict" eq exclude
employer recheck-running >"$T/lv-r3.out" 2>&1
check "recheck-running: the next run lists it only when it moves again" grep -q "nothing moved" "$T/lv-r3.out"
"$PY" -I "$S/usage.py" report --out "$T/lv-report.json" --env "$ENVF" >/dev/null 2>&1
"$PY" -I "$S/employer.py" merge --from-checks --into "$T/lv-blacklist.json" --env "$ENVF" >/dev/null 2>&1
check "the second check never leaves the person's files: not in the usage report, not in a merge" sh -c '
    [ -s "$1" ] && [ -s "$2" ] && grep -q "Acme sells" "$1" && grep -q "Acme sells" "$2" && ! grep -q "own_" "$1" && ! grep -q "own_" "$2"' _ "$T/lv-report.json" "$T/lv-blacklist.json"
cp -R "$T/old" "$T/lv-sync"
use "$T/lv-sync"
echo "EMPLOYER_RULES=apply/employer-rules.json" >>"$H/job-search.env"
cp "$T/lv/apply/employer-rules.json" "$H/apply/employer-rules.json"
cat >"$H/apply/employer-checks.json" <<'EOF'
{"employers": {"Epsilon Co": {"checks": {"defence": {"status": "flagged", "level": "indirect", "fact": "Epsilon sells software to an army",
                                                     "source_url": "https://example.com/e9", "checked": "2026-11-01"}},
                              "verdict": "discuss", "verdict_date": "2026-11-01"}}}
EOF
cat >"$T/lv-journal.jsonl" <<'EOF'
{"type": "started", "agentId": "b1", "label": "excl-screen:Acme Corp"}
{"type": "result", "agentId": "b1", "result": {"verdict": "allow", "hits": [], "ties": [], "notes": "", "checks": [{"category": "defence", "status": "flagged", "level": "indirect", "fact": "Acme sells its planning tool to an army", "source_url": "https://example.com/d1"}, {"category": "climate", "status": "flagged", "level": "direct", "fact": "Acme was fined for dumping waste", "source_url": "https://example.com/c1"}]}}
{"type": "started", "agentId": "b2", "label": "excl-own:Acme Corp"}
{"type": "result", "agentId": "b2", "result": {"checks": [{"category": "defence", "own_level": "direct", "why": "unnamed defence customers count as armed forces"}, {"category": "climate", "own_level": "none", "why": "not due: climate has no notes"}], "notes": ""}}
{"type": "started", "agentId": "b3", "label": "excl-own:Epsilon Co"}
{"type": "result", "agentId": "b3", "result": {"checks": [{"category": "defence", "own_level": "none", "why": "a general product"}], "notes": ""}}
{"type": "started", "agentId": "b4", "label": "excl-screen:Gamma Inc"}
{"type": "result", "agentId": "b4", "result": {"verdict": "allow", "hits": [], "ties": [], "notes": "", "checks": [{"category": "defence", "status": "flagged", "level": "indirect", "fact": "Gamma sells software to an army", "source_url": "https://example.com/g1"}]}}
EOF
track sync "$T/lv-journal.jsonl" >"$T/lv-sync.out" 2>&1
check "sync: the second check's level is recorded beside the finding and decides the verdict" sh -c '
    "$1" -I "$2/q.py" "$3/apply/employer-checks.json" "employers.Acme Corp.checks.defence.own_level" eq direct &&
    "$1" -I "$2/q.py" "$3/apply/employer-checks.json" "employers.Acme Corp.checks.defence.level" eq indirect &&
    "$1" -I "$2/q.py" "$3/apply/targets.json" "companies.name=Acme Corp.verdict" eq exclude' _ "$PY" "$T" "$H"
check "sync: a known employer's second check alone is recorded, and its verdict follows it" sh -c '
    "$1" -I "$2/q.py" "$3/apply/employer-checks.json" "employers.Epsilon Co.checks.defence.own_level" eq none &&
    "$1" -I "$2/q.py" "$3/apply/targets.json" "companies.name=Epsilon Co.verdict" eq allow' _ "$PY" "$T" "$H"
check "sync: a second-check result for a category with no notes of the person's is ignored" sh -c '
    "$1" -I "$2/q.py" "$3/apply/employer-checks.json" "employers.Acme Corp.checks.climate.status" eq flagged &&
    "$1" -I "$2/q.py" "$3/apply/employer-checks.json" "employers.Acme Corp.checks.climate.own_level" absent' _ "$PY" "$T" "$H"
check "sync: a finding whose second check did not run is discuss, never allow" sh -c '
    "$1" -I "$2/q.py" "$3/apply/targets.json" "companies.name=Gamma Inc.verdict" eq discuss &&
    "$1" -I "$2/q.py" "$3/apply/employer-checks.json" "employers.Gamma Inc.verdict" eq discuss' _ "$PY" "$T" "$H"
check "withdrawal template: a version with the reason and one without it" sh -c '
    grep -q "^With the reason:" "$1" && grep -q "^Without the reason" "$1"' _ "$S/../templates/withdrawal-email.txt"

# --- searches ------------------------------------------------------------------------------------------------------------------
use "$T/flat"
searches add LinkedIn "Java lead, remote" alert=yes gmail="from:alerts@example.com newer_than:2d" >"$T/s1.out" 2>&1
searches add "Acme careers" "engineering" alert=no every=7 >"$T/s2.out" 2>&1
check "searches add: two rows with their ids" sh -c 'grep -q "^1 LinkedIn" "$1" && grep -q "^2 Acme careers" "$2"' _ "$T/s1.out" "$T/s2.out"
searches due >"$T/due1.out" 2>&1
check "searches due: both are due before they were read" sh -c '[ "$(wc -l <"$1")" -eq 2 ]' _ "$T/due1.out"
searches done 1 found=3 >/dev/null 2>&1
searches due >"$T/due2.out" 2>&1
check "searches done: the search read today is no longer due" sh -c '[ "$(wc -l <"$1")" -eq 1 ] && grep -q "Acme careers" "$1"' _ "$T/due2.out"
searches seen "https://www.linkedin.com/jobs/view/1234567890/?trackingId=other&refId=zzz" "https://example.com/new-job" >"$T/seen.out" 2>&1
check "searches seen: a LinkedIn link with other tracking parameters is known" grep -q "^known https://www.linkedin.com" "$T/seen.out"
check "searches seen: a link nobody saw is new" grep -q "^new https://example.com/new-job" "$T/seen.out"

# --- check_setup --needs ---------------------------------------------------------------------------------------------------------
"$PY" -I "$S/check_setup.py" --needs --env "$ENVF" >"$T/needs.out" 2>&1
check "check_setup --needs: names the jobs that wait on the person" grep -q "1 job(s) wait: needs-person" "$T/needs.out"
"$PY" -I "$S/check_setup.py" --needs --env "$T/split-fresh/job-search.env" >"$T/needs2.out" 2>&1
check "check_setup --needs: works on a split tracker" sh -c '! grep -q "Traceback" "$1"' _ "$T/needs2.out"

# --- career_view ---------------------------------------------------------------------------------------------------------------------
"$PY" -I "$S/career_view.py" screen --env "$ENVF" >"$T/screen.json" 2>&1
"$PY" -I "$S/career_view.py" facts --env "$ENVF" >"$T/facts.json" 2>&1
check "career_view screen: only the employer rules and the decisions" q keys "$T/screen.json" _about,preferences,decisions
check "career_view screen: only the employer rules from the preferences" q "$T/screen.json" preferences.locations absent
check "career_view facts: the facts a letter may use, not the rest" sh -c '
    "$1" -I "$2/q.py" keys "$3" _about,profile,skills,languages,preferences,form_answers,cv_rules,never_claim &&
    "$1" -I "$2/q.py" "$3" preferences.locations.0 eq Rome && "$1" -I "$2/q.py" "$3" preferences.employer_rules absent &&
    "$1" -I "$2/q.py" "$3" private_extra absent' _ "$PY" "$T" "$T/facts.json"

# --- review fixes ----------------------------------------------------------------------------------------------------
track add J9 "Acme Corp" "Engineer" "https://boards.example.com/acme/jobs?gh_jid=111" >/dev/null 2>&1
printf '%s
' "https://boards.example.com/acme/jobs?gh_jid=222" "https://boards.example.com/acme/jobs?gh_jid=111&utm_source=mail" >"$T/links.txt"
searches seen --file "$T/links.txt" >"$T/seen2.out" 2>&1
check "searches seen --file: a job id in the query keeps two jobs apart; a tracking parameter does not" sh -c     'grep -q "^new .*gh_jid=222" "$1" && grep -q "^known .*gh_jid=111&utm_source=mail" "$1"' _ "$T/seen2.out"
check "a hand-set details path outside details/ is refused, and no file is written there" sh -c     '! "$1" -I "$2/track.py" set J1 submitted "x" details=../outside.json --env "$3" >/dev/null 2>&1 && [ ! -e "$4/outside.json" ]'     _ "$PY" "$S" "$ENVF" "$H"

echo "$PASSED passed, $FAILED failed"
[ "$FAILED" -eq 0 ]
