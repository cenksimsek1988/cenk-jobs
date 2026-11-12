"""The person's profile: one JSON file with every personal fact about them and the settings they chose, shared with
the other cenk-* plugins. Name, contact, nationality, languages, birth date and address (person), private answers
(private), referees and other people (contacts) and the true employment timeline (employment) live only there;
MASTER_RECORD keeps what cenk-jobs makes from them (CV wording, form answers, preferences, decisions, rules).

Where it is, first match wins:
  1. PROFILE in job-search.env (relative to JOB_SEARCH_HOME); when it is set, nothing else is looked at;
  2. the workbench setting profile_path (CLAUDE_PLUGIN_OPTION_PROFILE_PATH, else
     pluginConfigs["cenk-workbench@cenk-workbench"].options.profile_path in <Claude config folder>/settings.json);
  3. claude/profile.json in a Google Drive "My Drive" folder: <letter>:\\My Drive for C to Z on Windows,
     ~/Library/CloudStorage/GoogleDrive-*/My Drive sorted by name on a Mac;
  4. <Claude config folder>/claude/profile.json, the folder being CLAUDE_CONFIG_DIR, else ~/.claude.
None found: nothing is written. The session asks the person where to create it, suggesting the first "My Drive"
folder's claude/profile.json (else 4), and runs create after their answer.

python -I profilelib.py [--env <job-search.env>] <command>
  path                               the profile in use, or nothing
  get <plugin> <key>                 a setting: settings.<plugin>, then settings.common; a list joined by ", "; nothing
                                     when unset. Example: get cenk-jobs form_facts
  get <key>                          one value: a string as it is, anything else as JSON; [n] picks a list item.
                                     Example: get person.languages[0].level
  set <key> <json|-> [--old <json>] [--yes]
                                     compare-and-set: writes only when the file holds the --old value there (absent
                                     when --old is not given); - reads the value from stdin, for a private value.
                                     Example: set person.phone '"+39 06 0000 0000"'
  erase <key> [--yes]                the value and every trace of it in history
  create <path>                      a new, empty profile at the path the person chose; adds PROFILE= to the env file
                                     when the lookup would not find it there; with no env file, refused (exit 1)
                                     unless the lookup finds it
Exit: 0 done (or nothing to change), 1 refused (no profile, unreadable, a key not found, a setting without --yes),
2 bad arguments, 3 the file holds another value than --old says: nothing was written; show the person both values and
ask which is right.

A key under settings decides what sessions may do: set and erase change one only with --yes, given after the person's
yes for that key and value in the chat. Without it they write nothing, exit 1 and print the key, the old and the new
value to ask about. The workbench's guard asks before its own profile.js does this; it cannot see this writer.

Keys are dotted parts of letters, digits, - and _ (contacts.referee-sam.email). set and erase read the file right
before writing, keep each replaced value in history as {date, field, old, new}, and replace the file through a
temporary file in the same folder. These are the workbench's writing rules for the profile, so both writers agree.
"""
import datetime
import glob
import json
import os
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jsenv  # noqa: E402

RELATIVE = os.path.join("claude", "profile.json")
PART = re.compile(r"^([A-Za-z0-9_-]+)((?:\[\d+\])*)$")
FORBIDDEN = {"__proto__", "constructor", "prototype"}
PLUGIN = "cenk-jobs"
# The guarded items a form may answer from the profile only when the person lists them in the setting form_facts
# (settings.cenk-jobs, else settings.common; default none). ID numbers, passwords and card numbers: never.
FORM_FACTS = ("birth_date", "address", "references", "criminal_record", "relatives", "health")
ABSENT = object()  # no value at a key


class ProfileError(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


def config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def read_json(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def configured_path(claude_dir):
    """The workbench setting profile_path, or ''."""
    if "CLAUDE_PLUGIN_OPTION_PROFILE_PATH" in os.environ:
        return os.environ["CLAUDE_PLUGIN_OPTION_PROFILE_PATH"].strip()
    try:
        options = read_json(os.path.join(claude_dir, "settings.json"))["pluginConfigs"]["cenk-workbench@cenk-workbench"]
        return str((options.get("options") or {}).get("profile_path") or "").strip()
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return ""


def drive_roots():
    """The Google Drive "My Drive" folders on this computer, in lookup order."""
    if sys.platform == "win32":
        candidates = [f"{chr(code)}:\\My Drive" for code in range(ord("C"), ord("Z") + 1)]
    elif sys.platform == "darwin":
        storage = os.path.join(os.path.expanduser("~"), "Library", "CloudStorage")
        try:
            candidates = [os.path.join(storage, e, "My Drive") for e in sorted(os.listdir(storage))
                          if e.startswith("GoogleDrive-")]
        except OSError:
            candidates = []
    else:
        candidates = []
    return [root for root in candidates if os.path.isdir(root)]


def locate(env=None, roots=None, claude_dir=None):
    """{path, scope, suggested}: scope is env, setting, cloud, computer or None; suggested is where a new profile goes.
    roots and claude_dir replace the computer's own drive folders and Claude config folder (tests pass made-up ones)."""
    if env is not None and env.get("PROFILE"):
        own = env.path("PROFILE")
        return {"path": own, "scope": "env", "suggested": own}
    claude_dir = config_dir() if claude_dir is None else claude_dir
    configured = configured_path(claude_dir)
    if configured:
        return {"path": configured, "scope": "setting", "suggested": configured}
    roots = drive_roots() if roots is None else [r for r in roots if os.path.isdir(r)]
    for root in roots:
        candidate = os.path.join(root, RELATIVE)
        if os.path.exists(candidate):
            return {"path": candidate, "scope": "cloud", "suggested": candidate}
    local = os.path.join(claude_dir, RELATIVE)
    if os.path.exists(local):
        return {"path": local, "scope": "computer", "suggested": local}
    return {"path": None, "scope": None, "suggested": os.path.join(roots[0], RELATIVE) if roots else local}


def load(env=None, **where):
    """{path, scope, suggested, exists, data, error}: data is {} without a readable profile; error says why."""
    found = locate(env, **where)
    if not found["path"] or not os.path.exists(found["path"]):
        return dict(found, exists=False, data={}, error=None)
    try:
        data = read_json(found["path"])
    except (OSError, ValueError) as e:
        return dict(found, exists=True, data={}, error=str(e))
    if not isinstance(data, dict):
        return dict(found, exists=True, data={}, error="not a JSON object")
    return dict(found, exists=True, data=data, error=None)


def missing_message(profile):
    return (f"No profile yet: nothing was read or written. Ask the person where to create it, suggesting "
            f"{profile['suggested']}; then: profilelib.py create <path>.")


def setting(profile, key, default=None, plugin=PLUGIN):
    """A setting's raw value: settings.<plugin>, then settings.common, then the default."""
    settings = (profile.get("data") or {}).get("settings") or {}
    for section in (plugin, "common"):
        values = settings.get(section)
        if isinstance(values, dict) and key in values:
            return values[key]
    return default


def form_facts(profile):
    """(allowed, unknown): the guarded items the setting form_facts lets forms answer, and the names it lists that
    are not guarded items (an ID number never is). A string setting may list them with commas."""
    value = setting(profile, "form_facts", [])
    names = value if isinstance(value, list) else re.split(r"\s*,\s*", str(value).strip())
    names = [str(n).strip() for n in names if str(n).strip()]
    return [n for n in names if n in FORM_FACTS], [n for n in names if n not in FORM_FACTS]


def text_of(value):
    """A value as profile.js prints it in a setting: a string as it is, a list joined by ", "."""
    if isinstance(value, list):
        return ", ".join("" if v is None else text_of(v) for v in value)
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def parse_key(key, indexes):
    """'person.languages[0].level' -> ['person', 'languages', 0, 'level']; [n] only where indexes is true."""
    parts = []
    for piece in str(key or "").split("."):
        match = PART.match(piece)
        if not match or match.group(1) in FORBIDDEN or (match.group(2) and not indexes):
            raise ProfileError(f'Bad key "{key}": use dotted names of letters, digits, - and _'
                               + (", and [n] for a list item" if indexes else "")
                               + ". Example: contacts.lawyer.email", 2)
        parts.append(match.group(1))
        parts += [int(n) for n in re.findall(r"\d+", match.group(2))]
    return parts


def writable_key(key):
    parts = parse_key(key, False)
    if parts[0] == "history":
        raise ProfileError("history is written by set and erase only.", 2)
    return parts


def is_setting(parts):
    return parts[0] == "settings"


def ask_first(key, old, new):
    """The refusal for a settings change without the person's yes: the key and both values, to show them."""
    return ProfileError(f"{key} is a setting: nothing was written. Ask the person first, showing the key, the old value "
                        f"({shown(old)}) and the new one ({shown(new)}); after their yes, run again with --yes.", 1)


def same(a, b):
    """Equal JSON values, whatever the order of an object's keys; ABSENT equals only ABSENT."""
    if a is ABSENT or b is ABSENT:
        return a is b
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def shown(value):
    return "nothing" if value is ABSENT else json.dumps(value, ensure_ascii=False)


def read_for_write(env, **where):
    profile = load(env, **where)
    if not profile["exists"]:
        raise ProfileError(missing_message(profile), 1)
    if profile["error"]:
        raise ProfileError(f"The profile {profile['path']} cannot be read ({profile['error']}): nothing was written. "
                           "Tell the person.", 1)
    data = profile["data"]
    if "history" in data and not isinstance(data["history"], list):
        raise ProfileError(f"history in {profile['path']} is not a list: nothing was written. Tell the person.", 1)
    return profile["path"], data


def write_atomic(path, data):
    """A temporary file in the same folder, renamed over the profile, so a reader never sees half a file. A cloud
    drive's sync can hold the file for a moment: the rename is tried up to 4 times, 0.2 s apart. history goes last."""
    ordered = {k: v for k, v in data.items() if k != "history"}
    if "history" in data:
        ordered["history"] = data["history"]
    text = json.dumps(ordered, ensure_ascii=False, indent=2) + "\n"
    temp = os.path.join(os.path.dirname(path), f".{os.path.basename(path)}.{os.getpid()}.{int(time.time() * 1000)}.tmp")
    try:
        with open(temp, "xb") as f:
            f.write(text.encode("utf-8"))
        if os.path.exists(path):
            shutil.copymode(path, temp)  # keep the profile's own permissions
        for attempt in range(1, 5):
            try:
                os.replace(temp, path)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.2)
    except OSError as e:
        try:
            os.remove(temp)
        except OSError:
            pass
        raise ProfileError(f"The profile {path} could not be written ({e}); it is unchanged.", 1)


def get(key, env=None, **where):
    """The value at a key, or ABSENT. Raises ProfileError without a readable profile."""
    parts = parse_key(key, True)
    profile = load(env, **where)
    if not profile["exists"]:
        raise ProfileError(missing_message(profile), 1)
    if profile["error"]:
        raise ProfileError(f"The profile {profile['path']} cannot be read ({profile['error']}). Tell the person.", 1)
    node = profile["data"]
    for part in parts:
        if isinstance(part, int):
            if not isinstance(node, list) or part >= len(node):
                return ABSENT
        elif not isinstance(node, dict) or part not in node:
            return ABSENT
        node = node[part]
    return node


def set_value(key, value, old=ABSENT, env=None, yes=False, **where):
    """Compare-and-set: writes the value only when the file holds old at the key (ABSENT: no value there). A replaced
    value goes into history. Returns (path, changed); raises ProfileError with code 3 when the file holds another, and
    with code 1 for a change under settings without yes (the person's yes in the chat)."""
    parts = writable_key(key)
    path, data = read_for_write(env, **where)
    parent = data
    for i, part in enumerate(parts[:-1]):
        if part not in parent:
            parent[part] = {}
        elif not isinstance(parent[part], dict):
            raise ProfileError(f"{'.'.join(parts[:i + 1])} is not an object: nothing was written.", 1)
        parent = parent[part]
    last = parts[-1]
    current = parent.get(last, ABSENT)
    if same(current, value):
        return path, False
    if not same(current, old):
        raise ProfileError(f"{key} holds {shown(current)}, not {shown(old)}: nothing was written. Show the person both "
                           "values and ask which is right.", 3)
    if is_setting(parts) and not yes:
        raise ask_first(key, current, value)
    parent[last] = value
    if current is not ABSENT:
        data.setdefault("history", []).append(
            {"date": datetime.date.today().isoformat(), "field": key, "old": current, "new": value})
    write_atomic(path, data)
    return path, True


def get_in(obj, parts):
    """The value at parts inside obj (dotted names only), or ABSENT."""
    for part in parts:
        if not isinstance(obj, dict) or part not in obj:
            return ABSENT
        obj = obj[part]
    return obj


def remove_at(obj, parts):
    """Deletes the value at parts inside obj; True when there was one."""
    node = obj
    for part in parts[:-1]:
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    if not isinstance(node, dict) or parts[-1] not in node:
        return False
    del node[parts[-1]]
    return True


def erase(key, env=None, yes=False, **where):
    """Removes the value and every trace of it in history: entries for the key or a key under it, and the erased part
    inside entries recorded on a parent key (dropped when nothing else changed). Returns (path, changed). A key under
    settings is erased only with yes (the person's yes in the chat); without it, ProfileError with code 1."""
    parts = writable_key(key)
    path, data = read_for_write(env, **where)
    current = get_in(data, parts)
    changed = remove_at(data, parts)
    if "history" in data:
        kept = []
        for entry in data["history"]:
            field = entry.get("field") if isinstance(entry, dict) and isinstance(entry.get("field"), str) else ""
            if field == key or field.startswith(key + "."):
                changed = True
                continue
            if field and key.startswith(field + "."):
                rest = key[len(field) + 1:].split(".")
                scrubbed = any([remove_at(entry, [side, *rest]) for side in ("old", "new")])
                if scrubbed:
                    changed = True
                    if same(entry.get("old", ABSENT), entry.get("new", ABSENT)):
                        continue
            kept.append(entry)
        data["history"] = kept
    if changed and is_setting(parts) and not yes:
        raise ask_first(key, current, ABSENT)
    if changed:
        write_atomic(path, data)
    return path, changed


def cloud_note(path):
    """What the person still has to do after an erase: a cloud drive keeps earlier versions of the file."""
    norm = path.replace("\\", "/")
    if "/My Drive/" in norm or "/GoogleDrive-" in norm:
        return ("Google Drive keeps the earlier versions of this file for up to 30 days, and they still hold the "
                "erased value. After the person's yes (they cannot be restored), they delete them: drive.google.com, "
                "signed in to the account that holds the profile, right-click the file, File information, Manage "
                "versions, delete every version except the current one.")
    if "/OneDrive" in norm:
        return ("OneDrive keeps earlier versions of this file, and they still hold the erased value. After the "
                "person's yes, they delete them in the file's Version history.")
    return ""


def move_backups(env):
    """The backups move_to_profile.py --remove-old left beside the old records: they may still hold an erased value."""
    if env is None:
        return []
    sources = [env.path("MASTER_RECORD")] if env.get("MASTER_RECORD") else []
    sources.append(env.path("PERSONAL_RECORD") if env.get("PERSONAL_RECORD")
                   else os.path.join(env.home, "career-records", "personal.json"))
    return sorted(p for s in sources for p in glob.glob(glob.escape(s) + ".before-move-*.json"))


def shared_lookup_finds(path):
    """True when the lookup every cenk-* plugin uses (no job-search.env) would find a new profile at path: the
    workbench setting profile_path when set, else claude/profile.json in each "My Drive" folder, else in the Claude
    config folder. For a new profile only: with none anywhere yet, each place is reached in turn."""
    claude_dir = config_dir()
    configured = configured_path(claude_dir)
    places = ([configured] if configured else
              [os.path.join(root, RELATIVE) for root in drive_roots()] + [os.path.join(claude_dir, RELATIVE)])
    wanted = os.path.normcase(os.path.abspath(path))
    return any(os.path.normcase(os.path.abspath(p)) == wanted for p in places)


def create(path, env=None):
    """A new, empty profile at the path the person chose. Adds PROFILE=<path> to the env file when the lookup would not
    find the new file. Refuses when a profile exists already, and with no env file when the shared lookup would not
    find the new file (then nothing would)."""
    profile = load(env)
    if profile["exists"]:
        raise ProfileError(f"A profile exists already at {profile['path']}: nothing was created.", 1)
    path = os.path.abspath(path)
    if os.path.exists(path):
        raise ProfileError(f"{path} exists already: nothing was created.", 1)
    if env is None and not shared_lookup_finds(path):
        raise ProfileError(f"Nothing would find a profile at {path}: nothing was created. Create it where the cenk-* "
                           f"plugins look ({profile['suggested']}), or run from the main folder, whose "
                           "job-search.env will name it.", 1)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_atomic(path, {})
    if env is not None and os.path.normcase(os.path.abspath(locate(env)["path"] or "")) != os.path.normcase(path):
        with open(env.file, encoding="utf-8") as f:
            lines = f.read().splitlines()
        lines = [line for line in lines if not re.match(r"\s*PROFILE\s*=", line)] + [f"PROFILE={path}"]
        with open(env.file, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        return path, True
    return path, False


def parse_value(text, what):
    try:
        return json.loads(text[1:] if text.startswith("﻿") else text)
    except ValueError as e:
        raise ProfileError(f"{what} is not JSON ({e}). A string needs its quotes: '\"she/her\"'.", 2)


def env_of(argv):
    """The job-search.env from --env, else the one jsenv finds, else None (then only the shared lookup counts)."""
    if "--env" in argv:
        i = argv.index("--env")
        if i + 1 >= len(argv):
            raise ProfileError("--env needs a path.", 2)
        explicit = argv[i + 1]
        del argv[i:i + 2]
        return jsenv.load(explicit)
    try:
        return jsenv.load(None, __file__)
    except SystemExit:
        return None


USAGE = ("usage: profilelib.py [--env <job-search.env>] path | get <plugin> <key> | get <key> | "
         "set <key> <json|-> [--old <json>] [--yes] | erase <key> [--yes] | create <path>")


def main(argv):
    argv = list(argv)
    env = env_of(argv)
    command, rest = (argv[0], argv[1:]) if argv else ("", [])
    # --yes: the person said yes in the chat to this settings change (key and value); only set and erase take it.
    yes = command in ("set", "erase") and "--yes" in rest
    if yes:
        rest = [a for a in rest if a != "--yes"]
    if command == "path" and not rest:
        print(locate(env)["path"] or "")
    elif command == "get" and len(rest) == 2:
        profile = load(env)
        if profile["exists"] and profile["error"]:
            raise ProfileError(f"The profile {profile['path']} cannot be read ({profile['error']}). Tell the person.", 1)
        value = setting(profile, rest[1], None, rest[0])
        print("" if value is None else text_of(value))
    elif command == "get" and len(rest) == 1:
        value = get(rest[0], env)
        if value is ABSENT:
            raise ProfileError(f"{rest[0]} is not in the profile.", 1)
        print(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))
    elif command == "set" and (len(rest) == 2 or (len(rest) == 4 and rest[2] == "--old")):
        key, text = rest[0], rest[1]
        value = parse_value(sys.stdin.read() if text == "-" else text, "The value")
        old = parse_value(rest[3], "The --old value") if len(rest) == 4 else ABSENT
        path, changed = set_value(key, value, old, env, yes)
        print(f"set {key} in {path}" if changed else f"unchanged: {key} already holds this value")
    elif command == "erase" and len(rest) == 1:
        path, changed = erase(rest[0], env, yes)
        if changed:
            print(f"erased {rest[0]} and its history in {path}")
            note = cloud_note(path)
            if note:
                print(note)
        else:
            print(f"nothing to erase: {rest[0]} is not in the profile")
        backups = move_backups(env)
        if backups:
            print("These backups from move_to_profile.py may still hold the value; after the person's yes, delete them:")
            for backup in backups:
                print(f"  {backup}")
    elif command == "create" and len(rest) == 1:
        path, pinned = create(rest[0], env)
        print(f"created {path}" + (f"; PROFILE={path} added to {env.file}" if pinned else ""))
        if pinned:
            print("Only cenk-jobs reads job-search.env: for the workbench and the other cenk-* plugins to find it, "
                  f"set the workbench setting profile_path to {path}.")
    else:
        raise ProfileError(USAGE, 2)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    try:
        main(sys.argv[1:])
    except ProfileError as e:
        print(e, file=sys.stderr)
        sys.exit(e.code)
