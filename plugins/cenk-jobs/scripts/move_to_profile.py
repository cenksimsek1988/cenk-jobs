"""Move the person's own facts once from MASTER_RECORD and the old private record into their profile (profilelib.py),
so each fact is kept in one place. Prints field names and paths only, never a value.
A key can hold a name: contacts.referee-<first name>, employment.<employer>-<year>, as the profile's layout names them.

python -I move_to_profile.py [--env <job-search.env>]                       dry run: what would move, nothing written
python -I move_to_profile.py --apply [--confirm <profile key> ...]         adds each field the profile does not hold
python -I move_to_profile.py --remove-old                                   after the person's OK: removes from the old
                                                                            files what the profile holds unchanged
What moves:
  MASTER_RECORD profile: name, pronouns, email, phone, address, birth_date, work_authorisation -> person.*;
    citizenship or nationality -> person.nationality (a list); languages -> person.languages; every key under
    contact -> person.* (linkedin and github -> person.links.*; from a github object only its account);
    location as "City, Country" or {city, country} -> person.location; pronouns_on_linkedin -> person.pronouns, only
    with --confirm person.pronouns (a LinkedIn setting: the person confirms it first)
  MASTER_RECORD references (a list, {rows: [...]}, or entries by id) -> contacts.referee-<name>
  MASTER_RECORD employment or employment_timeline rows with an employer and a start -> employment.<employer>-<year>
  PERSONAL_RECORD (default career-records/personal.json) facts: an answer -> private.<key> (typed -> words); a
    person with an email or phone and no answer -> contacts.<key>
Listed for a hand move with the person: experience rows (their true start and end belong in employment; experience
keeps the CV's own wording and dates), a location of another shape, referees without agreed_on, MASTER_RECORD history
entries about moved fields, and every text file in the main folder that repeats a profile value (with a PDF of the same
name): rebuilding or deleting it is the person's call. Application folders, letters, CVs, the tracker and REDACT_FILE
are never read.
Statuses: add (the profile has no value), done (it holds the same), different (it holds another: never overwritten;
show the person both values and ask), confirm (needs --confirm <key>), left (a second source for one key).
Exit: 0 done, 1 refused (no profile, an unreadable file), 2 bad arguments, 3 a field holds another value in the
profile (--apply and --remove-old still do the rest).
"""
import datetime
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jsenv  # noqa: E402
import profilelib as pl  # noqa: E402
from trackerlib import json_indent  # noqa: E402

PERSON_KEYS = ("name", "pronouns", "email", "phone", "address", "birth_date", "work_authorisation")
LINKS = ("linkedin", "github")
TEXT_TYPES = (".md", ".txt", ".json", ".jsonl", ".csv", ".html", ".htm", ".env")
MAX_SCAN = 2 * 1024 * 1024


def usage(message=""):
    print(message or __doc__, file=sys.stderr)
    sys.exit(2)


args = sys.argv[1:]
env_arg = None
if "--env" in args:
    i = args.index("--env")
    if i + 1 >= len(args):
        usage("--env needs a path")
    env_arg = args[i + 1]
    del args[i:i + 2]
confirmed = set()
while "--confirm" in args:
    i = args.index("--confirm")
    if i + 1 >= len(args):
        usage("--confirm needs a profile key, e.g. --confirm person.pronouns")
    confirmed.add(args[i + 1])
    del args[i:i + 2]
apply, remove_old = "--apply" in args, "--remove-old" in args
args = [a for a in args if a not in ("--apply", "--remove-old")]
if args or (apply and remove_old):
    usage("" if args else "--apply and --remove-old are separate runs: --remove-old comes after the person's OK")
env = jsenv.load(env_arg, __file__)
master_path = env.path("MASTER_RECORD")
personal_path = env.path("PERSONAL_RECORD") if env.get("PERSONAL_RECORD") else \
    os.path.join(env.home, "career-records", "personal.json")


def read(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        print(f"cannot read {path} ({e}): nothing was changed", file=sys.stderr)
        sys.exit(1)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).translate(jsenv.ASCII).lower()).strip("-")[:40] or "x"


master = read(master_path) or {}
personal = read(personal_path)
moves = []  # {key, value, source: (file label, [path parts]), confirm}
by_hand = []  # lines
taken = {}


def move(key, value, label, parts, confirm=False):
    if value in (None, "", [], {}):
        return
    if key in taken:
        by_hand.append(f"left        {label} {dotted(parts)}: same profile key {key} as {taken[key]}")
        return
    taken[key] = f"{label} {dotted(parts)}"
    moves.append({"key": key, "value": value, "label": label, "parts": parts, "confirm": confirm})


def dotted(parts):
    return "".join(f"[{p}]" if isinstance(p, int) else ("." if i else "") + p for i, p in enumerate(parts))


# --- MASTER_RECORD profile -------------------------------------------------------------------------------------------
MR = "MASTER_RECORD"
profile = master.get("profile") if isinstance(master.get("profile"), dict) else {}
for k in PERSON_KEYS:
    move(f"person.{k}", profile.get(k), MR, ["profile", k])
for k in ("citizenship", "nationality"):
    if profile.get(k):
        value = profile[k] if isinstance(profile[k], list) else [profile[k]]
        move("person.nationality", value, MR, ["profile", k])
move("person.languages", profile.get("languages"), MR, ["profile", "languages"])
for k in LINKS:
    if isinstance(profile.get(k), str):
        move(f"person.links.{k}", profile[k], MR, ["profile", k])
contact = profile.get("contact") if isinstance(profile.get("contact"), dict) else {}
for k, v in contact.items():
    if k in LINKS and isinstance(v, dict):
        move(f"person.links.{k}", v.get("account"), MR, ["profile", "contact", k, "account"])
    elif k in LINKS:
        move(f"person.links.{k}", v, MR, ["profile", "contact", k])
    elif re.fullmatch(r"[A-Za-z0-9_-]+", k) and k not in pl.FORBIDDEN:
        move(f"person.{k}", v, MR, ["profile", "contact", k])
    else:
        by_hand.append(f"by hand     {MR} profile.contact.{k}: the key is not a plain name; choose one with the person")
location = profile.get("location")
if isinstance(location, str) and re.fullmatch(r"[^,]+,[^,]+", location.strip()):
    city, country = (s.strip() for s in location.split(","))
    move("person.location", {"city": city, "country": country}, MR, ["profile", "location"])
elif isinstance(location, dict) and set(location) == {"city", "country"}:
    move("person.location", location, MR, ["profile", "location"])
elif location:
    by_hand.append(f"by hand     {MR} profile.location: not \"City, Country\" or {{city, country}}; set person.location "
                   "{city, country} with the person")
move("person.pronouns", profile.get("pronouns_on_linkedin"), MR, ["profile", "pronouns_on_linkedin"], confirm=True)

# --- referees ----------------------------------------------------------------------------------------------------------
refs = master.get("references")
rows = []
if isinstance(refs, list):
    rows = [(["references", i], r) for i, r in enumerate(refs)]
elif isinstance(refs, dict) and isinstance(refs.get("rows"), list):
    rows = [(["references", "rows", i], r) for i, r in enumerate(refs["rows"])]
elif isinstance(refs, dict):
    rows = [(["references", k], r) for k, r in refs.items() if not k.startswith("_")]
used_ids = set()
for parts, row in rows:
    if not isinstance(row, dict) or not str(row.get("name") or "").strip():
        continue
    words = str(row["name"]).split()
    cid = f"referee-{slug(words[0])}"
    if cid in used_ids:
        cid = f"referee-{slug(row['name'])}"
    n = 2
    while cid in used_ids:
        cid, n = f"referee-{slug(row['name'])}-{n}", n + 1
    used_ids.add(cid)
    entry = {k: v for k, v in row.items() if k not in ("worked_together_since", "title")}
    entry["role"] = row.get("role") or row.get("title") or "referee"
    if row.get("worked_together_since"):
        entry["since"] = row["worked_together_since"]
    entry.setdefault("source", "MASTER_RECORD references")
    move(f"contacts.{cid}", entry, MR, parts)
    if not row.get("agreed_on"):
        by_hand.append(f"ask         contacts.{cid}: no agreed_on; ask the person the day this referee agreed, then "
                       f"set contacts.{cid}.agreed_on")

# --- employment ------------------------------------------------------------------------------------------------------
for top in ("employment", "employment_timeline"):
    block = master.get(top)
    items = (list(enumerate(block)) if isinstance(block, list) else
             [(k, v) for k, v in block.items() if not str(k).startswith("_")] if isinstance(block, dict) else [])
    for k, row in items:
        if isinstance(row, dict) and row.get("employer") and row.get("start"):
            year = re.search(r"\d{4}", str(row["start"]))
            eid = f"{slug(row['employer'])}-{year.group(0) if year else slug(row['start'])}"
            entry = {"employer": row["employer"], "role": row.get("role"), "start": row["start"],
                     "end": row.get("end"), "location": row.get("location")}  # end null: the current job
            entry.update({x: y for x, y in row.items() if x not in entry})
            entry = {x: y for x, y in entry.items() if y is not None or x == "end"}
            entry.setdefault("source", f"MASTER_RECORD {top}")
            move(f"employment.{eid}", entry, MR, [top, k])
if isinstance(master.get("experience"), list) and master["experience"]:
    by_hand.append(f"by hand     {MR} experience[0..{len(master['experience']) - 1}]: each job's true start and end "
                   "go into employment.<employer>-<start year>, with the person; experience keeps the CV's wording")

# --- the old private record ------------------------------------------------------------------------------------------
PR = "PERSONAL_RECORD"
facts = (personal or {}).get("facts") if isinstance((personal or {}).get("facts"), dict) else {}
for k, v in facts.items():
    if not re.fullmatch(r"[A-Za-z0-9_-]+", k) or k in pl.FORBIDDEN:
        by_hand.append(f"by hand     {PR} facts.{k}: the key is not a plain name; choose one with the person")
        continue
    if isinstance(v, dict) and "answer" not in v and v.get("name") and (v.get("email") or v.get("phone")):
        move(f"contacts.{k}", dict(v, source=v.get("source") or "PERSONAL_RECORD"), PR, ["facts", k])
        continue
    entry = dict(v) if isinstance(v, dict) else {"answer": v}
    if "typed" in entry:
        entry.setdefault("words", entry.pop("typed"))
    entry.setdefault("source", "PERSONAL_RECORD")
    move(f"private.{k}", entry, PR, ["facts", k])


# --- compare with the profile ------------------------------------------------------------------------------------------
prof = pl.load(env)
if prof["error"]:
    print(f"The profile {prof['path']} cannot be read ({prof['error']}): nothing was changed. Tell the person.",
          file=sys.stderr)
    sys.exit(1)
if not prof["exists"] and (apply or remove_old):
    print(pl.missing_message(prof), file=sys.stderr)
    sys.exit(1)


def status(m):
    current = pl.get(m["key"], env) if prof["exists"] else pl.ABSENT
    if pl.same(current, m["value"]):
        return "done"
    if current is not pl.ABSENT:
        return "different"
    if m["confirm"] and m["key"] not in confirmed:
        return "confirm"
    return "add"


for m in moves:
    m["status"] = status(m)
written = 0
if apply:
    for m in moves:
        if m["status"] != "add":
            continue
        try:
            _, changed = pl.set_value(m["key"], m["value"], pl.ABSENT, env)
            m["status"], written = "done", written + bool(changed)
        except pl.ProfileError as e:
            if e.code != 3:
                print(f"{m['key']}: not written ({e.code}); stopped here, nothing more was written", file=sys.stderr)
                sys.exit(1)
            m["status"] = "different"


def remove_at(data, parts):
    """Deletes the value at parts and every object or list left empty above it; True when there was one."""
    node, trail = data, []
    for p in parts[:-1]:
        try:
            trail.append((node, p))
            node = node[p]
        except (KeyError, IndexError, TypeError):
            return False
    try:
        del node[parts[-1]]
    except (KeyError, IndexError, TypeError):
        return False
    for parent, p in reversed(trail):
        if parent[p] in ({}, []) or (isinstance(parent[p], dict) and set(parent[p]) <= {"_about"}):
            del parent[p]
        else:
            break
    return True


def save(path, data):
    """Keep the file's indent, line endings and permissions; through a temporary file, removed when the write fails:
    it holds the person's values."""
    with open(path, "rb") as f:
        crlf = b"\r\n" in f.read(4096)
    text = json.dumps(data, ensure_ascii=False, indent=json_indent(path)) + "\n"
    temp = path + ".tmp"
    try:
        with open(temp, "wb") as f:
            f.write((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
        shutil.copymode(path, temp)
        os.replace(temp, path)
    except OSError:
        try:
            os.remove(temp)
        except OSError:
            pass
        raise


backups, removed = [], 0
if remove_old:
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    gone = {MR: [], PR: []}
    for m in sorted((m for m in moves if m["status"] == "done"), key=lambda m: str(m["parts"]), reverse=True):
        gone[m["label"]].append(m["parts"])
    for label, path, data in ((MR, master_path, master), (PR, personal_path, personal)):
        # Highest list index first, so removing one row never shifts another still to remove.
        todo = sorted(gone[label], key=lambda p: [(0, x) if isinstance(x, int) else (1, x) for x in p], reverse=True)
        if not todo or data is None:
            continue
        backup = f"{path}.before-move-{stamp}.json"
        shutil.copy2(path, backup)
        backups.append(backup)
        removed += sum(remove_at(data, parts) for parts in todo)
        if label == PR and not data.get("facts") and set(data) <= {"_about", "facts"}:
            os.remove(path)
            print(f"deleted {path}: everything in it is in the profile; the PERSONAL_RECORD line in "
                  f"{env.file} is no longer used")
        else:
            save(path, data)

# --- MASTER_RECORD history entries about moved fields ------------------------------------------------------------------
moved_paths = [dotted(m["parts"]) for m in moves if m["label"] == MR]
history = master.get("history") if isinstance(master.get("history"), list) else []
about = sorted({e.get("path") for e in history if isinstance(e, dict) and isinstance(e.get("path"), str)
                and any(e["path"] == p or e["path"].startswith(p + ".") for p in moved_paths)})
if about:
    by_hand.append(f"by hand     {MR} history: entries about {', '.join(about)} hold earlier values of moved facts; "
                   "the person decides whether to delete them")


# --- files in the main folder that repeat a profile value ---------------------------------------------------------------
def needles():
    """{profile key: [texts to find]} for the values worth finding: email, phone, address, birth date, contacts."""
    values = {m["key"]: m["value"] for m in moves}
    if prof["exists"]:
        data = pl.load(env)["data"]
        for k in ("email", "phone", "address", "birth_date"):
            if (data.get("person") or {}).get(k):
                values[f"person.{k}"] = data["person"][k]
        for cid, c in (data.get("contacts") or {}).items():
            if isinstance(c, dict):
                values[f"contacts.{cid}"] = c
    out = {}
    for key, value in values.items():
        texts = []
        if key in ("person.email", "person.address") and isinstance(value, str) and len(value) >= 6:
            texts.append(value.lower())
        elif key == "person.phone" and isinstance(value, str):
            texts.append(("digits", re.sub(r"\D", "", value)[-8:]))
        elif key == "person.birth_date" and isinstance(value, str):
            d = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value)
            texts += [value] + ([f"{d[3]}.{d[2]}.{d[1]}", f"{d[3]}/{d[2]}/{d[1]}"] if d else [])
        elif key.startswith("contacts.") and isinstance(value, dict):
            texts += [str(value["email"]).lower()] if value.get("email") else []
            texts += [("digits", re.sub(r"\D", "", str(value["phone"]))[-8:])] if value.get("phone") else []
        texts = [t for t in texts if (len(t[1]) >= 7 if isinstance(t, tuple) else t)]
        if texts:
            out[key] = texts
    return out


def skipped_paths():
    skip = {os.path.normcase(os.path.abspath(p)) for p in (master_path, personal_path, prof["path"] or "")}
    for key in ("APPLICATIONS_DIR", "LETTERS_DIR", "LETTER_BODIES_DIR", "CVS_DIR", "CV_VERSIONS_DIR", "SENT_CVS_DIR",
                "OTHER_FILES_DIR", "REDACT_FILE", "TRACKER"):
        if env.get(key):
            skip.add(os.path.normcase(env.path(key)))
    if env.get("TRACKER"):
        skip.add(os.path.normcase(os.path.join(os.path.dirname(env.path("TRACKER")), "details")))
    return skip


def repeats():
    found, wanted, skip = [], needles(), skipped_paths()
    if not wanted:
        return found
    for folder, dirs, files in os.walk(env.home):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".")
                         and os.path.normcase(os.path.join(folder, d)) not in skip)
        for name in sorted(files):
            path = os.path.join(folder, name)
            if not name.lower().endswith(TEXT_TYPES) or os.path.normcase(path) in skip or ".before-" in name:
                continue
            try:
                if os.path.getsize(path) > MAX_SCAN:
                    continue
                with open(path, encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                rel = os.path.relpath(path, env.home).replace(os.sep, "/")
                found.append(f"  {rel} (could not be read: check it by hand)")
                continue
            low = text.lower()
            # Phone numbers: the digits of each phone-like run, so digits of separate numbers never join.
            phones = [re.sub(r"\D", "", run) for run in re.findall(r"\+?\d[\d ().-]{5,}\d", text)]
            hits = sorted(k for k, ts in wanted.items()
                          if any(any(t[1] in d for d in phones) if isinstance(t, tuple) else (t in low) for t in ts))
            if hits:
                rel = os.path.relpath(path, env.home).replace(os.sep, "/")
                found.append(f"  {rel} ({', '.join(hits)})")
                pdf = os.path.splitext(path)[0] + ".pdf"
                if os.path.exists(pdf):
                    found.append(f"  {os.path.relpath(pdf, env.home).replace(os.sep, '/')} (beside {rel})")
    return found


# --- report ------------------------------------------------------------------------------------------------------------
print(f"Profile: {prof['path']}" if prof["exists"] else pl.missing_message(prof))
print(f"Sources: {master_path}" + (f", {personal_path}" if personal is not None else ""))
NOTE = {"add": "", "done": "", "different": "  (the profile holds another value: show the person both and ask)",
        "confirm": "  (after the person confirms: --confirm {key})"}
for m in moves:
    print(f"{m['status']:<11} {m['key']} <- {m['label']} {dotted(m['parts'])}" + NOTE[m["status"]].format(key=m["key"]))
for line in by_hand:
    print(line)
found = repeats()
if found:
    print("Files that repeat a profile value (rebuilding or deleting each is the person's call):")
    print("\n".join(found))
if backups:
    print("Backups (they hold the removed values: delete them once the profile is checked): " + ", ".join(backups))
counts = {s: sum(1 for m in moves if m["status"] == s) for s in ("add", "done", "different", "confirm")}
summary = ", ".join(f"{n} {s}" for s, n in counts.items() if n) or "nothing to move"
if apply:
    print(f"Written: {written} field(s) added to the profile. Now: {summary}.")
elif remove_old:
    print(f"Removed {removed} moved field(s) from the old files. Kept there: every field not marked done.")
else:
    print(f"Dry run, nothing written: {summary}. --apply adds the fields marked add.")
sys.exit(3 if counts["different"] else 0)
