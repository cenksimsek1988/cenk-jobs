"""The one way to write the shared records: a moved base is refused, the parts a command changed are checked, and
every write is logged.

Kinds, their job-search.env key and the path when the key is unset:
  tracker TRACKER, pipeline PIPELINE, logins LOGINS, employer-checks EMPLOYER_CHECKS: required;
  questions QUESTIONS: apply/questions.json; sessions SESSIONS: apply/sessions.json (both under JOB_SEARCH_HOME);
  searches SEARCHES: searches.json beside TRACKER; the change log CHANGES_LOG: changes.jsonl beside TRACKER.
These are the paths each script used before recordlib, so an install with a key unset keeps its files. Each kind's shape and vocabularies are in templates/schemas/<kind>.schema.json, a JSON Schema read by the small
check below (no jsonschema package); a vocabulary is listed there once, and a new value is added there first.

    import jsenv, recordlib
    env = jsenv.load()
    data, base = recordlib.load(env, "logins", {"logins": []})
    data["logins"].append({"id": "Workday · Acme", "status": "signed-in"})
    recordlib.save(env, "logins", data, base, "logins.py")

save reads the file's fingerprint (the sha256 of its bytes) again. When it moved since the load, nothing is written:
"STALE: apply/logins.json changed since it was read: run the command again", exit 3. It then checks the parts of
the rows the command changed, so an older row never blocks a write (records.py check names those): a value outside
its vocabulary or of the wrong type, a job made submitted with no applied date, a job made waiting with no waits_on.
A fault refuses the write: "REFUSED: apply/targets.json: J7 status: 'sent' is not one of ...", exit 1. Else it
writes a tmp file plus os.replace (which keeps the file's Drive id), in the file's own indent, line endings and final
newline, and appends {rev, at, script, file, ids} to the change log: ids are the rows that changed (the first 50, with
"more": <n> past them). A write whose data equals the file's is no write: nothing is written or logged. A command that
writes two files saves them with save_many: every base and every change is checked before the first write. A writer
that writes detail files before the main file calls check_base first. rev counts the log's lines; two sessions
writing at the same moment may log one rev twice (the log is a record of writes, not a lock).
"""
import copy
import datetime
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMAS = os.path.normpath(os.path.join(HERE, "..", "templates", "schemas"))

# kind: (env key, path when unset: None = the key is required; "@tracker/<name>" = beside TRACKER; else under home)
KINDS = {
    "tracker": ("TRACKER", None),
    "pipeline": ("PIPELINE", None),
    "logins": ("LOGINS", None),
    "questions": ("QUESTIONS", "apply/questions.json"),
    "sessions": ("SESSIONS", "apply/sessions.json"),
    "employer-checks": ("EMPLOYER_CHECKS", None),
    "searches": ("SEARCHES", "@tracker/searches.json"),
    "changes": ("CHANGES_LOG", "@tracker/changes.jsonl"),
}
# Where a kind keeps its rows: (key, the row's id key; None = an object keyed by id), and the row's schema.
ROWS = {"logins": ("logins", "id"), "sessions": ("sessions", "id"), "searches": ("searches", "id"),
        "questions": ("questions", None), "employer-checks": ("employers", None)}
ROW_DEF = {"tracker": "job", "pipeline": "entry", "logins": "login", "questions": "question", "sessions": "session",
           "searches": "search", "employer-checks": "employer"}
WAITING = ("account-needed", "needs-person", "needs-captcha")  # a job in one of these has waits_on
STALE_EXIT = 3
LOGGED_IDS = 50
_MISSING = object()


def path(env, kind):
    """The absolute path of a kind's file (see the module doc)."""
    key, default = KINDS[kind]
    if env.get(key) or default is None:
        return env.path(key)  # exits "<KEY> is not set in <env file>" when a required key is missing
    if default.startswith("@tracker/"):
        return os.path.normpath(os.path.join(os.path.dirname(env.path("TRACKER")), default[len("@tracker/"):]))
    return os.path.normpath(os.path.join(env.home, default))


def shown(env, file):
    """A file's path as the messages and the change log show it: relative to JOB_SEARCH_HOME, forward slashes."""
    try:
        rel = os.path.relpath(file, env.home)
    except ValueError:  # another drive
        return file.replace("\\", "/")
    return (file if rel.startswith("..") else rel).replace("\\", "/")


def _read(file):
    try:
        with open(file, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None


def _sha(raw):
    return hashlib.sha256(raw).hexdigest() if raw is not None else ""


def fingerprint(file):
    """The sha256 of a file's bytes; "" for a missing file."""
    return _sha(_read(file))


def _parse(raw):
    return json.loads(raw.decode("utf-8-sig"))


def load(env, kind, default=None):
    """(data, fingerprint) of a kind's file; (a copy of default, "") when it does not exist yet."""
    raw = _read(path(env, kind))
    if raw is None:
        return copy.deepcopy(default if default is not None else {}), ""
    return _parse(raw), _sha(raw)


def caller():
    """The running script's name, for the change log of a write made by a library. Example: "track.py"."""
    return os.path.basename(sys.argv[0] or "") or "python"


def stale(env, file):
    sys.stderr.write(f"STALE: {shown(env, file)} changed since it was read: run the command again\n")
    raise SystemExit(STALE_EXIT)


def check_base(env, kind, base):
    """Exit 3 (STALE) when the kind's file moved since base: before a writer writes the detail files of a row."""
    file = path(env, kind)
    if fingerprint(file) != base:
        stale(env, file)


def _style(raw, fallback_indent=2):
    """(indent, newline, final newline) of a file's own text, so a rewrite changes only what changed."""
    if not raw:
        return fallback_indent, "\n", True
    text = raw.decode("utf-8-sig", errors="replace")
    newline = "\r\n" if "\r\n" in text[:4096] else "\n"
    body = text.rstrip("\r\n")
    if "\n" not in body:
        return None, newline, text != body  # the whole file on one line
    second = body.split("\n", 2)[1]
    return (len(second) - len(second.lstrip(" "))) or fallback_indent, newline, text != body


def _text(data, style):
    indent, newline, final = style
    text = json.dumps(data, ensure_ascii=False, indent=indent)
    if newline != "\n":
        text = text.replace("\n", newline)
    return text + (newline if final else "")


def save(env, kind, data, base, script, ids=(), indent=2):
    """Write data as the kind's file when its base is unchanged; returns the new fingerprint (see the module doc)."""
    return save_many(env, [(kind, data, base, ids)], script, indent)[0]


def save_many(env, writes, script, indent=2):
    """writes: [(kind, data, base, ids)]. Every base and every change is checked before the first write."""
    plans = []
    for kind, data, base, ids in writes:
        file = path(env, kind)
        raw = _read(file)
        if _sha(raw) != base:
            stale(env, file)
        old = _parse(raw) if raw else None
        if raw and old == data:  # nothing changed: no write, no log line (seen: questions.py flushed it unchanged)
            plans.append((file, None, base))
            continue
        problems, changed_ids = diff(kind, old, data)
        if problems:
            for p in problems:
                sys.stderr.write(f"REFUSED: {shown(env, file)}: {p}\n")
            raise SystemExit(1)
        every = sorted({str(i) for i in ids} | set(changed_ids))
        plans.append((file, _text(data, _style(raw, indent)), every))
    done = []
    for file, text, every in plans:
        if text is None:
            done.append(every)  # the unchanged file's base
            continue
        os.makedirs(os.path.dirname(file), exist_ok=True)
        tmp = file + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, file)
        log_change(env, script, shown(env, file), every)
        done.append(hashlib.sha256(text.encode("utf-8")).hexdigest())
    return done


def rev(env):
    """The records' revision: the rev of the change log's last line (0 before the first logged write)."""
    try:
        with open(path(env, "changes"), "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 8192))
            tail = f.read().decode("utf-8", errors="replace").strip().splitlines()
    except FileNotFoundError:
        return 0
    for line in reversed(tail):
        try:
            return int(json.loads(line)["rev"])
        except (ValueError, KeyError, TypeError):
            continue
    return 0


def log_change(env, script, file, ids):
    log = path(env, "changes")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    line = {"rev": rev(env) + 1, "at": datetime.datetime.now().isoformat(timespec="seconds"), "script": script,
            "file": file, "ids": list(ids)[:LOGGED_IDS]}
    if len(ids) > LOGGED_IDS:
        line["more"] = len(ids) - LOGGED_IDS
    with open(log, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


# --- rows -----------------------------------------------------------------------------------------------------------

def rows(kind, data):
    """{id: row} of a kind's data. A tracker gives its jobs (either shape) and, as "company:<name>", each company's
    own fields; PIPELINE gives its entries."""
    out = {}
    if not isinstance(data, dict):
        return out
    if kind == "tracker":
        for job in data.get("jobs") or []:
            if isinstance(job, dict):
                out[str(job.get("id"))] = job
        for company in data.get("companies") or []:
            if not isinstance(company, dict):
                continue
            out["company:" + str(company.get("name", ""))] = {k: v for k, v in company.items() if k != "jobs"}
            for job in company.get("jobs") or []:
                if isinstance(job, dict):
                    out[str(job.get("id"))] = job
        return out
    if kind == "pipeline":
        return {k: v for k, v in data.items() if not k.startswith("_")}
    key, id_key = ROWS[kind]
    holder = data.get(key)
    if isinstance(holder, dict):
        return {str(k): v for k, v in holder.items()}
    if isinstance(holder, list):
        return {str(r.get(id_key)): r for r in holder if isinstance(r, dict)}
    return out


def diff(kind, old, new):
    """(faults in the changed parts, the ids of the rows that changed, were added or were removed)."""
    before, after = rows(kind, old), rows(kind, new)
    ids = [i for i in before if i not in after]
    problems = []
    sch = schema(kind)
    for rid, row in after.items():
        was = before.get(rid, _MISSING)
        if was == row:
            continue
        ids.append(rid)
        node = sch["$defs"]["company"] if rid.startswith("company:") and kind == "tracker" else \
            sch["$defs"][ROW_DEF[kind]]
        problems += [f"{where}: {message}" for where, message in changed(was, row, node, sch, rid)]
        problems += rules(kind, rid, was, row)
    return problems, ids


def rules(kind, rid, was, row):
    """The checks one schema cannot say, on a changed job: submitted needs applied; waiting needs waits_on."""
    if kind != "tracker" or rid.startswith("company:") or not isinstance(row, dict):
        return []
    status = row.get("status")
    if status == (was.get("status") if isinstance(was, dict) else None):
        return []
    out = []
    if status == "submitted" and not row.get("applied"):
        out.append(f"{rid} is made submitted with no applied date")
    if status in WAITING and not row.get("waits_on"):
        out.append(f"{rid} is made {status} with no waits_on: track.py wait {rid} ...")
    return out


# --- schemas: a JSON Schema subset ($ref, type, enum, properties, additionalProperties, items, required, pattern) --

_schemas = {}


def schema(kind):
    if kind not in _schemas:
        with open(os.path.join(SCHEMAS, kind + ".schema.json"), encoding="utf-8") as f:
            _schemas[kind] = json.load(f)
    return _schemas[kind]


def vocabulary(kind, name):
    """A vocabulary of a kind's schema, as a tuple. Example: vocabulary("tracker", "status")."""
    return tuple(schema(kind)["$defs"][name]["enum"])


TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _is(value, name):
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, TYPES[name])


def _deref(node, root):
    while isinstance(node, dict) and "$ref" in node:
        target = root
        for part in node["$ref"].lstrip("#/").split("/"):
            target = target[part]
        node = target
    return node


def type_name(value):
    for name in ("null", "boolean", "integer", "number", "string", "array", "object"):
        if _is(value, name):
            return {"array": "a list", "object": "an object"}.get(name, name)
    return type(value).__name__


def faults(value, node, root, where, unknown=True):
    """[(where, message)] for each place value does not fit node. unknown=False leaves out keys outside the shape and
    keys with spaces around them (a write is refused only for what it writes wrong)."""
    node = _deref(node, root)
    if not isinstance(node, dict) or not node:
        return []
    kinds = node.get("type")
    if kinds:
        kinds = kinds if isinstance(kinds, list) else [kinds]
        if not any(_is(value, k) for k in kinds):
            return [(where, f"is {type_name(value)}, not {' or '.join(kinds)}")]
    if "enum" in node and value not in node["enum"]:
        return [(where, f"'{value}' is not one of {', '.join(str(v) for v in node['enum'])}")]
    out = []
    if "pattern" in node and isinstance(value, str) and not re.search(node["pattern"], value):
        out.append((where, f"'{value}' is not {node.get('description') or 'of the form ' + node['pattern']}"))
    if isinstance(value, dict):
        props = node.get("properties", {})
        for key in node.get("required", []):
            if key not in value:
                out.append((where, f"has no {key}"))
        extra = node.get("additionalProperties", True)
        for key, sub in value.items():
            if unknown and (not key or key != key.strip()):
                out.append((where, f"key '{key}' has spaces around it"))
            if key in props:
                out += faults(sub, props[key], root, f"{where} {key}", unknown)
            elif extra is False:
                if unknown:
                    out.append((where, f"key '{key}' is not in the schema"))
            elif isinstance(extra, dict):
                out += faults(sub, extra, root, f"{where} {key}", unknown)
            elif unknown and isinstance(sub, (dict, list)):
                out += _spaced_keys(sub, f"{where} {key}")
    if isinstance(value, list) and isinstance(node.get("items"), dict):
        for i, sub in enumerate(value):
            out += faults(sub, node["items"], root, f"{where}[{i + 1}]", unknown)
    return out


def _spaced_keys(value, where):
    """Keys with spaces around them inside a part the schema leaves open (example: a prep's " gaps")."""
    out = []
    if isinstance(value, dict):
        for key, sub in value.items():
            if not key or key != key.strip():
                out.append((where, f"key '{key}' has spaces around it"))
            out += _spaced_keys(sub, f"{where} {key}")
    elif isinstance(value, list):
        for i, sub in enumerate(value):
            out += _spaced_keys(sub, f"{where}[{i + 1}]")
    return out


def changed(old, new, node, root, where):
    """Faults in the parts of new that differ from old: an unchanged value, an older key outside the shape and an
    unchanged list item (a step, by its position) are left alone."""
    if old is not _MISSING and old == new:
        return []
    node = _deref(node, root)
    if not isinstance(node, dict):
        return []
    kinds = node.get("type")
    kinds = kinds if isinstance(kinds, list) else [kinds] if kinds else []
    if isinstance(old, dict) and isinstance(new, dict) and (not kinds or "object" in kinds):
        props, extra, out = node.get("properties", {}), node.get("additionalProperties", True), []
        for key, value in new.items():
            sub = props.get(key, extra if isinstance(extra, dict) else None)
            if sub is not None:
                out += changed(old.get(key, _MISSING), value, sub, root, f"{where} {key}")
        return out
    if isinstance(old, list) and isinstance(new, list) and isinstance(node.get("items"), dict) \
            and (not kinds or "array" in kinds):
        out = []
        for i, value in enumerate(new):
            if value in old:  # an item that only moved (a to-do above it was removed) is unchanged
                continue
            out += changed(old[i] if i < len(old) else _MISSING, value, node["items"], root, f"{where}[{i + 1}]")
        return out
    return faults(new, node, root, where, unknown=False)
