#!/bin/sh
# Tests for the cenk-jobs scripts, on a made-up job search in a throwaway folder: one PASS or FAIL line per check.
# Why: the tracker's split into summary rows and detail files, the employer decisions and the small scripts must keep
# working on both tracker shapes, and no check may ever touch a real record.
# Usage: sh tests/run.sh          (PYTHON=<python> sh tests/run.sh to pick the interpreter)
# Exit 0: every check passed. 1: at least one failed. 2: the tests could not start.
# Safety: every script runs with --env <throwaway folder>/<home>/job-search.env and JOB_SEARCH_ENV points there too,
# from a working folder inside the throwaway folder, so no real job-search.env can be found. Every env names its own
# PROFILE inside the throwaway folder and the Claude config folder is a throwaway one, so no real profile is read or
# written; use() stops the tests when a profile path points anywhere else. The folder is removed on exit.
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
CLAUDE_CONFIG_DIR="$T/claude-config"
export CLAUDE_CONFIG_DIR
unset CLAUDE_PLUGIN_OPTION_PROFILE_PATH

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
PROFILE=profile/profile.json
TRACKER=apply/targets.json
PIPELINE=apply/pipeline.json
LOGINS=apply/logins.json
QUESTIONS=apply/questions.json
SEARCHES=apply/searches.json
EMPLOYER_CHECKS=apply/employer-checks.json
EOF
    echo '{}' >"$h/apply/pipeline.json"
    mkdir -p "$h/profile"
    cat >"$h/profile/profile.json" <<EOF
{"person": {"name": "Jane Doe", "email": "jane@example.com", "phone": "+39 06 0000 0000", "birth_date": "1990-01-02",
            "address": "1 Example Street, Rome", "languages": [{"language": "English", "level": "native"}]},
 "private": {"diet": {"answer": "vegetarian", "words": "veggie", "date": "2026-11-01", "source": "chat"}},
 "contacts": {"referee-sam": {"name": "Sam Example", "role": "manager", "email": "sam@example.com",
                              "agreed_on": "2026-11-01", "source": "chat"}}}
EOF
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

# Every script gets its env file explicitly; JOB_SEARCH_ENV is only the second line of defence. A home whose profile
# lies outside the throwaway folder stops the tests before any script reads or writes it.
use() {
    H=$1; ENVF="$H/job-search.env"; JOB_SEARCH_ENV=$ENVF; export JOB_SEARCH_ENV
    where=$("$PY" -I "$S/profilelib.py" --env "$ENVF" path | tr '\\' '/')
    case "$where" in
        "$T"/*) ;;
        *) echo "stopped: the profile of $H is not inside the throwaway folder ($where)" >&2; exit 2 ;;
    esac
}
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
check "recheck-running: the discuss of a due second check is never saved" q "$F" "employers.Acme Corp.verdict" eq allow
setrule indirect discuss
employer own "Acme Corp" defence indirect why="sales to an army, no defence line" >/dev/null 2>&1
employer recheck-running >"$T/lv-r2.json" 2>&1
check "recheck-running: after the second check, a verdict at discuss for a real reason is listed" sh -c '
    "$1" -I "$2/q.py" "$3" 0.now eq discuss && "$1" -I "$2/q.py" "$3" 0.saved eq allow && "$1" -I "$2/q.py" "$3" 0.recheck len 0' _ "$PY" "$T" "$T/lv-r2.json"
employer own "Acme Corp" defence direct why="unnamed defence customers count as armed forces" >/dev/null 2>&1
employer recheck-running >"$T/lv-r3.json" 2>&1
check "recheck-running: a verdict that moved to exclude is listed with its running job" sh -c '
    "$1" -I "$2/q.py" "$3" 0.now eq exclude && "$1" -I "$2/q.py" "$3" 0.saved eq discuss && "$1" -I "$2/q.py" "$3" 0.jobs.0.id eq R1' _ "$PY" "$T" "$T/lv-r3.json"
check "recheck-running: the moved verdict is saved" q "$F" "employers.Acme Corp.verdict" eq exclude
employer recheck-running >"$T/lv-r4.out" 2>&1
check "recheck-running: the next run lists it only when it moves again" grep -q "nothing moved" "$T/lv-r4.out"
"$PY" -I "$S/usage.py" report --out "$T/lv-report.json" --env "$ENVF" >/dev/null 2>&1
"$PY" -I "$S/employer.py" merge --from-checks --into "$T/lv-blacklist.json" --env "$ENVF" >/dev/null 2>&1
check "the second check never leaves the person's files: not in the usage report, not in a merge" sh -c '
    [ -s "$1" ] && [ -s "$2" ] && grep -q "Acme sells" "$1" && grep -q "Acme sells" "$2" && ! grep -q "own_" "$1" && ! grep -q "own_" "$2"' _ "$T/lv-report.json" "$T/lv-blacklist.json"
cp -R "$T/old" "$T/lv-sync"
use "$T/lv-sync"
echo "EMPLOYER_RULES=apply/employer-rules.json" >>"$H/job-search.env"
cat >"$H/apply/employer-rules.json" <<'EOF'
{"categories": {"defence": {"action": "exclude", "indirect": "warn",
                            "notes": "a defence product sold with no customer named counts as sold to armed forces"}},
 "changes": []}
EOF
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
check "sync: a finding whose second check did not run holds its jobs at discuss; the records keep the verdict from the findings" sh -c '
    "$1" -I "$2/q.py" "$3/apply/targets.json" "companies.name=Gamma Inc.verdict" eq discuss &&
    "$1" -I "$2/q.py" "$3/apply/employer-checks.json" "employers.Gamma Inc.verdict" eq allow' _ "$PY" "$T" "$H"
check "withdrawal template: a version with the reason and one without it" sh -c '
    grep -q "^With the reason:" "$1" && grep -q "^Without the reason" "$1"' _ "$S/../templates/withdrawal-email.txt"

# --- shared list updates: the copy last taken in, employers with the person's opinion asked, the rest updated ----------
cp -R "$T/old" "$T/su-first"
use "$T/su-first"
echo '{"employers": {"Acme Corp": {"checks": {}, "verdict": "allow"}}}' >"$H/apply/employer-checks.json"
cp "$H/apply/employer-checks.json" "$T/su-first-before.json"
employer shared-update --apply >"$T/su-first.out" 2>&1
check "shared-update the first time: saves the copy only" sh -c '
    grep -q "first time" "$1" && [ -s "$2/apply/employers/shared-seen.json" ] && cmp -s "$3" "$2/apply/employer-checks.json"' _ "$T/su-first.out" "$H" "$T/su-first-before.json"
cp -R "$T/old" "$T/su"
use "$T/su"
mkdir -p "$H/apply/employers"
cat >"$H/apply/employer-checks.json" <<'EOF'
{"employers": {
 "Acme Corp": {"checks": {"defence": {"status": "clear", "fact": "no arms", "source_url": "https://example.com/s1", "checked": "2026-11-01"}}, "verdict": "allow"},
 "Delta Inc": {"checks": {"defence": {"status": "flagged", "level": "indirect", "fact": "Delta sells to an army", "source_url": "https://example.com/s3", "checked": "2026-11-01"}},
               "verdict": "allow", "decisions": [{"date": "2026-11-10", "verdict": "allow", "category": "defence"}]},
 "Omega Ltd": {"checks": {"climate": {"status": "flagged", "level": "direct", "fact": "Omega was fined for dumping", "source_url": "https://example.com/s5", "checked": "2026-11-01"}}, "verdict": "discuss"},
 "Sigma Co": {"checks": {"climate": {"status": "clear", "fact": "no finding", "source_url": "https://example.com/s6", "checked": "2026-11-01"}}, "verdict": "allow"},
 "Nova": {"group": true, "checks": {"defence": {"status": "clear", "fact": "no arms", "source_url": "https://example.com/s12", "checked": "2026-11-01"}}, "verdict": "allow"},
 "Kappa AG": {"checks": {"defence": {"status": "flagged", "level": "direct", "fact": "Kappa makes arms", "source_url": "https://example.com/s15", "checked": "2026-11-05"}},
              "verdict": "exclude", "decisions": [{"date": "2026-11-05", "verdict": "exclude", "category": "defence"}]}}}
EOF
cat >"$T/su-old.json" <<'EOF'
{"employers": [
 {"name": "Acme Corp", "aliases": [], "checks": {"defence": {"status": "clear", "fact": "no arms", "source_url": "https://example.com/s1", "checked": "2026-11-01"}}},
 {"name": "Delta Inc", "aliases": [], "checks": {"defence": {"status": "flagged", "level": "indirect", "fact": "Delta sells to an army", "source_url": "https://example.com/s3", "checked": "2026-11-01"},
                                               "climate": {"status": "clear", "fact": "no finding", "source_url": "https://example.com/s17", "checked": "2026-11-01"}}},
 {"name": "Kappa AG", "aliases": [], "checks": {"defence": {"status": "clear", "fact": "no arms", "source_url": "https://example.com/s14", "checked": "2026-11-01"}}},
 {"name": "Omega Ltd", "aliases": [], "checks": {"climate": {"status": "flagged", "level": "direct", "fact": "Omega was fined for dumping", "source_url": "https://example.com/s5", "checked": "2026-11-01"}}},
 {"name": "Sigma Co", "aliases": [], "checks": {"defence": {"status": "clear", "fact": "no arms", "source_url": "https://example.com/s7", "checked": "2026-11-01"}}},
 {"name": "Zeta GmbH", "aliases": [], "checks": {"defence": {"status": "clear", "fact": "no arms", "source_url": "https://example.com/s8", "checked": "2026-11-01"}}}]}
EOF
cat >"$T/su-new.json" <<'EOF'
{"employers": [
 {"name": "Acme Corp", "aliases": [], "checks": {"defence": {"status": "flagged", "level": "direct", "fact": "Acme makes drones", "source_url": "https://example.com/s2", "checked": "2026-11-12"}}},
 {"name": "Delta Inc", "aliases": [], "checks": {"defence": {"status": "flagged", "level": "direct", "fact": "Delta has a defence line", "source_url": "https://example.com/s4", "checked": "2026-11-12"},
                                               "climate": {"status": "flagged", "level": "direct", "fact": "Delta was fined for dumping", "source_url": "https://example.com/s16", "checked": "2026-11-12"}}},
 {"name": "Kappa AG", "aliases": [], "checks": {"defence": {"status": "flagged", "level": "direct", "fact": "Kappa makes arms", "source_url": "https://example.com/s15", "checked": "2026-11-12"}}},
 {"name": "Omega Ltd", "aliases": [], "checks": {"climate": {"status": "clear", "fact": "the fine was overturned", "source_url": "https://example.com/s9", "checked": "2026-11-12"}}},
 {"name": "Sigma Co", "aliases": [], "checks": {"defence": {"status": "flagged", "level": "indirect", "fact": "Sigma sells to an army", "source_url": "https://example.com/s10", "checked": "2026-11-12"},
                                              "climate": {"status": "flagged", "level": "severe", "fact": "no source given", "checked": "2026-11-12"}}},
 {"name": "Zeta GmbH", "aliases": [], "checks": {"defence": {"status": "flagged", "level": "direct", "fact": "Zeta makes arms", "source_url": "https://example.com/s11", "checked": "2026-11-12"}}},
 {"name": "Nova Path", "aliases": [], "checks": {"defence": {"status": "flagged", "level": "direct", "fact": "Nova Path makes arms", "source_url": "https://example.com/s13", "checked": "2026-11-12"}}}]}
EOF
employer shared-update --from "$T/su-old.json" --apply >/dev/null 2>&1  # the first time: the old list's fingerprints
cp "$H/apply/employer-checks.json" "$T/su-before.json"
cp "$H/apply/employers/shared-seen.json" "$T/su-seen-before.json"
employer shared-update --from "$T/su-new.json" >"$T/su-dry.out" 2>&1
check "shared-update without --apply: a dry run that writes nothing" sh -c '
    grep -q "dry run" "$1" && cmp -s "$2" "$3/apply/employer-checks.json" && cmp -s "$4" "$3/apply/employers/shared-seen.json"' _ "$T/su-dry.out" "$T/su-before.json" "$H" "$T/su-seen-before.json"
employer shared-update --from "$T/su-new.json" --apply >"$T/su.out" 2>&1
F="$H/apply/employer-checks.json"
check "shared-update: an employer with no opinion of the person's takes the new finding; the old one goes to the history" sh -c '
    "$1" -I "$2/q.py" "$3" "employers.Acme Corp.checks.defence.level" eq direct &&
    "$1" -I "$2/q.py" "$3" "employers.Acme Corp.checks.defence.history.0.status" eq clear' _ "$PY" "$T" "$F"
check "shared-update: an employer with the person's opinion gets one question for all its changed categories; its record stays" sh -c '
    [ "$(grep -c "Shared list update for Delta Inc" "$1")" -eq 1 ] && grep "Shared list update for Delta Inc" "$1" | grep -q "Climate" &&
    grep -q "allow since 2026-11-10" "$1" &&
    "$2" -I "$3/q.py" "$4" "employers.Delta Inc.checks.defence.level" eq indirect' _ "$T/su.out" "$PY" "$T" "$F"
check "shared-update: with no opinion of the person's, a retraction (flagged to clear) is followed too; the finding goes to the history" sh -c '
    "$1" -I "$2/q.py" "$3" "employers.Omega Ltd.checks.climate.status" eq clear &&
    "$1" -I "$2/q.py" "$3" "employers.Omega Ltd.checks.climate.history.0.status" eq flagged' _ "$PY" "$T" "$F"
check "shared-update: a category with no own check, or an employer not in the records, is left to the shared list" sh -c '
    "$1" -I "$2/q.py" "$3" "employers.Sigma Co.checks.defence" absent && "$1" -I "$2/q.py" "$3" "employers.Zeta GmbH" absent' _ "$PY" "$T" "$F"
check "shared-update: a unit's new finding never rewrites the record of a group entry that covers it" q "$F" "employers.Nova.checks.defence.status" eq clear
check "shared-update: no question when the person's record already holds the new finding" sh -c '! grep -q "Kappa AG" "$1"' _ "$T/su.out"
check "shared-update: a malformed shared check (no source, an unknown level) never enters the records" sh -c '
    "$1" -I "$2/q.py" "$3" "employers.Sigma Co.checks.climate.status" eq clear && grep -q "\"invalid\": 1" "$4"' _ "$PY" "$T" "$F" "$T/su.out"
check "shared-update --apply: backs the records up and keeps only fingerprints of the new list" sh -c '
    cmp -s "$1" "$(ls "$2"/apply/employer-checks.json.before-shared-update-*.json | head -n 1)" &&
    grep -q "\"defence\": \"flagged direct [0-9a-f]\{12\}\"" "$2/apply/employers/shared-seen.json" &&
    ! grep -q "Acme makes drones" "$2/apply/employers/shared-seen.json"' _ "$T/su-before.json" "$H"
employer shared-update --from "$T/su-new.json" --apply >"$T/su2.out" 2>&1
check "shared-update: the same version again has nothing to do" grep -q "nothing to do" "$T/su2.out"
employer decide "Acme Corp" exclude defence >/dev/null 2>&1
check "decide: the employer has the person's opinion from now on" q "$F" "employers.Acme Corp.opinion" present
employer record "Sigma Co" sanctions clear fact="not on the lists" source=https://example.com/s18 --person >/dev/null 2>&1
check "record --person: a finding the person stated gives the employer their opinion" q "$F" "employers.Sigma Co.opinion" present

# --- the Questions page: a job's question closes once it is sent; typed answers are read before they are recorded -------
cp -R "$T/flat" "$T/qp"
use "$T/qp"
questions add job "Why do you want to join?" job=F1 >/dev/null 2>&1
track set F1 submitted "sent in the test" >/dev/null 2>&1
questions build "$T/qp-out" >/dev/null 2>&1
QF="$H/apply/questions.json"
check "build: a job question whose job was sent is closed, with a note" sh -c '
    "$1" -I "$2/q.py" "$3" "questions.job-f1-why-do-you-want-to-join.status" eq closed &&
    grep -q "Closed: the application was sent on" "$3" && [ -f "$4/questions/job-f1-why-do-you-want-to-join.json" ]' _ "$PY" "$T" "$QF" "$T/qp-out"
questions add job "What would you change first?" job=F2 >/dev/null 2>&1
track set F2 excluded "employer excluded in the test" >/dev/null 2>&1
questions build "$T/qp-out" >/dev/null 2>&1
check "build: a job question whose job ended unsent is dropped" q "$QF" "questions.job-f2-what-would-you-change-first.status" eq dropped
questions add fact "What is your notice period?" key=notice_period job=F2 >/dev/null 2>&1
mkdir -p "$T/qp-ans/answers"
echo '{"answer": "did we already send this?"}' >"$T/qp-ans/answers/fact-notice-period.json"
questions record "$T/qp-ans" >"$T/qp-rec.out" 2>&1
check "record: a typed answer is read first, never recorded as it is" sh -c '
    "$1" -I "$2/q.py" "$3" "questions.fact-notice-period.status" eq open && grep -q "^fact-notice-period | " "$4" &&
    "$1" -I "$2/q.py" "$5/career-records/career.json" form_answers.notice_period eq "1 month"' _ "$PY" "$T" "$QF" "$T/qp-rec.out" "$H"
questions add fact "Do you need any adjustments for the interview?" key=adjustments personal=yes job=F2 >/dev/null 2>&1
echo '{"answer": "none needed"}' >"$T/qp-ans/answers/fact-adjustments.json"
questions record "$T/qp-ans" >"$T/qp-rec2.out" 2>&1
check "record: a private typed answer is marked [private] under read first" grep -q "^\[private\] fact-adjustments | " "$T/qp-rec2.out"
questions answer fact-adjustments "None needed." typed="none needed" >/dev/null 2>&1
check "answer typed=: a private answer goes into the profile with the person's words and the page as its source" sh -c '
    "$1" -I "$2/q.py" "$3/profile/profile.json" private.adjustments.answer eq "None needed." &&
    "$1" -I "$2/q.py" "$3/profile/profile.json" private.adjustments.words eq "none needed" &&
    "$1" -I "$2/q.py" "$3/profile/profile.json" private.adjustments.source eq "Questions page, read by Claude" &&
    [ ! -e "$3/career-records/personal.json" ]' _ "$PY" "$T" "$H"
questions answer fact-notice-period "One month." >/dev/null 2>&1
check "answer: the answer Claude read and checked is recorded" q "$H/career-records/career.json" form_answers.notice_period.answer eq "One month."

# --- searches ------------------------------------------------------------------------------------------------------------------
use "$T/flat"
searches due >"$T/due0.out" 2>&1
check "searches due: with no saved search, one line says so" sh -c '[ "$(wc -l <"$1")" -eq 1 ] && grep -q "^no saved search" "$1"' _ "$T/due0.out"
searches sites >"$T/sites0.out" 2>&1
check "searches sites: every site of the tracker without a saved search" sh -c 'grep -q "^example.com | 1 job " "$1" && grep -q "^linkedin.com | 1 job " "$1"' _ "$T/sites0.out"
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
searches sites >"$T/sites1.out" 2>&1
check "searches sites: a site with a saved search is left out" sh -c '! grep -q linkedin "$1"' _ "$T/sites1.out"
# 2026-11-06 is a Friday, 2026-11-12 a Thursday, 2026-11-14 a Saturday, 2026-11-16 a Monday.
searches done 1 --today 2026-11-06 >/dev/null 2>&1
searches done 2 --today 2026-11-06 >/dev/null 2>&1
searches due --today 2026-11-12 >"$T/due3.out" 2>&1
check "searches due: a site search of every 7 days is not due after 6; the alert is" sh -c 'grep -q LinkedIn "$1" && ! grep -q "Acme careers" "$1"' _ "$T/due3.out"
searches due --today 2026-11-14 >"$T/due4.out" 2>&1
check "searches due: on a Saturday the site search waits, the alert is read" sh -c 'grep -q LinkedIn "$1" && ! grep -q "Acme careers" "$1"' _ "$T/due4.out"
searches due --today 2026-11-16 >"$T/due5.out" 2>&1
check "searches due: the site search is due on the Monday after" sh -c 'grep -q LinkedIn "$1" && grep -q "Acme careers" "$1"' _ "$T/due5.out"
searches add "Beta board" "analyst" alert=no note="no alert offered, 2026-11-13" >/dev/null 2>&1
searches list >"$T/list.out" 2>&1
check "searches add note=: the list shows why a site has no alert" grep -q "Beta board .*| no alert offered, 2026-11-13" "$T/list.out"
searches done 3 --today 2026-11-12 >/dev/null 2>&1
searches due --today 2026-11-13 >"$T/due6.out" 2>&1
check "searches due: a site without an alert is due on the next weekday by default" grep -q "Beta board" "$T/due6.out"
searches done 3 --today 2026-11-13 >/dev/null 2>&1
searches due --today 2026-11-14 >"$T/due7.out" 2>&1
check "searches due: and not on the Saturday after a Friday check" sh -c '! grep -q "Beta board" "$1"' _ "$T/due7.out"

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
    "$1" -I "$2/q.py" keys "$3" _about,profile,skills,languages,preferences,form_answers,cv_rules,never_claim,person,form_facts &&
    "$1" -I "$2/q.py" "$3" preferences.locations.0 eq Rome && "$1" -I "$2/q.py" "$3" preferences.employer_rules absent &&
    "$1" -I "$2/q.py" "$3" private_extra absent' _ "$PY" "$T" "$T/facts.json"

# --- the profile: lookup order, compare-and-set, history, settings, erase, create -------------------------------------------
cat >"$T/lookup.py" <<'PYEOF'
import os
import sys

sys.path.insert(0, os.environ["SCRIPTS"])
import jsenv  # noqa: E402
import profilelib as pl  # noqa: E402

base = sys.argv[1]
os.environ.pop("CLAUDE_PLUGIN_OPTION_PROFILE_PATH", None)


def make(path, text="{}"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


r1, r2, r3 = (os.path.join(base, n, "My Drive") for n in ("d1", "d2", "d3"))
for r in (r1, r2, r3):
    os.makedirs(r, exist_ok=True)
make(os.path.join(r1, "claude-profile", "profile.json"))  # the old name: never looked at
cloud = make(os.path.join(r2, "claude", "profile.json"))
cfg = os.path.join(base, "config")
local = make(os.path.join(cfg, "claude", "profile.json"))
chosen = os.path.join(base, "chosen.json").replace("\\", "/")
fails = []


def expect(name, got, want):
    if os.path.normcase(str(got)) != os.path.normcase(str(want)):
        fails.append(f"{name}: got {got}, want {want}")


expect("a drive's claude/profile.json before the computer's", pl.locate(None, [r1, r2, r3], cfg)["path"], cloud)
expect("the computer's when no drive has one", pl.locate(None, [r1, r3], cfg)["path"], local)
setting = make(os.path.join(cfg, "settings.json"),
               '{"pluginConfigs": {"cenk-workbench@cenk-workbench": {"options": {"profile_path": "%s"}}}}' % chosen)
expect("the workbench setting before the drives", pl.locate(None, [r2], cfg)["path"], chosen)
envfile = make(os.path.join(base, "home", "job-search.env"), "PROFILE=own/profile.json\n")
expect("PROFILE in job-search.env before everything", pl.locate(jsenv.load(envfile), [r2], cfg)["path"],
       os.path.join(base, "home", "own", "profile.json"))
os.remove(setting)
os.remove(local)
none = pl.locate(None, [r1, r3], cfg)
expect("none found: no path", none["path"], None)
expect("none found: the first drive is suggested", none["suggested"], os.path.join(r1, "claude", "profile.json"))
expect("no drive: the computer is suggested", pl.locate(None, [], cfg)["suggested"],
       os.path.join(cfg, "claude", "profile.json"))
print("\n".join(fails))
sys.exit(1 if fails else 0)
PYEOF
check "profile lookup: the env, the workbench setting, a drive's claude/profile.json, then the computer's" "$PY" -I "$T/lookup.py" "$T/lk"

pf() { "$PY" -I "$S/profilelib.py" --env "$ENVF" "$@"; }
cp -R "$T/flat" "$T/pf"
use "$T/pf"
PF="$H/profile/profile.json"
check "profile get: a string as it is; [n] picks a list item" sh -c '
    [ "$("$1" -I "$2/profilelib.py" --env "$3" get person.name)" = "Jane Doe" ] &&
    [ "$("$1" -I "$2/profilelib.py" --env "$3" get "person.languages[0].level")" = native ]' _ "$PY" "$S" "$ENVF"
pf get person.nickname >/dev/null 2>&1
check "profile get: a missing key exits 1" [ "$?" -eq 1 ]
cp "$PF" "$T/pf-before.json"
pf set person.phone '"+39 06 0000 0001"' >/dev/null 2>&1
rc=$?
check "profile set without --old: another value there changes nothing and exits 3" sh -c '[ "$1" -eq 3 ] && cmp -s "$2" "$3"' _ "$rc" "$PF" "$T/pf-before.json"
pf set person.phone '"+39 06 0000 0001"' --old '"+39 06 0000 0000"' >/dev/null 2>&1
check "profile set --old: the new value, and the old one in history" sh -c '
    "$1" -I "$2/q.py" "$3" person.phone eq "+39 06 0000 0001" && "$1" -I "$2/q.py" "$3" history len 1 &&
    "$1" -I "$2/q.py" "$3" history.0.field eq person.phone && "$1" -I "$2/q.py" "$3" history.0.old eq "+39 06 0000 0000"' _ "$PY" "$T" "$PF"
pf set person.phone '"+39 06 0000 0001"' >"$T/pf-same.out" 2>&1
rc=$?
check "profile set: the value it holds already is done, with nothing written" sh -c '[ "$1" -eq 0 ] && grep -q "^unchanged" "$2"' _ "$rc" "$T/pf-same.out"
printf '%s' '{"answer": "none", "words": "nothing", "date": "2026-11-12", "source": "chat"}' | pf set private.allergies - >/dev/null 2>&1
check "profile set -: the value from stdin; a new key adds no history" sh -c '
    "$1" -I "$2/q.py" "$3" private.allergies.answer eq none && "$1" -I "$2/q.py" "$3" history len 1' _ "$PY" "$T" "$PF"
pf set history '[]' >/dev/null 2>&1
rc1=$?
pf set "person.languages[0].level" '"fluent"' >/dev/null 2>&1
rc2=$?
pf set person.phone 'not json' >/dev/null 2>&1
rc3=$?
check "profile set: history, a list index and a value that is not JSON are refused (exit 2)" sh -c '
    [ "$1" -eq 2 ] && [ "$2" -eq 2 ] && [ "$3" -eq 2 ]' _ "$rc1" "$rc2" "$rc3"
pf set settings.common.form_facts '["address"]' --yes >/dev/null 2>&1
check "profile get <plugin> <key>: settings.common when the plugin has none" sh -c '
    [ "$("$1" -I "$2/profilelib.py" --env "$3" get cenk-jobs form_facts)" = address ]' _ "$PY" "$S" "$ENVF"
pf set settings.cenk-jobs.form_facts '["birth_date", "id_number"]' --yes >/dev/null 2>&1
check "profile get <plugin> <key>: the plugin's own setting first, a list joined by commas" sh -c '
    [ "$("$1" -I "$2/profilelib.py" --env "$3" get cenk-jobs form_facts)" = "birth_date, id_number" ]' _ "$PY" "$S" "$ENVF"
cp "$PF" "$T/pf-before.json"
pf set settings.common.form_facts '["address", "health"]' --old '["address"]' >/dev/null 2>"$T/pf-ask.err"
rc=$?
check "profile set under settings without --yes: nothing written, exit 1, the key and both values to ask about" sh -c '
    [ "$1" -eq 1 ] && cmp -s "$2" "$3" && grep -qF "settings.common.form_facts is a setting" "$4" &&
    grep -qF "old value ([\"address\"])" "$4" && grep -qF "new one ([\"address\", \"health\"])" "$4" &&
    grep -qF -- "--yes" "$4"' _ "$rc" "$PF" "$T/pf-before.json" "$T/pf-ask.err"
pf set settings.common.form_facts '["address", "health"]' --old '["address"]' --yes >/dev/null 2>&1
rc1=$?
pf set settings.common.form_facts '["address", "health"]' >"$T/pf-same2.out" 2>&1
rc2=$?
check "profile set under settings --yes: written, the old value in history; the value it holds already needs no yes" sh -c '
    [ "$1" -eq 0 ] && "$2" -I "$3/q.py" "$4" settings.common.form_facts.1 eq health &&
    grep -q "\"field\": \"settings.common.form_facts\"" "$4" && [ "$5" -eq 0 ] && grep -q "^unchanged" "$6"' \
    _ "$rc1" "$PY" "$T" "$PF" "$rc2" "$T/pf-same2.out"
cp "$PF" "$T/pf-before.json"
pf erase settings.common.form_facts >/dev/null 2>"$T/pf-ask2.err"
rc1=$?
cp "$PF" "$T/pf-after-ask.json"
pf erase settings.common.form_facts --yes >/dev/null 2>&1
rc2=$?
check "profile erase under settings: without --yes asks and writes nothing; with it the setting and its history go" sh -c '
    [ "$1" -eq 1 ] && cmp -s "$2" "$3" && grep -qF "old value ([\"address\", \"health\"])" "$4" && [ "$5" -eq 0 ] &&
    "$6" -I "$7/q.py" "$8" settings.common.form_facts absent && ! grep -q "settings.common.form_facts" "$8"' \
    _ "$rc1" "$T/pf-after-ask.json" "$T/pf-before.json" "$T/pf-ask2.err" "$rc2" "$PY" "$T" "$PF"
pf set private.allergies.words '"none at all"' --old '"nothing"' >/dev/null 2>&1
printf '{}\n' >"$H/career-records/career.json.before-move-20261112-000000.json"
pf erase private.allergies >"$T/pf-erase.out" 2>&1
check "profile erase: the value and every history entry under it, nothing else" sh -c '
    "$1" -I "$2/q.py" "$3" private.allergies absent && ! grep -q allergies "$3" && "$1" -I "$2/q.py" "$3" history len 1 &&
    grep -q "^erased private.allergies" "$4" && ! grep -q "Manage versions" "$4"' _ "$PY" "$T" "$PF" "$T/pf-erase.out"
check "profile erase: names the move's backups, which may still hold the value" \
    grep -q "career.json.before-move-20261112-000000.json" "$T/pf-erase.out"
rm -f "$H/career-records/career.json.before-move-20261112-000000.json"
"$PY" -I "$S/career_view.py" facts --env "$ENVF" >"$T/pf-facts.json" 2>/dev/null
check "career_view facts: person without address or birth date, form_facts names only, never private or contacts" sh -c '
    "$1" -I "$2/q.py" "$3" person.name eq "Jane Doe" && "$1" -I "$2/q.py" "$3" person.birth_date absent &&
    "$1" -I "$2/q.py" "$3" person.address absent && "$1" -I "$2/q.py" "$3" form_facts.0 eq birth_date &&
    "$1" -I "$2/q.py" "$3" form_facts len 1 && "$1" -I "$2/q.py" "$3" private absent &&
    "$1" -I "$2/q.py" "$3" contacts absent && ! grep -q "vegetarian\|1990-01-02\|Example Street\|sam@example.com" "$3"' _ "$PY" "$T" "$T/pf-facts.json"
"$PY" -I "$S/check_setup.py" --env "$ENVF" >"$T/pf-setup.out" 2>&1
check "check_setup: the profile is found; a form_facts name that is no guarded item is warned about" sh -c '
    grep -q "^OK .*Profile (the person" "$1" && grep -q "^WARN.*form_facts.*id_number" "$1"' _ "$T/pf-setup.out"
questions add fact "What is your date of birth?" key=person.birth_date job=F2 >/dev/null 2>&1
questions answer fact-person-birth-date "1990-02-01" >"$T/pf-q1.out" 2>&1
check "answer to a profile key holding another value: not recorded, asked, the question stays open" sh -c '
    grep -q "^ask the person.*fact-person-birth-date" "$1" && "$2" -I "$3/q.py" "$4" person.birth_date eq 1990-01-02 &&
    "$2" -I "$3/q.py" "$5/apply/questions.json" questions.fact-person-birth-date.status eq open' _ "$T/pf-q1.out" "$PY" "$T" "$PF" "$H"
questions answer fact-person-birth-date "1990-02-01" replace=yes >/dev/null 2>&1
check "answer replace=yes: the person's choice goes in, the old value into history" sh -c '
    "$1" -I "$2/q.py" "$3" person.birth_date eq 1990-02-01 && grep -q "\"field\": \"person.birth_date\"" "$3" &&
    "$1" -I "$2/q.py" "$4/apply/questions.json" questions.fact-person-birth-date.status eq answered' _ "$PY" "$T" "$PF" "$H"

cp -R "$T/flat" "$T/gd"
mkdir -p "$T/gd-drive/My Drive/claude"
cp "$T/gd/profile/profile.json" "$T/gd-drive/My Drive/claude/profile.json"
sed "s#^PROFILE=.*#PROFILE=$T/gd-drive/My Drive/claude/profile.json#" "$T/gd/job-search.env" >"$T/gd/env.tmp" &&
    mv "$T/gd/env.tmp" "$T/gd/job-search.env"
use "$T/gd"
pf erase private.diet >"$T/gd-erase.out" 2>&1
check "profile erase in a Google Drive: says the earlier versions still hold the value, and how to delete them" grep -q "Manage versions" "$T/gd-erase.out"

cp -R "$T/flat" "$T/np"
rm -rf "$T/np/profile"
use "$T/np"
pf set person.name '"Jane Doe"' >"$T/np-set.out" 2>&1
rc=$?
check "profile set with no profile: exits 1, creates nothing, says to ask the person where" sh -c '
    [ "$1" -eq 1 ] && [ ! -e "$2/profile" ] && grep -q "Ask the person where to create it" "$3"' _ "$rc" "$H" "$T/np-set.out"
"$PY" -I "$S/check_setup.py" --needs --env "$ENVF" >"$T/np-needs.out" 2>&1
check "check_setup --needs: no profile yet, with the place to suggest" grep -q "^profile: none yet: ask the person where to create it" "$T/np-needs.out"
questions add fact "Any dietary needs?" key=diet personal=yes job=F2 >/dev/null 2>&1
questions answer fact-diet "None." >"$T/np-q.out" 2>&1
check "answer with no profile: not recorded, listed under no profile, nothing created" sh -c '
    grep -q "^no profile.*fact-diet" "$1" && "$2" -I "$3/q.py" "$4/apply/questions.json" questions.fact-diet.status eq open &&
    [ ! -e "$4/profile" ] && [ ! -e "$4/career-records/personal.json" ]' _ "$T/np-q.out" "$PY" "$T" "$H"
pf create "$H/elsewhere/profile.json" >/dev/null 2>&1
check "profile create: the file at the path the person chose, and one PROFILE line naming it" sh -c '
    [ -f "$1/elsewhere/profile.json" ] && grep -q "^PROFILE=.*elsewhere" "$1/job-search.env" &&
    [ "$(grep -c "^PROFILE=" "$1/job-search.env")" -eq 1 ]' _ "$H"
pf create "$H/third/profile.json" >/dev/null 2>&1
rc=$?
check "profile create: refused when a profile exists" sh -c '[ "$1" -eq 1 ] && [ ! -e "$2/third" ]' _ "$rc" "$H"
# --- create with no job-search.env, and PROFILE against the lookup the other cenk-* plugins use ------------------
# Each command pins the shared lookup to a throwaway path (profile_path), so no real drive folder is looked at.
mkdir -p "$T/noenv"
found=$(cd "$T/noenv" && unset JOB_SEARCH_ENV && "$PY" -I -c '
import sys
sys.path.insert(0, sys.argv[1])
import jsenv
try:
    print(jsenv.find(None, sys.argv[1] + "/profilelib.py"))
except SystemExit:
    pass' "$S" 2>/dev/null)
if [ -n "$found" ]; then
    fail "profile create with no job-search.env: not run, one is found from the throwaway folder ($found)"
else
    (cd "$T/noenv" && unset JOB_SEARCH_ENV &&
        CLAUDE_PLUGIN_OPTION_PROFILE_PATH="$T/noenv-shared/profile.json" "$PY" -I "$S/profilelib.py" \
            create "$T/noenv/lost/profile.json") >"$T/noenv.out" 2>&1
    rc=$?
    check "profile create with no job-search.env at a path no lookup finds: exits 1, creates nothing" sh -c '
        [ "$1" -eq 1 ] && [ ! -e "$2/noenv/lost" ] && grep -q "^Nothing would find a profile" "$3"' \
        _ "$rc" "$T" "$T/noenv.out"
    (cd "$T/noenv" && unset JOB_SEARCH_ENV &&
        CLAUDE_PLUGIN_OPTION_PROFILE_PATH="$T/noenv-shared/profile.json" "$PY" -I "$S/profilelib.py" \
            create "$T/noenv-shared/profile.json") >"$T/noenv2.out" 2>&1
    rc=$?
    check "profile create with no job-search.env where the lookup looks: created, no PROFILE line" sh -c '
        [ "$1" -eq 0 ] && [ -f "$2/noenv-shared/profile.json" ] && ! grep -q "PROFILE=" "$3"' \
        _ "$rc" "$T" "$T/noenv2.out"
fi
CLAUDE_PLUGIN_OPTION_PROFILE_PATH="$T/other-profile/profile.json" \
    "$PY" -I "$S/check_setup.py" --env "$ENVF" >"$T/split-setup.out" 2>&1
CLAUDE_PLUGIN_OPTION_PROFILE_PATH="$H/elsewhere/profile.json" \
    "$PY" -I "$S/check_setup.py" --env "$ENVF" >"$T/same-setup.out" 2>&1
check "check_setup: warns when PROFILE is not the file the other cenk-* plugins read; silent when it is" sh -c '
    grep -q "^WARN.*Same profile for the other cenk-.*profile_path" "$1" &&
    ! grep -q "Same profile for the other" "$2"' _ "$T/split-setup.out" "$T/same-setup.out"

# --- move_to_profile: the person's facts from the old records into the profile, once -----------------------------------
cp -R "$T/flat" "$T/mv"
use "$T/mv"
P="$H/profile/profile.json"
C="$H/career-records/career.json"
echo '{"person": {"name": "Jane Doe", "email": "jane@example.com"}}' >"$P"
cat >"$C" <<EOF
{"profile": {"name": "Jane Doe", "headline": "Engineer", "citizenship": ["Italian"], "work_authorisation": "EU citizen",
             "languages": [{"language": "Italian", "level": "native"}], "location": "Rome, Italy",
             "pronouns_on_linkedin": "she/her",
             "contact": {"email": "jane.doe@example.org", "phone": "+39 06 0000 0007",
                         "linkedin": "https://www.linkedin.com/in/jane-example",
                         "github": {"account": "jane-example", "on_cv": true}}},
 "references": {"_about": "referees", "rows": [
   {"name": "Sam Example", "email": "sam@example.com", "relation": "former manager", "company": "Acme Corp",
    "worked_together_since": "2020", "agreed_on": "2026-11-01"},
   {"name": "Alex Example", "phone": "+39 06 0000 0009", "relation": "colleague"}]},
 "experience": [{"id": "acme", "employer": "Acme Corp", "dates": {"cv": "2020-2024"}}],
 "employment_timeline": {"heading": "Timeline"},
 "history": [{"date": "2026-10-01", "path": "profile.contact.phone", "old": "+39 06 0000 0006"}],
 "skills": ["Java"], "form_answers": {}, "never_claim": []}
EOF
cat >"$H/career-records/personal.json" <<EOF
{"_about": "private", "facts": {
  "adjustments": {"answer": "None needed.", "typed": "none needed", "date": "2026-11-01", "source": "chat"},
  "lawyer": {"name": "Jo Example", "email": "jo@example.com", "role": "employment lawyer"},
  "self_id": {"gender": "woman", "date": "2026-11-01", "words": "woman"}}}
EOF
mkdir -p "$H/notes" "$H/job-applications/pending/acme"
echo "Call me at +39 06 0000 0007" >"$H/notes/old.md"
echo "not a real pdf" >"$H/notes/old.pdf"
echo "+39 06 0000 0007" >"$H/job-applications/pending/acme/answers.md"
cp "$P" "$T/mv-before.json"
"$PY" -I "$S/move_to_profile.py" --env "$ENVF" >"$T/mv-dry.out" 2>&1
rc=$?
check "move dry run: what moves, what differs and what waits; nothing written; exit 3 for a different value" sh -c '
    [ "$1" -eq 3 ] && cmp -s "$2" "$3" &&
    grep -q "^add  *person.phone <- MASTER_RECORD profile.contact.phone" "$4" && grep -q "^done  *person.name" "$4" &&
    grep -q "^different  *person.email" "$4" && grep -q "^confirm  *person.pronouns" "$4" &&
    grep -q "^add  *contacts.referee-sam" "$4" && grep -q "^add  *contacts.lawyer <- PERSONAL_RECORD facts.lawyer" "$4" &&
    grep -q "^add  *private.adjustments <- PERSONAL_RECORD facts.adjustments" "$4" &&
    grep -q "^ask .*contacts.referee-alex" "$4" && grep -q "^by hand .*experience\[0..0\]" "$4" &&
    grep -q "history: entries about profile.contact.phone" "$4"' _ "$rc" "$P" "$T/mv-before.json" "$T/mv-dry.out"
check "move dry run: lists the main-folder files that repeat a value, never an application folder" sh -c '
    grep -q "^  notes/old.md (person.phone)" "$1" && grep -q "^  notes/old.pdf (beside notes/old.md)" "$1" &&
    ! grep -q "job-applications" "$1"' _ "$T/mv-dry.out"
check "move: prints field names and paths, never a value" sh -c '
    ! grep -q "0000 0007\|0000 0009\|sam@example.com\|None needed\|Italian\|she/her\|jane-example" "$1"' _ "$T/mv-dry.out"
"$PY" -I "$S/move_to_profile.py" --env "$ENVF" --apply >"$T/mv-apply.out" 2>&1
rc=$?
check "move --apply: adds what the profile lacks, never writes over another value" sh -c '
    [ "$1" -eq 3 ] && "$2" -I "$3/q.py" "$4" person.phone eq "+39 06 0000 0007" &&
    "$2" -I "$3/q.py" "$4" person.email eq jane@example.com && "$2" -I "$3/q.py" "$4" person.links.github eq jane-example &&
    "$2" -I "$3/q.py" "$4" person.location.city eq Rome && "$2" -I "$3/q.py" "$4" person.nationality.0 eq Italian &&
    "$2" -I "$3/q.py" "$4" contacts.referee-sam.since eq 2020 && "$2" -I "$3/q.py" "$4" contacts.referee-sam.role eq referee &&
    "$2" -I "$3/q.py" "$4" contacts.lawyer.email eq jo@example.com &&
    "$2" -I "$3/q.py" "$4" private.adjustments.words eq "none needed" && "$2" -I "$3/q.py" "$4" private.self_id.gender eq woman &&
    "$2" -I "$3/q.py" "$4" person.pronouns absent && "$2" -I "$3/q.py" "$4" history absent' _ "$rc" "$PY" "$T" "$P"
"$PY" -I "$S/move_to_profile.py" --env "$ENVF" --apply --confirm person.pronouns >/dev/null 2>&1
check "move --apply --confirm: a field to confirm moves only with the person's yes" q "$P" person.pronouns eq she/her
"$PY" -I "$S/move_to_profile.py" --env "$ENVF" --apply --remove-old >/dev/null 2>&1
check "move: --apply and --remove-old together are refused (exit 2)" [ "$?" -eq 2 ]
"$PY" -I "$S/move_to_profile.py" --env "$ENVF" --remove-old >"$T/mv-rm.out" 2>&1
check "move --remove-old: removes only what the profile holds unchanged, after a backup" sh -c '
    "$1" -I "$2/q.py" "$3" profile.contact.phone absent && "$1" -I "$2/q.py" "$3" profile.contact.email eq jane.doe@example.org &&
    "$1" -I "$2/q.py" "$3" profile.contact.github.on_cv eq True && "$1" -I "$2/q.py" "$3" profile.contact.github.account absent &&
    "$1" -I "$2/q.py" "$3" profile.headline eq Engineer && "$1" -I "$2/q.py" "$3" profile.pronouns_on_linkedin absent &&
    "$1" -I "$2/q.py" "$3" references absent && "$1" -I "$2/q.py" "$3" experience.0.employer eq "Acme Corp" &&
    ls "$4"/career-records/career.json.before-move-*.json >/dev/null 2>&1' _ "$PY" "$T" "$C" "$H"
check "move --remove-old: the old private record, all moved, is deleted; its backup is named for deleting" sh -c '
    [ ! -e "$1/career-records/personal.json" ] && grep -q "personal.json.before-move-" "$2"' _ "$H" "$T/mv-rm.out"

# --- to-dos: track.py todo, and the to-dos a sent or ended job loses ---------------------------------------------------
day() { "$PY" -I -c 'import datetime, sys; print((datetime.date.today() + datetime.timedelta(days=int(sys.argv[1]))).isoformat())' "$1"; }
D0=$(day 0)
cp -R "$T/flat" "$T/todo-flat"
use "$T/todo-flat"
TF="$H/apply/targets.json"
track todo F1 add waiting "reply on the interview date" >/dev/null 2>&1
check "todo add: the kind, the text and today as since" sh -c '
    "$1" -I "$2/q.py" "$3" jobs.0.todo.0.kind eq waiting && "$1" -I "$2/q.py" "$3" jobs.0.todo.0.since eq "$4" &&
    "$1" -I "$2/q.py" "$3" jobs.0.todo.0.text eq "reply on the interview date"' _ "$PY" "$T" "$TF" "$D0"
check "todo add: an unknown kind is refused and nothing is written" sh -c '
    ! "$1" -I "$2/track.py" todo F1 add someday "x" --env "$3" >/dev/null 2>&1 && "$1" -I "$4/q.py" "$5" jobs.0.todo len 1' \
    _ "$PY" "$S" "$ENVF" "$T" "$TF"
check "todo add: a due that is no date is refused" sh -c '! "$1" -I "$2/track.py" todo F1 add task "x" due=tomorrow --env "$3" >/dev/null 2>&1' \
    _ "$PY" "$S" "$ENVF"
track todo F1 add todo "approve the letter" session=local_a1 where=pc >/dev/null 2>&1
check "todo add: a to-do names its session by id" q "$TF" jobs.0.todo.1.session eq local_a1
track todo F1 list >"$T/todo-list.out" 2>&1
check "todo list: numbered, with the kind" sh -c 'grep -q "^ 1 waiting " "$1" && grep -q "^ 2 todo .*approve the letter" "$1"' _ "$T/todo-list.out"
track todo F1 done 1 >/dev/null 2>&1
check "todo done <n>: that one goes, the other stays" sh -c '
    "$1" -I "$2/q.py" "$3" jobs.0.todo len 1 && "$1" -I "$2/q.py" "$3" jobs.0.todo.0.text eq "approve the letter"' _ "$PY" "$T" "$TF"
track set F1 needs-person "still waiting" >/dev/null 2>&1
check "set: a status that does not end the job keeps its to-dos" q "$TF" jobs.0.todo len 1
track set F1 submitted "sent in the test" >"$T/todo-set.out" 2>&1
check "set submitted: the to-dos are dropped, printed and kept in the history" sh -c '
    grep -q "dropped 1 to-do(s): approve the letter" "$1" && "$2" -I "$3/q.py" "$4" jobs.0.todo absent &&
    "$2" -I "$3/q.py" "$4" "jobs.0.history.status=submitted.todo_dropped.0.text" eq "approve the letter"' \
    _ "$T/todo-set.out" "$PY" "$T" "$TF"
track todo F1 add task "book the interview" >/dev/null 2>&1
track set F1 submitted "a new note, the same status" >/dev/null 2>&1
check "set: the same status again drops nothing" q "$TF" jobs.0.todo len 1
track todo F2 add click "sign in" >/dev/null 2>&1
track todo F2 add click "open the page" >/dev/null 2>&1
track todo F2 add todo "answer" >/dev/null 2>&1
track todo F2 done kind=click >/dev/null 2>&1
check "todo done kind=: every to-do of that kind" sh -c '
    "$1" -I "$2/q.py" "$3" jobs.1.todo len 1 && "$1" -I "$2/q.py" "$3" jobs.1.todo.0.kind eq todo' _ "$PY" "$T" "$TF"
track set F2 excluded "employer excluded in the test" >/dev/null 2>&1
check "set excluded: the to-dos are dropped too" q "$TF" jobs.1.todo absent
cp -R "$T/old" "$T/todo-split"
use "$T/todo-split"
track split --apply >/dev/null 2>&1
track todo J1 add urgent "type the emailed code" where=pc >/dev/null 2>&1
check "todo on a split tracker, the older shape: the to-do is in the summary row, not the detail" sh -c '
    "$1" -I "$2/q.py" "$3/apply/targets.json" companies.0.jobs.0.todo.0.kind eq urgent &&
    "$1" -I "$2/q.py" "$3/apply/details/jobs/J1.json" todo absent' _ "$PY" "$T" "$H"
track set J1 submitted "sent in the test" >/dev/null 2>&1
check "set submitted on a split tracker: dropped from the row, kept in the detail's history" sh -c '
    "$1" -I "$2/q.py" "$3/apply/targets.json" companies.0.jobs.0.todo absent &&
    "$1" -I "$2/q.py" "$3/apply/details/jobs/J1.json" "history.status=submitted.todo_dropped.0.text" eq "type the emailed code"' \
    _ "$PY" "$T" "$H"

# --- the dashboard export: ended jobs, steps from PIPELINE, one row per job, Claude's next, logins -------------------
# A made-up search. D1 moves forward (a take-home done, a test coming, a questionnaire past due); D2 shares D1's
# process; D3 was rejected and D4 declined after sending; D5 waits on the person; D6's site is signed in; D7 is found;
# D8 is excluded; D9 is sent, with its old not-applied folder kept.
mkhome "$T/dash" flat
use "$T/dash"
cat >"$T/mkdash.py" <<'PYEOF'
import datetime
import json
import sys

home = sys.argv[1]
day = lambda n: (datetime.date.today() + datetime.timedelta(days=n)).isoformat()  # noqa: E731
now = datetime.datetime.now().replace(microsecond=0)
job = lambda i, company, title, status, **more: dict(  # noqa: E731
    {"id": i, "company": company, "title": title, "url": f"https://example.com/{i.lower()}", "status": status,
     "note": "made up"}, **more)
jobs = [
    job("D1", "Acme Corp", "Engineer", "submitted", applied=day(-5),
        todo=[{"kind": "waiting", "text": "feedback on the take-home", "since": day(-1)}]),
    job("D2", "Acme Corp", "Staff Engineer", "submitted", applied=day(-5)),
    job("D3", "Beta Ltd", "Analyst", "submitted", applied=day(-5),
        todo=[{"kind": "todo", "text": "approve the letter", "since": day(-5)},
              {"kind": "todo", "text": "a to-do without a date"}]),
    job("D4", "Gamma Inc", "Designer", "submitted", applied=day(-5),
        todo=[{"kind": "todo", "text": "send the withdrawal email", "since": day(-1)},
              {"kind": "todo", "text": "press Submit", "since": day(-5)}]),
    job("D5", "Delta GmbH", "Tester", "needs-person",
        todo=[{"kind": "todo", "text": "the newer to-do", "since": day(-1)},
              {"kind": "todo", "text": "the older to-do", "since": day(-5)},
              {"kind": "task", "text": "call the recruiter", "due": day(-3), "since": day(-5)},
              {"kind": "task", "text": "send the form", "due": day(1), "since": day(-1)},
              {"kind": "waiting", "text": "the recruiter's reply", "since": day(-3)},
              {"kind": "todo", "text": "a to-do from before the since date"}]),
    job("D6", "Epsilon Co", "Developer", "account-needed", platform="Workday"),
    job("D7", "Zeta Works", "Architect", "found"),
    job("D8", "Eta Labs", "Lead", "excluded", platform="Workday",
        todo=[{"kind": "todo", "text": "a to-do left on an excluded job", "since": day(0)}]),
    job("D9", "Theta AG", "Manager", "needs-person"),
]
pipeline = {
    "D1": {"stage": "approved", "steps": [
        {"date": day(-3), "due": day(1), "name": "Take-home task", "with": "the team", "done": day(0)},
        {"date": day(5), "due": day(5), "name": "Online test", "with": "the recruiter",
         "mail": "https://mail.example.com/1"},
        {"date": day(-5), "due": day(-3), "name": "Questionnaire", "with": "the recruiter"}]},
    "D2": {"same_as": "D1"},
    "D3": {"stage": "rejected", "date": day(-3), "reason": "made up"},
    "D4": {"stage": "declined", "date": day(-1), "why": "other", "reason": "made up"},
}
site = lambda i, status, checked, **more: dict(  # noqa: E731
    {"id": i, "name": i, "kind": "site", "status": status, "checked": checked.isoformat(), "note": "made up",
     "jobs": []}, **more)
logins = [
    site("Workday · Epsilon Co", "signed-in", now),
    site("Workday · Eta Labs", "expired", now, fix="sign in again"),
    site("Greenhouse", "signed-in", now - datetime.timedelta(days=6)),
    site("Lever", "signed-in", now - datetime.timedelta(hours=1)),
]
for name, data in (("targets", {"jobs": jobs}), ("pipeline", pipeline), ("logins", {"logins": logins})):
    with open(f"{home}/apply/{name}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
PYEOF
"$PY" -I "$T/mkdash.py" "$H"
build() { "$PY" -I "$S/build_app_folders.py" --env "$ENVF"; }
export_dash() { "$PY" -I "$S/export_dashboard.py" "$@" --env "$ENVF"; }
build >/dev/null 2>&1
# D9 is sent; its not-applied folder holds a file that cannot move (the new folder has one of that name), so it stays.
STALE="$H/job-applications/not-applied/Theta AG - Manager"
track set D9 submitted "sent in the test" >/dev/null 2>&1
mkdir -p "$H/job-applications/pending/$D0 Theta AG - Manager"
echo "my notes" >"$STALE/notes.md"
echo "newer notes" >"$H/job-applications/pending/$D0 Theta AG - Manager/notes.md"
build >"$T/dash-build.out" 2>&1
check "build_app_folders: the sent job's old folder is kept for its notes" sh -c '[ -f "$1/notes.md" ] && grep -q "kept, as they hold other files" "$2"' \
    _ "$STALE" "$T/dash-build.out"
check "build_app_folders: an application that shares a process is filed in that one's stage" sh -c 'ls "$1/job-applications/approved" | grep -q "Acme Corp - Staff Engineer"' _ "$H"
check "build_app_folders: a done step says so and is no next step; the coming one is" sh -c '
    grep -q "Take-home task.*done $2" "$1"/job-applications/approved/*"Acme Corp - Engineer"/overview.md &&
    ! grep "^- \*\*" "$1/job-applications/README.md" | grep -q "Take-home task" &&
    grep "^- \*\*" "$1/job-applications/README.md" | grep -q "Online test"' _ "$H" "$D0"
OUT="$T/dash-out"
export_dash "$OUT" >"$T/dash-export.out" 2>&1
check "export: runs and writes the seven files" sh -c 'grep -q "applications, " "$1" && for f in index applications steps actions logins excluded sessions; do [ -f "$2/$f.json" ] || exit 1; done' \
    _ "$T/dash-export.out" "$OUT"
# dq.py <file> <expression>: PASS when the expression is true; R is the file, K a list's rows by key (or id).
cat >"$T/dq.py" <<'PYEOF'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    R = json.load(f)
K = {r.get("key", r.get("id")): r for r in R} if isinstance(R, list) else {}
pos =lambda text: next(i for i, r in enumerate(R) if r.get("text") == text)  # noqa: E731
sys.exit(0 if eval(sys.argv[2]) else 1)
PYEOF
dq() { "$PY" -I "$T/dq.py" "$@"; }
check "export: one application row per job; the kept not-applied folder of a sent job is not counted" dq "$OUT/applications.json" \
    'len(R) == len(K) == 8 and K["D9"]["stage"] == "Waiting for reply"'
check "export: the stage counts follow" dq "$OUT/index.json" \
    'K["stage:Not sent"]["n"] == 3 and K["stage:Waiting for reply"]["n"] == 1 and K["stage:Moving forward"]["n"] == 2'
check "export: the header names weekdays when no days are set" dq "$OUT/index.json" 'K["meta:run"]["label"].endswith("Next: weekdays at 19:00.")'
for d in daily none "Mon, Wed"; do
    { cat "$ENVF"; echo "SEARCH_DAYS=$d"; echo "SEARCH_TIME=08:30"; } >"$H/days.env"
    "$PY" -I "$S/export_dashboard.py" "$T/dash-days" --env "$H/days.env" >/dev/null 2>&1
    cp "$T/dash-days/index.json" "$T/days-$(echo "$d" | tr -d ' ,').json"
done
rm -f "$H/days.env"
check "export: the header follows SEARCH_DAYS and SEARCH_TIME" sh -c '
    "$1" -I "$2/dq.py" "$2/days-daily.json" "K[\"meta:run\"][\"label\"].endswith(\"Next: every day at 08:30.\")" &&
    "$1" -I "$2/dq.py" "$2/days-none.json" "K[\"meta:run\"][\"label\"].endswith(\"No run scheduled.\")" &&
    "$1" -I "$2/dq.py" "$2/days-MonWed.json" "K[\"meta:run\"][\"label\"].endswith(\"Next: Mon, Wed at 08:30.\")"' _ "$PY" "$T"
check "export: a waiting to-do is never in Do now" dq "$OUT/actions.json" 'not any("take-home" in r["text"] or "reply" in r["text"] for r in R)'
check "export: the wait is on the last done step, with since" dq "$OUT/steps.json" \
    'K["D1#1"]["state"] == "done" and K["D1#1"]["awaits"] == "feedback on the take-home" and K["D1#1"]["since"] != ""'
check "export: a job without steps gets a waiting row of its own" dq "$OUT/steps.json" \
    'K["D5#wait"]["state"] == "waiting" and K["D5#wait"]["date"] == K["D5#wait"]["since"] != ""'
check "export: the waits are counted" dq "$OUT/index.json" 'K["actions:waiting"]["n"] == 2'
check "export: a rejected job lists no older to-do" dq "$OUT/actions.json" '"D3:1" not in K and "D3:2" not in K'
check "export: a to-do set on the day a sent job ended stays; an older one goes" dq "$OUT/actions.json" \
    'K["D4:1"]["text"] == "send the withdrawal email" and "D4:2" not in K'
check "export: a job ended by its tracker status lists no to-do" dq "$OUT/actions.json" '"D8:1" not in K'
check "export: a past due date is late, never urgent; one due tomorrow is urgent" dq "$OUT/actions.json" \
    'K["D5:3"]["kind"] == "late" and K["D5:4"]["kind"] == "urgent"'
check "export: a done step due tomorrow makes no row; the coming test makes one task" dq "$OUT/actions.json" \
    '"D1#1:do" not in K and K["D1#2:do"]["kind"] == "task" and K["D1#2:do"]["link"] == "https://mail.example.com/1"'
check "export: a step past its due date without done is late" dq "$OUT/actions.json" \
    'K["D1#3:do"]["kind"] == "late" and "was due" in K["D1#3:do"]["text"]'
check "export: the step states come from PIPELINE" dq "$OUT/steps.json" \
    'K["D1#2"]["state"] == "upcoming" and K["D1#3"]["state"] == "past" and K["D1#1"]["due"] > K["D1#1"]["done"] != ""'
check "export: a shared process is on the steps of the application that owns it, once" dq "$OUT/steps.json" \
    'K["D1#2"]["also"] == ["D2"] and not any(r["app"] == "D2" for r in R)'
check "export: the order is urgent, then dates with the past due first, then the older to-do first" dq "$OUT/actions.json" \
    'R[0]["kind"] == "urgent" and pos("call the recruiter") < pos("the older to-do") < pos("the newer to-do")'
check "export: a job whose site is signed in is Claude's next" dq "$OUT/actions.json" \
    'any(r["kind"] == "queued" and r["apps"] == ["D6"] and "ready to send" in r["text"] for r in R)'
check "export: a found job nobody owns is Claude's next, last in the list" dq "$OUT/actions.json" \
    'K["queued:new"]["apps"] == ["D7"] and R[-1]["kind"] == "queued"'
check "export: the new kinds are counted" dq "$OUT/index.json" 'K["actions:late"]["n"] == 2 and K["actions:queued"]["n"] == 2'
check "export: an excluded employer's own site is left out, whatever its state" sh -c '
    "$1" -I "$2/dq.py" "$3/logins.json" "not any(\"Eta Labs\" in r[\"id\"] for r in R) and len(R) == 3" &&
    "$1" -I "$2/dq.py" "$3/actions.json" "not any(r[\"key\"].startswith(\"login:\") for r in R)"' _ "$PY" "$T" "$OUT"
check "export: a sign-in checked 6 days ago is stale and not counted as working" sh -c '
    "$1" -I "$2/dq.py" "$3/logins.json" "K[\"Greenhouse\"][\"stale\"] == \"yes\" and K[\"Lever\"][\"stale\"] == \"\"" &&
    "$1" -I "$2/dq.py" "$3/index.json" "K[\"logins:ok\"][\"n\"] == 2"' _ "$PY" "$T" "$OUT"
# A proposed date is no task; a step left open on a job that is over is "ended", never past due.
cp "$H/apply/pipeline.json" "$T/pipeline.bak"
cat >"$T/mkprop.py" <<'PYEOF'
import json
import sys

path, how = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as f:
    p = json.load(f)
if how == "proposed":
    p["D1"]["steps"][1]["proposed"] = True
else:
    p["D1"].update(stage="rejected", date=sys.argv[3])
with open(path, "w", encoding="utf-8") as f:
    json.dump(p, f, indent=2)
PYEOF
"$PY" -I "$T/mkprop.py" "$H/apply/pipeline.json" proposed
export_dash "$T/dash-prop" >/dev/null 2>&1
check "export: a proposed step reads proposed and is no task in Do now" sh -c '
    "$1" -I "$2/dq.py" "$2/dash-prop/steps.json" "K[\"D1#2\"][\"state\"] == \"proposed\"" &&
    "$1" -I "$2/dq.py" "$2/dash-prop/actions.json" "\"D1#2:do\" not in K"' _ "$PY" "$T"
cp "$T/pipeline.bak" "$H/apply/pipeline.json"
"$PY" -I "$T/mkprop.py" "$H/apply/pipeline.json" over "$(day 0)"
export_dash "$T/dash-over" >"$T/over-export.out" 2>&1
check "export: an open step of a job that is over is ended: not upcoming, not past due" sh -c '
    "$1" -I "$2/dq.py" "$2/dash-over/steps.json" "K[\"D1#2\"][\"state\"] == \"ended\" and K[\"D1#3\"][\"state\"] == \"ended\" and K[\"D1#1\"][\"state\"] == \"done\"" &&
    "$1" -I "$2/dq.py" "$2/dash-over/actions.json" "\"D1#2:do\" not in K and \"D1#3:do\" not in K" &&
    ! grep -q "^check: past due: D1 step" "$3"' _ "$PY" "$T" "$T/over-export.out"
cp "$T/pipeline.bak" "$H/apply/pipeline.json"
# With a run recorded, a state from before the run started was not looked at in it: connectors too.
cp "$H/apply/logins.json" "$T/logins.bak"
cat >"$T/mkrun.py" <<'PYEOF'
import datetime
import json
import sys

home = sys.argv[1]
now = datetime.datetime.now().replace(microsecond=0)
with open(f"{home}/apply/logins.json", encoding="utf-8") as f:
    data = json.load(f)
for r in data["logins"]:
    if r["id"] == "Lever":
        r["note"] = "create the account first"
data["logins"].append({"id": "gmail", "name": "Gmail", "kind": "connector", "status": "connected",
                       "checked": (now - datetime.timedelta(hours=2)).isoformat(), "note": "answered", "jobs": []})
with open(f"{home}/apply/logins.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
with open(f"{home}/apply/usage-log.jsonl", "w", encoding="utf-8") as f:
    f.write(json.dumps({"time": (now - datetime.timedelta(minutes=30)).isoformat(), "step": "run", "result": "started"}) + chr(10))
PYEOF
"$PY" -I "$T/mkrun.py" "$H"
export_dash "$T/dash-run" >"$T/run-export.out" 2>&1
check "export: with a run recorded, a state from before its start reads not checked, a connector too" sh -c '
    "$1" -I "$2/dq.py" "$2/dash-run/logins.json" "K[\"Lever\"][\"stale\"] == \"yes\" and K[\"gmail\"][\"stale\"] == \"yes\" and K[\"Workday · Epsilon Co\"][\"stale\"] == \"\"" &&
    "$1" -I "$2/dq.py" "$2/dash-run/index.json" "K[\"logins:ok\"][\"n\"] == 1"' _ "$PY" "$T"
check "check: a connector not checked in this run" grep -q "^check: connectors not checked in this run: Gmail (last " "$T/run-export.out"
check "check: a row that reads signed in while its note asks for an account" grep -q "^check: reads signed in or connected, but its note asks for a sign-in or an account: Lever " "$T/run-export.out"
check "check: only a sign-in older than 3 days is named as old" sh -c 'grep "^check: sign-ins not checked for more than 3 days" "$1" | grep -q "Greenhouse" && ! grep "^check: sign-ins not checked for more than 3 days" "$1" | grep -q "Lever"' _ "$T/run-export.out"
cp "$T/logins.bak" "$H/apply/logins.json"
rm -f "$H/apply/usage-log.jsonl"
# The cross-check: one line per mismatch between the records and the page; it changes nothing and never fails a run.
files_of() { find "$1" -type f | sort | cksum; }
BEFORE=$(files_of "$H")
export_dash --check >"$T/check1.out" 2>&1
check "export --check: exits 0 and writes no file" sh -c '[ "$1" = 0 ] && [ "$2" = "$3" ]' _ "$?" "$BEFORE" "$(files_of "$H")"
has() { grep -q "^check: $1" "$T/${2:-check1.out}"; }
check "check: a second folder of one job" has "duplicate folder: D9 in pending and not-applied (the second is not counted)"
check "check: to-dos on a rejected job, with the command that removes them" has "to-do on an ended job: D3 (rejected $(day -3)), 2 to-do(s) -> track.py todo D3 done all"
check "check: to-dos on a job ended by its status, and on one where a later to-do stays" sh -c '
    grep -q "^check: to-do on an ended job: D8 (excluded), 1 to-do(s) -> track.py todo D8 done all" "$1" &&
    grep -q "^check: to-do on an ended job: D4 (declined .*), 1 to-do(s) -> track.py todo D4 done <n>" "$1"' _ "$T/check1.out"
check "check: the jobs with to-dos without since, in one line" has "to-dos without since: D5 (1) -> track.py todo"
check "check: a past due to-do and a past due step" sh -c '
    grep -q "^check: past due: D5 \"call the recruiter\", due $2" "$1" && grep -q "^check: past due: D1 step \"Questionnaire\", due $2" "$1"' \
    _ "$T/check1.out" "$(day -3)"
check "check: a job whose site is signed in and that nobody started" has "ready, not started: D6 (Workday .* Epsilon Co is signed in)"
check "check: a found job without an owner" has "no owner: D7 (found or pending; no to-do, question or session)"
check "check: sign-ins not checked for days" has "sign-ins not checked for more than 3 days: Greenhouse (6 days)"
check "check: an excluded employer without a source" has "excluded employers without a source: Eta Labs"
check "check: the last line counts them" grep -q "^check: 1[0-9] mismatches" "$T/check1.out"
cp -R "$T/flat" "$T/clean"
use "$T/clean"
track set F2 skipped "does not fit" >/dev/null 2>&1
build >/dev/null 2>&1
export_dash --check >"$T/check0.out" 2>&1
check "export --check on records that agree with the page: 0 mismatches, nothing else" sh -c '
    grep -q "^check: 0 mismatches" "$1" && [ "$(wc -l <"$1")" -eq 1 ]' _ "$T/check0.out"
use "$T/dash"
"$PY" -I "$S/logins.py" sync --env "$ENVF" >/dev/null 2>&1
check "logins sync: an excluded employer's own site is marked excluded, also from expired" dq "$H/apply/logins.json" \
    'next(r for r in R["logins"] if "Eta Labs" in r["id"])["status"] == "excluded" and next(r for r in R["logins"] if r["id"] == "Greenhouse")["status"] == "signed-in"'
# The older tracker shape, unsplit and split (built further up): the same rows from both.
for h in build-flat build-split; do
    use "$T/$h"
    track todo J1 add click "sign in to the site" since="$D0" >/dev/null 2>&1
    build >/dev/null 2>&1
    export_dash "$T/dash-$h" >/dev/null 2>&1
done
check "export on the older tracker shape: the to-do is a row" dq "$T/dash-build-flat/actions.json" 'K["J1:1"]["kind"] == "click" and K["J1:1"]["since"] != ""'
check "export: the same rows from a split tracker" sh -c 'for f in applications steps actions logins excluded sessions; do cmp -s "$1/$f.json" "$2/$f.json" || exit 1; done' \
    _ "$T/dash-build-flat" "$T/dash-build-split"
use "$T/dash"
questions add fact "What is your notice period?" key=notice_two job=D7 >/dev/null 2>&1
questions build "$T/dash-q" >/dev/null 2>&1
check "questions build: the status has the time of this check and the open count" sh -c '
    "$1" -I "$2/q.py" "$3" checked ne "" && "$1" -I "$2/q.py" "$3" open eq 1 && "$1" -I "$2/q.py" "$3" at eq ""' \
    _ "$PY" "$T" "$T/dash-q/status/run.json"
# --- sessions: the record from the app's list, the order to answer them, and their rows on the dashboard --------------
use "$T/dash"
sessions() { "$PY" -I "$S/sessions.py" "$@" --env "$ENVF"; }
SF="$H/apply/sessions.json"
check "export without a sessions record: an empty sessions file" dq "$OUT/sessions.json" 'R == []'
# The app's session list as its tool returns it; the second one archives a session, leaves one out and renames one.
cat >"$T/mklist.py" <<'PYEOF'
import json
import sys

home, out, second = sys.argv[1], sys.argv[2], sys.argv[3] in ("2", "3")
row = lambda i, name, title, cwd=home, **more: dict(  # noqa: E731
    {"sessionId": i, "name": name, "title": title, "cwd": cwd, "isArchived": False, "isRunning": False,
     "lastActivityAt": "2026-11-13T08:40:30.321Z", "link": "claude://example/" + i}, **more)
rows = [
    row("local_a1", "apply-delta", "You · Delta open questions" + (" (2 left)" if second else "")),
    row("local_b2", "study-acme", "You · Acme test study"),
    row("local_c3", "answers-zeta", "You · Zeta answers"),
    row("local_d4", "essays-eps", "You · Epsilon essays"),
    row("local_f6", "prep-old", "Done · Old prep", isArchived=second),
    row("local_g7", "job-coordinator", "Job search coordinator"),
    row("local_h8", "elsewhere", "You · Another project", cwd=home + "-other"),
]
if not second:
    rows.append(row("local_e5", "search-today", "Search sweep", isRunning=True))
if sys.argv[3] == "3":  # the second list again, with a session whose title names an employer that said no
    rows.append(row("local_i9", "beta-follow-up", "You · Beta Ltd follow-up"))
with open(out, "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False)
PYEOF
"$PY" -I "$T/mklist.py" "$H" "$T/list1.json" 1
sessions sync "$T/list1.json" >"$T/sync1.out" 2>&1
check "sessions sync: the main folder's sessions come in; the main session and another folder's do not" sh -c '
    grep -q "^6 sessions: 6 added" "$1" &&
    "$2" -I "$3/dq.py" "$4" "sorted(s[\"id\"] for s in R[\"sessions\"]) == [\"local_a1\", \"local_b2\", \"local_c3\", \"local_d4\", \"local_e5\", \"local_f6\"]"' \
    _ "$T/sync1.out" "$PY" "$T" "$SF"
check "sessions sync: the state is the title's prefix; a title without one is ready" dq "$SF" \
    '{s["name"]: s["state"] for s in R["sessions"]} == {"apply-delta": "you", "study-acme": "you", "answers-zeta": "you", "essays-eps": "you", "search-today": "ready", "prep-old": "done"}'
sessions set apply-delta jobs=D5 waits="your yes to send the form" >/dev/null 2>&1
sessions set study-acme jobs=D1,D2 >/dev/null 2>&1
sessions set answers-zeta jobs=D7 steps=1 >/dev/null 2>&1
sessions set essays-eps jobs=D6 >/dev/null 2>&1
check "sessions set: waits and jobs, the job in hand first" dq "$SF" \
    'next(s for s in R["sessions"] if s["name"] == "study-acme")["jobs"] == ["D1", "D2"] and next(s for s in R["sessions"] if s["name"] == "apply-delta")["waits"] == "your yes to send the form"'
check "sessions set: a job the tracker does not know is refused" sh -c '! "$1" -I "$2/sessions.py" set essays-eps jobs=NOPE --env "$3" >/dev/null 2>&1' \
    _ "$PY" "$S" "$ENVF"
check "sessions set: a session the record does not know is refused" sh -c '! "$1" -I "$2/sessions.py" set nobody state=done --env "$3" >/dev/null 2>&1' \
    _ "$PY" "$S" "$ENVF"
sessions show >"$T/show1.out" 2>&1
check "sessions show: urgent, then the fixed date, then the fewest steps left, then the rest" sh -c '
    grep -q "^ 1 you   apply-delta .*urgent" "$1" && grep -q "^ 2 you   study-acme .*by $2" "$1" &&
    grep -q "^ 3 you   answers-zeta .*1 step left" "$1" && grep -q "^ 4 you   essays-eps .*waiting since" "$1"' _ "$T/show1.out" "$(day 5)"
sessions set essays-eps tab=yes >/dev/null 2>&1
sessions show >"$T/show1b.out" 2>&1
check "sessions show: a form held open in a tab comes before the fewest steps left" sh -c '
    grep -q "^ 3 you   essays-eps .*form open in a tab" "$1" && grep -q "^ 4 you   answers-zeta .*1 step left" "$1"' _ "$T/show1b.out"
sessions set essays-eps tab=no >/dev/null 2>&1
check "sessions set: quick is refused and names steps= and tab=" sh -c '"$1" -I "$2/sessions.py" set essays-eps quick=yes --env "$3" 2>&1 | grep -q "steps=1"' \
    _ "$PY" "$S" "$ENVF"
cat >"$T/oldquick.py" <<'PYEOF'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    d = json.load(f)
for s in d["sessions"]:
    if s["name"] == "answers-zeta":
        s.pop("steps", None)
        s["quick"] = True
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(d, f)
PYEOF
"$PY" -I "$T/oldquick.py" "$SF"
sessions show >"$T/show1c.out" 2>&1
check "sessions show: a quick flag of an older record reads as one step left" grep -q "^ 3 you   answers-zeta .*1 step left" "$T/show1c.out"
sessions set answers-zeta steps=1 >/dev/null 2>&1
sessions order essays-eps >/dev/null 2>&1
sessions show >"$T/show2.out" 2>&1
check "sessions order: the named one first, the rule for the rest" sh -c '
    grep -q "^ 1 you   essays-eps .*set by Claude" "$1" && grep -q "^ 2 you   apply-delta" "$1"' _ "$T/show2.out"
sessions order auto >/dev/null 2>&1
check "sessions order auto: the rule alone again" dq "$SF" 'R["order"] == []'
sessions set study-acme state=done >/dev/null 2>&1
sessions show >"$T/show3.out" 2>&1
check "sessions show: a title whose prefix differs from the state is named for a rename; so is one without a prefix" sh -c '
    grep -q "^rename local_b2 to: Done .* Acme test study" "$1" && grep -q "^rename local_e5 to: Ready .* Search sweep" "$1" &&
    ! grep -q "^rename local_a1" "$1"' _ "$T/show3.out"
sessions set study-acme state=you >/dev/null 2>&1
"$PY" -I "$T/mklist.py" "$H" "$T/list2.json" 2
sessions sync "$T/list2.json" >"$T/sync2.out" 2>&1
check "sessions sync again: an archived one is dropped, a missing one stays and is named" sh -c '
    grep -q "1 archived and dropped, 1 not in the list" "$1" && grep -q "^dropped: prep-old" "$1" &&
    grep -q "^not in the list.*: search-today" "$1"' _ "$T/sync2.out"
check "sessions sync again: a known one takes its new title and keeps its state, jobs and waits" dq "$SF" \
    'len(R["sessions"]) == 5 and [(s["title"].endswith("(2 left)"), s["state"], s["jobs"]) for s in R["sessions"] if s["id"] == "local_a1"] == [(True, "you", ["D5"])]'
# On the dashboard: D6's to-do names its session; D5 gets an urgent one that names its session; D10 waits on the
# person with no to-do, in a session; D9 has an old to-do outside every session.
track add D10 "Iota BV" "Planner" "https://example.com/d10" >/dev/null 2>&1
track set D10 needs-person "waits on you" >/dev/null 2>&1
sessions set essays-eps jobs=D6,D10 >/dev/null 2>&1
track todo D6 add todo "approve the essays" session=local_d4 >/dev/null 2>&1
track todo D5 add urgent "type the emailed code" session=local_a1 where=pc >/dev/null 2>&1
track todo D9 add todo "an old row outside the sessions" since="$(day -9)" >/dev/null 2>&1
build >/dev/null 2>&1
export_dash "$OUT" >/dev/null 2>&1
check "export: one numbered row per waiting session, in the order, right after the urgent rows" dq "$OUT/actions.json" \
    '[r["key"] for r in R if r["kind"] == "session"] == ["s:local_a1", "s:local_b2", "s:local_c3", "s:local_d4"] and [r["rank"] for r in R if r["kind"] == "session"] == [1, 2, 3, 4] and all(r["kind"] == "urgent" for r in R[:R.index(K["s:local_a1"])])'
check "export: the session row has its title without the prefix, what it waits on, its jobs and its date" dq "$OUT/actions.json" \
    'K["s:local_a1"]["text"].startswith("Delta open questions (2 left)") and "your yes to send the form" in K["s:local_a1"]["text"] and K["s:local_b2"]["apps"] == ["D1", "D2"] and "by " in K["s:local_b2"]["text"]'
check "export: a to-do that names its session is on the session's row, not a row of its own" dq "$OUT/actions.json" \
    '"D6:1" not in K and "approve the essays" in K["s:local_d4"]["text"] and K["s:local_d4"]["apps"] == ["D6", "D10"]'
check "export: an urgent to-do that names its session stays a row of its own" dq "$OUT/actions.json" \
    'any(r["kind"] == "urgent" and r["text"] == "type the emailed code" for r in R)'
check "export: a job in a session has no row from its note and is not Claude's next" dq "$OUT/actions.json" \
    '"D10:todo" not in K and not any(r["kind"] == "queued" for r in R)'
check "export: a session that works alone is one in-progress row" dq "$OUT/actions.json" 'K["s:local_e5"]["kind"] == "working"'
check "export: the rows of a session's jobs come before an older row outside the sessions" dq "$OUT/actions.json" \
    'pos("the older to-do") < pos("the newer to-do") < pos("an old row outside the sessions")'
check "export: the sessions file has every session with its rank, state, jobs and why" dq "$OUT/sessions.json" \
    'len(R) == 5 and K["local_a1"]["rank"] == 1 and K["local_a1"]["apps"] == ["D5"] and K["local_a1"]["why"] == "urgent" and K["local_e5"]["rank"] == 0 and K["local_e5"]["state"] == "ready" and K["local_b2"]["why"].startswith("by ") and not K["local_a1"]["title"].startswith("You")'
check "export: the sessions are counted" dq "$OUT/index.json" \
    'K["sessions:you"]["n"] == 4 and K["sessions:ready"]["n"] == 1 and K["sessions:done"]["n"] == 0 and K["actions:session"]["n"] == 4'

# The cross-check on sessions and steps: a date that passed, jobs that all ended, a title that names an employer
# whose job ended, a title that differs from the state, a to-do naming an unknown session, an old sync, and a
# PIPELINE step the folders do not have yet.
"$PY" -I "$T/mklist.py" "$H" "$T/list3.json" 3
sessions sync "$T/list3.json" >/dev/null 2>&1
sessions set study-acme due="$(day -2)" >/dev/null 2>&1
sessions set answers-zeta jobs=D3 >/dev/null 2>&1
sessions set essays-eps state=done >/dev/null 2>&1
track todo D5 add todo "ask in the session" session=local_zz >/dev/null 2>&1
"$PY" -I -c '
import datetime, json, sys
home = sys.argv[1]
def patch(name, change):
    path = home + "/apply/" + name
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    change(data)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
patch("pipeline.json", lambda p: p["D1"]["steps"].append({"date": "2030-01-01", "name": "Final talk", "with": "the team"}))
patch("sessions.json", lambda s: s.update(synced=(datetime.datetime.now() - datetime.timedelta(days=3)).replace(microsecond=0).isoformat()))' "$H"
export_dash --check >"$T/check2.out" 2>&1
check "check: a session whose date is past" has "session study-acme: its date $(day -2) is past -> sessions.py set study-acme state=done" check2.out
check "check: a session whose jobs are all sent or ended" has "session answers-zeta: its jobs are all sent or ended" check2.out
check "check: a session whose title names an employer whose job ended" has "session beta-follow-up: the title names Beta Ltd, whose job D3 is rejected" check2.out
check "check: a session whose title differs from its state" has "session essays-eps: its title says you, its state is done -> rename it" check2.out
check "check: a to-do that names a session the record does not hold, and one whose session is done" sh -c '
    grep -q "^check: to-do of D5 names session local_zz, not in the record" "$1" &&
    grep -q "^check: to-do of D6 names session local_d4, which is done" "$1"' _ "$T/check2.out"
check "check: a to-do older than its job's sending" has "to-do set before D9 was sent: \"an old row outside the sessions\"" check2.out
check "check: a sessions record not synced for days" has "the sessions record was synced 3 days ago -> sessions.py sync" check2.out
check "check: PIPELINE has a step the folder does not" has "D1: 4 steps in PIPELINE, 3 in its folder -> build_app_folders.py" check2.out
# What to upload: every file at first; after --uploaded, only what changed.
export_dash "$T/up" >"$T/up1.out" 2>&1
check "export: with nothing recorded as on the page, every file is to upload" grep -q "^upload: index.json applications.json steps.json actions.json logins.json excluded.json sessions.json" "$T/up1.out"
export_dash --uploaded "$T/up" >"$T/up-rec.out" 2>&1
check "export --uploaded: records the seven files beside the tracker" sh -c 'grep -q "^recorded as on the page: index.json .* sessions.json" "$1" && [ -f "$2/apply/dashboard-uploads.json" ]' \
    _ "$T/up-rec.out" "$H"
track todo D5 add todo "one more thing" >/dev/null 2>&1
export_dash "$T/up" >"$T/up2.out" 2>&1
check "export after --uploaded: only the changed files are to upload" sh -c '
    grep "^upload:" "$1" | grep -q "actions.json" && ! grep "^upload:" "$1" | grep -q "logins.json" &&
    grep "^unchanged:" "$1" | grep -q "logins.json" && grep "^unchanged:" "$1" | grep -q "excluded.json"' _ "$T/up2.out"

# The two pages: each one's script must parse (node --check); without node the check is skipped, and says so.
if command -v node >/dev/null 2>&1; then
    for page in dashboard questions; do
        "$PY" -I -c 'import re, sys; open(sys.argv[2], "w", encoding="utf-8").write(re.search(r"<script>(.*)</script>", open(sys.argv[1], encoding="utf-8").read(), re.S).group(1))' \
            "$S/../templates/$page/index.html" "$T/page-$page.js"
        check "templates/$page/index.html: the page's script parses" node --check "$T/page-$page.js"
    done
else
    echo "SKIP the pages' scripts: node not found"
fi

# --- review fixes ----------------------------------------------------------------------------------------------------
track add J9 "Acme Corp" "Engineer" "https://boards.example.com/acme/jobs?gh_jid=111" >/dev/null 2>&1
printf '%s
' "https://boards.example.com/acme/jobs?gh_jid=222" "https://boards.example.com/acme/jobs?gh_jid=111&utm_source=mail" >"$T/links.txt"
searches seen --file "$T/links.txt" >"$T/seen2.out" 2>&1
check "searches seen --file: a job id in the query keeps two jobs apart; a tracking parameter does not" sh -c     'grep -q "^new .*gh_jid=222" "$1" && grep -q "^known .*gh_jid=111&utm_source=mail" "$1"' _ "$T/seen2.out"
check "a hand-set details path outside details/ is refused, and no file is written there" sh -c     '! "$1" -I "$2/track.py" set J1 submitted "x" details=../outside.json --env "$3" >/dev/null 2>&1 && [ ! -e "$4/outside.json" ]'     _ "$PY" "$S" "$ENVF" "$H"

echo "$PASSED passed, $FAILED failed"
[ "$FAILED" -eq 0 ]
