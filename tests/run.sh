#!/bin/sh
# Tests for the cenk-jobs scripts, on a made-up job search in a throwaway folder: one PASS or FAIL line per check.
# Why: the tracker's split into summary rows and detail files, the employer decisions and the small scripts must keep
# working on both tracker shapes, and no check may ever touch a real record.
# Usage: sh tests/run.sh          (PYTHON=<python> sh tests/run.sh to pick the interpreter)
# The profile is read through the base plugin cenk-base: CENK_BASE_SRC names its folder, else the session's
# CENK_BASE, else a cenk-base folder beside this repository's main checkout. Example: CENK_BASE_SRC=../cenk-base.
# Exit 0: every check passed. 1: at least one failed. 2: the tests could not start.
# Safety: every script runs with --env <throwaway folder>/<home>/job-search.env and JOB_SEARCH_ENV points there too,
# from a working folder inside the throwaway folder, so no real job-search.env can be found. CENK_HOME always names a
# folder inside the throwaway folder (use() sets each home's own) and the Claude config folder is a throwaway one, so
# no real profile is read or written; use() stops the tests when the cenk folder is anywhere else. The folder is
# removed on exit.
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
S="$HERE/../plugins/cenk-jobs/scripts"
[ -f "$S/track.py" ] || { echo "cannot find the scripts beside $HERE" >&2; exit 2; }
BASE_SRC=${CENK_BASE_SRC:-${CENK_BASE:-}}
if [ -z "$BASE_SRC" ]; then
    common=$(git -C "$HERE" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) &&
        BASE_SRC="$(dirname "$(dirname "$common")")/cenk-base"
fi
unset CENK_HOME CENK_PROFILE CENK_BASE
[ -f "${BASE_SRC:-}/lib/profile.py" ] || { echo "cannot find cenk-base (${BASE_SRC:-none}): set CENK_BASE_SRC" >&2; exit 2; }

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
CENK_BASE=$(win "$(cd "$BASE_SRC" && pwd)")
CENK_HOME="$T/no-cenk-home"
export CLAUDE_CONFIG_DIR CENK_BASE CENK_HOME
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

# Every script gets its env file explicitly; JOB_SEARCH_ENV is only the second line of defence. Each home's cenk
# folder is its profile/ (CENK_HOME); one outside the throwaway folder stops the tests before any script reads it.
use() {
    H=$1; ENVF="$H/job-search.env"; JOB_SEARCH_ENV=$ENVF; CENK_HOME="$H/profile"; export JOB_SEARCH_ENV CENK_HOME
    where=$("$PY" -I "$S/profilelib.py" --env "$ENVF" home | tr '\\' '/')
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
cp -R "$T/emp" "$T/emp-not2"
use "$T/emp-not2"
employer alias "Examplia Internet GmbH" "Examplia" >/dev/null 2>&1
employer alias --not "Examplia Internet GmbH" "Examplia Cloud" >/dev/null 2>&1
employer check "Examplia Cloud" >"$T/c-examplia4.json" 2>&1
check "alias --not: the other employer is not offered by any of its keys, an alias key included" \
    q "$T/c-examplia4.json" 0.possible len 0
use "$T/emp-not"

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

# An undecided level: recorded as such, never a silent direct; the person is asked and the verdict stays.
check "employer record: a flagged finding without a level is refused" sh -c '
    ! "$1" -I "$2/employer.py" record "Lambda Co" defence flagged fact="x" source=https://example.com/u0 --env "$3" >"$4" 2>&1 &&
    grep -q "level=<direct|indirect|undecided>" "$4"' _ "$PY" "$S" "$ENVF" "$T/undec0.out"
employer record "Lambda Co" defence flagged level=undecided fact="a reseller lists an army as a customer" source=https://example.com/u1 >/dev/null 2>&1
employer check "Lambda Co" >"$T/undec1.out" 2>&1
check "employer check: an undecided level leaves the verdict at allow and says ask" sh -c '
    grep -q "allow" "$1" && grep -q "ask: .*(undecided)" "$1" && ! grep -q "exclude" "$1"' _ "$T/undec1.out"
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
employer record "Lambda Two" defence flagged level=undecided fact="an unsettled reseller claim" source=https://example.com/u2 >/dev/null 2>&1
"$PY" -I "$S/usage.py" report --out "$T/lv-report.json" --env "$ENVF" >/dev/null 2>&1
check "usage run-due: due on a search day after its time with no run started; not before, not on a weekend" sh -c '
    "$1" -I "$2/usage.py" run-due at=2026-11-16T19:05 --env "$3" | grep -q "^due: today.s 19:00 run has not started" &&
    "$1" -I "$2/usage.py" run-due at=2026-11-16T18:30 --env "$3" | grep -q "^not due: today.s run is at 19:00" &&
    "$1" -I "$2/usage.py" run-due at=2026-11-15T19:05 --env "$3" | grep -q "^not due: no run on Sun"' _ "$PY" "$S" "$ENVF"
"$PY" -I "$S/employer.py" merge --from-checks --into "$T/lv-blacklist.json" --env "$ENVF" >/dev/null 2>&1
check "an undecided level is never shared: not in the usage report, not in a merge" sh -c '
    [ -s "$1" ] && [ -s "$2" ] && ! grep -q "unsettled reseller claim" "$1" && ! grep -q "unsettled reseller claim" "$2"' _ "$T/lv-report.json" "$T/lv-blacklist.json"
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
# 0.37.0: a question about a sent job stays open; "|" separates options with a comma; general questions.
questions add job "Withdraw from Acme?" job=F1 options="withdraw:Yes, withdraw it|keep:No, keep it" >/dev/null 2>&1
questions build "$T/qp-out" >/dev/null 2>&1
check "add: a question about a job already sent is kept open by the build, its comma labels whole" sh -c '
    "$1" -I "$2/q.py" "$3" "questions.job-f1-withdraw-from-acme.status" eq open &&
    "$1" -I "$2/q.py" "$3" "questions.job-f1-withdraw-from-acme.keep" eq True &&
    "$1" -I "$2/q.py" "$3" "questions.job-f1-withdraw-from-acme.options" len 2 &&
    "$1" -I "$2/q.py" "$3" "questions.job-f1-withdraw-from-acme.options.0.label" eq "Yes, withdraw it"' _ "$PY" "$T" "$QF"
questions add general "Which monitor holds the call?" >"$T/qp-gen.out" 2>&1
check "add general: a question with no job or key" sh -c 'grep -q "^q-which-monitor-holds-the-call -> no job$" "$1"' _ "$T/qp-gen.out"
rm -f "$T/qp-ans/answers/"*.json
echo '{"answer": "withdraw", "sent": "2026-11-17T10:00:00.000Z"}' >"$T/qp-ans/answers/job-f1-withdraw-from-acme.json"
questions record "$T/qp-ans" >"$T/qp-rec3.out" 2>&1
check "record: a keep question's button answer is kept and listed under act on, never as a form answer; build is named next" sh -c '
    "$1" -I "$2/q.py" "$3" "questions.job-f1-withdraw-from-acme.status" eq answered &&
    "$1" -I "$2/q.py" "$3" "questions.job-f1-withdraw-from-acme.answer.answer" eq "Yes, withdraw it" &&
    grep -q "^act on (.*): job-f1-withdraw-from-acme | Withdraw from Acme? | Yes, withdraw it | F1$" "$4" &&
    grep -q "^next, in this turn: questions.py build" "$4"' _ "$PY" "$T" "$QF" "$T/qp-rec3.out"
questions answer q-which-monitor-holds-the-call "Monitor 2" >/dev/null 2>&1
check "answer: a general question's answer is kept with a note" q "$QF" "questions.q-which-monitor-holds-the-call.answer.answer" eq "Monitor 2"
employer decide "Acme Corp" exclude >"$T/qp-decide.out" 2>&1
check "decide exclude: the employer's running applications are printed, for the withdrawal question" \
    grep -q "^running: F1 | Developer | sent .* | stage sent$" "$T/qp-decide.out"
check "keys: a board's name in brackets is no part of the employer's name" "$PY" -I -c '
import sys; sys.path.insert(0, sys.argv[1]); import employerlib as el
assert el.keys("Examplia (ashby)") == {"examplia"} and "aws" in el.keys("Amazon (AWS)")' "$S"

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
for name in ("CENK_HOME", "CENK_PROFILE", "CLAUDE_PLUGIN_OPTION_PROFILE_PATH"):
    os.environ.pop(name, None)


def make(path, text="{}"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


drive = os.path.join(base, "d1", "My Drive")
os.makedirs(drive, exist_ok=True)
cfg = os.path.join(base, "config")
own = make(os.path.join(base, "home", "own", "profile.json"))
env = jsenv.load(make(os.path.join(base, "home", "job-search.env"), "PROFILE=own/profile.json\n"))
fails = []


def expect(name, got, want):
    if os.path.normcase(str(got)) != os.path.normcase(str(want)):
        fails.append(f"{name}: got {got}, want {want}")


found = pl.load(env, roots=[drive], claude_dir=cfg)
expect("an old PROFILE line is read as an old place", found["path"], own)
expect("an old PROFILE line: old", found["old"], True)
expect("an old PROFILE line: the cenk folder is suggested", found["suggested"], os.path.join(drive, "cenk"))
if "create copies it" not in pl.move_message(found):
    fails.append("the move message names create")
new = make(os.path.join(drive, "cenk", "profile.json"))
expect("the cenk folder's profile before an old PROFILE line", pl.locate(env, roots=[drive], claude_dir=cfg)["path"],
       new)
os.environ["CENK_HOME"] = os.path.join(base, "named")
expect("CENK_HOME before everything", pl.locate(env, roots=[drive], claude_dir=cfg)["path"],
       os.path.join(base, "named", "profile.json"))
print("\n".join(fails))
sys.exit(1 if fails else 0)
PYEOF
check "profile lookup: cenk-base's order; an old PROFILE line in job-search.env only as an old place" \
    "$PY" -I "$T/lookup.py" "$T/lk"
CENK_BASE= "$PY" -I "$S/profilelib.py" path >"$T/nobase.out" 2>&1
rc=$?
check "profilelib without CENK_BASE: exits 1, says cenk-base is not loaded and how to install it" sh -c '
    [ "$1" -eq 1 ] && grep -q "cenk-base is not loaded" "$2" && grep -q "claude plugin install cenk-jobs@cenk" "$2"' \
    _ "$rc" "$T/nobase.out"
mkdir -p "$T/oldbase/lib"
cp "$BASE_SRC/lib/profile.py" "$T/oldbase/lib/"
CENK_BASE=$(win "$T/oldbase") "$PY" -I "$S/profilelib.py" coordinator >"$T/oldbase.out" 2>&1
rc=$?
check "profilelib coordinator with a cenk-base older than 0.2.0: exits 1, names 0.2.0 and the update line" sh -c '
    [ "$1" -eq 1 ] && grep -q "cenk-base 0.2.0 or later" "$2" && grep -q "claude plugin update cenk-base@cenk" "$2"' \
    _ "$rc" "$T/oldbase.out"
CENK_BASE= "$PY" -I "$S/profilelib.py" coordinator >"$T/nobase-coord.out" 2>&1
rc=$?
check "profilelib coordinator without CENK_BASE: exits 1, says cenk-base is not loaded" sh -c '
    [ "$1" -eq 1 ] && grep -q "cenk-base is not loaded" "$2"' _ "$rc" "$T/nobase-coord.out"
check "profilelib coordinator: prints the shared rules file of cenk-base" sh -c '
    p=$("$1" -I "$2/profilelib.py" coordinator) && [ -f "$p" ] && grep -q "^# Coordinator rules" "$p"' _ "$PY" "$S"

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
mkdir -p "$T/gd-drive/My Drive/cenk"
cp "$T/gd/profile/profile.json" "$T/gd-drive/My Drive/cenk/profile.json"
use "$T/gd"
CENK_HOME="$T/gd-drive/My Drive/cenk" pf erase private.diet >"$T/gd-erase.out" 2>&1
check "profile erase in a Google Drive: says the earlier versions still hold the value, and how to delete them" grep -q "Manage versions" "$T/gd-erase.out"

cp -R "$T/flat" "$T/np"
rm -rf "$T/np/profile"
use "$T/np"
pf set person.name '"Jane Doe"' >"$T/np-set.out" 2>&1
rc=$?
check "profile set with no profile: exits 1, creates nothing, says to ask the person" sh -c '
    [ "$1" -eq 1 ] && [ ! -e "$2/profile" ] && grep -q "Ask the person whether to create it there" "$3"' _ "$rc" "$H" "$T/np-set.out"
"$PY" -I "$S/check_setup.py" --needs --env "$ENVF" >"$T/np-needs.out" 2>&1
check "check_setup --needs: no profile yet, with the place to suggest" grep -q "^profile: none yet: ask the person where to create it" "$T/np-needs.out"
questions add fact "Any dietary needs?" key=diet personal=yes job=F2 >/dev/null 2>&1
questions answer fact-diet "None." >"$T/np-q.out" 2>&1
check "answer with no profile: not recorded, listed under no profile, nothing created" sh -c '
    grep -q "^no profile.*fact-diet" "$1" && "$2" -I "$3/q.py" "$4/apply/questions.json" questions.fact-diet.status eq open &&
    [ ! -e "$4/profile" ] && [ ! -e "$4/career-records/personal.json" ]' _ "$T/np-q.out" "$PY" "$T" "$H"
pf create "$H/elsewhere" >"$T/np-create1.out" 2>&1
rc=$?
check "profile create: refused in another folder than CENK_HOME names" sh -c '
    [ "$1" -eq 1 ] && [ ! -e "$2/elsewhere" ] && grep -q "CENK_HOME names" "$3"' _ "$rc" "$H" "$T/np-create1.out"
pf create "$H/profile" >/dev/null 2>&1
rc=$?
check "profile create: profile.json in the cenk folder, empty, without touching job-search.env" sh -c '
    [ "$1" -eq 0 ] && [ "$(cat "$2/profile/profile.json")" = "{}" ] && ! grep -q "PROFILE=" "$2/job-search.env"' _ "$rc" "$H"
pf create "$H/profile" >/dev/null 2>&1
rc=$?
check "profile create: refused when a profile exists" [ "$rc" -eq 1 ]
CENK_BASE= "$PY" -I "$S/check_setup.py" --needs --env "$ENVF" >"$T/nobase-needs.out" 2>&1
check "check_setup --needs without cenk-base: names it and the install line" sh -c '
    grep -q "^profile: cenk-base is not loaded" "$1" && grep -q "claude plugin install cenk-jobs@cenk" "$1"' _ "$T/nobase-needs.out"
mkdir -p "$T/old-base/lib"
echo 'ABSENT = object()' >"$T/old-base/lib/profile.py"
CENK_BASE="$T/old-base" "$PY" -I "$S/check_setup.py" --needs --env "$ENVF" >"$T/oldbase-needs.out" 2>&1
rc=$?
check "check_setup --needs with a cenk-base that lacks what cenk-jobs uses: no traceback, names the cause" sh -c '
    [ "$1" -eq 0 ] && grep -q "^profile: .*cannot be used (no ProfileError" "$2" && ! grep -q Traceback "$2"' \
    _ "$rc" "$T/oldbase-needs.out"

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
# A sent job shows only the letter its sent record names: a prepared one for a form with no letter field is left out.
cp "$H/apply/targets.json" "$T/targets-letter.bak"
mkdir -p "$H/apply/letters"
echo "made-up letter" >"$H/apply/letters/prepared-letter.pdf"
cat >"$T/mkletter.py" <<'PYEOF'
import json
import sys

path, key = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as f:
    d = json.load(f)
for j in d["jobs"]:
    if j["id"] == "D9":
        j[key] = "apply/letters/prepared-letter.pdf"
with open(path, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
PYEOF
"$PY" -I "$T/mkletter.py" "$H/apply/targets.json" letter_pdf
build >/dev/null 2>&1
SENTDIR=$(ls -d "$H"/job-applications/pending/*"Theta AG - Manager" | head -n 1)
check "build_app_folders: a sent job whose record names no letter keeps its prepared one, as before" sh -c '
    grep -q "Cover letter:\*\* \[prepared-letter.pdf\]" "$1/overview.md" && [ -f "$1/prepared-letter.pdf" ]' _ "$SENTDIR"
rm -f "$SENTDIR/prepared-letter.pdf"
track set D9 submitted "sent, the form had no letter field" letter=none >/dev/null 2>&1
build >/dev/null 2>&1
check "build_app_folders: letter=none in the sent record lists no letter and copies none" sh -c '
    grep -q "Cover letter:\*\* none sent (the form had no letter field)" "$1/overview.md" && [ ! -f "$1/prepared-letter.pdf" ]' _ "$SENTDIR"
cp "$T/targets-letter.bak" "$H/apply/targets.json"
rm -f "$SENTDIR/prepared-letter.pdf" "$H/apply/letters/prepared-letter.pdf"
build >/dev/null 2>&1
OUT="$T/dash-out"
# 0.37.0: the calendar and the page against the records. D1's step 2 is in 5 days; D3 (Beta Ltd) was rejected.
cat >"$T/mkcal.py" <<'PYEOF'
import datetime
import json
import sys

day = lambda n: (datetime.date.today() + datetime.timedelta(days=n)).isoformat()  # noqa: E731
ev = lambda i, summary, start, desc="", colour="3": {"id": i, "summary": summary, "description": desc,  # noqa: E731
                                                   "colorId": colour, "start": start, "end": start}
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump({"events": [ev("e1", "Job search · Beta Ltd: reply due", {"date": day(2)}, "[job-search: D3 due]"),
                          ev("e2", "Lunch", {"date": day(1)}, colour="")]}, f)
with open(sys.argv[2], "w", encoding="utf-8") as f:
    json.dump({"events": [ev("e3", "Online test with Acme Corp", {"date": day(5)})]}, f)
PYEOF
"$PY" -I "$T/mkcal.py" "$T/cal-1.json" "$T/cal-2.json"
export_dash --check --calendar "$T/cal-1.json" >"$T/cal-1.out" 2>&1
check "export --calendar: an event of an ended job, and a coming step with no event, are named; another event is not" sh -c '
    grep -q "^check: calendar: .* \"Job search · Beta Ltd: reply due\" is for D3 Beta Ltd, which ended (rejected " "$1" &&
    grep -q "^check: calendar: no event for D1 Acme Corp step 2 \"Online test\" on " "$1" && ! grep -q "Lunch" "$1"' _ "$T/cal-1.out"
export_dash --check --calendar "$T/cal-2.json" >"$T/cal-2.out" 2>&1
check "export --calendar: an invitation titled with the company on the step's date counts as its event" sh -c '
    ! grep -q "calendar:" "$1" && grep -q "mismatches$" "$1"' _ "$T/cal-2.out"
check "calendar check: an event at another time than the step, by its job tag" "$PY" -I -c '
import sys; sys.path.insert(0, sys.argv[1]); import export_dashboard as x
env = {"CALENDAR_COLOR": "3"}
jobs = [{"id": "J1", "company": "Acme", "status": "submitted"}]
pipe = {"J1": {"stage": "approved", "steps": [{"date": "2026-12-01", "time": "10:00-11:00", "name": "Interview"}]}}
cal = {"events": [{"id": "a", "summary": "Job search · Acme interview", "colorId": "3", "description": "[job-search: J1 step 1]",
                   "start": {"dateTime": "2026-12-01T09:00:00"}}]}
out = x.calendar_checks(env, cal, jobs, pipe, "2026-11-20")
assert len(out) == 1 and "is at 10:00 in PIPELINE, its event at 09:00" in out[0], out
cal["events"][0]["start"]["dateTime"] = "2026-12-01T10:00:00"
assert x.calendar_checks(env, cal, jobs, pipe, "2026-11-20") == []
del pipe["J1"]["steps"][0]["time"]
assert x.calendar_checks(env, cal, jobs, pipe, "2026-11-20") == []' "$S"
check "outcome check: a rejection whose reason says the role was filled reads closed; a plain no does not" "$PY" -I -c '
import sys; sys.path.insert(0, sys.argv[1]); import export_dashboard as x
jobs = [{"id": "J1", "company": "Acme"}, {"id": "J2", "company": "Beta"}, {"id": "J3", "company": "Gamma"}]
pipe = {"J1": {"stage": "rejected", "reason": "email: the position has been filled"},
        "J2": {"stage": "rejected", "reason": "we will not move forward with you"},
        "J3": {"stage": "closed", "reason": "the role was filled"}}
out = x.outcome_checks(jobs, pipe)
assert len(out) == 1 and out[0].startswith("recorded rejected, its reason reads closed: J1 Acme"), out' "$S"
cp "$S/../templates/dashboard/index.html" "$T/page-now.html"
sed 's/data-tab="sessions"/data-tab="old"/' "$S/../templates/dashboard/index.html" >"$T/page-old.html"
check "export --page: the plugin's template passes; an older copy is the first check line" sh -c '
    "$1" -I "$2/export_dashboard.py" --check --page "$3" --env "$5" | grep -qv "dashboard page is not" &&
    ! "$1" -I "$2/export_dashboard.py" --check --page "$3" --env "$5" | grep -q "dashboard page is not" &&
    "$1" -I "$2/export_dashboard.py" --check --page "$4" --env "$5" | head -n 1 | grep -q "^check: the dashboard page is not the plugin.s template"' \
    _ "$PY" "$S" "$T/page-now.html" "$T/page-old.html" "$ENVF"
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
check "export: a found job nobody owns is a Do now row of its own: the gap is never silent" dq "$OUT/actions.json" \
    'K["D7:noowner"]["kind"] == "todo" and K["D7:noowner"]["text"].startswith("Waits on you: unknown, ask Claude")'
check "export: the new kinds are counted" dq "$OUT/index.json" 'K["actions:late"]["n"] == 2 and K["actions:queued"]["n"] == 1'
check "export: an excluded employer's own site is left out, whatever its state" sh -c '
    "$1" -I "$2/dq.py" "$3/logins.json" "not any(\"Eta Labs\" in r[\"id\"] for r in R) and len(R) == 3" &&
    "$1" -I "$2/dq.py" "$3/actions.json" "not any(r[\"key\"].startswith(\"login:\") for r in R)"' _ "$PY" "$T" "$OUT"
check "export: a sign-in checked 6 days ago is stale and not counted as working" sh -c '
    "$1" -I "$2/dq.py" "$3/logins.json" "K[\"Greenhouse\"][\"stale\"] == \"yes\" and K[\"Lever\"][\"stale\"] == \"\"" &&
    "$1" -I "$2/dq.py" "$3/index.json" "\"logins:ok\" not in K"' _ "$PY" "$T" "$OUT"
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
    "$1" -I "$2/dq.py" "$2/dash-run/logins.json" "sum(1 for r in R if r[\"status\"] in (\"signed-in\", \"connected\") and not r[\"stale\"]) == 1"' _ "$PY" "$T"
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
check "check: a past due to-do, and a past due step (records.py steps, with its command)" sh -c '
    grep -q "^check: past due: D5 \"call the recruiter\", due $2" "$1" &&
    grep -q "^check: steps: [0-9]* past step(s) not done: .*D1 step [0-9]* \"Questionnaire\" due $2.* -> track.py step <id> done <n> <date>" "$1"' \
    _ "$T/check1.out" "$(day -3)"
check "check: a job whose site is signed in and that nobody started" has "ready, not started: D6 (Workday .* Epsilon Co is signed in)"
check "check: a found job without an owner" has "no owner: D7 (found or pending; no to-do, question or session)"
check "check: sign-ins not checked for days" has "sign-ins not checked for more than 3 days: Greenhouse (6 days)"
check "check: an excluded employer without a source" has "excluded employers without a source: Eta Labs"
check "check: the last line counts them" grep -q "^check: 1[0-9] mismatches" "$T/check1.out"
cp -R "$T/flat" "$T/clean"
use "$T/clean"
track set F2 skipped "does not fit" >/dev/null 2>&1
# F1 waits on the person: with a to-do that says what, the records agree (0.42.0: without one it is a check line).
track wait F1 needs-person "a phone number" >/dev/null 2>&1
build >/dev/null 2>&1
export_dash --check >"$T/check0.out" 2>&1
check "export --check on records that agree with the page: 0 mismatches, nothing else" sh -c '
    grep -q "^check: 0 mismatches" "$1" && [ "$(wc -l <"$1")" -eq 1 ] || { cat "$1"; false; }' _ "$T/check0.out"
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
sessions set essays-eps state=done >"$T/held-done.out" 2>&1
check "sessions set 0.46.1: state=done is refused while tab=yes, and nothing is written" sh -c '
    grep -q "holds a filled form (tab=yes)" "$1" && "$2" -I "$3/dq.py" "$4" \
    "[s[\"state\"] for s in R[\"sessions\"] if s.get(\"name\") == \"essays-eps\"] == [\"you\"]"' _ "$T/held-done.out" "$PY" "$T" "$SF"
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
# prep-old still held a form when the app archived it (written by hand: set refuses tab=yes on a done session).
"$PY" -I -c 'import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
[s.update(tab=True) for s in d["sessions"] if s.get("name") == "prep-old"]
json.dump(d, open(sys.argv[1], "w", encoding="utf-8"))' "$SF"
sessions sync "$T/list2.json" >"$T/sync2.out" 2>&1
check "sessions sync again: an archived one is dropped, a missing one stays and is named" sh -c '
    grep -q "1 archived and dropped, 1 not in the list" "$1" && grep -q "^dropped: prep-old" "$1" &&
    grep -q "^not in the list.*: search-today" "$1"' _ "$T/sync2.out"
check "sessions sync 0.46.1: one archived while holding a form is named on its own line" \
    grep -q "^archived while holding a filled form: prep-old (jobs .*); its tab is gone" "$T/sync2.out"
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
    'not any(k.startswith("sessions:") for k in K) and K["actions:session"]["n"] == 4 and K["actions:working"]["n"] == 1'

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
check "export --uploaded: without the uploaded files it is refused and records nothing" sh -c '
    ! "$1" -I "$2/export_dashboard.py" --uploaded "$3" --env "$4" >"$5" 2>&1 && grep -q "name the files you uploaded" "$5" &&
    [ ! -f "$6/apply/dashboard-uploads.json" ]' _ "$PY" "$S" "$T/up" "$ENVF" "$T/up-bare.out" "$H"
export_dash --uploaded "$T/up" index.json actions.json >"$T/up-two.out" 2>&1
export_dash "$T/up" >"$T/up1b.out" 2>&1
check "export --uploaded <files>: only the files named are on the page; the others are still to upload" sh -c '
    grep -q "^recorded as on the page: index.json actions.json$" "$1" && grep -q "^never recorded as uploaded: applications.json .* sessions.json" "$1" &&
    grep "^upload:" "$2" | grep -q "sessions.json" && grep "^upload:" "$2" | grep -q "logins.json" &&
    ! grep "^upload:" "$2" | grep -q "actions.json"' _ "$T/up-two.out" "$T/up1b.out"
check "export --uploaded: a name that is no export file is refused" sh -c '
    ! "$1" -I "$2/export_dashboard.py" --uploaded "$3" notes.json --env "$4" >"$5" 2>&1 && grep -q "not a file of the export: notes.json" "$5"' \
    _ "$PY" "$S" "$T/up" "$ENVF" "$T/up-bad.out"
export_dash --uploaded "$T/up" all >"$T/up-rec.out" 2>&1
check "export --uploaded all: records the seven files beside the tracker" sh -c 'grep -q "^recorded as on the page: index.json .* sessions.json" "$1" && [ -f "$2/apply/dashboard-uploads.json" ]' \
    _ "$T/up-rec.out" "$H"
track todo D5 add todo "one more thing" >/dev/null 2>&1
export_dash "$T/up" >"$T/up2.out" 2>&1
check "export after --uploaded: only the changed files are to upload" sh -c '
    grep "^upload:" "$1" | grep -q "actions.json" && ! grep "^upload:" "$1" | grep -q "logins.json" &&
    grep "^unchanged:" "$1" | grep -q "logins.json" && grep "^unchanged:" "$1" | grep -q "excluded.json"' _ "$T/up2.out"

# The pages: each one's script must parse (node --check); without node the check is skipped, and says so.
if command -v node >/dev/null 2>&1; then
    for page in dashboard questions cheat-sheet; do
        "$PY" -I -c 'import re, sys; open(sys.argv[2], "w", encoding="utf-8").write(re.search(r"<script>(.*)</script>", open(sys.argv[1], encoding="utf-8").read(), re.S).group(1))' \
            "$S/../templates/$page/index.html" "$T/page-$page.js"
        check "templates/$page/index.html: the page's script parses" node --check "$T/page-$page.js"
    done
else
    echo "SKIP the pages' scripts: node not found"
fi

# --- the cheat-sheet page -----------------------------------------------------------------------------------------------
cheat() { "$PY" -I "$S/cheat_sheet.py" "$@" --env "$ENVF"; }
check "cheat_sheet: without a keywords.md it says who writes it" sh -c '
    ! "$1" -I "$2/cheat_sheet.py" D1 --env "$3" >"$4" 2>&1 && grep -q "no keywords.md for step 2 of D1" "$4"' _ "$PY" "$S" "$ENVF" "$T/cs0.out"
CSDIR=$(ls -d "$H"/job-applications/approved/*"Acme Corp - Engineer"/02\ * | head -n 1)
cat >"$CSDIR/keywords.md" <<'EOF'
# Numbers
- 12 engineers, **3 teams**
- <uptime> 99.9

## Stack
Java 21, Kafka
EOF
cheat D1 >"$T/cs1.out" 2>&1
check "cheat_sheet: the next open step, three columns by default, blocks and lines counted" sh -c '
    grep -q "cheat-sheet-wide.html$" "$1" && grep -q "^step 2: Online test.* | spot top, 3 columns | 2 blocks, 3 lines" "$1"' _ "$T/cs1.out"
check "cheat_sheet: the page holds the blocks, bold, escaped text, the columns and the email-free top line" sh -c '
    grep -q "column-count: 3" "$1" && grep -q "<h2>Numbers</h2>" "$1" && grep -q "<b>3 teams</b>" "$1" &&
    grep -q "&lt;uptime&gt; 99.9" "$1" && grep -q "<p>Java 21, Kafka</p>" "$1" && grep -q "<b>Online test</b>" "$1" &&
    ! grep -q "__[A-Z]*__" "$1" && ! grep -q "mail.example.com" "$1"' _ "$CSDIR/cheat-sheet-wide.html"
cheat D1 spot=corner >"$T/cs2.out" 2>&1
check "cheat_sheet spot=: two columns in a corner, and the spot is kept in job-search.env" sh -c '
    grep -q "column-count: 2" "$1" && grep -q "^CHEAT_SHEET_SPOT=corner$" "$2"' _ "$CSDIR/cheat-sheet-wide.html" "$ENVF"
cheat D1 >"$T/cs3.out" 2>&1
check "cheat_sheet: the kept spot is used the next time" grep -q "spot corner, 2 columns" "$T/cs3.out"
printf '# __BLOCKS__ and __TOP__\n- a line with __COLUMNS__\n' >"$CSDIR/keywords.md"
cheat D1 >/dev/null 2>&1
check "cheat_sheet: a line that holds a placeholder's text is shown as it is" sh -c '
    grep -q "<h2>__BLOCKS__ and __TOP__</h2>" "$1" && grep -q "<p>a line with __COLUMNS__</p>" "$1" &&
    [ "$(grep -c "class=\"block\"" "$1")" -eq 1 ]' _ "$CSDIR/cheat-sheet-wide.html"
check "cheat_sheet: a spot's place on a monitor, and the page goes on a monitor other than the call's" "$PY" -I -c '
import sys; sys.path.insert(0, sys.argv[1]); import cheat_sheet as c
a, b = (-1920, 0, 1920, 1080, False), (0, 0, 3440, 1400, True)
assert c.place(b, "top") == (0, 0, 3440, 700) and c.place(a, "corner") == (-960, 0, 960, 540)
assert c.page_monitor([a, b], 1) == b and c.page_monitor([a, b], 2) == a and c.page_monitor([b], 1) == b
assert c.page_monitor([a, b], 0) == a and c.page_monitor([], 1) is None' "$S"
check "cheat_sheet call=: a monitor number only, kept in job-search.env" sh -c '
    ! "$1" -I "$2/cheat_sheet.py" D1 call=left --env "$3" >/dev/null 2>&1 &&
    "$1" -I "$2/cheat_sheet.py" D1 call=2 --env "$3" >/dev/null 2>&1 && grep -q "^CALL_MONITOR=2$" "$3"' _ "$PY" "$S" "$ENVF"
check "cheat_sheet: an unknown spot is refused" sh -c '! "$1" -I "$2/cheat_sheet.py" D1 spot=middle --env "$3" >/dev/null 2>&1' _ "$PY" "$S" "$ENVF"
sed '/^CHEAT_SHEET_SPOT=/d; /^CALL_MONITOR=/d' "$ENVF" >"$T/env.tmp" && cp "$T/env.tmp" "$ENVF"
rm -f "$CSDIR/keywords.md" "$CSDIR/cheat-sheet-wide.html"

# --- 0.34.0: the funnel, collect_postings, variants, token_report -------------------------------------------------------
mkhome "$T/s34" old
use "$T/s34"
# Only an excluded employer stops: a "discuss" employer's and an unscreened employer's prepared jobs are attached.
cat >"$T/s34-journal.jsonl" <<'EOF'
{"type": "started", "agentId": "b1", "label": "prep-jobs:Gamma Inc"}
{"type": "result", "agentId": "b1", "result": {"jobs": [{"id": "J3", "action": "apply", "platform": "Workable", "title": "Designer", "apply_url": "https://example.com/j3", "needs": [], "reason": "fits"}]}}
{"type": "started", "agentId": "b2", "label": "prep-fit:Epsilon Co"}
{"type": "result", "agentId": "b2", "result": {"jobs": [{"id": "E1", "action": "skip", "title": "Tester", "apply_url": "https://example.com/e1", "reason": "the role is junior"}]}}
EOF
track sync "$T/s34-journal.jsonl" >"$T/s34-sync.out" 2>&1
check "sync: a discuss employer's prepared job is attached; its verdict stays discuss" sh -c '
    "$1" -I "$2/q.py" "$3/apply/targets.json" "companies.name=Gamma Inc.verdict" eq discuss &&
    "$1" -I "$2/q.py" "$3/apply/targets.json" "companies.name=Gamma Inc.jobs.0.prep.action" eq apply' _ "$PY" "$T" "$H"
check "sync: an employer the run did not screen gets its fit result (prep-fit:) when no file was written" \
    q "$H/apply/targets.json" "companies.name=Epsilon Co.jobs.0.prep.action" eq skip
# A "discuss" employer is asked about only once it answers with a hiring step.
echo "EMPLOYER_RULES=apply/employer-rules.json" >>"$ENVF"
cat >"$H/apply/employer-rules.json" <<'EOF'
{"categories": {"defence": {"action": "discuss", "indirect": "discuss"}}, "changes": []}
EOF
cat >"$H/apply/employer-checks.json" <<'EOF'
{"employers": {"Gamma Inc": {"checks": {"defence": {"status": "flagged", "level": "direct", "fact": "Gamma sells to an army",
                                                  "source_url": "https://example.com/g1", "checked": "2026-11-01"}}}}}
EOF
cat >"$T/s34-journal2.jsonl" <<'EOF'
{"type": "started", "agentId": "c1", "label": "excl-screen:Epsilon Co"}
{"type": "result", "agentId": "c1", "result": {"verdict": "allow", "hits": [], "ties": [], "checks": [{"category": "defence", "status": "flagged", "level": "direct", "fact": "Epsilon sells to an army", "source_url": "https://example.com/e9"}], "notes": "made up"}}
{"type": "started", "agentId": "c2", "label": "prep-jobs:Epsilon Co"}
{"type": "result", "agentId": "c2", "result": {"jobs": [{"id": "E1", "action": "apply", "title": "Tester", "apply_url": "https://example.com/e1", "needs": [], "reason": "fits"}]}}
EOF
track sync "$T/s34-journal2.jsonl" >/dev/null 2>&1
check "sync: a screened employer the rules set to discuss keeps its prepared job and verdict discuss" sh -c '
    "$1" -I "$2/q.py" "$3/apply/targets.json" "companies.name=Epsilon Co.verdict" eq discuss &&
    "$1" -I "$2/q.py" "$3/apply/targets.json" "companies.name=Epsilon Co.jobs.0.prep.action" eq apply' _ "$PY" "$T" "$H"
questions build "$T/s34-q1" >/dev/null 2>&1
check "questions build: no question about a discuss employer that has not answered" sh -c '[ ! -f "$1/questions/ask-gamma-inc.json" ]' _ "$T/s34-q1"
track set J3 submitted "sent in the test" >/dev/null 2>&1
echo '{"J3": {"stage": "approved", "steps": []}}' >"$H/apply/pipeline.json"
questions build "$T/s34-q2" >/dev/null 2>&1
check "questions build: the employer answered with a hiring step: Allow, or exclude? is asked" \
    sh -c 'ls "$1/questions" | grep -q "^ask-gamma"' _ "$T/s34-q2"

# collect_postings.py: the searches a script can read, filtered, minus the tracker, added with found_by.
mkhome "$T/cp" flat
use "$T/cp"
check "searches add: a board source without board= is refused" sh -c '
    ! "$1" -I "$2/searches.py" add "Acme jobs" engineer source=greenhouse --env "$3" >/dev/null 2>&1 &&
    ! "$1" -I "$2/searches.py" add "Acme jobs" engineer source=monster board=x --env "$3" >/dev/null 2>&1' _ "$PY" "$S" "$ENVF"
searches add "Acme jobs" "engineer" source=greenhouse board=acme place="Rome" >/dev/null 2>&1
searches add LinkedIn "developer" source=linkedin place="Rome" >/dev/null 2>&1
searches add "Beta careers" "analyst" alert=no >/dev/null 2>&1
mkdir -p "$T/cp-src"
cat >"$T/cp-src/greenhouse-acme.json" <<'EOF'
{"jobs": [
 {"title": "Senior Engineer", "location": {"name": "Rome, Italy"}, "absolute_url": "https://boards.example.com/acme/jobs/1", "first_published": "2026-11-12T08:00:00Z"},
 {"title": "Sales Lead", "location": {"name": "Rome, Italy"}, "absolute_url": "https://boards.example.com/acme/jobs/2", "first_published": "2026-11-12T08:00:00Z"},
 {"title": "Engineer", "location": {"name": "Berlin"}, "absolute_url": "https://boards.example.com/acme/jobs/3", "first_published": "2026-11-12T08:00:00Z"},
 {"title": "Platform Engineer", "location": {"name": "Remote"}, "absolute_url": "https://boards.example.com/acme/jobs/4", "first_published": "2026-11-12T08:00:00Z"}
]}
EOF
cat >"$T/cp-src/linkedin-search.html" <<'EOF'
<li><div class="base-card relative"><a class="base-card__full-link absolute" href="https://www.linkedin.com/jobs/view/1234567890/?trk=x">x</a>
<h3 class="base-search-card__title">Java Developer</h3><h4 class="base-search-card__subtitle"><a>Beta Ltd</a></h4>
<span class="job-search-card__location">Rome, Lazio</span><time datetime="2026-11-12">1 day ago</time></div></li>
<li><div class="base-card relative"><a class="base-card__full-link absolute" href="https://www.linkedin.com/jobs/view/2222222222/?trk=y">y</a>
<h3 class="base-search-card__title">Backend Developer</h3><h4 class="base-search-card__subtitle"><a>Zeta Works</a></h4>
<span class="job-search-card__location">Rome, Lazio</span><time datetime="2026-11-12">1 day ago</time></div></li>
EOF
# A US-remote posting is left out; a bare "Remote" one passes; REMOTE_REGIONS lets "Remote, EU" through.
cat >"$T/cp-src/greenhouse-acme.json" <<'EOF'
{"jobs": [
 {"title": "Senior Engineer", "location": {"name": "Rome, Italy"}, "absolute_url": "https://boards.example.com/acme/jobs/1", "first_published": "2026-11-12T08:00:00Z"},
 {"title": "Sales Lead", "location": {"name": "Rome, Italy"}, "absolute_url": "https://boards.example.com/acme/jobs/2", "first_published": "2026-11-12T08:00:00Z"},
 {"title": "Engineer", "location": {"name": "Berlin"}, "absolute_url": "https://boards.example.com/acme/jobs/3", "first_published": "2026-11-12T08:00:00Z"},
 {"title": "Platform Engineer", "location": {"name": "Remote"}, "absolute_url": "https://boards.example.com/acme/jobs/4", "first_published": "2026-11-12T08:00:00Z"},
 {"title": "Data Engineer", "location": {"name": "Remote, US"}, "absolute_url": "https://boards.example.com/acme/jobs/5", "first_published": "2026-11-12T08:00:00Z"},
 {"title": "Cloud Engineer", "location": {"name": "Remote, EU"}, "absolute_url": "https://boards.example.com/acme/jobs/6", "first_published": "2026-11-12T08:00:00Z"},
 {"title": "Old Engineer", "location": {"name": "Rome, Italy"}, "absolute_url": "https://boards.example.com/acme/jobs/7", "first_published": "2026-10-20T08:00:00Z"}
]}
EOF
echo "REMOTE_REGIONS=EU, Europe" >>"$ENVF"
"$PY" -I "$S/collect_postings.py" --since 2026-11-01 --from "$T/cp-src" --out "$T/cp-search.json" --add --env "$ENVF" >"$T/cp.out" 2>&1
check "collect_postings: the title and place filters, remote kept, the tracker's link dropped; a board's first read whole" sh -c '
    grep -q "^Acme | Senior Engineer | Rome, Italy | 2026-11-12 | https://boards.example.com/acme/jobs/1 | script:greenhouse:acme$" "$1" &&
    grep -q "| Platform Engineer | Remote |" "$1" && grep -q "| Cloud Engineer | Remote, EU |" "$1" &&
    grep -q "^Acme | Old Engineer | Rome, Italy | 2026-10-20 | " "$1" &&
    ! grep -q "Sales Lead\|jobs/3\|Remote, US\|1234567890" "$1" &&
    grep -q "^Zeta Works | Backend Developer | Rome, Lazio | 2026-11-12 | https://www.linkedin.com/jobs/view/2222222222/ | script:linkedin:search$" "$1" &&
    grep -q "^5 new postings from 2 searches read by script, added to the tracker; window from 2026-11-01 00:00$" "$1"' _ "$T/cp.out"
check "collect_postings --add: each new posting is in the tracker with found_by" sh -c '
    "$1" -I "$2/dq.py" "$3/apply/targets.json" "len([j for j in R[\"jobs\"] if j.get(\"found_by\", \"\").startswith(\"script:\")]) == 5"' _ "$PY" "$T" "$H"
check "collect_postings --out: a search file the workflow reads" sh -c '
    "$1" -I "$2/dq.py" "$3" "sorted(c[\"name\"] for c in R[\"companies\"]) == [\"Acme\", \"Zeta Works\"] and all(j[\"id\"].startswith(\"P\") for c in R[\"companies\"] for j in c[\"jobs\"])"' \
    _ "$PY" "$T" "$T/cp-search.json"
searches due >"$T/cp-due.out" 2>&1
check "collect_postings: the script searches are marked read; the agent search is still due" sh -c '
    grep -q "Beta careers" "$1" && ! grep -q "Acme jobs\|LinkedIn" "$1"' _ "$T/cp-due.out"

# 0.34.1: the window from the last run, the cap, LinkedIn's refusal, a board that is gone, sites --add, terms.
cat >"$T/mklog.py" <<'PYEOF'
import json
import sys

with open(sys.argv[1], "a", encoding="utf-8") as f:
    f.write(json.dumps({"time": "2026-11-12T19:00:00", "step": "run", "result": "started"}) + "\n")
    f.write(json.dumps({"time": "2026-11-12T19:40:00", "step": "run", "result": "ok"}) + "\n")
PYEOF
"$PY" -I "$T/mklog.py" "$H/apply/usage-log.jsonl"
searches add "Gone board" "engineer" source=ashby board=gone >/dev/null 2>&1
echo 404 >"$T/cp-src/ashby-gone.status"
echo 429 >"$T/cp-src/linkedin-search.status"
searches add LinkedIn "developer" source=linkedin place="Milan" >/dev/null 2>&1
echo "MAX_NEW_PER_RUN=1" >>"$ENVF"
"$PY" -I "$S/collect_postings.py" --from "$T/cp-src" --out "$T/cp2.json" --env "$ENVF" >"$T/cp2.out" 2>&1
check "collect_postings: the window starts at the last finished run's start" grep -q "window from 2026-11-12 19:00$" "$T/cp2.out"
check "collect_postings: LinkedIn refused (429) stops LinkedIn for the run; its searches stay due" sh -c '
    grep -q "not read (HTTP 429): LinkedIn stops for this run; it stays due" "$1" &&
    "$2" -I "$3/searches.py" due --env "$4" | grep -q "LinkedIn | developer"' _ "$T/cp2.out" "$PY" "$S" "$ENVF"
check "collect_postings --out: at most MAX_NEW_PER_RUN jobs; the tracker's unprepared finds wait" sh -c '
    grep -q "^1 postings for this run.s funnel (MAX_NEW_PER_RUN=1); 4 wait for the next run$" "$1" &&
    "$2" -I "$3/dq.py" "$4" "sum(len(c[\"jobs\"]) for c in R[\"companies\"]) == 1"' _ "$T/cp2.out" "$PY" "$T" "$T/cp2.json"
"$PY" -I "$S/collect_postings.py" --from "$T/cp-src" --env "$ENVF" >/dev/null 2>&1
searches list >"$T/cp-list.out" 2>&1
check "searches fail: a board that answers 404 twice is gone, not due, and listed so" sh -c '
    grep -q "Gone board .* gone since" "$1" && ! "$2" -I "$3/searches.py" due --env "$4" | grep -q "Gone board"' \
    _ "$T/cp-list.out" "$PY" "$S" "$ENVF"
searches add "Examplia (ashby)" "engineer" source=ashby board=examplia >/dev/null 2>&1
echo '{"jobs": [{"title": "Backend Engineer", "location": "Remote", "jobUrl": "https://jobs.example.com/examplia/9", "publishedAt": "2026-11-16T08:00:00Z"}]}' >"$T/cp-src/ashby-examplia.json"
"$PY" -I "$S/collect_postings.py" --since 2026-11-01 --from "$T/cp-src" --env "$ENVF" >"$T/cp-ashby.out" 2>&1
check "collect_postings: a site named \"<employer> (ashby)\" gives the employer without the board" \
    grep -q "^Examplia | Backend Engineer | Remote | " "$T/cp-ashby.out"
check "searches add: a script search without terms is refused when ROLE_TERMS is not set" sh -c '
    ! "$1" -I "$2/searches.py" add "Acme jobs" "" source=lever board=acme --env "$3" >"$4" 2>&1 && grep -q "needs terms" "$4"' \
    _ "$PY" "$S" "$ENVF" "$T/terms.out"
mkhome "$T/sa" flat
use "$T/sa"
track add S1 "Grafana Labs" "Engineer" "https://boards.greenhouse.io/grafanalabs/jobs/123" >/dev/null 2>&1
track add S2 "Beta Ltd" "Analyst" "https://jobs.lever.co/beta/abc" >/dev/null 2>&1
track add S3 "Grafana Labs" "Designer" "https://boards.greenhouse.io/grafanalabs/jobs/456" >/dev/null 2>&1
echo "ROLE_TERMS=engineer, analyst" >>"$ENVF"
searches sites --add >"$T/sa.out" 2>&1
check "searches sites --add: one script row per board, named by the employer, with ROLE_TERMS" sh -c '
    grep -q "^2 script searches added$" "$1" && grep -q "Grafana Labs | greenhouse grafanalabs" "$1" &&
    "$2" -I "$3/dq.py" "$4/apply/searches.json" "[r[\"query\"] for r in R[\"searches\"]] == [\"engineer, analyst\"] * 2"' \
    _ "$T/sa.out" "$PY" "$T" "$H"
use "$T/cp"
check "employer check: an employer nobody checked says unknown, never checked, and goes on" sh -c '
    "$1" -I "$2/employer.py" check "Neverseen Widgets" --env "$3" >"$4" 2>&1 &&
    grep -q "unknown, never checked" "$4" && grep -q "\"never_checked\": true" "$4" && ! grep -q "\"verdict\": \"exclude\"" "$4"' \
    _ "$PY" "$S" "$ENVF" "$T/never.out"
mkdir -p "$H/CVs/versions"
echo '{"name": "Jane Doe", "title": "Backend Lead"}' >"$H/CVs/versions/1 Backend Lead.json"
echo '{"name": "Jane Doe", "title": "Data Lead"}' >"$H/CVs/versions/2 Data Lead.json"
echo "made up" >"$H/CVs/Jane-Doe-CV-Backend-Lead.pdf"
"$PY" -I "$S/career_view.py" cvs --env "$ENVF" >"$T/cvs.out" 2>"$T/cvs.err"
check "career_view cvs: only the versions whose PDF exists; a missing one is named" sh -c '
    "$1" -I "$2/dq.py" "$3" "[c[\"variant\"] for c in R] == [\"Backend Lead\"] and R[0][\"file\"].endswith(\"Jane-Doe-CV-Backend-Lead.pdf\")" &&
    grep -q "no PDF for 2 Data Lead.json" "$4"' _ "$PY" "$T" "$T/cvs.out" "$T/cvs.err"
# The free employer lookup: founded or headquartered in a state is direct; the settings exclude, or the notes decide.
mkhome "$T/lk" flat
use "$T/lk"
echo "EMPLOYER_RULES=apply/employer-rules.json" >>"$ENVF"
cat >"$H/apply/employer-rules.json" <<'EOF'
{"categories": {"israel": {"action": "exclude", "indirect": "warn"},
                "defence": {"action": "discuss", "indirect": "discuss", "notes": "Western arms producers are excluded"}},
 "changes": []}
EOF
mkdir -p "$T/lk-src"
echo '{"id": "Q1", "label": "Gamma.io", "description": "software company", "facts": {"country": ["United States"], "origin": ["Israel"], "industry": ["software"]}}' >"$T/lk-src/Gamma.json"
echo '{"id": "Q2", "label": "Arma AG", "description": "German arms maker", "facts": {"country": ["Germany"], "industry": ["arms industry"]}}' >"$T/lk-src/Arma-AG.json"
echo '{"id": "Q3", "label": "Plainsoft", "description": "software company", "facts": {"country": ["Italy"], "industry": ["software"]}}' >"$T/lk-src/Plainsoft.json"
echo '{"id": "Q4", "label": "Delta Defence Systems", "description": "arms maker", "facts": {"country": ["Israel"], "industry": ["arms industry"]}, "exact": false}' >"$T/lk-src/Delta.json"
"$PY" -I "$S/employer_lookup.py" Gamma "Arma AG" Plainsoft Unseenco Delta --from "$T/lk-src" --record --out "$T/lk.json" --env "$ENVF" >"$T/lk.out" 2>&1
check "employer_lookup: founded in Israel is a direct tie and the settings exclude it, before any token" sh -c '
    grep -q "^Gamma | exclude | israel: Wikidata (Gamma.io): founded in Israel" "$1"' _ "$T/lk.out"
check "employer_lookup: a finding the person's notes decide goes to the cheap check" \
    grep -q "^Arma AG | undecided | defence: .* the person.s notes for the category decide" "$T/lk.out"
check "employer_lookup: a name that only starts another item's name never excludes: the cheap check decides" \
    grep -q "^Delta | undecided | not certain it is the same employer: Wikidata Q4" "$T/lk.out"
check "employer_lookup: nothing that touches a rule goes on; no item is undecided" sh -c '
    grep -q "^Plainsoft | go on |" "$1" && grep -q "^Unseenco | undecided | no single Wikidata item" "$1"' _ "$T/lk.out"
"$PY" -I "$S/employer_lookup.py" Gamma Plainsoft --from "$T/lk-src" --env "$ENVF" >"$T/lk2.out" 2>&1
check "employer_lookup --record: the findings are in the records and every lookup in the cache: never twice" sh -c '
    grep -q "^Gamma | exclude | in the list" "$1" && grep -q "^Plainsoft | go on | looked up " "$1" &&
    "$2" -I "$3/dq.py" "$4/apply/employers/public-lookup.json" "sorted(R) == [\"Arma AG\", \"Delta\", \"Gamma\", \"Plainsoft\", \"Unseenco\"]"' \
    _ "$T/lk2.out" "$PY" "$T" "$H"
# The order: from the measured defaults the employer check goes first; a person whose fit check stops more goes fit-first.
check "variants order: with no history, the employer check first (it stops more per token)" sh -c '
    CLAUDE_CONFIG_DIR="$4/no-config" "$1" -I "$2/variants.py" order --env "$3" | grep -q "^employer-first"' _ "$PY" "$S" "$ENVF" "$T"
cat >"$T/funnel.json" <<'EOF'
[{"name": "A", "route": "no-fit", "fits": 0, "fit_ran": true, "quick_ran": false},
 {"name": "B", "route": "no-fit", "fits": 0, "fit_ran": true, "quick_ran": true},
 {"name": "C", "route": "verified", "fits": 1, "fit_ran": true, "quick_ran": true}]
EOF
for n in 1 2 3 4 5 6 7 8 9 10; do "$PY" -I "$S/variants.py" funnel "$T/funnel.json" --env "$ENVF" >/dev/null 2>&1; done
check "variants funnel and order: a fit check that stops most employers moves the order to fit-first" sh -c '
    grep -q "\"fit_stops\": 2" "$4/apply/usage-log.jsonl" &&
    CLAUDE_CONFIG_DIR="$5/no-config" "$1" -I "$2/variants.py" order --env "$3" | grep -q "^fit-first"' _ "$PY" "$S" "$ENVF" "$H" "$T"
"$PY" -I "$S/career_view.py" fit --out "$T/fit-view.json" --env "$ENVF" >/dev/null 2>&1
check "career_view fit: the fit check's smaller view" q keys "$T/fit-view.json" _about,languages,preferences,profile,skills,person

# choices.py: the cost choices, their defaults, a folder from before 0.35.0, and the fit grade.
mkhome "$T/ch" flat
use "$T/ch"
check "choices show: a folder without the keys gets the defaults; ASK_FIRST keeps drafts for approval, sends alone" sh -c '
    "$1" -I "$2/choices.py" show --env "$3" >"$4/ch.out" &&
    grep -q "^APPLY_FITS=normal  (default)" "$4/ch.out" && grep -q "^ASK_FIRST=free_text  (older folder: from APPLY_MODE)" "$4/ch.out"' _ "$PY" "$S" "$ENVF" "$T"
echo "APPLY_MODE=review" >>"$ENVF"
check "choices workflow: the older APPLY_MODE=review asks before sending" sh -c '
    "$1" -I "$2/choices.py" workflow --env "$3" | grep -q "\"askFirst\": \[\"send\", \"free_text\"\]"' _ "$PY" "$S" "$ENVF"
check "choices set: a wrong value is refused and nothing is written" sh -c '
    ! "$1" -I "$2/choices.py" set APPLY_FITS=low --env "$3" >/dev/null 2>&1 && ! grep -q "^APPLY_FITS" "$3"' _ "$PY" "$S" "$ENVF"
"$PY" -I "$S/choices.py" set APPLY_FITS=high MAX_NEW_PER_RUN=unlimited ASK_FIRST= --env "$ENVF" >/dev/null 2>&1
"$PY" -I "$S/choices.py" set APPLY_FITS=normal --env "$ENVF" >/dev/null 2>&1
check "choices set: each key one line, replaced in place; an empty ASK_FIRST means all alone" sh -c '
    [ "$(grep -c "^APPLY_FITS=" "$3")" = 1 ] && grep -q "^APPLY_FITS=normal$" "$3" && grep -q "^MAX_NEW_PER_RUN=unlimited$" "$3" &&
    "$1" -I "$2/choices.py" workflow --env "$3" | grep -q "\"askFirst\": \[\]"' _ "$PY" "$S" "$ENVF"
check "choices suggest pro: list only, no letters, one run a week" sh -c '
    "$1" -I "$2/choices.py" suggest pro --env "$3" >"$4/sg.out" && grep -q "^APPLY=list$" "$4/sg.out" &&
    grep -q "^LETTERS=never$" "$4/sg.out" && grep -q "^PLAN=pro$" "$4/sg.out"' _ "$PY" "$S" "$ENVF" "$T"
cat >"$T/graded.json" <<'EOF'
{"jobs": [{"id": "G1", "action": "apply", "gaps": []},
          {"id": "G2", "action": "apply", "gaps": [{"kind": "pay_below", "what": "5% under"}]},
          {"id": "G3", "action": "apply", "gaps": [{"kind": "seniority", "what": "lead"}, {"kind": "missing_must_have", "what": "Go"}]},
          {"id": "G4", "action": "apply", "gaps": [{"kind": "hard", "what": "on site in Oslo"}]},
          {"id": "G5", "action": "skip", "reason": "closed", "gaps": []}]}
EOF
"$PY" -I "$S/choices.py" grade "$T/graded.json" --env "$ENVF" >"$T/gr.out" 2>&1
check "choices grade (no requirements): no gap high, one soft gap normal, two a long-shot (a skip at cap 0), a hard gap a skip" sh -c '
    grep -q "^G1 | apply | high | - |" "$1" && grep -q "^G2 | apply | normal | - |" "$1" &&
    grep -q "^G3 | skip | long-shot | - | long-shot: 2 soft gap kinds (LONG_SHOTS_PER_DAY=0): lead; Go" "$1" &&
    grep -q "^G4 | skip | - | - | a hard gap: on site in Oslo" "$1" && grep -q "^G5 | skip | - | - |" "$1"' _ "$T/gr.out"
"$PY" -I "$S/choices.py" set APPLY_FITS=high --env "$ENVF" >/dev/null 2>&1
check "choices grade: with APPLY_FITS=high a normal fit is a skip" sh -c '
    "$1" -I "$2/choices.py" grade "$3" --env "$4" | grep -q "^G2 | skip | normal | - | not a high fit (APPLY_FITS=high): 5% under"' _ "$PY" "$S" "$T/graded.json" "$ENVF"
# statusline.py: the plan's share saved by the status line, read back for the run report.
echo '{"rate_limits": {"five_hour": {"used_percentage": 23.4}, "seven_day": {"used_percentage": 41}}}' |
    "$PY" -I "$S/statusline.py" --out "$H/apply/plan-usage.json" >"$T/sl.out" 2>&1
check "statusline: prints both windows and saves them; read gives the report's line" sh -c '
    grep -q "^5h 23% .* 7d 41%" "$1" &&
    "$2" -I "$3/statusline.py" read --env "$4" | grep -q "^Plan used: 5 hours 23%, 7 days 41%$"' _ "$T/sl.out" "$PY" "$S" "$ENVF"
check "statusline read: nothing without the file" sh -c '
    rm -f "$4/apply/plan-usage.json" && [ -z "$("$1" -I "$2/statusline.py" read --env "$3")" ]' _ "$PY" "$S" "$ENVF" "$H"

# track.py wait and logins sync: a wait is a status and a to-do with its link; one row per Workday tenant host.
mkhome "$T/wk" flat
use "$T/wk"
cat >"$H/apply/targets.json" <<'EOF'
{"companies": [
 {"name": "Zeta Works", "verdict": "allow", "jobs": [{"id": "W1", "title": "Architect", "company": "Zeta Works", "status": "found",
   "apply_url": "https://zw-hr.wd3.myworkdayjobs.com/en-US/careers/job/1"}]},
 {"name": "Acme", "verdict": "allow", "jobs": [{"id": "W2", "title": "Engineer", "company": "Acme", "status": "account-needed",
   "apply_url": "https://acme.wd5.myworkdayjobs.com/x/job/2"}]}]}
EOF
cat >"$H/apply/logins.json" <<'EOF'
{"logins": [
 {"id": "Workday · Zeta Works SpA", "name": "Workday · Zeta Works SpA", "kind": "site", "status": "signed-in",
  "link": "https://zw-hr.wd3.myworkdayjobs.com/en-US/careers", "note": "set by hand", "jobs": []},
 {"id": "beta.wd1.myworkdayjobs.com", "name": "beta.wd1.myworkdayjobs.com", "kind": "site", "status": "signed-in",
  "note": "set by hand", "jobs": []},
 {"id": "acme.wd5.myworkdayjobs.com", "name": "acme.wd5.myworkdayjobs.com", "kind": "site", "status": "needs-sign-in",
  "note": "an application waits on this site's sign-in or account", "jobs": ["W2"]}]}
EOF
check "track wait: only needs-person or account-needed, with what it waits on" sh -c '
    ! "$1" -I "$2/track.py" wait W1 found "x" --env "$3" >/dev/null 2>&1 && ! "$1" -I "$2/track.py" wait W1 needs-person --env "$3" >/dev/null 2>&1' \
    _ "$PY" "$S" "$ENVF"
"$PY" -I "$S/track.py" wait W1 account-needed "Workday sign-in" --env "$ENVF" >/dev/null 2>&1
"$PY" -I "$S/track.py" wait W1 account-needed "Workday sign-in" --env "$ENVF" >/dev/null 2>&1
check "track wait: the status and one sign-in to-do with the job's own link, never twice" dq "$H/apply/targets.json" \
    '[(j["status"], [(t["kind"], t["text"], t.get("link"), t.get("login")) for t in j["todo"]]) for j in R["companies"][0]["jobs"]] == [("account-needed", [("click", "Workday sign-in", "https://zw-hr.wd3.myworkdayjobs.com/en-US/careers/job/1", "Workday · Zeta Works SpA")])]'
"$PY" -I "$S/track.py" wait W1 needs-person "Self-ratings on the form" --env "$ENVF" >/dev/null 2>&1
"$PY" -I "$S/track.py" wait W1 account-needed "Self-ratings on the form" --env "$ENVF" >/dev/null 2>&1
check "track wait: the same wait again takes the new kind and sign-in; still one to-do of that text" dq "$H/apply/targets.json" \
    '[(t["kind"], t.get("login")) for t in R["companies"][0]["jobs"][0]["todo"] if t["text"] == "Self-ratings on the form"] == [("click", "Workday \u00b7 Zeta Works SpA")]'
"$PY" -I "$S/logins.py" sync --env "$ENVF" >/dev/null 2>&1
check "logins sync: a host-named row no job matches keeps its state" dq "$H/apply/logins.json" \
    '{r["id"]: r["status"] for r in R["logins"]}.get("beta.wd1.myworkdayjobs.com") == "signed-in"'
check "logins sync: a Workday job matches its tenant host's row, whatever the employer's spelling" dq "$H/apply/logins.json" \
    '{r["id"]: r["jobs"] for r in R["logins"]}["Workday · Zeta Works SpA"] == ["W1"]'
check "logins sync: a row named by its host takes the employer's name; only an unmatched one stays" dq "$H/apply/logins.json" \
    '{r["id"]: r["jobs"] for r in R["logins"]}.get("Workday · Acme") == ["W2"] and [r["id"] for r in R["logins"] if "myworkdayjobs" in r["id"]] == ["beta.wd1.myworkdayjobs.com"]'

# --- 0.35.1: the first real run's faults ---------------------------------------------------------------------------
mkhome "$T/r1" old
use "$T/r1"
cat >"$H/apply/targets.json" <<'EOF'
{"companies": [
 {"name": "Acme (Parent)", "verdict": "allow", "jobs": [
  {"id": "A0", "title": "Senior Software Engineer (m/f/d)", "status": "submitted", "applied": "2026-11-02"}]},
 {"name": "Acme", "verdict": "allow", "jobs": [
  {"id": "A1", "title": "Platform Engineer", "status": "found", "date": "2026-11-14"},
  {"id": "A2", "title": "Tester", "status": "found", "date": "2026-11-13"}]}]}
EOF
cat >"$T/r1-search.json" <<'EOF'
{"companies": [{"name": "Acme", "jobs": [{"id": "P1", "title": "Software Engineer - Senior"},
                                          {"id": "P2", "title": "Staff Software Engineer"}]}]}
EOF
"$PY" -I "$S/reposts.py" "$T/r1-search.json" --env "$ENVF" >"$T/r1-reposts.out" 2>&1
check "reposts: the same employer (a bracketed name) and the same title words are a repost; another title is not" sh -c '
    grep -q "^P1 | Acme | Software Engineer - Senior | repost of A0$" "$1" && ! grep -q "^P2" "$1"' _ "$T/r1-reposts.out"
# Sync: the plugin's labels count even when the person's settings list only older ones; a fit's decision is a status.
echo "TRACKER_SETTINGS=apply/tracker-settings.json" >>"$ENVF"
echo '{"sync": {"labels": {"prep": ["prep-old:"], "exclusion": ["excl-old:"]}}}' >"$H/apply/tracker-settings.json"
cat >"$T/r1-journal.jsonl" <<'EOF'
{"type": "started", "agentId": "f1", "label": "prep-fit:Acme"}
{"type": "result", "agentId": "f1", "result": {"jobs": [{"id": "A1", "action": "apply", "title": "Platform Engineer", "gaps": []}, {"id": "A2", "action": "skip", "title": "Tester", "reason": "a junior role", "gaps": []}]}}
EOF
track sync "$T/r1-journal.jsonl" >/dev/null 2>&1
check "sync: a prep-fit: result counts though the person's settings list only older prep labels" \
    q "$H/apply/targets.json" "companies.name=Acme.jobs.0.prep.grade" eq high
check "sync: a fit's apply becomes pending, its skip skipped with the reason" sh -c '
    "$1" -I "$2/dq.py" "$3" "[(j[\"status\"], j.get(\"outcome\", \"\")) for j in R[\"companies\"][1][\"jobs\"]] == [(\"pending\", \"fit: apply\"), (\"skipped\", \"fit: a junior role\")]"' \
    _ "$PY" "$T" "$H/apply/targets.json"
printf 'A1\tneeds-person\tWorkday sign-in\nA2\tclosed\tthe posting is gone\nA0\tsubmitted\tsent\n' >"$T/r1-batch.tsv"
track set --file "$T/r1-batch.tsv" >/dev/null 2>&1
check "track set --file: three changes in one write, each in its job's history" sh -c '
    "$1" -I "$2/dq.py" "$3" "[j[\"status\"] for c in R[\"companies\"] for j in c[\"jobs\"]] == [\"submitted\", \"needs-person\", \"closed\"] and R[\"companies\"][1][\"jobs\"][1][\"history\"][-1][\"outcome\"] == \"the posting is gone\""' \
    _ "$PY" "$T" "$H/apply/targets.json"
check "track set --file: a line without a status is refused" sh -c '
    printf "A1\n" >"$4/r1-bad.tsv" && ! "$1" -I "$2/track.py" set --file "$4/r1-bad.tsv" --env "$3" >/dev/null 2>&1' _ "$PY" "$S" "$ENVF" "$T"
# Title terms match whole words; a phrase as a whole.
check "collect: a term matches whole words of the title, a phrase as a whole" "$PY" -I -c '
import sys; sys.path.insert(0, sys.argv[1]); import collect_postings as c
assert not c.title_has("Leadership Coach", ["lead"]) and c.title_has("Tech Lead, Payments", ["tech lead"])
assert not c.title_has("Lead Project Manager", ["tech lead"]) and c.title_has("Senior Java Engineer", ["java"])' "$S"
check "collect: a ruled-out city never passes, also inside an accepted country; PLACES where a search names none" "$PY" -I -c '
import sys; sys.path.insert(0, sys.argv[1]); import collect_postings as c
c.PLACES, c.NOT_PLACES = ["rome", "italy", "vienna"], ["turin"]
assert c.place_ok("Rome, Italy", c.PLACES, []) and c.place_ok("Vienna, Austria", c.PLACES, [])
assert not c.place_ok("Jerome, Idaho", ["rome"], [])
assert not c.place_ok("Turin, Italy", c.PLACES, []) and not c.place_ok("Oslo, Norway", c.PLACES, [])
assert c.place_ok("Remote", c.PLACES, []) and not c.place_ok("Remote, US", c.PLACES, ["eu"])
assert c.wanted({"query": "engineer"}, "Software Engineer", "Vienna, Austria", [], [])' "$S"
"$PY" -I "$S/career_view.py" pay Vienna --set "75000 EUR gross a year" --env "$ENVF" >/dev/null 2>&1
check "career_view pay: a city's figure is kept in the private table and given to the posting in that city" sh -c '
    [ "$("$1" -I "$2/career_view.py" pay vienna --env "$3")" = "75000 EUR gross a year" ] &&
    "$1" -I "$2/career_view.py" pay Lisbon --env "$3" | grep -q "^no figure for Lisbon" &&
    "$1" -I -c "import sys; sys.path.insert(0, sys.argv[1]); import trackerlib as t; assert t.pay_for({\"Vienna\": \"x\"}, \"Vienna, Germany\") == \"x\" and t.pay_for({\"Vienna\": \"x\"}, \"Viennagasse, Rome\") == \"\"" "$2"' \
    _ "$PY" "$S" "$ENVF"
check "workflow: the grades are counted before the APPLY_FITS cut" grep -q "raw_grade === g" "$S/../workflows/screen-and-prepare.js"
# The free lookup: a 429 is a pause and a second pass, not the end; a name holding " | " keeps the line's fields.
mkdir -p "$T/r1-lk"
echo '{"id": "Q7", "label": "Plainsoft", "description": "software company", "facts": {"country": ["Italy"], "industry": ["software"]}}' >"$T/r1-lk/Plainsoft.json"
: >"$T/r1-lk/Plainsoft.throttle"
echo '{"id": "Q8", "label": "Pipe Co", "description": "software company", "facts": {"country": ["Italy"], "industry": ["software"]}}' >"$T/r1-lk/Pipe-Co.json"
"$PY" -I "$S/employer_lookup.py" Plainsoft "Pipe | Co" --from "$T/r1-lk" --wait 0 --env "$ENVF" >"$T/r1-lk.out" 2>&1
check "employer_lookup: after a 429 the employer is looked up again later, and decided" grep -q "^Plainsoft | go on |" "$T/r1-lk.out"
check "employer_lookup: a name holding \" | \" is printed with \" / \"" grep -q "^Pipe / Co | go on |" "$T/r1-lk.out"
# workflow_args: small args, the rules in a file, an excluded employer left out.
mkdir -p "$T/r1-out"
echo '{"companies": [{"name": "Acme", "jobs": [{"id": "P2", "title": "Staff Software Engineer"}]}, {"name": "ACME", "jobs": [{"id": "P4", "title": "Engineer"}]}, {"name": "Beta Ltd", "jobs": [{"id": "P3", "title": "Analyst"}]}]}' >"$T/r1-out/search.json"
echo '{"Beta Ltd": {"verdict": "exclude", "why": "in the list"}, "Acme": {"verdict": "undecided", "why": "two items"}}' >"$T/r1-lookup.json"
CLAUDE_CONFIG_DIR="$T/no-config" "$PY" -I "$S/workflow_args.py" --search "$T/r1-out/search.json" --lookup "$T/r1-lookup.json" --env "$ENVF" >"$T/r1-args.out" 2>&1
check "workflow_args: args under 8 KB with the rules in a file; an excluded employer is left out and named" sh -c '
    grep -q "^left out: Beta Ltd | exclude" "$1" && [ "$(wc -c <"$2/args.json")" -lt 8192 ] &&
    "$3" -I "$4/dq.py" "$2/args.json" "[c[\"name\"] for c in R[\"companies\"]] == [\"Acme\", \"ACME\"] and R[\"companies\"][0][\"quick\"] and R[\"rulesFile\"].endswith(\"rules.json\") and \"what\" not in str(R[\"employerRules\"])" &&
    [ -s "$2/rules.json" ] && [ -s "$2/fit.json" ]' _ "$T/r1-args.out" "$T/r1-out" "$PY" "$T"
check "workflow_args: one jobs file per employer, a unique name whatever the case, named in its entry" sh -c '
    "$1" -I "$2/dq.py" "$3/args.json" "[c[\"jobs_file\"].rsplit(\"/\", 1)[1] for c in R[\"companies\"]] == [\"Acme.json\", \"ACME-2.json\"]" &&
    grep -q "\"P4\"" "$3/jobs/ACME-2.json" && ! grep -q "\"P4\"" "$3/jobs/Acme.json"' _ "$PY" "$T" "$T/r1-out"
# searches: --since reaches a script search read earlier today; sites --add skips an excluded employer.
cat >"$H/apply/searches.json" <<'EOF'
{"searches": [{"id": 1, "site": "Acme", "query": "engineer", "method": "script", "source": "greenhouse", "board": "acme",
  "alert": false, "every_days": 1, "last_checked": "2026-11-15T01:00"}]}
EOF
check "searches due --since: a script search read since then is due again" sh -c '
    "$1" -I "$2/searches.py" due --json --since 2026-11-15T00:00 --today 2026-11-15 --env "$3" | grep -q "\"id\": 1" &&
    ! "$1" -I "$2/searches.py" due --json --today 2026-11-15 --env "$3" | grep -q "\"id\": 1"' _ "$PY" "$S" "$ENVF"
cat >"$H/apply/targets.json" <<'EOF'
{"companies": [{"name": "Beta Ltd", "verdict": "exclude", "jobs": [{"id": "B1", "title": "Analyst", "status": "excluded",
  "url": "https://boards.greenhouse.io/betaltd/jobs/1"}]}]}
EOF
echo "ROLE_TERMS=engineer" >>"$ENVF"
searches sites --add >"$T/r1-sites.out" 2>&1
check "searches sites --add: no search for an employer the person excluded" grep -q "^0 script searches added" "$T/r1-sites.out"
# sessions: a scheduled run's session is a coordinator, never a piece; the lock keeps a second coordinator out.
printf '[{"sessionId": "local_r1", "title": "Job search: weekday run", "cwd": "%s"}, {"sessionId": "local_r2", "title": "You · Acme answers", "cwd": "%s"}]' "$H" "$H" >"$T/r1-list.json"
sessions sync "$T/r1-list.json" >/dev/null 2>&1
check "sessions sync: a scheduled run's session is no piece" sh -c '
    "$1" -I "$2/dq.py" "$3" "[s[\"id\"] for s in R[\"sessions\"]] == [\"local_r2\"]"' _ "$PY" "$T" "$H/apply/sessions.json"
check "sessions lock: the first coordinator takes it; a second one is refused and named" sh -c '
    "$1" -I "$2/sessions.py" lock local_a --env "$3" | grep -q "^lock: local_a" &&
    ! "$1" -I "$2/sessions.py" lock local_b --env "$3" >"$4/r1-lock.out" &&
    grep -q "another coordinator holds the lock: local_a" "$4/r1-lock.out"' _ "$PY" "$S" "$ENVF" "$T"
check "sessions unlock: freed, the next one takes it; a stale lock is taken over" sh -c '
    "$1" -I "$2/sessions.py" unlock local_a --env "$3" >/dev/null && "$1" -I "$2/sessions.py" lock local_b --env "$3" >/dev/null &&
    echo "{\"id\": \"local_b\", \"beat\": \"2026-01-01T00:00:00\"}" >"$4/.coordinator.lock" &&
    "$1" -I "$2/sessions.py" lock local_c --env "$3" | grep -q "stale lock of local_b"' _ "$PY" "$S" "$ENVF" "$H"

use "$T/cp"
# variants.py: off by default; a rotation once on; the good-fit count of a run 10 days back.
check "variants: with no file the run's variant is default and its models are empty" sh -c '
    [ "$("$1" -I "$2/variants.py" current --env "$3")" = default ] && [ "$("$1" -I "$2/variants.py" models --env "$3")" = "{}" ]' _ "$PY" "$S" "$ENVF"
cat >"$H/apply/variants.json" <<'EOF'
{"on": true, "rotation": ["a", "b"], "variants": {"a": {"fit": {"model": "sonnet", "effort": "low"}}, "b": {"fit": {"model": "haiku", "effort": "low"}}}}
EOF
cat >"$T/mkruns.py" <<'PYEOF'
import datetime
import json
import sys

home = sys.argv[1]
d = (datetime.date.today() - datetime.timedelta(days=10)).isoformat()
with open(f"{home}/apply/usage-log.jsonl", "w", encoding="utf-8") as f:
    f.write(json.dumps({"time": d + "T00:05:00", "step": "run", "result": "started", "variant": "a"}) + "\n")
    f.write(json.dumps({"time": d + "T23:50:00", "step": "run", "result": "ok"}) + "\n")
with open(f"{home}/apply/targets.json", encoding="utf-8") as f:
    t = json.load(f)
t["jobs"][0]["status"] = "to-apply"
t["jobs"][0]["history"] = [{"date": d, "status": "found"}, {"date": d, "status": "to-apply"}]
t["jobs"][1]["status"] = "skipped"
t["jobs"][1]["history"] = [{"date": d, "status": "to-apply"}, {"date": d, "status": "skipped"}]
with open(f"{home}/apply/targets.json", "w", encoding="utf-8") as f:
    json.dump(t, f, ensure_ascii=False, indent=1)
# A made-up transcript of that day: one main message, one fitter agent.
cc = sys.argv[2]
import os, re
proj = os.path.join(cc, "projects", re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(home)))
os.makedirs(os.path.join(proj, "s1", "subagents"), exist_ok=True)
msg = lambda i, model, tokens: json.dumps({"type": "assistant", "timestamp": d + "T12:00:00Z", "message": {
    "id": i, "model": model, "usage": {"input_tokens": tokens, "cache_creation_input_tokens": 0,
                                       "cache_read_input_tokens": 0, "output_tokens": 0}}})
with open(os.path.join(proj, "s1.jsonl"), "w", encoding="utf-8") as f:
    f.write(msg("m1", "claude-opus-5-5", 1000) + "\n")
with open(os.path.join(proj, "s1", "subagents", "agent-x1.jsonl"), "w", encoding="utf-8") as f:
    f.write(msg("m2", "claude-sonnet-5-5", 1000) + "\n")
with open(os.path.join(proj, "s1", "subagents", "agent-x1.meta.json"), "w", encoding="utf-8") as f:
    json.dump({"agentType": "cenk-jobs:fitter"}, f)
PYEOF
"$PY" -I "$T/mkruns.py" "$H" "$T/cc"
check "variants: on, the run after a run of a takes b; b's models for the workflow" sh -c '
    [ "$("$1" -I "$2/variants.py" current --env "$3")" = b ] &&
    "$1" -I "$2/variants.py" models --env "$3" | grep -q "\"model\": \"haiku\""' _ "$PY" "$S" "$ENVF"
"$PY" -I "$S/variants.py" count --env "$ENVF" >"$T/var-count.out" 2>&1
"$PY" -I "$S/variants.py" count --env "$ENVF" >"$T/var-count2.out" 2>&1
check "variants count: one good-fit job (the skipped one does not count), logged once" sh -c '
    grep -q "variant a: 1 good-fit jobs" "$1" && grep -q "^0 run(s) counted" "$2" &&
    [ "$(grep -c "run-result" "$3/apply/usage-log.jsonl")" -eq 1 ]' _ "$T/var-count.out" "$T/var-count2.out" "$H"
CLAUDE_CONFIG_DIR="$T/cc" "$PY" -I "$S/token_report.py" --days 30 --json "$T/tok.json" --env "$ENVF" >"$T/tok.out" 2>&1
check "token_report: the run's W, main and agents, per good-fit job; the agent kind; numbers only" sh -c '
    grep -q " a  .* main    0.00M  agents   0.00M  good-fit   1" "$1" &&
    grep -q "^agent cenk-jobs:fitter .* 1 .* 1k W each" "$1" &&
    "$2" -I "$3/dq.py" "$4" "R[\"runs\"][0][\"main_w\"] == 1000 and R[\"runs\"][0][\"agents_w\"] == 600 and R[\"runs\"][0][\"w_per_good_fit\"] == 1600"' \
    _ "$T/tok.out" "$PY" "$T" "$T/tok.json"

use "$T/dash"  # the next section runs in the home it ran in before 0.34.0
# --- review fixes ----------------------------------------------------------------------------------------------------
track add J9 "Acme Corp" "Engineer" "https://boards.example.com/acme/jobs?gh_jid=111" >/dev/null 2>&1
printf '%s
' "https://boards.example.com/acme/jobs?gh_jid=222" "https://boards.example.com/acme/jobs?gh_jid=111&utm_source=mail" >"$T/links.txt"
searches seen --file "$T/links.txt" >"$T/seen2.out" 2>&1
check "searches seen --file: a job id in the query keeps two jobs apart; a tracking parameter does not" sh -c     'grep -q "^new .*gh_jid=222" "$1" && grep -q "^known .*gh_jid=111&utm_source=mail" "$1"' _ "$T/seen2.out"
check "a hand-set details path outside details/ is refused, and no file is written there" sh -c     '! "$1" -I "$2/track.py" set J1 submitted "x" details=../outside.json --env "$3" >/dev/null 2>&1 && [ ! -e "$4/outside.json" ]'     _ "$PY" "$S" "$ENVF" "$H"

# --- 0.38.0: sources in order, remote feeds, title rules, the remote text check, LinkedIn's one retry, duplicates,
# the fit cache, real fit rates, import, the scope from the record ------------------------------------------------------
mkhome "$T/s38" flat
use "$T/s38"
echo "MAX_NEW_PER_RUN=10" >>"$ENVF"
cat >"$T/mk38.py" <<'PYEOF'
import datetime
import json
import os
import sys

home, src = sys.argv[1], sys.argv[2]
today = datetime.date.today().isoformat()
os.makedirs(src, exist_ok=True)
w = lambda name, data: open(os.path.join(src, name), "w", encoding="utf-8").write(  # noqa: E731
    data if isinstance(data, str) else json.dumps(data))
gh = lambda n, title, place: {"title": title, "location": {"name": place},  # noqa: E731
                              "absolute_url": f"https://boards.example.com/acme/jobs/{n}", "first_published": "2026-11-16T08:00:00Z"}
w("greenhouse-acme.json", {"jobs": [gh(1, "Staff Engineer", "Remote"), gh(2, "Junior Engineer", "Remote"),
                                    gh(3, "Sales Engineer Lead", "Remote")]})
w("remoteok-feed.json", [{"legal": "made up"},
    {"position": "Principal Engineer", "company": "Beta Ltd", "location": "Europe", "date": "2026-11-16T09:00:00Z",
     "url": "https://feeds.example.com/beta/1"},
    {"position": "Staff Engineer", "company": "Gamma Inc", "location": "USA only", "date": "2026-11-16T09:00:00Z",
     "url": "https://feeds.example.com/gamma/1"},
    {"position": "Staff Engineer", "company": "Acme", "location": "Worldwide", "date": "2026-11-16T09:00:00Z",
     "url": "https://feeds.example.com/acme/1"},
    {"position": "Staff Engineer", "company": "Delta GmbH", "location": "Worldwide", "date": "2026-11-16T09:00:00Z",
     "url": "https://feeds.example.com/delta/1"}])
card = lambda n, title, company: (  # noqa: E731
    f'<li><div class="base-card relative"><a class="base-card__full-link absolute" href="https://www.linkedin.com/jobs/view/{n}/?trk=x">x</a>'
    f'<h3 class="base-search-card__title">{title}</h3><h4 class="base-search-card__subtitle"><a>{company}</a></h4>'
    f'<span class="job-search-card__location">Milan, Lombardy, Italy</span><time datetime="2026-11-16">1 day ago</time></div></li>')
w("linkedin-search.html", card(5550000001, "Staff Engineer Java", "Zeta Works") + card(5550000002, "Principal Architect", "Eta Labs"))
w("linkedin-search.status", "429 200")
w("linkedin-job-5550000001.html", "<div>A fully remote role in Italy.</div>")
w("linkedin-job-5550000002.html", "<div>Hybrid: three days a week in our Milan office.</div>")
json.dump({"low": "junior", "level": "staff|principal|lead|architect", "no": "sales", "need": "engineer|architect"},
          open(os.path.join(home, "apply", "search-rules.json"), "w", encoding="utf-8"))
career = json.load(open(os.path.join(home, "career-records", "career.json"), encoding="utf-8"))
career["preferences"]["locations"] = {"base": "made up", "search_scope": {
    "text": "made up", "remote_regions": ["Europe", "Worldwide", "Italy"], "any_mode_places": ["Istanbul"]}}
json.dump(career, open(os.path.join(home, "career-records", "career.json"), "w", encoding="utf-8"))
tracker = json.load(open(os.path.join(home, "apply", "targets.json"), encoding="utf-8"))
tracker["jobs"].append({"id": "S1", "company": "Delta GmbH", "title": "Staff Engineer", "url": "https://example.com/s1",
                        "status": "skipped", "history": [{"date": today, "status": "skipped", "note": "fit: a hard gap"}]})
json.dump(tracker, open(os.path.join(home, "apply", "targets.json"), "w", encoding="utf-8"))
PYEOF
"$PY" -I "$T/mk38.py" "$H" "$T/s38-src"
echo "ROLE_TERMS=engineer, architect" >>"$ENVF"
searches add "Acme" "" source=greenhouse board=acme employer=Acme >/dev/null 2>&1
searches add remoteok "engineer, architect" source=remoteok mode=remote >/dev/null 2>&1
searches add "LinkedIn Italy" "staff engineer java, principal architect" source=linkedin place=Italy mode=remote >/dev/null 2>&1
"$PY" -I "$S/collect_postings.py" --since 2026-11-01 --from "$T/s38-src" --out "$T/s38-search.json" --add --env "$ENVF" >"$T/s38.out" 2>&1
check "0.38 collect: title rules leave titles out before any text; a feed posting outside the scope's regions never comes" sh -c '
    grep -q "^search 1 Acme: title rules left out 1 (a word you drop), 1 (level too low)$" "$1" && ! grep -q "Gamma" "$1"' _ "$T/s38.out"
check "0.38 collect: one job on a board and a feed is screened once (the board kept); a fit skip of 30 days stands" sh -c '
    grep -q "| Acme | Staff Engineer | the same job as P.* (found twice this run)$" "$1" &&
    grep -q "| Delta GmbH | Staff Engineer | the same job as S1, skipped for fit$" "$1"' _ "$T/s38.out"
check "0.38 collect: LinkedIn refused once goes on after the pause; a remote search hit whose text says no remote is left out" sh -c '
    ! grep -q "LinkedIn stops" "$1" && grep -q "| Eta Labs | Principal Architect | location: its text says nothing of remote work" "$1"' _ "$T/s38.out"
check "0.38 collect: the funnel takes boards and feeds first, LinkedIn remote last, each found with its search row" sh -c '
    "$1" -I "$2/dq.py" "$3" "[c[\"name\"] for c in R[\"companies\"]] == [\"Acme\", \"Beta Ltd\", \"Zeta Works\"]" &&
    "$1" -I "$2/dq.py" "$4/apply/targets.json" "[j.get(\"search\") for j in R[\"jobs\"] if j[\"company\"] == \"Beta Ltd\" and j[\"id\"].startswith(\"P\")] == [\"2\"]"' \
    _ "$PY" "$T" "$T/s38-search.json" "$H"
cat >"$T/mk38b.py" <<'PYEOF'
import json
import sys

path = sys.argv[1]
t = json.load(open(path, encoding="utf-8"))
for n in range(20):
    t["jobs"].append({"id": f"R{n}", "company": "Theta AG", "title": "Lead", "url": f"https://example.com/r{n}",
                      "status": "skipped", "search": "3", "prep": {"action": "skip", "reason": "location"}})
t["jobs"].append({"id": "R99", "company": "Iota", "title": "Lead", "url": "https://example.com/r99", "status": "pending",
                  "search": "2", "prep": {"action": "apply", "grade": "normal"}})
json.dump(t, open(path, "w", encoding="utf-8"))
PYEOF
"$PY" -I "$T/mk38b.py" "$H/apply/targets.json"
searches rates >"$T/s38-rates.out" 2>&1
check "0.38 searches rates: real fits per row; 20 screened and none asks the person, never drops" sh -c '
    grep -q "^2 remoteok | engineer, architect | found 4 | screened 1 | real fits 1 | 100%$" "$1" &&
    grep -q "^ask the person whether to drop.*3 LinkedIn Italy | staff engineer java, principal architect: 20 screened, 0 real fits$" "$1"' _ "$T/s38-rates.out"
cat >"$T/s38-profile.json" <<'EOF'
{"linkedin": [{"location": "Istanbul", "remote": false, "queries": ["java architect", "staff engineer java"]}],
 "boards": [{"source": "ashby", "board": "examplia", "site": "Examplia"}], "feeds": ["remotive", "nofeed"]}
EOF
searches import "$T/s38-profile.json" >"$T/s38-imp1.out" 2>&1
searches import "$T/s38-profile.json" >"$T/s38-imp2.out" 2>&1
check "0.38 searches import: rows with source, place and mode; a known feed only; again: none added" sh -c '
    grep -q "^4 searches added$" "$1" && grep -q "^0 searches added$" "$2" &&
    "$3" -I "$4/dq.py" "$5" "[(r[\"source\"], r.get(\"mode\")) for r in R[\"searches\"][3:]] == [(\"linkedin\", \"any\"), (\"linkedin\", \"any\"), (\"ashby\", None), (\"remotive\", \"remote\")]"' \
    _ "$T/s38-imp1.out" "$T/s38-imp2.out" "$PY" "$T" "$H/apply/searches.json"
check "0.38 searches add: an unknown mode is refused; a feed needs no board" sh -c '
    ! "$1" -I "$2/searches.py" add X "" source=linkedin mode=hybrid --env "$3" >/dev/null 2>&1 &&
    "$1" -I "$2/searches.py" add Y "engineer" source=jobicy --env "$3" >/dev/null 2>&1' _ "$PY" "$S" "$ENVF"
check "0.38 feeds: each feed gives title, company, a remote place and a date" "$PY" -I -c '
import sys; sys.path.insert(0, sys.argv[1]); import collect_postings as c
assert c.feed_postings("himalayas", {"jobs": [{"title": "Staff Engineer", "companyName": "Acme", "locationRestrictions": [], "pubDate": 1763280000, "guid": "u"}]}) == [("Staff Engineer", "Acme", "Remote, Worldwide", c.day(1763280000), "u")]
assert c.feed_postings("arbeitnow", {"data": [{"title": "T", "company_name": "B", "location": "Berlin", "created_at": 1763280000, "url": "u", "remote": False}]}) == []
assert c.feed_postings("jobicy", {"jobs": [{"jobTitle": "T", "companyName": "B", "jobGeo": "Europe", "pubDate": "2026-11-16 10:00:00", "url": "u"}]})[0][2] == "Remote, Europe"
none = c.feed_postings("remoteok", [{"position": "T", "company": "B", "location": "", "url": "u"}])[0][2]
assert none == "Remote, no region given" and not c.place_ok(none, [], ["europe", "worldwide"])
assert c.job_text("https://example.com/jobs/acme-lead", None, c.LinkedInQueue(False)) is None' "$S"
check "0.38 scope: each field of search_scope stands alone; one missing keeps the env value" "$PY" -I -c '
import json, os, sys; sys.path.insert(0, sys.argv[1]); import collect_postings as c
class E(dict):
    home = sys.argv[2]
    def path(self, k): return os.path.join(self.home, self[k])
p = os.path.join(sys.argv[2], "rec.json")
json.dump({"preferences": {"locations": {"search_scope": {"remote_regions": ["EU"]}}}}, open(p, "w"))
assert c.scope_of(E(MASTER_RECORD="rec.json")) == (["eu"], None)
json.dump([1, 2], open(p, "w"))
assert c.scope_of(E(MASTER_RECORD="rec.json")) == (None, None)' "$S" "$T"

# --- 0.40.0: plan cost table, calibration log, coordinator context --------------------------------------------------
"$PY" -I "$S/cost.py" table pro --env "$ENVF" >"$T/cost-table.out" 2>&1
check "cost table: each step with its source, a steady week, shares unknown before a calibration" sh -c '
    grep -q "^  setup  .* share unknown  (estimate)" "$1" && grep -q "^  steady week " "$1" &&
    grep -q "^target: a steady week within 30% of a Pro week (unknown until calibrated)" "$1"' _ "$T/cost-table.out"
rm -f "$T/pl.log"
for pct in 10 10 12; do
    echo "{\"rate_limits\": {\"seven_day\": {\"used_percentage\": $pct, \"resets_at\": 1900000000}}}" |
        "$PY" -I "$S/statusline.py" --out "$T/pl.json" --log "$T/pl.log" >/dev/null 2>&1
done
check "statusline --log: one row per change of the 7-day share" sh -c '
    [ "$(grep -c seven_day "$1")" -eq 2 ] && tail -1 "$1" | grep -q "\"seven_day\": 12"' _ "$T/pl.log"
mkdir -p "$T/c40"
cat >"$T/mk40.py" <<'PYEOF'
import datetime, json, os, re, sys
home, cc, log = sys.argv[1], sys.argv[2], sys.argv[3]
with open(log, "w", encoding="utf-8") as f:
    f.write(json.dumps({"at": "2026-01-01T00:00:00", "seven_day": 10, "resets_at": "r1"}) + "\n")
    f.write(json.dumps({"at": "2026-01-03T00:00:00", "seven_day": 20, "resets_at": "r1"}) + "\n")
proj = os.path.join(cc, "projects", re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(home)))
os.makedirs(proj, exist_ok=True)
other = os.path.join(cc, "projects", "elsewhere")
os.makedirs(other, exist_ok=True)
def msg(i, at, tokens):
    return json.dumps({"type": "assistant", "timestamp": at, "message": {"id": i, "model": "claude-opus-5-5", "usage": {
        "input_tokens": tokens, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "output_tokens": 0}}})
with open(os.path.join(other, "o.jsonl"), "w", encoding="utf-8") as f:
    f.write(msg("o1", "2026-01-02T00:00:00Z", 1000000) + "\n")
now = datetime.datetime.now(datetime.timezone.utc)
def coordinator(name, started, ctx):
    with open(os.path.join(proj, name + ".jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "user", "timestamp": started.strftime("%Y-%m-%dT%H:%M:%SZ")}) + "\n")
        f.write(json.dumps({"type": "custom-title", "customTitle": "Job search coordinator"}) + "\n")
        f.write(msg(name, now.strftime("%Y-%m-%dT%H:%M:%SZ"), ctx) + "\n")
coordinator(sys.argv[4], now - datetime.timedelta(days=int(sys.argv[5])), int(sys.argv[6]))
PYEOF
"$PY" -I "$T/mk40.py" "$H" "$T/c40" "$H/apply/plan-usage-log.jsonl" k1 0 50000
CLAUDE_CONFIG_DIR="$T/c40" "$PY" -I "$S/cost.py" calibrate max5 --env "$ENVF" >"$T/cal.out" 2>&1
check "cost calibrate: W of every project between two log rows, per point of the rise; Pro week from the plan" sh -c '
    grep -q "^W per 1% of the week: 100k (1.0M W over 10 points" "$1" && grep -q "^Pro week: 2.0M W (from max5, a low figure)" "$1"' \
    _ "$T/cal.out"
CLAUDE_CONFIG_DIR="$T/c40" "$PY" -I "$S/cost.py" context --env "$ENVF" >"$T/ctx1.out" 2>&1
"$PY" -I "$T/mk40.py" "$H" "$T/c40" "$H/apply/plan-usage-log.jsonl" k1 0 250000
CLAUDE_CONFIG_DIR="$T/c40" "$PY" -I "$S/cost.py" context --env "$ENVF" >"$T/ctx2.out" 2>&1
"$PY" -I "$T/mk40.py" "$H" "$T/c40" "$H/apply/plan-usage-log.jsonl" k1 2 50000
CLAUDE_CONFIG_DIR="$T/c40" "$PY" -I "$S/cost.py" context --env "$ENVF" >"$T/ctx3.out" 2>&1
check "cost context: keep today under 200k; hand off past 200k or when started before today" sh -c '
    grep -q "^coordinator context 50k, started .*: keep$" "$1" && grep -q "^coordinator context 250k, .*: hand off$" "$2" &&
    grep -q "^coordinator context 50k, .*: hand off$" "$3"' _ "$T/ctx1.out" "$T/ctx2.out" "$T/ctx3.out"
check "choices: plans pro, max5, max20; SESSION_MODEL sonnet by default" sh -c '
    "$1" -I "$2/choices.py" suggest max20 --env "$3" | grep -q "^SESSION_MODEL=sonnet$" &&
    ! "$1" -I "$2/choices.py" suggest max7 --env "$3" >/dev/null 2>&1' _ "$PY" "$S" "$ENVF"

# --- 0.41.0: fit score, long-shots, unread, new sources, location check, reply feedback --------------------------------
"$PY" -I "$S/choices.py" set APPLY_FITS=normal LONG_SHOTS_PER_DAY=0 --env "$ENVF" >/dev/null 2>&1
# 0.46.0: the grade comes from the kinds of soft gaps (each 1; a domain kind with no adjacent fact 2); the score stays as
# information.
cat >"$T/score41.json" <<'EOF'
{"jobs": [
 {"id": "G1", "action": "apply", "gaps": [], "read": "full", "requirements": [{"text": "Java", "place": "title", "level": "hands_on"}]},
 {"id": "G2", "action": "apply", "gaps": [{"kind": "stack", "what": "Go as the main language"}], "read": "full", "requirements": []},
 {"id": "G3", "action": "apply", "gaps": [{"kind": "stack", "what": "Go"}, {"kind": "scope", "what": "staff role"}], "read": "full", "requirements": []},
 {"id": "G4", "action": "apply", "gaps": [{"kind": "domain", "what": "payments", "closest": "none"}], "read": "full", "requirements": []},
 {"id": "G5", "action": "apply", "gaps": [{"kind": "domain", "what": "payments", "closest": "billing service for a retailer"}], "read": "full", "requirements": []},
 {"id": "G6", "action": "apply", "gaps": [{"kind": "stack", "what": "Go"}, {"kind": "scope", "what": "head role"}, {"kind": "relocation", "what": "moving to another city"}], "read": "full", "requirements": []},
 {"id": "G7", "action": "apply", "gaps": [{"kind": "hard", "what": "security clearance"}], "read": "full", "requirements": []},
 {"id": "G8", "action": "apply", "gaps": [], "read": "summary", "requirements": []},
 {"id": "G9", "action": "skip", "reason": "closed", "gaps": [], "read": "none", "requirements": []},
 {"id": "G10", "action": "apply", "gaps": [], "read": "full", "must_haves": [], "requirements": []},
 {"id": "G11", "action": "apply", "gaps": [{"kind": "stack", "what": "Go"}, {"kind": "stack", "what": "Kubernetes, warning"}], "read": "full", "requirements": []}]}
EOF
"$PY" -I "$S/choices.py" grade "$T/score41.json" --env "$ENVF" >"$T/score41.out" 2>&1
check "fit grade 0.46.0: a read posting with no must-haves and no requirements is never high (no evidence)" \
    grep -q "^G10 | apply | normal | - |" "$T/score41.out"
check "fit grade 0.46.0: two gaps of one kind count once (Go and Kubernetes missing: normal)" \
    grep -q "^G11 | apply | normal | - |" "$T/score41.out"
check "fit grade 0.46.0: soft gap kinds counted (a domain kind with no adjacent fact twice); long-shot and weak are skips at cap 0; hard and unread skip" sh -c '
    grep -q "^G1 | apply | high | 100 |" "$1" && grep -q "^G2 | apply | normal | - |" "$1" &&
    grep -q "^G3 | skip | long-shot | - | long-shot: 2 soft gap kinds (LONG_SHOTS_PER_DAY=0): Go; staff role" "$1" &&
    grep -q "^G4 | skip | long-shot | - | long-shot: 2 soft gap kinds" "$1" && grep -q "^G5 | apply | normal | - |" "$1" &&
    grep -q "^G6 | skip | weak | - | weak: 3 soft gap kinds" "$1" && grep -q "^G7 | skip | - | - | a hard gap: security clearance" "$1" &&
    grep -q "^G8 | skip | unread | - | unread:" "$1" && grep -q "^G9 | skip | - | - | closed" "$1"' _ "$T/score41.out"
if command -v node >/dev/null 2>&1; then
    cat >"$T/score41.js" <<'EOF'
const fs = require('fs')
const src = fs.readFileSync(process.argv[2], 'utf8')
const part = src.slice(src.indexOf('const SOFT = '), src.indexOf('const CHANNEL_NOTES'))
const gradedOnly = new Function('A', part + '; return gradedOnly')({ applyFits: 'normal', longShots: 0 })
for (const j of JSON.parse(fs.readFileSync(process.argv[3], 'utf8')).jobs) {
  const g = gradedOnly(j)
  console.log([j.id, g.action, g.grade || '-', g.score === undefined ? '-' : g.score, g.reason || ''].join(' | '))
}
EOF
    node "$T/score41.js" "$S/../workflows/screen-and-prepare.js" "$T/score41.json" >"$T/score41-js.out" 2>&1
    check "fit score: the workflow (JS) grades every job as choices.py does" diff --strip-trailing-cr "$T/score41.out" "$T/score41-js.out"
else
    echo "SKIP fit score in JS: no node"
fi
"$PY" -I "$S/choices.py" set LONG_SHOTS_PER_DAY=2 --env "$ENVF" >/dev/null 2>&1
check "fit grade 0.46.0: with LONG_SHOTS_PER_DAY above 0 a long-shot and a weak fit go on" sh -c '
    "$1" -I "$2/choices.py" grade "$3" --env "$4" >"$5" && grep -q "^G3 | apply | long-shot | - |" "$5" &&
    grep -q "^G6 | apply | weak | - |" "$5"' _ "$PY" "$S" "$T/score41.json" "$ENVF" "$T/score41b.out"
track add L4 "Lambda Co" "Lead Java Engineer 4" "https://example.com/lambda/4" found_by=script:greenhouse:lambda >/dev/null 2>&1
"$PY" -I - "$H/apply/targets.json" <<'PYEOF2'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
for j in data["jobs"]:
    if j["id"] == "L4":
        j["unread"] = "2026-11-18"
json.dump(data, open(sys.argv[1], "w", encoding="utf-8"))
PYEOF2
mkdir -p "$H/apply/postings"
echo "# Job description: Lambda Co - Lead Java Engineer 4" >"$H/apply/postings/L4.md"
track add X41 "Omicron" "Principal Engineer" "https://old.example.com/x41" >/dev/null 2>&1
cat >"$T/mk41.py" <<'PYEOF'
import datetime, hashlib, json, os, sys
src = sys.argv[1]
os.makedirs(src, exist_ok=True)
now = datetime.datetime.now(datetime.timezone.utc)
iso, epoch = now.strftime("%Y-%m-%dT%H:%M:%SZ"), int(now.timestamp())
def w(name, data):
    with open(os.path.join(src, name), "w", encoding="utf-8") as fh:
        fh.write(data if isinstance(data, str) else json.dumps(data))
pid = lambda url: "P" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]  # noqa: E731
uuid = "11111111-2222-3333-4444-555555555555"
rr = lambda i, title, company, url, **more: dict(id=i, roleTitle=title, company={"name": company}, url=url,  # noqa: E731
                                                 locationType="remote", created_at=iso, **more)
jobs = [rr(1, "Staff Java Engineer", "Acme", f"https://jobs.ashbyhq.com/acmeco/{uuid}"),
        rr(2, "Principal Engineer", "Kappa", "https://boards.greenhouse.io/kappa/jobs/777"),
        rr(3, "Lead Java Engineer", "Lambda Two", "https://jobs.example.com/l3"),
        rr(4, "Junior Java Engineer", "Junio", "https://jobs.example.com/j4", isEntryLevel=True),
        rr(5, "Principal Engineer", "Omicron", "https://new.example.com/o")]
w("remoterocketship-italy.json", '<html><script id="__NEXT_DATA__" type="application/json">'
  + json.dumps({"props": {"pageProps": {"initialJobOpenings": jobs}}}) + "</script></html>")
w("ashby-acmeco.json", {"jobs": [{"id": uuid, "location": "Germany", "isRemote": True,
                                  "secondaryLocations": [{"location": "Italy"}], "descriptionPlain": "Build things."}]})
w("greenhouse-job-777.json", {"location": {"name": "Poland"}, "content": "Office in Warsaw."})
w(f"page-{pid('https://jobs.example.com/l3')}.html", "<p>Candidates must be based in the United States.</p>")
w("workable-search-feed.json", {"jobs": [
    {"title": "Team Lead, Customer Success", "workplace": "remote", "locations": ["Italy"], "company": {"title": "Xi"},
     "created": iso, "url": "https://apply.workable.com/xi/j/A1"},
    {"title": "Team Lead Software Engineer", "workplace": "remote", "locations": ["Germany"], "company": {"title": "Mu"},
     "description": "Work from anywhere in Europe.", "created": iso, "url": "https://apply.workable.com/mu/j/B2"},
    {"title": "Team Lead Platform Engineer", "workplace": "hybrid", "locations": ["Italy"], "company": {"title": "Pi"},
     "created": iso, "url": "https://apply.workable.com/pi/j/C3"},
    {"title": "Team Lead Java Engineer", "workplace": "remote", "locations": ["Spain"], "company": {"title": "Rho"},
     "created": iso, "url": "https://apply.workable.com/rho/j/D4"}]})
w("himalayas-search-Italy.json", {"jobs": [{"title": "Staff Java Engineer", "companyName": "Nu",
    "locationRestrictions": ["Italy", "Spain"], "pubDate": epoch, "applicationLink": "https://himalayas.app/companies/nu/jobs/x"}]})
w("jobicy-feed.status", "429 429 200")
w("jobicy-feed.json", {"jobs": []})
PYEOF
"$PY" -I "$T/mk41.py" "$T/s41-src"
searches add "Remote Rocketship Italy" "java engineer, principal engineer" source=remoterocketship board=italy >/dev/null 2>&1
searches add "Workable search" "team lead" source=workable-search >/dev/null 2>&1
searches add "Himalayas Italy" "java engineer" source=himalayas-search board=Italy >/dev/null 2>&1
for n in 1 2 3; do searches add "Jobicy $n" "java engineer" source=jobicy >/dev/null 2>&1; done
"$PY" -I "$S/collect_postings.py" --from "$T/s41-src" --out "$T/s41-search.json" --add --env "$ENVF" >"$T/s41.out" 2>&1
check "Remote Rocketship: postings from __NEXT_DATA__, entry-level left out; the posting's own page decides its location" sh -c '
    grep -q "^Acme | Staff Java Engineer | Remote, Italy |" "$1" && ! grep -q "Junio" "$1" &&
    grep -q "| Kappa | Principal Engineer | location on its own page: Poland$" "$1" &&
    grep -q "| Lambda Two | Lead Java Engineer | hires only in United States$" "$1" &&
    "$2" -I "$3/dq.py" "$4" "any(j[\"title\"] == \"Staff Java Engineer\" for c in R[\"companies\"] if c[\"name\"] == \"Acme\" for j in c[\"jobs\"])"' \
    _ "$T/s41.out" "$PY" "$T" "$T/s41-search.json"
check "collect: a posting whose employer and title are in the tracker under another link is left out" \
    grep -q "| Omicron | Principal Engineer | the same job as X41 (already in the tracker)$" "$T/s41.out"
check "Workable search: remote only, with a place or region of the person; a team lead needs an engineering word" sh -c '
    grep -q "a team lead without an engineering word" "$1" && grep -q "^Mu | Team Lead Software Engineer |" "$1" &&
    ! grep -q "^Rho |" "$1" && ! grep -q "^Pi |" "$1"' _ "$T/s41.out"
check "Himalayas search: discovery only, the apply link left for the employer's own page" \
    "$PY" -I "$T/dq.py" "$T/s41-search.json" "[(j[\"apply_url\"], bool(j.get(\"apply_note\"))) for c in R[\"companies\"] if c[\"name\"] == \"Nu\" for j in c[\"jobs\"]] == [(\"\", True)]"
check "feeds: 2 refusals in a row stop a source for the run; its rows stay due" \
    grep -q "jobicy stopped this run (2 refusals in a row); it stays due" "$T/s41.out"
check "an unread job goes to the next fit check with its saved text" \
    "$PY" -I "$T/dq.py" "$T/s41-search.json" "[j.get(\"text_file\", \"\").endswith(\"postings/L4.md\") for c in R[\"companies\"] for j in c[\"jobs\"] if j[\"id\"] == \"L4\"] == [True]"
check "searches: boards and Workable search weekly by default; every sets a source's rows" sh -c '
    "$1" -I "$2/dq.py" "$3" "[r[\"every_days\"] for r in (R[\"searches\"] if isinstance(R, dict) else R) if r.get(\"source\") == \"workable-search\"] == [7]" &&
    "$4" -I "$5/searches.py" every jobicy 3 --env "$6" | grep -q "^[0-9]* searches read every 3 days$"' \
    _ "$PY" "$T" "$H/apply/searches.json" "$PY" "$S" "$ENVF"
# 0.43.0: board discovery from web search links; a row turned off
searches add "Acme" "java engineer" source=greenhouse board=acme >"$T/d43-add.out" 2>&1
cat >"$T/d43-links.txt" <<'EOF'
https://boards.greenhouse.io/acme/jobs/123
https://job-boards.greenhouse.io/betaco/jobs/456
https://jobs.ashbyhq.com/gamma.io/abc
https://jobs.lever.co/delta/0f1e2d
https://apply.workable.com/epsilon/j/ABC123/
https://job-boards.greenhouse.io/BetaCo/jobs/789
https://example.com/careers/1
EOF
searches discover --file "$T/d43-links.txt" >"$T/d43.out" 2>&1
check "discover: the five link forms, a saved board and a repeat dropped, an unknown host ignored" sh -c '
    grep -q "^new greenhouse betaco https://job-boards.greenhouse.io/betaco/jobs/456$" "$1" &&
    grep -q "^new ashby gamma.io " "$1" && grep -q "^new lever delta " "$1" && grep -q "^new workable epsilon " "$1" &&
    [ "$(grep -c "^new [a-z]* [^ ]* https://" "$1")" -eq 4 ] && ! grep -q "acme\|example.com" "$1" &&
    grep -q "^new boards: 4; links to saved boards: 2; links not on a board: 1$" "$1"' _ "$T/d43.out"
D43=$(cut -d" " -f1 "$T/d43-add.out")
searches every "$D43" off >"$T/d43-off.out" 2>&1
searches due >"$T/d43-due.out" 2>&1
searches list >"$T/d43-list.out" 2>&1
check "every off: the row is never due and listed as off; a number turns it back on" sh -c '
    grep -q "^1 searches off$" "$1" && ! grep -q "^$4 Acme " "$2" && grep -q "^$4 Acme .*| off since " "$3" &&
    "$5" -I "$6/searches.py" every "$4" 7 --env "$7" >/dev/null && "$5" -I "$6/searches.py" due --env "$7" | grep -q "^$4 Acme "' \
    _ "$T/d43-off.out" "$T/d43-due.out" "$T/d43-list.out" "$D43" "$PY" "$S" "$ENVF"
"$PY" -I "$S/init_career_folder.py" "$T/d43-home" "Jane Doe" >"$T/d43-init.out" 2>&1
check "init: the three study-note files, empty, and INTERVIEW_LESSONS_DIR in job-search.env" sh -c '
    for f in technical screening roadmap; do [ -f "$1/career-records/interview-lessons/$f.md" ] &&
        [ ! -s "$1/career-records/interview-lessons/$f.md" ] || exit 1; done &&
    grep -q "^INTERVIEW_LESSONS_DIR=career-records/interview-lessons$" "$1/job-search.env"' _ "$T/d43-home"
H38=$H
mkhome "$T/h41" old
use "$T/h41"
"$PY" -I - "$H/apply/targets.json" <<'PYEOF2'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
data["companies"].append({"name": "Lambda Co", "verdict": "allow", "jobs": [
    {"id": f"L{n}", "title": f"Lead Java Engineer {n}", "url": f"https://example.com/lambda/{n}", "status": "found",
     "outcome": ""} for n in range(1, 6)]})
json.dump(data, open(sys.argv[1], "w", encoding="utf-8"))
PYEOF2
"$PY" -I "$S/choices.py" set LONG_SHOTS_PER_DAY=2 --env "$ENVF" >/dev/null 2>&1
LS='"gaps": [{"kind": "stack", "what": "Go"}, {"kind": "scope", "what": "staff role"}], "requirements": []'
cat >"$T/journal41.jsonl" <<EOF
{"type": "started", "agentId": "l1", "label": "prep-jobs:Lambda Co"}
{"type": "result", "agentId": "l1", "result": {"jobs": [{"id": "L1", "action": "apply", "read": "full", "title": "Lead Java Engineer 1", $LS}, {"id": "L2", "action": "apply", "read": "full", "title": "Lead Java Engineer 2", $LS}, {"id": "L3", "action": "apply", "read": "full", "title": "Lead Java Engineer 3", $LS}, {"id": "L4", "action": "skip", "grade": "unread", "reason": "unread", "read": "summary", "title": "Lead Java Engineer 4", $LS}, {"id": "L5", "action": "apply", "read": "full", "title": "Lead Java Engineer 5", "gaps": [{"kind": "stack", "what": "Go"}, {"kind": "domain", "what": "payments", "closest": "none"}], "requirements": []}]}}
EOF
track sync "$T/journal41.jsonl" >"$T/sync41.out" 2>&1
check "long-shots and weak fits 0.46.0: at most LONG_SHOTS_PER_DAY together in the queue, the rest wait (a weak fit is no skip); an unread job stays found" sh -c '
    [ "$(grep -c "^L[1235] | Lambda Co" "$1")" -eq 2 ] && grep -q "^long-shots and weak fits waiting for a later day (LONG_SHOTS_PER_DAY): 2$" "$1" &&
    ! grep -q "^L[45] | Lambda Co" "$1" &&
    "$2" -I "$3/dq.py" "$4" "next(j for c in R[\"companies\"] for j in c[\"jobs\"] if j[\"id\"] == \"L4\")[\"status\"] == \"found\"" &&
    "$2" -I "$3/dq.py" "$4" "next(j for c in R[\"companies\"] for j in c[\"jobs\"] if j[\"id\"] == \"L4\").get(\"unread\")" &&
    "$2" -I "$3/dq.py" "$4" "next(j for c in R[\"companies\"] for j in c[\"jobs\"] if j[\"id\"] == \"L5\")[\"prep\"][\"grade\"] == \"weak\""' \
    _ "$T/sync41.out" "$PY" "$T" "$H/apply/targets.json"
track set L1 submitted "sent in the test" >/dev/null 2>&1
"$PY" -I "$S/feedback.py" add J1 rejection not_fit="payments domain" --env "$ENVF" >"$T/fb1.out" 2>&1
"$PY" -I "$S/feedback.py" silent --days 0 --add --env "$ENVF" >"$T/fb2.out" 2>&1
"$PY" -I "$S/feedback.py" clues --env "$ENVF" >"$T/fb3.out" 2>&1
check "feedback: a reply line per job, silence after the days given, clues by role type and variant" sh -c '
    grep -q "^feedback J1: rejection (senior-ic" "$1" && grep -q "^L1 | Lambda Co | Lead Java Engineer 1 |" "$2" &&
    grep -q "^- senior-ic: 0 / 1 / 0$" "$3" && grep -q "^- team-tech-lead: 0 / 0 / 1$" "$3" &&
    grep -q "payments domain$" "$3"' _ "$T/fb1.out" "$T/fb2.out" "$H/apply/fit-clues.md"
cat >>"$H/apply/reply-feedback.jsonl" <<'EOF'
{"date": "2026-11-10", "job": "F1", "outcome": "rejection", "score": 66, "grade": "normal"}
{"date": "2026-11-10", "job": "F2", "outcome": "rejection", "score": 67, "grade": "normal"}
{"date": "2026-11-10", "job": "F3", "outcome": "silence", "score": 68, "grade": "normal"}
{"date": "2026-11-10", "job": "F4", "outcome": "rejection", "score": 65, "grade": "normal"}
{"date": "2026-11-10", "job": "F5", "outcome": "rejection", "score": 69, "grade": "normal"}
EOF
check "feedback analyse: replies by score band; a normal band with 5 replies and no invitation proposes a higher normal" sh -c '
    "$1" -I "$2/feedback.py" analyse --env "$3" | grep -q "^proposal: raise normal from 65 to 70: 5 replies at 65-69, no invitation$"' \
    _ "$PY" "$S" "$ENVF"

# --- 0.42.0: the dashboard review: page date logic, list fields as text, check lines, one row per site -------------
mkhome "$T/h42" flat
use "$T/h42"
cat >"$T/mk42.py" <<'PYEOF'
import datetime
import json
import sys

home = sys.argv[1]
day = lambda n: (datetime.date.today() + datetime.timedelta(days=n)).isoformat()  # noqa: E731
now = datetime.datetime.now().replace(microsecond=0)
job = lambda i, company, title, status, **more: dict(  # noqa: E731
    {"id": i, "company": company, "title": title, "url": f"https://example.com/{i.lower()}", "status": status,
     "note": ""}, **more)
jobs = [
    job("K1", "Acme Corp", "Staff Engineer", "submitted", applied=day(-20)),
    job("K2", "Acme Corp", "Staff Engineer (m/f/d)", "submitted", applied=day(-1)),
    job("K3", "Kappa Co", "Developer", "needs-jane", note="hand score 68"),
    job("K4", "Lambda Co", "Engineer", "to-apply", grade="long-shot"),
    job("K5", "Mu Ltd", "Analyst", "found", unread=day(-1)),
    job("K6", "Nu Inc", "Lead", "submitted", applied=day(-3),
        todo=[{"kind": "todo", "text": "Claude: score with the weighted fit check", "since": day(-1)}]),
    job("K7", "Xi AG", "Architect", "submitted", applied=day(-30)),
    job("K8", "Omicron SA", "Manager", "submitted", applied=day(-4)),
    job("K9", "Pi Co", "Tester", "submitted", applied=day(-4)),
    job("K10", "Rho Srl", "Developer", "submitted", applied=day(-4)),
    job("K11", "Sigma Co", "Engineer", "account-needed"),
    job("K13", "Tau Ltd", "Engineer", "needs-person",
        todo=[{"kind": "todo", "text": "send the references", "due": day(5), "since": day(-1)}]),
]
pipeline = {
    "K7": {"stage": "approved", "steps": [{"date": day(-12), "name": "Screening call", "done": day(-12)}]},
    "K8": {"stage": "approved", "steps": [{"date": day(3), "name": "Performance chat"}]},
    "K9": {"stage": "pending", "steps": [{"date": day(2), "due": day(2), "name": "Online test"}]},
    "K10": {"stage": "approved", "steps": [{"name": "Phone call (to be proposed)"}]},
}
site = lambda i, status, checked, **more: dict(  # noqa: E731
    {"id": i, "name": i, "kind": "site", "status": status, "checked": checked.isoformat(), "note": "",
     "jobs": []}, **more)
logins = [site("LinkedIn", "signed-in", now - datetime.timedelta(days=5), jobs=["K14"]),
          site("Workday · Acme", "needs-sign-in", now, fix="sign in again"),
          site("LinkedIn Easy Apply", "needs-sign-in", now - datetime.timedelta(hours=2), jobs=["K11"],
               link="https://www.linkedin.com/jobs/"),
          site("linkedin", "needs-sign-in", now - datetime.timedelta(hours=1), jobs=["K12"]),
          site("DataCo", "signed-in", now, link="https://www.linkedin.com/jobs/view/1")]
for name, data in (("targets", {"jobs": jobs}), ("pipeline", pipeline), ("logins", {"logins": logins})):
    with open(f"{home}/apply/{name}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
with open(f"{home}/apply/usage-log.jsonl", "w", encoding="utf-8") as f:
    f.write(json.dumps({"step": "run", "result": "started",
                        "time": (now - datetime.timedelta(hours=10)).isoformat()}) + "\n")
with open(f"{home}/apply/dashboard-uploads.json", "w", encoding="utf-8") as f:
    json.dump({"at": now.isoformat(), "files": {"index.json": "0" * 64}}, f)
PYEOF
"$PY" -I "$T/mk42.py" "$H"
"$PY" -I "$S/build_app_folders.py" --env "$ENVF" >/dev/null 2>&1
"$PY" -I "$S/export_dashboard.py" "$T/d42" --env "$ENVF" >"$T/d42.out" 2>&1
"$PY" -I "$S/export_dashboard.py" --check --env "$ENVF" >"$T/d42c.out" 2>&1
check "export 0.42: the same employer and role sent twice is a check line (records.py dupes) and a flag on the later row" sh -c '
    grep -q "^check: dupes: the same employer and role twice: K1 and K2 Acme Corp" "$1" &&
    "$2" -I "$3/dq.py" "$4/applications.json" "K[\"K2\"][\"again\"] == \"re-application of K1\" and K[\"K1\"][\"again\"] == \"\""' \
    _ "$T/d42.out" "$PY" "$T" "$T/d42"
check "export 0.42: a status the plugin does not know is a check line; its note is a Waits on you row with a check" sh -c '
    grep -q "^check: shape: tracker K3 status: .needs-jane. is not one of" "$1" &&
    grep -q "^check: waits: needs-jane with no waits_on and no to-do: .*K3" "$1" &&
    "$2" -I "$3/dq.py" "$4/actions.json" "K[\"K3:todo\"][\"text\"] == \"Waits on you: hand score 68\""' \
    _ "$T/d42.out" "$PY" "$T" "$T/d42"
check "export 0.42: Claude's own to-do, a job ready to send (with its long-shot) and an unread posting are Claude's next" \
    dq "$T/d42/actions.json" \
    'K["K6:1"]["kind"] == "queued" and "1 long-shot wait" in K["queued:send"]["text"] and K["queued:unread"]["kind"] == "queued" and not any(r["key"] == "K4:todo" or r["key"] == "K5:noowner" for r in R)'
check "export 0.42: whole words only: \"Performance chat\" is no task row; a step with no date is proposed" sh -c '
    "$1" -I "$2/dq.py" "$3/actions.json" "not any(\"Performance chat\" in r[\"text\"] for r in R)" &&
    "$1" -I "$2/dq.py" "$3/steps.json" "K[\"K10#1\"][\"state\"] == \"proposed\""' _ "$PY" "$T" "$T/d42"
check "export 0.42: a pending job's PIPELINE steps are rows; Moving forward idle 7 days is a check line" sh -c '
    "$1" -I "$2/dq.py" "$3/steps.json" "K[\"K9#1\"][\"state\"] == \"upcoming\"" &&
    grep -q "^check: moving forward, nothing since .*: K7 Xi AG" "$4"' _ "$PY" "$T" "$T/d42" "$T/d42.out"
check "export 0.42: one row per job board, the plainest name kept, the latest check's state, all its jobs; no job waiting is no need" sh -c '
    "$1" -I "$2/dq.py" "$3/logins.json" "len(R) == 3 and K[\"LinkedIn\"][\"jobs\"] == 3 and K[\"LinkedIn\"][\"status\"] == \"needs-sign-in\" and K[\"LinkedIn\"][\"needs\"] == \"yes\" and K[\"DataCo\"][\"needs\"] == \"\" and not any(r[\"needs\"] for r in R if r[\"id\"].startswith(\"Workday\"))" &&
    grep -q "^check: one site, 3 login rows: LinkedIn, LinkedIn Easy Apply, linkedin -> keep LinkedIn in LOGINS with the latest check (needs-sign-in" "$4" &&
    grep -q "^check: a site.s link is a job board.s page: DataCo" "$4"' _ "$PY" "$T" "$T/d42" "$T/d42.out"
check "export 0.42: a run with no end for hours reads no end recorded; --check says the page is behind" sh -c '
    "$1" -I "$2/dq.py" "$3/index.json" "\"no end recorded\" in K[\"meta:run\"][\"label\"] and K[\"meta:calendar_color\"][\"label\"] == \"3\"" &&
    head -n 1 "$4" | grep -q "^check: the page is behind the records: index.json"' _ "$PY" "$T" "$T/d42" "$T/d42c.out"
check "export 0.42: a to-do with a due date is a task on a deadline" dq "$T/d42/actions.json" 'K["K13:1"]["kind"] == "task"'
# 0.42.1: the export time alone is no change: an upload recorded with another export time, then --check and a new
# export find nothing behind.
"$PY" -I - "$T/d42/index.json" <<'PYEOF'
import json
import sys
rows = json.load(open(sys.argv[1], encoding="utf-8"))
for r in rows:
    if r.get("key") == "meta:generated":
        r["label"] = "2000-01-01 00:00"
json.dump(rows, open(sys.argv[1], "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
PYEOF
"$PY" -I "$S/export_dashboard.py" --uploaded "$T/d42" all --env "$ENVF" >/dev/null 2>&1 || echo "setup failed: --uploaded" >&2
"$PY" -I "$S/export_dashboard.py" --check --env "$ENVF" >"$T/d42c2.out" 2>&1 || echo "setup failed: --check" >&2
"$PY" -I "$S/export_dashboard.py" "$T/d42b" --env "$ENVF" >"$T/d42b.out" 2>&1 || echo "setup failed: export" >&2
check "export 0.42.1: after --uploaded all, another export time is not behind and nothing is to upload" sh -c '
    ! grep -q "page is behind" "$1" && grep -q "^upload: none$" "$2" && grep -q "^unchanged: index.json" "$2"' _ "$T/d42c2.out" "$T/d42b.out"
cat >"$T/run42.py" <<'PYEOF'
import json
import sys
rows = {"alone": [("2026-11-16T22:25:00", "started"), ("2026-11-16T22:57:00", "ok"), ("2026-11-18T01:34:00", "ok")],
        "night": [("2026-11-16T22:25:00", "started"), ("2026-11-17T01:34:00", "ok")]}[sys.argv[2]]
with open(sys.argv[1], "w", encoding="utf-8") as f:
    for t, r in rows:
        f.write(json.dumps({"step": "run", "time": t, "result": r}))
        f.write(chr(10))
PYEOF
"$PY" -I "$T/run42.py" "$H/apply/usage-log.jsonl" alone
"$PY" -I "$S/export_dashboard.py" "$T/d42a" --env "$ENVF" >/dev/null 2>&1
"$PY" -I "$T/run42.py" "$H/apply/usage-log.jsonl" night
"$PY" -I "$S/export_dashboard.py" "$T/d42b" --env "$ENVF" >/dev/null 2>&1
check "export 0.42: an end alone reads no start recorded; a run past midnight keeps its end date" sh -c '
    "$1" -I "$2/dq.py" "$3/index.json" "K[\"meta:run\"][\"label\"].startswith(\"Last run ended 2026-11-18 01:34: finished; no start recorded.\")" &&
    "$1" -I "$2/dq.py" "$4/index.json" "K[\"meta:run\"][\"label\"].startswith(\"Last run 2026-11-16 22:25 to 2026-11-17 01:34: finished.\")"' \
    _ "$PY" "$T" "$T/d42a" "$T/d42b"
cat >"$H/apply/questions.json" <<'QEOF'
{"questions": {"job-k1-old": {"kind": "job", "status": "done", "asked": "2026-11-15", "text": "An older done question",
  "jobs": ["K1"], "note": "Done.", "noted_at": "2099-01-01T00:00:00.000Z"}}}
QEOF
mkdir -p "$T/q42"
questions build "$T/q42" >/dev/null 2>&1
check "questions build 0.42: an older done status is shown under Done" dq "$T/q42/questions/job-k1-old.json" 'R["done"] is True and R["open"] is False'
check "questions build 0.42: with no round recorded, the last answer's time comes from the questions" dq "$T/q42/status/run.json" \
    'R["recorded_at"] == "2099-01-01T00:00:00.000Z"'
check "pay mask 0.42: whole words; \"Moderate\" and \"Corporate\" stay, a salary line is masked" "$PY" -I -c '
import sys; sys.path.insert(0, sys.argv[1]); from trackerlib import no_pay
assert no_pay("Moderate English, Corporate rate") == "Moderate English, Corporate rate", no_pay("Moderate English, Corporate rate")
assert no_pay("salary 70k") == "[private]"' "$S"
check "choices 0.42: EMAILED_CODES and OPTIONAL_FIELDS default off; bad values refused; show names essays" sh -c '
    "$1" -I "$2/choices.py" show --env "$3" | grep -q "^EMAILED_CODES=off  (default)" &&
    "$1" -I "$2/choices.py" show --env "$3" | grep -q "^OPTIONAL_FIELDS=off  (default)" &&
    "$1" -I "$2/choices.py" show --env "$3" | grep -q "^essays: ask" &&
    ! "$1" -I "$2/choices.py" set EMAILED_CODES=maybe --env "$3" >/dev/null 2>&1 &&
    "$1" -I "$2/choices.py" set EMAILED_CODES=on OPTIONAL_FIELDS=fill --env "$3" >/dev/null &&
    "$1" -I "$2/track.py" brief K4 --env "$3" | head -n 1 | grep -q "^filling: LETTERS=asked EMAILED_CODES=on OPTIONAL_FIELDS=fill first_name=Jane$"' \
    _ "$PY" "$S" "$ENVF"
cat >"$T/ecb.xml" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
<Cube><Cube time="2026-11-19"><Cube currency="USD" rate="1.0812"/><Cube currency="GBP" rate="0.8400"/></Cube></Cube>
</gesmes:Envelope>
EOF
check "fx: the ECB rate of the saved day, rounded up, with the line naming ECB and the date; a missing rate exits 1" sh -c '
    [ "$("$1" -I "$2/fx.py" 60000 EUR USD --rates "$3")" = "60000 EUR = 64872 USD (ECB 1.0812, 2026-11-19)" ] &&
    [ "$("$1" -I "$2/fx.py" 64872 usd eur --rates "$3")" = "64872 USD = 60000 EUR (ECB 0.9249, 2026-11-19)" ] &&
    ! "$1" -I "$2/fx.py" 100 EUR JPY --rates "$3" 2>/dev/null' _ "$PY" "$S" "$T/ecb.xml"
if command -v node >/dev/null 2>&1; then
    # The page's own calculations, with the runtime's shapes: list fields as JSON text, numbers as numbers, and a
    # fixed "today". Seen 19 Nov: list fields as text emptied Do now, Sessions and Hiring steps.
    cat >"$T/page42.js" <<'EOF'
const fs = require('fs')
const html = fs.readFileSync(process.argv[2], 'utf8')
const js = html.slice(html.indexOf('<script>') + 8, html.lastIndexOf('</script>'))
const pad = (n) => String(n).padStart(2, '0')
const fmt = (f) => (d) => f === '%H:%M' ? pad(d.getHours()) + ':' + pad(d.getMinutes())
  : d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate())
const calcs = {}
global.window = global
global.d3 = { timeFormat: fmt, timeDay: { offset: (d, n) => new Date(d.getTime() + n * 864e5) } }
global.dash = { calc: (id, o) => { calcs[id] = o }, loader () {}, draw () {}, setParams () {}, setLink () {}, onData () {},
                data: () => ({ status: 'loading', data: [] }) }
global.document = { querySelectorAll: () => [], getElementById: () => null }
global.location = { hash: '' }
new Function(js)()
window.jaToday = () => '2026-11-19'
const apps = [{ id: 'A1', company: 'Acme', role: 'Engineer', stage: 'Moving forward' },
              { id: 'A2', company: 'Acme', role: 'Lead', stage: 'Moving forward' }]
const steps = calcs.steps_view.fn([
  { key: 'A1#1', app: 'A1', step: 'Call', date: '2026-11-18', due: '', state: 'upcoming', also: '["A2"]' },
  { key: 'A1#2', app: 'A1', step: 'Test', date: '2026-11-20', due: '2026-11-25', state: 'upcoming', also: '[]' },
  { key: 'A1#3', app: 'A1', step: 'Phone', date: '', due: '', state: 'proposed', also: '' }], apps)
const k = Object.fromEntries(steps.map((r) => [r.key, r]))
const doNow = calcs.do_now.fn([
  { key: 'x1', app: 'A1', kind: 'task', due: '2026-11-19', text: 'test' },
  { key: 'x2', app: 'A1', kind: 'todo', due: '2026-11-18', text: 'reply' },
  { key: 'x3', app: '', apps: '["A1","A2"]', kind: 'queued', due: '', text: 'two ready' }], apps, [])
const d = Object.fromEntries(doNow.map((r) => [r.key, r]))
const counts = Object.fromEntries(calcs.do_counts.fn(doNow).map((r) => [r.kind, r.n]))
const cal = calcs.calendar_jobs.fn([
  { id: 'c1', start: '2099-01-01T10:00:00', end: '2099-01-01T11:00:00', all_day: false, title: 'Job search · Acme call', color: '', where: '', meet: 'https://meet.example.com/a', link: 'https://cal.example.com/1', job: '' },
  { id: 'c2', start: '2099-01-02T10:00:00', end: '2099-01-02T11:00:00', all_day: false, title: 'Beta call', color: '3', where: 'https://zoom.example.com/b', meet: '', link: 'https://cal.example.com/2', job: '' }],
  apps, [{ key: 'meta:calendar_color', label: '3' }, { key: 'meta:calendar_prefix', label: 'Job search ·' }])
const sess = calcs.sessions_view.fn([{ id: 's1', rank: 1, state: 'you', title: 'Prep', apps: '["A2"]', link: 'https://claude.ai/x' }], apps)
console.log([k['A1#1'].state, k['A1#1'].company, k['A1#2'].when, k['A1#2'].state, k['A1#3'].state,
             d.x1.kind, d.x2.kind, d.x3.for, doNow[0].key, counts.urgent, counts.late, sess[0].jobs, sess[0].link,
             cal.map((e) => e.title + '/' + e.where + '/' + e.link).join(';')].join(' | '))
EOF
    node "$T/page42.js" "$S/../templates/dashboard/index.html" >"$T/page42.out" 2>&1
    # The expected line holds a middle dot and an en dash: written by a heredoc, never passed in argv.
    cat >"$T/page42.want" <<'EOF'
Past | Acme: Engineer; Lead | 2026-11-20 · due 2026-11-25 | Upcoming | Proposed, no date yet | urgent | late | Acme – Engineer; Acme – Lead | x1 | 1 | 1 | Acme – Lead | https://claude.ai/x | Acme call/Video call/https://meet.example.com/a;Beta call/Video call/https://zoom.example.com/b
EOF
    check "page 0.42: list fields as JSON text; past, proposed and due worked out for today; counts from the rows" \
        diff --strip-trailing-cr "$T/page42.want" "$T/page42.out"
else
    echo "SKIP page 0.42 date logic: no node"
fi
# 0.44.0: a sign-in at the employer's own site, one login row per site, discussed and dropped questions, one --check
# for both pages, repeat_of. The middle dot of "Workday · Beta" is written by the heredoc's escape, never in argv.
mkhome "$T/h44" flat
use "$T/h44"
cat >"$T/mk44.py" <<'PYEOF'
import datetime
import json
import sys

home = sys.argv[1]
now = datetime.datetime.now().replace(microsecond=0)
day = lambda n: (datetime.date.today() + datetime.timedelta(days=n)).isoformat()  # noqa: E731
job = lambda i, company, title, status, **more: dict(  # noqa: E731
    {"id": i, "company": company, "title": title, "url": f"https://www.linkedin.com/jobs/view/{i[1:]}0000/",
     "status": status, "note": ""}, **more)
jobs = [
    job("A1", "Acme Corp", "Backend Engineer", "found", platform="LinkedIn"),
    job("A2", "Beta Ltd", "Platform Engineer", "found", platform="LinkedIn Easy Apply"),
    job("A3", "Gamma Co", "Data Engineer", "skipped"),
    job("A4", "Delta Co", "Engineer", "skipped"),
    job("A5", "Kappa Co", "Staff Engineer", "submitted", applied=day(-20)),
    job("A6", "Kappa Co", "Staff Engineer", "submitted", applied=day(-1)),
    job("A7", "Mu Co", "Engineer", "account-needed", platform="linkedin"),
    job("A8", "Nu Co", "Engineer", "account-needed", platform="linkedin",
        todo=[{"kind": "click", "text": "sign in", "login": "linkedin", "since": day(-1)}]),
    job("A9", "Xi Co", "Engineer", "to-apply", platform="linkedin"),
    job("A10", "Omicron Co", "Engineer", "account-needed", platform="Indeed Apply"),
    job("A11", "Pi Co", "Engineer", "account-needed", platform="indeed apply"),
]
site = lambda i, status, checked, note, **more: dict(  # noqa: E731
    {"id": i, "name": i, "kind": "site", "status": status, "checked": checked.isoformat(), "note": note,
     "jobs": []}, **more)
logins = [site("LinkedIn", "signed-in", now - datetime.timedelta(days=5), "signed in"),
          site("linkedin", "needs-sign-in", now, "an application waits on this site's sign-in or account",
               jobs=["A7"]),
          site("Workday · Beta", "needs-sign-in", now - datetime.timedelta(days=7), "Sign in on Beta's Workday")]
questions = {"_about": "made up", "handled": {"at": "", "summary": "0 recorded, 2 to discuss"}, "questions": {
    "job-a3-why-gamma": {"kind": "job", "text": "Why Gamma?", "status": "open", "asked": day(-3), "jobs": ["A3"],
                         "discuss": day(-2)},
    "job-a4-why-delta": {"kind": "job", "text": "Why Delta?", "status": "open", "asked": day(-3), "jobs": ["A4"]}}}
for name, data in (("targets", {"jobs": jobs}), ("logins", {"logins": logins}), ("questions", questions)):
    with open(f"{home}/apply/{name}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
PYEOF
"$PY" -I "$T/mk44.py" "$H"
"$PY" -I "$S/build_app_folders.py" --env "$ENVF" >/dev/null 2>&1
"$PY" -I "$S/export_dashboard.py" "$T/d44" --env "$ENVF" >"$T/d44.out" 2>&1
"$PY" -I "$S/export_dashboard.py" --check --env "$ENVF" >"$T/d44c.out" 2>&1
check "export 0.44: a board row sync made never overrides a checked sign-in: the merged row is signed in" \
    dq "$T/d44/logins.json" 'K["LinkedIn"]["status"] == "signed-in"'
check "export 0.44: an account at no named site and a sign-in to-do naming a board are check lines; Claude finds the site" sh -c '
    grep -q "^check: waits: account-needed with no site named: A7 " "$1" &&
    grep -q "^check: waits: a wait or sign-in to-do names a job board.*A8 (linkedin)" "$1" &&
    "$2" -I "$3/dq.py" "$4/actions.json" "K[\"queued:nosite\"][\"text\"].startswith(\"1 application waits on an account\") and \"A7:signin\" not in K"' \
    _ "$T/d44.out" "$PY" "$T" "$T/d44"
check "export 0.44: --check names a Questions page with no build record" grep -q "^check: the Questions page has no build record" "$T/d44c.out"
questions build "$T/q44" >"$T/q44.out" 2>&1
check "build 0.44: a discussed question whose job ended stays open, with what happened" \
    dq "$T/q44/questions/job-a3-why-gamma.json" 'R["open"] and R["note"].startswith("Gamma Co") and R["note"].endswith("was skipped: still needed?")'
check "build 0.44: an undiscussed one is dropped with a note and shown under Done" \
    dq "$T/q44/questions/job-a4-why-delta.json" 'R["done"] and not R["open"] and R["note"].startswith("Dropped: Delta Co") and R["note"].endswith("was skipped; nothing to answer now.")'
check "build 0.44: \"to discuss\" is counted now, not copied from the last record" \
    dq "$T/q44/status/run.json" 'R["summary"] == "0 recorded, 1 to discuss"'
questions build --check >"$T/q44c1.out" 2>&1
questions note job-a3-why-gamma "Asked again in the chat." >"$T/q44n.out" 2>&1
questions build --check >"$T/q44c2.out" 2>&1
"$PY" -I "$S/export_dashboard.py" --check --env "$ENVF" >"$T/d44c2.out" 2>&1
check "build 0.44: --check is up to date after a build; a note makes the page behind, in export --check too" sh -c '
    grep -q "^the Questions page is up to date$" "$1" && grep -q "^the Questions page is behind the records: 1 file(s)" "$2" &&
    grep -q "^check: the Questions page is behind the records: 1 file(s)" "$3" && grep -q "^pages behind: refresh both" "$4"' \
    _ "$T/q44c1.out" "$T/q44c2.out" "$T/d44c2.out" "$T/q44n.out"
questions add job "Which of these two?" job=A1 detail="https://example.com/p/1 or https://example.com/p/2" >"$T/q44a1.out" 2>&1
echo "exit $?" >>"$T/q44a1.out"
questions add job "Which of these two?" job=A1 detail="https://example.com/p/1 or https://example.com/p/2" --one-job >"$T/q44a2.out" 2>&1
check "questions 0.44: several links with one job are refused; --one-job lets them through" sh -c '
    grep -q "2 links and one job: name every job" "$1" && grep -q "^exit 1$" "$1" && grep -q "^job-a1-which-of-these-two -> A1$" "$2"' \
    _ "$T/q44a1.out" "$T/q44a2.out"
printf 'I build payment systems that stay up.\n' >"$T/q44-answer.md"
questions answer job-a1-which-of-these-two --file "$T/q44-answer.md" >"$T/q44ans.out" 2>&1
check "questions 0.44: answer --file records the text of the file" sh -c '
    grep -q "^job-a1-which-of-these-two: recorded" "$1" && grep -q "I build payment systems that stay up." "$2"' \
    _ "$T/q44ans.out" "$H/apply/targets.json"
track wait A1 account-needed "create the candidate account" >"$T/w44a.out" 2>&1
echo "exit $?" >>"$T/w44a.out"
track wait A1 account-needed "create the candidate account" login="Acme careers" >"$T/w44b.out" 2>&1
track wait A2 account-needed "sign in to LinkedIn" >"$T/w44c.out" 2>&1
"$PY" -I "$S/logins.py" sync --env "$ENVF" >"$T/l44.out" 2>&1
check "wait 0.44: a job found on a board needs login= for its site; with it, sync files the job under that site" sh -c '
    grep -q "account-needed needs login=<site>" "$1" && grep -q "^exit 1$" "$1" && grep -q "^pages behind: refresh both" "$2" &&
    "$3" -I "$4/dq.py" "$5" "[r for r in R[\"logins\"] if r[\"id\"] == \"Acme careers\"][0][\"jobs\"] == [\"A1\"]"' \
    _ "$T/w44a.out" "$T/w44b.out" "$PY" "$T" "$H/apply/logins.json"
check "logins 0.44: an Easy Apply job waits under the board's row; the empty row sync made goes; no second board row" \
    dq "$H/apply/logins.json" '[r["jobs"] for r in R["logins"] if r["id"] == "LinkedIn"] == [["A2"]] and not any(r["id"] in ("linkedin", "LinkedIn Easy Apply") for r in R["logins"])'
check "logins 0.44: two spellings of one board with no row yet make one row" \
    dq "$H/apply/logins.json" '[sorted(r["jobs"]) for r in R["logins"] if "indeed" in r["id"].lower()] == [["A10", "A11"]]'
"$PY" -I "$S/check_setup.py" --needs --env "$ENVF" >"$T/needs44.out" 2>&1
check "check_setup 0.44: a planned job whose site is not named asks for no sign-in" sh -c '
    ! grep -q "^sign in to :" "$1" && ! grep -q "Traceback" "$1"' _ "$T/needs44.out"
questions add job "Which one?" job=A2 detail="https://example.com/p/1 and https://example.com/p/1/." >"$T/q44a3.out" 2>&1
check "questions 0.44: one posting written twice is one link" grep -q "^job-a2-which-one -> A2$" "$T/q44a3.out"
check "logins 0.44: a hand-set row no job waits on says so; its old note is in its history; its state stays" \
    dq "$H/apply/logins.json" 'any(r["id"].startswith("Workday") and r["status"] == "needs-sign-in" and r["note"].startswith("no application waits on it (since ") and r["history"][-1]["note"] == "Sign in on Beta'"'"'s Workday" for r in R["logins"])'
track set A6 submitted "" repeat_of=A5 >"$T/r44.out" 2>&1
"$PY" -I "$S/export_dashboard.py" "$T/d44b" --env "$ENVF" >"$T/d44b.out" 2>&1
check "export 0.44: the same role twice is a check line until the later job names the earlier; the flag stays" sh -c '
    grep -q "^check: dupes: the same employer and role twice: A5 and A6 Kappa Co.*repeat_of=A5$" "$1" &&
    ! grep -q "the same employer and role twice" "$2" &&
    "$3" -I "$4/dq.py" "$5/applications.json" "K[\"A6\"][\"again\"] == \"re-application of A5\""' \
    _ "$T/d44.out" "$T/d44b.out" "$PY" "$T" "$T/d44b"
mkhome "$T/h44o" old
use "$T/h44o"
"$PY" -I - "$H/apply/targets.json" <<'PYEOF'
import json
import sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
for n, name in ((7, "Acme Defence Systems"), (8, "Acme Defence Systems GmbH")):
    data["companies"].append({"name": name, "verdict": "allow", "jobs": [
        {"id": f"L4{n}", "title": "Engineer", "url": f"https://example.com/l4{n}", "status": "found", "outcome": ""}]})
json.dump(data, open(sys.argv[1], "w", encoding="utf-8"))
PYEOF
cat >"$T/journal44.jsonl" <<'EOF'
{"type": "started", "agentId": "c1", "label": "excl-screen:Acme"}
{"type": "result", "agentId": "c1", "result": {"verdict": "exclude", "hits": [{"criterion": "A", "finding": "made up"}], "ties": []}}
{"type": "started", "agentId": "c2", "label": "excl-screen:Acme Defence Systems"}
{"type": "result", "agentId": "c2", "result": {"verdict": "exclude", "hits": [{"criterion": "A", "finding": "made up"}], "ties": []}}
EOF
track sync "$T/journal44.jsonl" >"$T/s44.out" 2>&1
check "sync 0.44: a result labelled with another employer's shorter name is never taken" \
    "$PY" -I "$T/q.py" "$H/apply/targets.json" companies.0.verdict eq allow
check "sync 0.44: a 20-character name that is another employer's whole name is that employer's only" \
    dq "$H/apply/targets.json" '{c["name"]: c["verdict"] for c in R["companies"]}["Acme Defence Systems"] == "exclude" and {c["name"]: c["verdict"] for c in R["companies"]}["Acme Defence Systems GmbH"] == "allow"'
# 0.44.1: the prepared file holds only the jobs to apply to and is merged with the fit result by job id; a reply that
# names the file in a sentence; a job whose review is still due is held; a screened employer is marked, and --screen
# runs once; make_letter_pdf takes the company and role from the prepared file.
mkdir -p "$T/prep441"
cat >"$T/prep441/epsilon-1.json" <<'EOF'
{"company": "Epsilon Co", "jobs": [{"id": "E1", "title": "Tester", "apply_url": "https://example.com/e1/apply", "action": "apply", "platform": "Greenhouse", "variant": "", "salary": 0, "setup": "remote", "cv_pdf": "", "letter_pdf": "", "letter_txt": "", "answers": [{"question": "Notice period", "answer": "1 month"}], "needs": [], "notes": "", "review": "done"}]}
EOF
cat >"$T/prep441/gamma-2.json" <<'EOF'
{"company": "Gamma Inc", "jobs": [{"id": "J3", "title": "Designer", "apply_url": "https://example.com/j3/apply", "action": "apply", "platform": "Ashby", "variant": "", "salary": 0, "setup": "remote", "cv_pdf": "", "letter_pdf": "", "letter_txt": "", "answers": [], "needs": [], "notes": "", "review": "due"}]}
EOF
"$PY" -I - "$T/journal441.jsonl" "$T/prep441" <<'PYEOF'
import json
import sys
journal, folder = sys.argv[1], sys.argv[2].replace("\\", "/")
fit = lambda i, t: {"jobs": [{"id": i, "title": t, "action": "apply", "read": "full", "gaps": [], "reason": "fits",  # noqa: E731
                              "requirements": [{"text": "Testing", "place": "title", "level": "hands_on"}]}]}
rows = [("s1", "excl-screen:Epsilon Co", {"verdict": "allow", "hits": [], "ties": [], "checks": []}),
        ("f1", "prep-fit:Epsilon Co", fit("E1", "Tester")),
        ("v1", "excl-verify:Epsilon Co", {"verdict": "allow", "hits": [], "ties": [], "checks": []}),
        ("p1", "prep-jobs:Epsilon Co", f"Wrote and/or saved {folder}/epsilon-1.json"),
        ("f2", "prep-fit:Gamma Inc", fit("J3", "Designer")),
        ("p2", "prep-jobs:Gamma Inc", f"`{folder}/gamma-2.json`")]
with open(journal, "w", encoding="utf-8") as f:
    for agent, label, result in rows:
        f.write(json.dumps({"type": "started", "agentId": agent, "label": label}) + "\n")
        f.write(json.dumps({"type": "result", "agentId": agent, "result": result}) + "\n")
PYEOF
track sync "$T/journal441.jsonl" >"$T/s441.out" 2>&1
check "sync 0.44.1: a prepared file named in a sentence is read, merged with the fit result by job id" \
    dq "$H/apply/targets.json" '[(j["prep"]["answers"][0]["answer"], j["prep"]["requirements"][0]["text"], j["status"]) for c in R["companies"] if c["name"] == "Epsilon Co" for j in c["jobs"]] == [("1 month", "Testing", "pending")]'
check "sync 0.44.1: a job whose review is still due is held: no prep, still found, marked unreviewed" \
    dq "$H/apply/targets.json" '[(j["status"], "prep" in j, bool(j.get("unreviewed"))) for c in R["companies"] if c["name"] == "Gamma Inc" for j in c["jobs"]] == [("found", False, True)]'
check "sync 0.44.1: an employer whose full check completed is marked screened today" \
    dq "$H/apply/targets.json" '[c.get("screened") for c in R["companies"] if c["name"] == "Epsilon Co"] == [__import__("datetime").date.today().isoformat()]'
CLAUDE_CONFIG_DIR="$T/no-config" "$PY" -I "$S/workflow_args.py" --screen "Epsilon Co" --screen "Gamma Inc" --out "$T/scr441" --env "$ENVF" >"$T/scr441.out" 2>&1
check "workflow_args 0.44.1: --screen runs once per employer: a screened one is named, another is screen-only" sh -c '
    grep -q "^screened on .*: Epsilon Co$" "$1" &&
    "$2" -I "$3/dq.py" "$4/args.json" "[(c[\"name\"], c.get(\"screen\"), c.get(\"screen_only\")) for c in R[\"companies\"]] == [(\"Gamma Inc\", True, True)]"' \
    _ "$T/scr441.out" "$PY" "$T" "$T/scr441"
"$PY" -I "$S/make_letter_pdf.py" --job-file "$T/prep441/epsilon-1.json" --job NOPE --body "$T/none.txt" --env "$ENVF" >"$T/ml441a.out" 2>&1
"$PY" -I "$S/make_letter_pdf.py" --job-file "$T/prep441/epsilon-1.json" --job E1 --company Acme --body "$T/none.txt" --env "$ENVF" >"$T/ml441b.out" 2>&1
printf '[]' >"$T/prep441/list.json"
"$PY" -I "$S/make_letter_pdf.py" --job-file "$T/prep441/list.json" --job E1 --body "$T/none.txt" --env "$ENVF" >"$T/ml441c.out" 2>&1
check "make_letter_pdf 0.44.1: --job-file finds the job by id, refuses another shape, never goes with --company" sh -c '
    grep -q "no job .NOPE." "$1" && grep -q "together, without --company and --role" "$2" &&
    grep -q "not a prepared-jobs file" "$3"' _ "$T/ml441a.out" "$T/ml441b.out" "$T/ml441c.out"
check "workflow 0.44.1: whole names in labels, one file per company, the employer check before a first hiring step" sh -c '
    grep -q "const label = (kind, name) => kind + .:. + name$" "$1" && grep -q "findIndex(c => c.name === name) + 1" "$1" &&
    grep -q "if (c.screen_only) return" "$1" && ! grep -q "A.decided" "$1"' _ "$S/../workflows/screen-and-prepare.js"
# 0.44.2: the no-screenshot hook denies a screenshot or a zoom through Claude in Chrome, alone or in a batch, in a
# main folder (job-search.env in it or above it), and an unreadable call that names one; a click, a typed word and a
# call outside a main folder pass with no output.
"$PY" -I - "$T/hk" <<'PYEOF'
import json
import os
import sys

base = sys.argv[1]
main, sub, other = (os.path.join(base, *p) for p in (("main",), ("main", "sub"), ("other",)))
for folder in (sub, other):
    os.makedirs(folder, exist_ok=True)
open(os.path.join(main, "job-search.env"), "w").close()


def call(tool, given, cwd):
    return json.dumps({"session_id": "s1", "transcript_path": "t.jsonl", "cwd": cwd, "permission_mode": "default",
                       "hook_event_name": "PreToolUse", "tool_name": "mcp__claude-in-chrome__" + tool,
                       "tool_input": given})


cases = {"shot": call("computer", {"action": "screenshot", "tabId": 1}, main),
         "zoom": call("computer", {"action": "zoom", "region": [0, 0, 9, 9]}, sub),
         "batch": call("browser_batch", {"actions": [{"name": "computer", "input": {"action": "left_click"}},
                                                     {"name": "computer", "input": {"action": "zoom"}}]}, main),
         "broken": '{"tool_input": {"action": "screenshot"',
         "click": call("computer", {"action": "left_click", "coordinate": [1, 2]}, main),
         "typed": call("computer", {"action": "type", "text": "screenshot"}, main),
         "other": call("computer", {"action": "screenshot"}, other)}
for name, raw in cases.items():
    with open(os.path.join(base, name + ".json"), "w", encoding="utf-8") as f:
        f.write(raw)
PYEOF
for c in shot zoom batch broken click typed other; do
    "$PY" -I "$S/../hooks/no_screenshot.py" <"$T/hk/$c.json" >"$T/hk/$c.out" 2>&1
    echo "exit $?" >>"$T/hk/$c.out"
done
check "hook 0.44.2: a screenshot, a zoom below the main folder, a zoom in a batch and an unreadable call are denied" sh -c '
    for c in shot zoom batch broken; do
        grep -q "permissionDecision.: .deny" "$1/$c.out" && grep -q "^exit 0$" "$1/$c.out" || exit 1
    done' _ "$T/hk"
check "hook 0.44.2: a click, a typed word and a screenshot outside a main folder pass with no output" sh -c '
    for c in click typed other; do [ "$(cat "$1/$c.out")" = "exit 0" ] || exit 1; done' _ "$T/hk"
check "hook 0.44.2: hooks.json runs it on both browsers' computer and browser_batch, with a timeout" \
    dq "$S/../hooks/hooks.json" 'R["hooks"]["PreToolUse"][0]["matcher"] == "mcp__claude-in-chrome__computer|mcp__claude-in-chrome__browser_batch|mcp__Claude_Browser__computer|mcp__Claude_Browser__browser_batch" and R["hooks"]["PreToolUse"][0]["hooks"][0]["timeout"] == 10 and "/hooks/no_screenshot.py" in R["hooks"]["PreToolUse"][0]["hooks"][0]["command"]'
check "rules 0.44.2: the moved parts exist and every skill points to them" sh -c '
    for f in RULES/start.md RULES/tools.md references/install.md references/choices.md references/study.md \
        references/weekly.md references/saved-searches.md; do [ -s "$1/$f" ] || exit 1; done
    grep -q "RULES/start.md" "$1/RULES.md" && grep -q "RULES/tools.md" "$1/RULES.md" &&
    grep -q "references/install.md" "$1/skills/setup/SKILL.md" && grep -q "references/choices.md" "$1/skills/setup/SKILL.md" &&
    grep -q "references/study.md" "$1/skills/prepare/SKILL.md" && grep -q "references/weekly.md" "$1/skills/search/SKILL.md" &&
    grep -q "references/saved-searches.md" "$1/skills/search/SKILL.md" && grep -q "^## Each run$" "$1/skills/coordinate/SKILL.md"' \
    _ "$S/.."
# 0.44.3: the search scope reaches the scripts (career_view.py scope; a row's place narrows; due leaves out a row
# outside it); a Remote Rocketship title with no page is that title's; an unread page with no text is named; sync
# holds an apply job the form step left out and dates only a completed check; --screen runs again after 90 days.
mkhome "$T/h443" flat
use "$T/h443"
"$PY" -I "$S/career_view.py" scope --set any_mode_places=Springfield remote_regions=EU --env "$ENVF" >"$T/sc443.out" 2>&1
"$PY" -I "$S/career_view.py" scope --set colour=red --env "$ENVF" >"$T/sc443b.out" 2>&1
echo "exit $?" >>"$T/sc443b.out"
"$PY" -I "$S/career_view.py" scope remote_regions=Asia --env "$ENVF" >"$T/sc443c.out" 2>&1
echo "exit $?" >>"$T/sc443c.out"
check "scope 0.44.3: --set prints both keys; an unknown key, or a key without --set, is refused" sh -c '
    grep -q "^any_mode_places: Springfield$" "$1" && grep -q "^remote_regions: EU$" "$1" &&
    grep -q "^scope --set takes " "$2" && grep -q "^exit 1$" "$2" &&
    grep -q "^scope alone prints the scope" "$3" && grep -q "^exit 1$" "$3"' _ "$T/sc443.out" "$T/sc443b.out" "$T/sc443c.out"
check "scope 0.44.3: --set writes the master record; an older list of places stays as locations.places" \
    dq "$H/career-records/career.json" 'R["preferences"]["locations"] == {"places": ["Rome"], "search_scope": {"any_mode_places": ["Springfield"], "remote_regions": ["EU"]}}'
searches add "LinkedIn Berlin" "engineer" source=linkedin place=Berlin mode=any >/dev/null 2>&1
searches add "LinkedIn Springfield" "engineer" source=linkedin place="Springfield, Illinois" mode=any >/dev/null 2>&1
searches add "LinkedIn EU remote" "engineer" source=linkedin place="European Union" mode=remote >/dev/null 2>&1
searches due >"$T/due443.out" 2>&1
searches due --json >"$T/due443.json" 2>&1
check "searches 0.44.3: due names a city row outside the scope and leaves it out; one inside it and a remote one stay" sh -c '
    grep -q "^outside the scope: 1 LinkedIn Berlin (Berlin): ask the person to turn it off (searches.py every 1 off) or keep it (searches.py scope-ok 1)$" "$1" &&
    grep -q "^2 LinkedIn Springfield " "$1" && grep -q "^3 LinkedIn EU remote " "$1"' _ "$T/due443.out"
check "searches 0.44.3: due --json leaves the row outside the scope out" \
    dq "$T/due443.json" '[r["site"] for r in R] == ["LinkedIn Springfield", "LinkedIn EU remote"]'
searches scope-ok 1 >"$T/sok443.out" 2>&1
searches due >"$T/due443b.out" 2>&1
searches query 3 "staff engineer, principal engineer" >"$T/q443.out" 2>&1
check "searches 0.44.3: scope-ok keeps a row outside the scope; query replaces a row's terms" sh -c '
    grep -q "^1 LinkedIn Berlin: kept outside the scope$" "$1" && grep -q "^1 LinkedIn Berlin " "$2" &&
    ! grep -q "^outside the scope" "$2" && grep -q "^3 LinkedIn EU remote: staff engineer, principal engineer$" "$3"' \
    _ "$T/sok443.out" "$T/due443b.out" "$T/q443.out"
check "collect 0.44.3: a row's place narrows the person's places; a remote search or posting keeps its own" "$PY" -I -c '
import sys; sys.path.insert(0, sys.argv[1]); import collect_postings as c
c.PLACES, c.NOT_PLACES = ["rome", "italy"], []
assert not c.wanted({"query": "engineer", "place": "Berlin"}, "Staff Engineer", "Berlin, Germany", [], [])
assert not c.wanted({"query": "engineer", "place": "Berlin"}, "Staff Engineer", "Berlin (Hybrid, remote 2 days)", [], [])
assert c.wanted({"query": "engineer", "place": "Rome"}, "Staff Engineer", "Rome, Lazio, Italy", [], [])
assert c.wanted({"query": "engineer", "place": "Berlin", "mode": "remote"}, "Staff Engineer", "Berlin, Germany", [], [])
assert c.wanted({"query": "engineer", "place": "Berlin"}, "Staff Engineer", "Remote, Germany", [], ["germany"])
assert c.wanted({"query": "engineer"}, "Staff Engineer", "Milan, Italy", [], [])' "$S"
searches every linkedin off >/dev/null 2>&1
mkdir -p "$T/rr443"
"$PY" -I - "$T/rr443" <<'PYEOF'
import datetime
import json
import os
import sys

src = sys.argv[1]
iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
job = {"id": 9, "roleTitle": "Java Engineer", "company": {"name": "Sigma"}, "url": "https://jobs.example.com/sigma-9",
       "locationType": "remote", "created_at": iso}
page = ('<html><script id="__NEXT_DATA__" type="application/json">'
        + json.dumps({"props": {"pageProps": {"initialJobOpenings": [job]}}}) + "</script></html>")
for name, text in (("remoterocketship-spain.status", "404"), ("remoterocketship-spain-p2.json", page),
                   ("remoterocketship-gone.status", "404"), ("remoterocketship-gone-p2.status", "404")):
    with open(os.path.join(src, name), "w", encoding="utf-8") as f:
        f.write(text)
PYEOF
searches add "Remote Rocketship Spain" "staff, java engineer" source=remoterocketship board=spain >/dev/null 2>&1
searches add "Remote Rocketship Gone" "staff, lead" source=remoterocketship board=gone >/dev/null 2>&1
track add U1 "Upsilon" "Java Engineer" "https://jobs.dover.com/upsilon/1" found_by=script:greenhouse:upsilon \
    location="Springfield, Illinois" >/dev/null 2>&1
"$PY" -I - "$H/apply/targets.json" <<'PYEOF'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
for j in data["jobs"]:
    if j["id"] == "U1":
        j["unread"] = "2026-11-19"
json.dump(data, open(sys.argv[1], "w", encoding="utf-8"))
PYEOF
"$PY" -I "$S/collect_postings.py" --from "$T/rr443" --out "$T/rr443.json" --env "$ENVF" >"$T/rr443.out" 2>&1
check "collect 0.44.3: a Remote Rocketship title with no page is skipped and named; only a row with none fails" sh -c '
    grep -q "^no Remote Rocketship page: https://www.remoterocketship.com/country/spain/jobs/staff: drop that title or stack from search 4 " "$1" &&
    "$2" -I "$3/dq.py" "$4" "[(r[\"site\"], r.get(\"fails\", 0)) for r in R[\"searches\"] if r.get(\"source\") == \"remoterocketship\"] == [(\"Remote Rocketship Spain\", 0), (\"Remote Rocketship Gone\", 1)]"' \
    _ "$T/rr443.out" "$PY" "$T" "$H/apply/searches.json"
check "collect 0.44.3: an unread posting with no saved text is named with the file it waits for" \
    grep -q "^no text saved for unread U1 (https://jobs.dover.com/upsilon/1): save it from Chrome as .*/postings/U1.md (references/sites/dover.md)$" "$T/rr443.out"
mkhome "$T/h443s" old
use "$T/h443s"
track add E2 "Epsilon Co" "Tester 2" "https://example.com/e2" >/dev/null 2>&1
track add Z1 "Zeta AG" "Engineer" "https://example.com/z1" >/dev/null 2>&1
mkdir -p "$T/prep443"
"$PY" -I - "$T/journal443.jsonl" "$T/prep443" "$S" "$ENVF" <<'PYEOF'
import json
import sys

journal, folder, scripts, envfile = sys.argv[1], sys.argv[2].replace("\\", "/"), sys.argv[3], sys.argv[4]
sys.path.insert(0, scripts)
import employerlib as el  # noqa: E402
import jsenv  # noqa: E402

cats = list(el.rules(jsenv.load(envfile)).get("categories") or {}) or list(el.CATEGORIES)
clear = [{"category": c, "status": "clear", "level": "", "fact": "nothing found", "source_url": ""} for c in cats]
fit = lambda *jobs: {"jobs": [{"id": i, "title": t, "action": "apply", "read": "full", "gaps": [], "reason": "fits",  # noqa: E731
                               "requirements": [{"text": "Testing", "place": "title", "level": "hands_on"}]}
                              for i, t in jobs]}
prepared = {"company": "Epsilon Co", "jobs": [{"id": "E1", "title": "Tester", "apply_url": "https://example.com/e1/apply",
            "action": "apply", "platform": "Greenhouse", "variant": "", "salary": 0, "setup": "remote", "cv_pdf": "",
            "letter_pdf": "", "letter_txt": "", "answers": [], "needs": [], "notes": "", "review": "done"}]}
with open(folder + "/epsilon-1.json", "w", encoding="utf-8") as f:
    json.dump(prepared, f)
# A Git Bash path (/c/...) on Windows, the plain path elsewhere.
bash_path = "/" + folder[0].lower() + folder[2:] if folder[1:2] == ":" else folder
rows = [("s1", "excl-screen:Epsilon Co", {"verdict": "allow", "hits": [], "ties": [], "checks": clear}),
        ("f1", "prep-fit:Epsilon Co", fit(("E1", "Tester"), ("E2", "Tester 2"))),
        ("p1", "prep-jobs:Epsilon Co", f"Wrote {bash_path}/epsilon-1.json"),
        ("f2", "prep-fit:Gamma Inc", fit(("J3", "Designer"))),
        ("p2", "prep-jobs:Gamma Inc", "Done."),
        ("s3", "excl-screen:Zeta AG", {"verdict": "allow", "hits": [], "ties": [], "checks": [
            {"category": cats[0], "status": "unknown", "level": "", "fact": "not checked", "source_url": ""}]})]
with open(journal, "w", encoding="utf-8") as f:
    for agent, label, result in rows:
        f.write(json.dumps({"type": "started", "agentId": agent, "label": label}) + "\n")
        f.write(json.dumps({"type": "result", "agentId": agent, "result": result}) + "\n")
PYEOF
track sync "$T/journal443.jsonl" >"$T/s443.out" 2>&1
check "sync 0.44.3: a Git Bash path is read; an apply job the form step left out, or one whose step wrote no file, is held" \
    dq "$H/apply/targets.json" '{j["id"]: (j["status"], "prep" in j, bool(j.get("unreviewed"))) for c in R["companies"] for j in c["jobs"] if j["id"] in ("E1", "E2", "J3")} == {"E1": ("pending", True, False), "E2": ("found", False, True), "J3": ("found", False, True)}'
check "sync 0.44.3: a clean screen dates the check; a screen with an unknown and no second check does not" \
    dq "$H/apply/targets.json" '[(c["name"], bool(c.get("screened"))) for c in R["companies"] if c["name"] in ("Epsilon Co", "Zeta AG")] == [("Epsilon Co", True), ("Zeta AG", False)]'
"$PY" -I - "$H/apply/targets.json" <<'PYEOF'
import datetime
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
for c in data["companies"]:
    if c["name"] == "Epsilon Co":
        c["screened"] = (datetime.date.today() - datetime.timedelta(days=100)).isoformat()
json.dump(data, open(sys.argv[1], "w", encoding="utf-8"))
PYEOF
CLAUDE_CONFIG_DIR="$T/no-config" "$PY" -I "$S/workflow_args.py" --screen "Epsilon Co" --out "$T/scr443" --env "$ENVF" >"$T/scr443.out" 2>&1
check "workflow_args 0.44.3: a full check over 90 days old runs again before a hiring step" sh -c '
    ! grep -q "^screened on" "$1" &&
    "$2" -I "$3/dq.py" "$4/args.json" "[(c[\"name\"], c.get(\"screen\")) for c in R[\"companies\"]] == [(\"Epsilon Co\", True)]"' \
    _ "$T/scr443.out" "$PY" "$T" "$T/scr443"
track add T9 "Theta AG" "Engineer" "https://example.com/t9" >/dev/null 2>&1
track add I1 "Iota AG" "Engineer" "https://example.com/i1" >/dev/null 2>&1
track add K1 "Kappa AG" "Engineer" "https://example.com/k1" >/dev/null 2>&1
"$PY" -I - "$T/jA443.jsonl" "$T/jB443.jsonl" "$T/prep443" <<'PYEOF'
import json
import sys

older, newer, folder = sys.argv[1], sys.argv[2], sys.argv[3].replace("\\", "/")
fit = lambda i: {"jobs": [{"id": i, "title": "Engineer", "action": "apply", "read": "full", "gaps": [], "reason": "fits",  # noqa: E731
                           "requirements": [{"text": "Testing", "place": "title", "level": "hands_on"}]}]}
form = lambda i, **more: {"id": i, "title": "Engineer", "apply_url": "https://example.com/" + i, "action": "apply",  # noqa: E731
                          "platform": "Ashby", "variant": "", "salary": 0, "setup": "remote", "cv_pdf": "",
                          "letter_pdf": "", "letter_txt": "", "answers": [], "needs": [], "notes": "", **more}
for name, data in (("iota-1.json", {"company": "Iota AG", "jobs": [form("I2", review="done")]}),
                   ("kappa-2.json", {"company": "Kappa AG", "jobs": [form("K1")]})):
    with open(folder + "/" + name, "w", encoding="utf-8") as f:
        json.dump(data, f)
unknown = {"verdict": "allow", "hits": [], "ties": [], "checks": [
    {"category": "defence", "status": "unknown", "level": "", "fact": "not checked", "source_url": ""}]}
journals = {older: [("v9", "excl-verify:Theta AG", {"verdict": "allow", "hits": [], "ties": [], "checks": []}),
                    ("p9", "prep-jobs:Iota AG", f"Wrote {folder}/iota-1.json")],
            newer: [("s9", "excl-screen:Theta AG", unknown),
                    ("f9", "prep-fit:Iota AG", fit("I1")),
                    ("f8", "prep-fit:Kappa AG", fit("K1")),
                    ("p8", "prep-jobs:Kappa AG", f"Wrote {folder}/kappa-2.json")]}
for path, rows in journals.items():
    with open(path, "w", encoding="utf-8") as f:
        for agent, label, result in rows:
            f.write(json.dumps({"type": "started", "agentId": agent, "label": label}) + "\n")
            f.write(json.dumps({"type": "result", "agentId": agent, "result": result}) + "\n")
PYEOF
track sync "$T/jA443.jsonl" "$T/jB443.jsonl" >"$T/s443b.out" 2>&1
check "sync 0.44.3: an older run's second check dates nothing; an older form step holds nothing; no review is due" \
    dq "$H/apply/targets.json" '[(c["name"], bool(c.get("screened")), [(j["id"], j["status"]) for j in c["jobs"]]) for c in R["companies"] if c["name"] in ("Theta AG", "Iota AG", "Kappa AG")] == [("Theta AG", False, [("T9", "found")]), ("Iota AG", False, [("I1", "pending")]), ("Kappa AG", False, [("K1", "found")])]'
check "0.44.3 text: the Dover note, board discovery by allowed_domains, the form step checked by its file name" sh -c '
    [ -s "$1/references/sites/dover.md" ] && grep -q "allowed_domains" "$1/references/weekly.md" &&
    ! grep -q "site:greenhouse.io" "$1/references/weekly.md" &&
    grep -q "fileOf(r.c.name).split(./.).pop()" "$1/workflows/screen-and-prepare.js"' _ "$S/.."
# 0.44.4: tabs are closed before a report, the health check opens no tab group, and the apply order is one rule
# that the run, apply, plan and urgent point to.
check "0.44.4 text: tabs closed before a report, no createIfEmpty in the health check, the apply order and its pointers" sh -c '
    grep -q "Before the final report or handoff" "$1/RULES.md" && grep -q "^## Apply order$" "$1/RULES.md" &&
    grep -q "without .createIfEmpty." "$1/RULES/run.md" && grep -q "Close your Chrome tabs before your final report" "$1/skills/coordinate/SKILL.md" &&
    grep -q "only a held .>>>. tab stays open" "$1/agents/applier.md" && grep -q "Apply order" "$1/skills/apply/SKILL.md" &&
    grep -q "apply order" "$1/skills/plan/SKILL.md" && grep -q "Apply order" "$1/RULES/urgent.md" &&
    ! grep -q "apply where the person is" "$1/skills/coordinate/SKILL.md" &&
    ! grep -q "does its pieces as subagents" "$1/skills/schedule/SKILL.md"' _ "$S/.."
check "0.46.1 text: a held form has its tab title, plain link and draft fact; its session is never archived; every site note has a Draft line" sh -c '
    grep -q "^- Every held form is named the same way" "$1/references/filling.md" &&
    grep -q "its session is never archived" "$1/RULES.md" && grep -q "Never one with .tab=yes." "$1/skills/coordinate/SKILL.md" &&
    grep -q "one .Held:. line per form left open" "$1/skills/coordinate/SKILL.md" && grep -q "Held:" "$1/skills/apply/SKILL.md" &&
    for f in "$1"/references/sites/*.md; do grep -q "^- Draft: " "$f" || exit 1; done' _ "$S/.."
# --- 0.45.0: recordlib (a stale base refused, the changed rows checked, the change log), PIPELINE by command,
# waits_on and a login row's origin as fields, records.py check -------------------------------------------------
mkhome "$T/h45" flat
use "$T/h45"
"$PY" -I - "$S" "$ENVF" >"$T/r45.out" 2>&1 <<'PYEOF'
import os
import sys
sys.path.insert(0, sys.argv[1])
import jsenv
import recordlib as rl
env = jsenv.load(sys.argv[2])
data, base = rl.load(env, "tracker")
path = rl.path(env, "tracker")
with open(path, "a", encoding="utf-8") as f:
    f.write(" ")
before = open(path, "rb").read()
try:
    rl.save(env, "tracker", data, base, "test", ["F1"])
except SystemExit as e:
    print("exit", e.code)
print("same", open(path, "rb").read() == before, "tmp", os.path.exists(path + ".tmp"))
PYEOF
check "recordlib 0.45.0: a file changed since it was read is not written: STALE, exit 3, no tmp file left" sh -c '
    grep -q "^exit 3" "$1" && grep -q "STALE: apply/targets.json changed since it was read: run the command again" "$1" &&
    grep -q "^same True tmp False" "$1"' _ "$T/r45.out"
track set F2 to-apply "ready" >"$T/x.out" 2>&1
check "recordlib 0.45.0: a write appends its rev, script, file and changed rows to changes.jsonl" "$PY" -I -c '
import json, sys
line = json.loads(open(sys.argv[1], encoding="utf-8").read().splitlines()[-1])
assert line["file"] == "apply/targets.json" and line["ids"] == ["F2"] and line["script"] == "track.py" and line["rev"] >= 1, line
' "$H/apply/changes.jsonl"
track set F2 needs-jane "x" >"$T/x.out" 2>&1
rc=$?
check "track.py 0.45.0: a status outside the schema's vocabulary is refused" sh -c '
    [ "$1" -eq 1 ] && grep -q "status must be one of" "$2"' _ "$rc" "$T/x.out"
track set F2 needs-person "an essay" >"$T/x.out" 2>&1
track set F2 submitted "sent" >>"$T/x.out" 2>&1
check "track.py 0.45.0: a waiting status gets waits_on; a sent job keeps it only in its history" "$PY" -I -c '
import json, sys
f2 = [j for j in json.load(open(sys.argv[1], encoding="utf-8"))["jobs"] if j["id"] == "F2"][0]
assert "waits_on" not in f2 and f2["history"][-1]["waits_on"]["kind"] == "person" and f2["applied"], f2
' "$H/apply/targets.json"
track wait F1 account-needed "sign in to Acme Jobs" login="Acme Jobs" >"$T/x.out" 2>&1
check "track.py 0.45.0: wait writes waits_on {kind, login, since}, not the older login field" "$PY" -I -c '
import json, sys
f1 = [j for j in json.load(open(sys.argv[1], encoding="utf-8"))["jobs"] if j["id"] == "F1"][0]
assert f1["waits_on"]["kind"] == "account" and f1["waits_on"]["login"] == "Acme Jobs" and "login" not in f1, f1
' "$H/apply/targets.json"
track step F2 add name="Recruiter screen" date=2026-11-18 time=10:00-10:30 >"$T/p45.out" 2>&1
track step F2 add name="Take-home" due=2026-11-25 proposed=yes >>"$T/p45.out" 2>&1
track step F2 done 1 2026-11-18 >>"$T/p45.out" 2>&1
track step F2 set 2 proposed=no due=2026-11-26 >>"$T/p45.out" 2>&1
track outcome F2 rejected 2026-11-27 reason="not moving forward" >>"$T/p45.out" 2>&1
track outcome F2 withdrawn 2026-11-28 why=relocation >>"$T/p45.out" 2>&1
check "track.py 0.45.0: step and outcome write PIPELINE: steps by number, an earlier outcome kept in history" "$PY" -I -c '
import json, sys
e = json.load(open(sys.argv[1], encoding="utf-8"))["F2"]
s = e["steps"]
assert s[0]["done"] == "2026-11-18" and s[0]["time"] == "10:00-10:30" and "proposed" not in s[1] and s[1]["due"] == "2026-11-26", e
assert e["stage"] == "declined" and e["why"] == "relocation" and e["history"][0]["stage"] == "rejected", e
' "$H/apply/pipeline.json"
track step F2 add name="Call" date="18 Nov" >"$T/x.out" 2>&1
rc1=$?
track outcome F1 rejected 2026-11-27 >"$T/y.out" 2>&1
rc2=$?
check "track.py 0.45.0: a step date not written YYYY-MM-DD, and an outcome of a job not sent, are refused" sh -c '
    [ "$1" -eq 1 ] && grep -q "date is a date" "$2" && [ "$3" -eq 1 ] && grep -q "an outcome is for a sent job" "$4"' \
    _ "$rc1" "$T/x.out" "$rc2" "$T/y.out"
"$PY" -I "$S/logins.py" sync --env "$ENVF" >"$T/x.out" 2>&1
"$PY" -I "$S/logins.py" set "Acme Jobs" signed-in "signed in" origin=person --env "$ENVF" >>"$T/x.out" 2>&1
check "logins.py 0.45.0: a row sync makes has origin sync; a set row says who: person here" "$PY" -I -c '
import json, sys
rows = {r["id"]: r for r in json.load(open(sys.argv[1], encoding="utf-8"))["logins"]}
assert rows["Acme Jobs"]["origin"] == "person" and rows["Acme Jobs"]["history"][-1]["origin"] == "sync", rows
' "$H/apply/logins.json"
"$PY" -I - "$H" <<'PYEOF'
import json
import os
import sys
p = os.path.join(sys.argv[1], "apply", "targets.json")
data = json.load(open(p, encoding="utf-8"))
f1 = [j for j in data["jobs"] if j["id"] == "F1"][0]
f1["todo"] = [{"kind": "todo", "text": "first", "since": "2026-11-01"},
              {"kind": "todo", "text": "older", "due": "next week"}]
with open(p, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=1)
PYEOF
track todo F1 done 1 >"$T/x.out" 2>&1
rc=$?
check "recordlib 0.45.0: removing a to-do is not refused for an older one below it (only changed parts are checked)" sh -c '
    [ "$1" -eq 0 ] && grep -q "removed 1 to-do" "$2"' _ "$rc" "$T/x.out"
"$PY" -I - "$S" "$ENVF" >"$T/r45n.out" 2>&1 <<'PYEOF'
import sys
sys.path.insert(0, sys.argv[1])
import jsenv
import recordlib as rl
env = jsenv.load(sys.argv[2])
before = rl.rev(env)
data, base = rl.load(env, "tracker")
again = rl.save(env, "tracker", data, base, "test")
print("same base", again == base, "rev", rl.rev(env) == before)
PYEOF
check "recordlib 0.45.0: a write that changes nothing writes and logs nothing" grep -q "^same base True rev True" "$T/r45n.out"
# records.py check: each id on a made-up case, then a clean folder.
mkhome "$T/h45r" flat
use "$T/h45r"
mkdir -p "$H/job-applications"
"$PY" -I - "$H" <<'PYEOF'
import json
import os
import sys
h = sys.argv[1]


def put(name, data):
    with open(os.path.join(h, "apply", name), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)


put("targets.json", {"jobs": [
    {"id": "R1", "company": "Acme Corp", "title": "Staff Engineer", "status": "needs-jane"},
    {"id": "R2", "company": "Acme Corp", "title": "Staff Engineer", "status": "submitted", "applied": "2026-11-01",
     "cv": "a.pdf"},
    {"id": "R3", "company": "Acme Corp", "title": "Staff Engineer", "status": "submitted", "applied": "2026-11-05"},
    {"id": "R4", "company": "Beta Ltd", "title": "Lead", "status": "needs-person"},
    {"id": "R5", "company": "Gamma Inc", "title": "Dev", "status": "account-needed", "platform": "linkedin",
     "url": "https://www.linkedin.com/jobs/view/1", "todo": [{"kind": "click", "text": "sign in", "login": "LinkedIn"}]},
    {"id": "R5", "company": "Gamma Inc", "title": "Dev 2", "status": "found"},
    {"id": "R6", "company": "Delta Co", "title": "Eng", "status": "submitted", "applied": "2026-11-02", "cv": "b.pdf",
     "prep": {" gaps": ["x"]}, "repeat_of": "R99"},
    {"id": "R10", "company": "Omega GmbH", "title": "A", "status": "excluded", "note": "employer excluded"},
    {"id": "R11", "company": "Omega GmbH", "title": "B", "status": "pending"},
    {"id": "R12", "company": "Zeta AG", "title": "Ops", "status": "account-needed",
     "url": "https://www.linkedin.com/jobs/view/2"}]})
put("pipeline.json", {"R2": {"stage": "approved", "steps": [
    {"name": "Call", "date": "2026-11-03"}, {"name": "Panel", "date": "2026-11-04", "how": "video, done 4 Nov"}]},
    "R9": {"stage": "pending", "notes": "by hand"}, "R6": {"same_as": "R7"}})
put("questions.json", {"questions": {"q1": {"kind": "job", "status": "open", "text": "x", "jobs": ["R8"]}}})
PYEOF
"$PY" -I "$S/records.py" check --env "$ENVF" >"$T/rc45.out" 2>&1
check "records.py 0.45.0: shape names an unknown status, a key with spaces and a PIPELINE key no reader knows" sh -c '
    grep -q "^check: shape: tracker R1 status: .needs-jane. is not one of" "$1" &&
    grep -q "^check: shape: tracker R6 prep: key . gaps. has spaces around it" "$1" &&
    grep -q "^check: shape: pipeline R9 key .notes. is not in the schema" "$1"' _ "$T/rc45.out"
check "records.py 0.45.0: sent, waits (no waits_on, no to-do, no site, a job board) and links" sh -c '
    grep -q "^check: sent: 1 submitted naming no CV: R3" "$1" &&
    grep -q "^check: waits: needs-person with no waits_on and no to-do: R4 -> track.py wait <id> needs-person" "$1" &&
    grep -q "^check: waits: account-needed with no site named: R12 " "$1" && grep -q "^check: waits: a wait or sign-in to-do names a job board.*R5 (LinkedIn)" "$1" &&
    grep -q "^check: links: 1 question(s) naming jobs not in the tracker: q1 (R8)" "$1" && grep -q "^check: links: PIPELINE entries of no tracker job: R9" "$1" &&
    grep -q "^check: links: same_as naming no PIPELINE entry: R6 (R7)" "$1" && grep -q "^check: links: repeat_of naming no tracker job: R6 (R99)" "$1"' _ "$T/rc45.out"
check "records.py 0.45.0: dupes, steps and employer, each with its command" sh -c '
    grep -q "^check: dupes: one id on two tracker rows: R5" "$1" &&
    grep -q "^check: dupes: the same employer and role twice: R2 and R3 .* -> track.py set R3 submitted \"\" repeat_of=R2" "$1" &&
    grep -q "^check: steps: 1 past step(s) not done: R2 step 1 \"Call\" on 2026-11-03 -> track.py step <id> done <n> <date>" "$1" &&
    grep -q "^check: steps: 1 step(s) done only in its how text: R2 step 2" "$1" &&
    grep -q "^check: employer: Omega GmbH is excluded .*, not sent yet: R11 -> track.py set <id> excluded" "$1" &&
    grep -q "^check: 1[0-9] record faults" "$1"' _ "$T/rc45.out"
export_dash --check >"$T/ec45.out" 2>&1
check "export --check 0.45.0: prints records.py's lines in place of its own status, repeat and wait lines" sh -c '
    grep -q "^check: shape: tracker R1 status" "$1" && grep -q "^check: dupes: the same employer and role twice" "$1" &&
    ! grep -q "status not known to the plugin" "$1" && ! grep -q "^check: the same employer and role twice" "$1" &&
    ! grep -q "^check: account-needed with no site named" "$1" && ! grep -q "with no to-do: R4" "$1"' _ "$T/ec45.out"
mkhome "$T/h45c" flat
use "$T/h45c"
"$PY" -I - "$H" <<'PYEOF'
import json
import os
import sys
h = sys.argv[1]
with open(os.path.join(h, "apply", "targets.json"), "w", encoding="utf-8") as f:
    json.dump({"jobs": [{"id": "C1", "company": "Acme Corp", "title": "Engineer", "status": "submitted",
                         "applied": "2026-11-01", "cv": "c.pdf"}]}, f, indent=1)
with open(os.path.join(h, "apply", "pipeline.json"), "w", encoding="utf-8") as f:
    json.dump({"C1": {"stage": "approved", "steps": [{"name": "Call", "date": "2026-11-03", "done": "2026-11-03"}]}},
              f, indent=1)
PYEOF
"$PY" -I "$S/records.py" check --env "$ENVF" >"$T/rc45c.out" 2>&1
check "records.py 0.45.0: a clean folder gives no fault line" sh -c '
    [ "$(grep -c . "$1")" -eq 1 ] && grep -q "^check: 0 record faults" "$1"' _ "$T/rc45c.out"
check "0.45.0 text: records only by their scripts, STALE means run again, PIPELINE by step and outcome" sh -c '
    grep -q "never by hand: each write is checked and logged" "$1/RULES/run.md" && grep -q "STALE" "$1/RULES/run.md" &&
    grep -q "track.py outcome <id> rejected" "$1/RULES/hiring-steps.md" && grep -q "track.py step <id> done <n>" "$1/RULES/run.md" &&
    grep -q "Keeps the shared records" "$1/skills/coordinate/SKILL.md" &&
    ! grep -q "Is the only writer of the shared records" "$1/skills/coordinate/SKILL.md" &&
    grep -q "records.py" "$1/RULES/tools.md"' _ "$S/.."
# --- 0.45.1: the person's name and contact line from the profile; job-search.env's lines only override ------------
mkhome "$T/h451" flat
use "$T/h451"
grep -v -e '^PERSON_NAME=' -e '^NAME_ON_CV=' -e '^CONTACT_LINE=' "$ENVF" >"$ENVF.tmp" && mv "$ENVF.tmp" "$ENVF"
"$PY" -I - "$H/profile/profile.json" <<'PYEOF'
import json
import sys
p = sys.argv[1]
data = json.load(open(p, encoding="utf-8"))
data["person"]["location"] = {"city": "Rome", "country": "Italy"}
data["person"]["links"] = {"linkedin": "https://www.linkedin.com/in/jane-example/"}
with open(p, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=1)
PYEOF
check "profilelib 0.45.1: with no lines in job-search.env, the name, the name on top and the contact line come from the profile" "$PY" -I -c '
import sys
sys.path.insert(0, sys.argv[1])
import jsenv, profilelib
env = jsenv.load(sys.argv[2])
who = profilelib.person(env)
assert (who["name"], who["first"], who["name_on_cv"]) == ("Jane Doe", "Jane", "JANE DOE"), who
assert who["contact_line"].split(" " + chr(183) + " ") == ["Rome", "+39 06 0000 0000", "jane@example.com",
                                                          "linkedin.com/in/jane-example"], who
assert env.file_prefix(who["name"]) == "Jane-Doe"
' "$S" "$ENVF"
printf 'CONTACT_LINE=Rome, jane@example.com\nPERSON_NAME=Jane Doe\n' >>"$ENVF"
check "profilelib 0.45.1: a job-search.env line overrides the profile" "$PY" -I -c '
import sys
sys.path.insert(0, sys.argv[1])
import jsenv, profilelib
assert profilelib.person(jsenv.load(sys.argv[2]))["contact_line"] == "Rome, jane@example.com"
' "$S" "$ENVF"
"$PY" -I "$S/check_setup.py" --env "$ENVF" >"$T/cs451.out" 2>&1
check "check_setup 0.45.1: a line that repeats the profile is named, another wording is not; none of the three is required" sh -c '
    grep -q "job-search.env repeats the profile - PERSON_NAME: remove the line" "$1" &&
    ! grep -q "repeats the profile - .*CONTACT_LINE" "$1" && ! grep -q -E "empty or missing: .*(NAME_ON_CV|CONTACT_LINE)" "$1"' \
    _ "$T/cs451.out"
"$PY" -I "$S/init_career_folder.py" "$T/i451" >"$T/i451.out" 2>&1
check "init_career_folder 0.45.1: no name needed; job-search.env sets no name (the profile holds it)" sh -c '
    [ -f "$1/job-search.env" ] && ! grep -q "^PERSON_NAME=" "$1/job-search.env" && grep -q "^#PERSON_NAME=$" "$1/job-search.env"' \
    _ "$T/i451"
grep -v -e '^PERSON_NAME=' -e '^CONTACT_LINE=' "$ENVF" >"$ENVF.tmp" && mv "$ENVF.tmp" "$ENVF"
employer record "Acme Corp" defence flagged level=direct fact="Jane Doe and +39 06 0000 0000 named in a filing" \
    source=https://example.com/f451 >/dev/null 2>&1
"$PY" -I "$S/usage.py" report --out "$T/r451.json" --env "$ENVF" >"$T/r451.out" 2>&1
check "usage 0.45.1: the report masks the name and the phone that only the profile holds" sh -c '
    [ -s "$1" ] && grep -q "named in a filing" "$1" && ! grep -q -i -e "jane" -e "doe" -e "0000 0000" "$1"' _ "$T/r451.json"
"$PY" -I - "$H/profile/profile.json" <<'PYEOF'
import json
import sys
p = sys.argv[1]
data = json.load(open(p, encoding="utf-8"))
data["person"].pop("name", None)
with open(p, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=1)
PYEOF
"$PY" -I "$S/usage.py" report --out "$T/r451n.json" --env "$ENVF" >"$T/r451n.out" 2>&1
rc1=$?
"$PY" -I "$S/make_letter_pdf.py" --env "$ENVF" >"$T/l451n.out" 2>&1
rc2=$?
check "usage and letters 0.45.1: with no name known, no report is written and no letter is made" sh -c '
    [ "$1" -eq 1 ] && grep -q "no name to mask" "$2" && [ ! -e "$3" ] && [ "$4" -eq 1 ] && grep -q "no name for the letter" "$5"' \
    _ "$rc1" "$T/r451n.out" "$T/r451n.json" "$rc2" "$T/l451n.out"
# --- 0.46.0: posting texts that were unread: JSON-LD JobPosting, Workday's job JSON --------------------------------
check "fetch_jd 0.46.0: a page's JSON-LD JobPosting gives the posting; a Workday link maps to its job JSON" "$PY" -I -c '
import sys
sys.path.insert(0, sys.argv[1])
import fetch_jd as f
page = "<html><head><script type=\"application/ld+json\">{\"@type\": \"JobPosting\", \"title\": \"Engineering Manager\", " \
       "\"datePosted\": \"2026-11-20\", \"jobLocation\": {\"address\": {\"addressLocality\": \"Rome\", \"addressCountry\": \"IT\"}}, " \
       "\"description\": \"&lt;p&gt;Lead a team of eight engineers.&lt;/p&gt;\"}</script></head><body>menu</body></html>"
head, text = f.job_posting_ld(page)
assert head == "Engineering Manager | Rome, IT | posted 2026-11-20" and "Lead a team of eight engineers." in text, (head, text)
assert f.job_posting_ld("<html>no data</html>") is None
assert f.workday_api("https://acme.wd5.myworkdayjobs.com/en-US/Careers/job/Rome/Lead_R1") == \
    "https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/Careers/job/Rome/Lead_R1"
assert f.workday_api("https://boards.greenhouse.io/acme/jobs/1") == ""
' "$S"
# --- 0.46.0: more postings reach the fit check ----------------------------------------------------------------------
check "collect 0.46.0: a board's remote flag, a region-only place, OR-joined LinkedIn terms, the list's text kept" "$PY" -I -c '
import json, sys
sys.path.insert(0, sys.argv[1])
import collect_postings as c
c.PLACES, c.NOT_PLACES = ["rome"], []
assert c.remote_like("emea") and c.remote_like("europe; worldwide") and c.remote_like("remote, us")
assert not c.remote_like("berlin, emea") and not c.remote_like("hybrid - europe") and not c.remote_like("")
assert c.place_ok("EMEA", c.PLACES, ["emea"]) and not c.place_ok("Berlin, EMEA", c.PLACES, ["emea"])
assert c.wanted({"query": "engineer"}, "Engineer", "Europe", [], ["europe"])
assert c.linkedin_keywords(["engineering manager", "cto", " "]) == "\"engineering manager\" OR cto"
body = "<p>" + "Lead the platform team. " * 20 + "</p>"
rows = c.parse("ashby", "Acme", json.dumps({"jobs": [
    {"title": "Engineer", "location": "Germany", "isRemote": True, "jobUrl": "https://jobs.example.com/a/1",
     "publishedAt": "2026-11-16T08:00:00Z", "descriptionHtml": body},
    {"title": "Engineer II", "location": "Remote, EU", "isRemote": True, "jobUrl": "https://jobs.example.com/a/2",
     "publishedAt": "2026-11-16T08:00:00Z", "descriptionHtml": "<p>short</p>"}]}))
assert [r[2] for r in rows] == ["Remote - Germany", "Remote, EU"], rows
assert "Lead the platform team." in c.TEXTS["https://jobs.example.com/a/1"] and "https://jobs.example.com/a/2" not in c.TEXTS
lever = c.parse("lever", "Acme", json.dumps([{"text": "Engineer", "categories": {"location": ""}, "workplaceType": "remote",
                                              "createdAt": 1763280000000, "hostedUrl": "https://jobs.example.com/l/1"}]))
assert lever[0][2] == "Remote", lever
' "$S"
check "collect 0.46.0: LinkedIn pages newest first, each from the posting after the last one read" "$PY" -I -c '
import datetime, sys, urllib.parse
sys.path.insert(0, sys.argv[1])
import collect_postings as c
calls = []
def fake(url):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    calls.append((int(q["start"][0]), q["sortBy"][0], q["keywords"][0]))
    return "<div class=\"base-card x\"></div>" * (10 if len(calls) < 3 else 0)
c.fetch = fake
class Q:
    def call(self, f, gap=None):
        return f()
c.answers({"source": "linkedin", "query": "engineering manager, cto"}, None, Q(),
          datetime.datetime.now() - datetime.timedelta(days=1), ["engineering manager", "cto"])
assert [x[0] for x in calls] == [0, 10, 20] and calls[0][1] == "DD", calls
assert calls[0][2] == "\"engineering manager\" OR cto", calls
' "$S"
check "collect 0.46.0: some overlap with US hours keeps a posting; working US hours, or a full overlap, leaves it out" "$PY" -I -c '
import os, sys
sys.path.insert(0, sys.argv[1])
import collect_postings as c
c.PLACES, c.NOT_PLACES = ["rome"], []
for pid, text in (("P461", "Remote in Europe, full-time, with some overlap with US hours each day."),
                  ("P462", "Remote in Europe. You work US hours."),
                  ("P463", "Remote in Europe, with full overlap with US hours.")):
    with open(os.path.join(sys.argv[2], f"page-{pid}.html"), "w", encoding="utf-8") as fh:
        fh.write("<p>" + text + "</p>")
assert c.location_out({"url": "https://jobs.example.com/1", "id": "P461"}, sys.argv[2], ["europe"]) == ""
assert c.location_out({"url": "https://jobs.example.com/2", "id": "P462"}, sys.argv[2], ["europe"]) == "works US hours"
assert c.location_out({"url": "https://jobs.example.com/3", "id": "P463"}, sys.argv[2], ["europe"]) == "works US hours"
' "$S" "$T"
mkhome "$T/r46b" flat
use "$T/r46b"
echo "REMOTE_REGIONS=EMEA" >>"$ENVF"
searches add "Acme jobs" "engineer" source=greenhouse board=acme >/dev/null 2>&1
mkdir -p "$T/r46b-src"
cat >"$T/mk46b.py" <<'PYEOF'
import html
import json
import sys

body = html.escape("<p>" + "Lead the payments platform team in Rome. " * 12 + "</p>")
jobs = [{"title": "Senior Engineer", "location": {"name": "Rome, Italy"}, "absolute_url": "https://boards.example.com/acme/jobs/1",
         "first_published": "2026-10-20T08:00:00Z", "content": body},
        {"title": "Platform Engineer", "location": {"name": "EMEA"}, "absolute_url": "https://boards.example.com/acme/jobs/2",
         "first_published": "2026-11-12T08:00:00Z", "content": "&lt;p&gt;short&lt;/p&gt;"}]
if sys.argv[2] == "again":
    jobs.append({"title": "Old Engineer", "location": {"name": "Rome, Italy"}, "absolute_url": "https://boards.example.com/acme/jobs/3",
                 "first_published": "2026-10-21T08:00:00Z"})
json.dump({"jobs": jobs}, open(sys.argv[1], "w", encoding="utf-8"))
PYEOF
"$PY" -I "$T/mk46b.py" "$T/r46b-src/greenhouse-acme.json" first
"$PY" -I "$S/collect_postings.py" --since 2026-11-01 --from "$T/r46b-src" --out "$T/r46b.json" --add --env "$ENVF" >"$T/r46b.out" 2>&1
check "collect 0.46.0: a board's first read takes its older postings; a region-only place passes; the list's text is the text_file" sh -c '
    grep -q "^Acme | Senior Engineer | Rome, Italy | 2026-10-20 | " "$1" && grep -q "^Acme | Platform Engineer | EMEA | " "$1" &&
    grep -q "^1 posting texts saved for the fit check (boards. lists, LinkedIn remote checks)$" "$1" &&
    "$2" -I "$3/dq.py" "$4" "sorted((j[\"title\"], bool(j.get(\"text_file\"))) for c in R[\"companies\"] for j in c[\"jobs\"]) == [(\"Platform Engineer\", False), (\"Senior Engineer\", True)]" &&
    grep -q "Lead the payments platform team in Rome." "$5"/apply/postings/P*.md' _ "$T/r46b.out" "$PY" "$T" "$T/r46b.json" "$H"
"$PY" -I "$T/mk46b.py" "$T/r46b-src/greenhouse-acme.json" again
"$PY" -I "$S/collect_postings.py" --since 2026-11-01 --from "$T/r46b-src" --env "$ENVF" >"$T/r46b2.out" 2>&1
check "collect 0.46.0: a board read before keeps its window: an older posting stays out" sh -c '
    ! grep -q "Old Engineer" "$1" && grep -q "^0 new postings from 1 searches read by script" "$1"' _ "$T/r46b2.out"
mkhome "$T/r46" flat
use "$T/r46"
searches add "Beta careers" "analyst" alert=no >/dev/null 2>&1
cat >"$T/mk46.py" <<'PYEOF'
import datetime
import json
import os
import sys

today = datetime.date.today().isoformat()


def job(i, title, status, note, **more):
    return dict({"id": i, "company": "Kappa", "title": title, "url": f"https://example.com/{i}", "status": status,
                 "note": note, "found_by": "agent", "history": [{"date": today, "status": status, "note": note}]}, **more)


jobs = [job("K1", "Engineering Manager", "skipped", "fit: not a high fit (APPLY_FITS=high): Go",
            prep={"action": "skip", "grade": "normal", "reason": "not a high fit (APPLY_FITS=high): Go"}, grade="normal"),
        job("K2", "Staff Engineer", "skipped", "fit: a hard gap: on-site in Oslo"),
        job("K3", "Platform Lead", "skipped", "fit: long-shot: 2 soft gaps (LONG_SHOTS_PER_DAY=0): Go; staff role"),
        job("K4", "Data Engineer", "submitted", "sent", applied=today),
        job("K5", "Backend Engineer", "closed", "the posting is gone"),
        job("K6", "Site Reliability Lead", "skipped", "fit: not a high fit (APPLY_FITS=high): Go"),
        job("K7", "Site Reliability Lead", "found", "posted again under a new link"),
        job("K8", "Release Manager", "skipped", "the person: not now (APPLY_FITS=high)"),
        job("K9", "Delivery Lead", "skipped", "not a high fit (APPLY_FITS=high): Go", location="Oslo, Norway")]
json.dump({"jobs": jobs}, open(os.path.join(sys.argv[1], "apply", "targets.json"), "w", encoding="utf-8"))
PYEOF
"$PY" -I "$T/mk46.py" "$H"
echo "PLACES=Rome" >>"$ENVF"
track reopen >"$T/r46-dry.out" 2>&1
check "track reopen 0.46.0: lists only a fit skipped by a setting's cut no longer made, inside the places; a dry run changes nothing" sh -c '
    grep -q "^K1 | Kappa | Engineering Manager | APPLY_FITS no longer cuts it$" "$1" && ! grep -q "^K[2-9] " "$1" &&
    grep -q "^1 left skipped: the same job is in the tracker under a newer row$" "$1" &&
    grep -q "^1 left skipped: outside the person.s places now$" "$1" &&
    grep -q "^1 to reopen; dry run" "$1" &&
    "$2" -I "$3/dq.py" "$4" "[j[\"status\"] for j in R[\"jobs\"]][0] == \"skipped\""' _ "$T/r46-dry.out" "$PY" "$T" "$H/apply/targets.json"
check "collect 0.46.0: a title skipped by a setting's cut no longer made, or closed, blocks no new posting; a hard gap still does" "$PY" -I -c '
import json, sys
sys.path.insert(0, sys.argv[1])
import collect_postings as c, jsenv, reposts
c.ENV = jsenv.load(sys.argv[2])
keys = c.tracked_keys()
ids = set(keys.values())
assert not {"K1", "K5", "K6", "K9"} & ids and {"K2", "K3", "K4", "K7", "K8"} <= ids, ids
index = reposts.Index(c.ENV, json.load(open(c.ENV.path("TRACKER"), encoding="utf-8")))
assert index.fit_skip_of("Kappa", "Engineering Manager") == "" and index.fit_skip_of("Kappa", "Staff Engineer") == "K2"
' "$S" "$ENVF"
check "choices 0.46.1: a setting cut is the fit check's own message, with or without fit: before it; the person's note is none" "$PY" -I -c '
import sys
sys.path.insert(0, sys.argv[1])
import choices, jsenv
env = jsenv.load(sys.argv[2])
cut = lambda note: choices.setting_cut(note, env)
assert cut("not a high fit (APPLY_FITS=high): Go") == cut("fit: not a high fit (APPLY_FITS=high): Go") == "APPLY_FITS"
assert cut("the person: not now (APPLY_FITS=high)") == "" and cut("fit: a hard gap: on-site in Oslo") == ""
' "$S" "$ENVF"
"$PY" -I "$S/choices.py" set LONG_SHOTS_PER_DAY=2 --env "$ENVF" >/dev/null 2>&1
track reopen --apply --per-day 0 >"$T/r46-bad.out" 2>&1
check "track reopen 0.46.0: --per-day takes a whole number above 0 and changes nothing otherwise" sh -c '
    grep -q "^--per-day is a whole number above 0" "$1" &&
    "$2" -I "$3/dq.py" "$4" "not any(j.get(\"reopened\") for j in R[\"jobs\"])"' _ "$T/r46-bad.out" "$PY" "$T" "$H/apply/targets.json"
track reopen --apply --per-day 1 >"$T/r46-apply.out" 2>&1
check "track reopen --apply --per-day 0.46.0: back to found with the old fit result in the history row, one a day" sh -c '
    grep -q "^reopened 2: the next run takes 1, then 1 a day until $5; each gets a fit check" "$1" &&
    "$2" -I "$3/dq.py" "$4" "[(j[\"id\"], j[\"status\"], j[\"reopened\"]) for j in R[\"jobs\"] if j.get(\"reopened\")] == [(\"K1\", \"found\", \"$6\"), (\"K3\", \"found\", \"$5\")]" &&
    "$2" -I "$3/dq.py" "$4" "not R[\"jobs\"][0].get(\"prep\") and not R[\"jobs\"][0].get(\"grade\") and R[\"jobs\"][0][\"history\"][-1][\"prep\"][\"grade\"] == \"normal\""' \
    _ "$T/r46-apply.out" "$PY" "$T" "$H/apply/targets.json" \
    "$("$PY" -I -c 'import datetime; print(datetime.date.today() + datetime.timedelta(days=1))')" \
    "$("$PY" -I -c 'import datetime; print(datetime.date.today())')"
mkdir -p "$T/r46-src"
"$PY" -I "$S/collect_postings.py" --since 2026-11-01 --from "$T/r46-src" --out "$T/r46.json" --env "$ENVF" >"$T/r46-collect.out" 2>&1
check "collect 0.46.0: a reopened job joins the funnel on its reopened day, whoever found it" sh -c '
    "$1" -I "$2/dq.py" "$3" "sorted(j[\"id\"] for c in R[\"companies\"] for j in c[\"jobs\"]) == [\"K1\"]"' _ "$PY" "$T" "$T/r46.json"
check "workflow 0.46.0: the fit check reads a LinkedIn job with no saved text at its public guest page" \
    grep -q "read its text at https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/<number>" "$S/../workflows/screen-and-prepare.js"
check "choices 0.46.0: FIT_MODEL sonnet by default; opus and opus-max move the fit check to Opus, medium or max effort" sh -c '
    "$1" -I "$2/choices.py" workflow --env "$3" | grep -q "\"fitModel\": \"sonnet\"" &&
    "$1" -I "$2/choices.py" set FIT_MODEL=opus-max --env "$3" >/dev/null 2>&1 &&
    "$1" -I "$2/choices.py" workflow --env "$3" | grep -q "\"fitModel\": \"opus-max\"" &&
    grep -q "^const FIT_MODELS = { opus: { model: .opus., effort: .medium. }, .opus-max.: { model: .opus., effort: .max. } }$" "$2/../workflows/screen-and-prepare.js" &&
    ! "$1" -I "$2/choices.py" set FIT_MODEL=haiku --env "$3" >/dev/null 2>&1' _ "$PY" "$S" "$ENVF"
use "$H38"
echo "$PASSED passed, $FAILED failed"
[ "$FAILED" -eq 0 ]
