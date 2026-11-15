"""cenk-jobs' door to the person's profile. The profile and its lookup belong to the base plugin cenk-base: this file
loads its lib/profile.py by path from CENK_BASE (set by cenk-base's SessionStart hook for Bash tool commands; the
standard library has a module named profile) and adds only what cenk-jobs needs: the setting form_facts, cenk-jobs as
the default plugin for a setting, a job-search.env PROFILE line of an old install, and move_to_profile.py's backups.

Lookup (cenk-base's, first match wins): CENK_HOME; cenk/profile.json in a Google Drive "My Drive" folder; cenk/ in the
Claude config folder; then old places, read with a note to move: CENK_PROFILE (a PROFILE line in job-search.env counts
as it, when CENK_PROFILE is unset), the workbench setting profile_path, claude/profile.json in "My Drive", then in the
Claude config folder. Set and erase refuse an old place; create copies it to the cenk folder.

python -I profilelib.py [--env <job-search.env>] <command>
  the commands of cenk-base's lib/profile.py: home | path | get <plugin> <key> | get <key> |
  set <key> <json|-> [--old <json>] [--yes] | erase <key> [--yes] | create [<folder>] | pin <folder> [--yes]
  Example: profilelib.py get cenk-jobs form_facts
  After erase it also lists the backups move_to_profile.py --remove-old left, which may still hold the value.
Exit: cenk-base's (0 done, 1 refused, 2 bad arguments, 3 the file holds another value than --old says); 1 when
cenk-base is not found.
"""
import glob
import importlib.util
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jsenv  # noqa: E402

PLUGIN = "cenk-jobs"
# The guarded items a form may answer from the profile only when the person lists them in the setting form_facts
# (settings.cenk-jobs, else settings.common; default none). ID numbers, passwords and card numbers: never.
FORM_FACTS = ("birth_date", "address", "references", "criminal_record", "relatives", "health")
MISSING = ("cenk-base is not loaded (CENK_BASE is not set or has no lib/profile.py): cenk-jobs cannot read the "
           "person's profile. Either cenk-base is not installed or enabled (a plain plugin update does not install "
           "it: run `claude plugin install cenk-jobs@cenk`, or cenk-jobs@<its marketplace>, again), or this session "
           "started before it was (start a new one), or the command ran outside the Bash tool (PowerShell does not "
           "get CENK_BASE: use Git Bash).")


USED = ("ProfileError", "ABSENT", "FORBIDDEN", "same", "text_of", "cloud_note", "move_message", "missing_message",
        "locate", "load", "get", "set_value", "setting", "main")


def load_base():
    """cenk-base's lib/profile.py as a module, or None; a base that fails to load or lacks a name cenk-jobs uses adds
    the cause to MISSING, so check_setup.py still reports it."""
    global MISSING
    folder = os.environ.get("CENK_BASE", "").strip()
    path = os.path.join(folder, "lib", "profile.py") if folder else ""
    if not path or not os.path.isfile(path):
        return None
    try:
        spec = importlib.util.spec_from_file_location("cenk_profile", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        lacking = [name for name in USED if not hasattr(module, name)]
        if lacking:
            raise ImportError(f"no {', '.join(lacking)}: update cenk-base")
    except Exception as problem:  # noqa: BLE001 - any failure means no usable base; the cause is reported
        MISSING = f"{path} cannot be used ({problem}). " + MISSING
        return None
    return module


base = load_base()

if base:
    ProfileError, ABSENT, FORBIDDEN = base.ProfileError, base.ABSENT, base.FORBIDDEN
    same, text_of, cloud_note, move_message = base.same, base.text_of, base.cloud_note, base.move_message
else:
    class ProfileError(Exception):
        def __init__(self, message, code):
            super().__init__(message)
            self.code = code
    ABSENT = object()
    FORBIDDEN = {"__proto__", "constructor", "prototype"}


def need():
    if not base:
        raise ProfileError(MISSING, 1)
    return base


def old_profile_line(env):
    """A PROFILE line in job-search.env (before 0.36.0) is read as cenk-base's old place CENK_PROFILE: found only when
    the cenk folder holds no profile, with a note to move it."""
    if env is not None and env.get("PROFILE") and not os.environ.get("CENK_PROFILE", "").strip():
        os.environ["CENK_PROFILE"] = env.path("PROFILE")


def locate(env=None, **where):
    old_profile_line(env)
    return need().locate(**where)


def load(env=None, **where):
    """cenk-base's load: {home, path, scope, old, suggested, exists, data, error}. Without cenk-base: no profile, and
    missing_message says why."""
    if not base:
        return {"home": None, "path": None, "scope": None, "old": False, "suggested": None, "exists": False,
                "data": {}, "error": None, "no_base": True}
    old_profile_line(env)
    return base.load(**where)


def missing_message(profile):
    return MISSING if profile.get("no_base") else need().missing_message(profile)


def get(key, env=None, **where):
    old_profile_line(env)
    return need().get(key, **where)


def set_value(key, value, old=ABSENT, env=None, yes=False, **where):
    old_profile_line(env)
    return need().set_value(key, value, old, yes, **where)


def setting(profile, key, default=None, plugin=PLUGIN):
    """A setting's raw value: settings.<plugin>, then settings.common, then the default."""
    return need().setting(profile, key, default, plugin) if base else default


def form_facts(profile):
    """(allowed, unknown): the guarded items the setting form_facts lets forms answer, and the names it lists that
    are not guarded items (an ID number never is). A string setting may list them with commas."""
    value = setting(profile, "form_facts", [])
    names = value if isinstance(value, list) else re.split(r"\s*,\s*", str(value).strip())
    names = [str(n).strip() for n in names if str(n).strip()]
    return [n for n in names if n in FORM_FACTS], [n for n in names if n not in FORM_FACTS]


def move_backups(env):
    """The backups move_to_profile.py --remove-old left beside the old records: they may still hold an erased value."""
    if env is None:
        return []
    sources = [env.path("MASTER_RECORD")] if env.get("MASTER_RECORD") else []
    sources.append(env.path("PERSONAL_RECORD") if env.get("PERSONAL_RECORD")
                   else os.path.join(env.home, "career-records", "personal.json"))
    return sorted(p for s in sources for p in glob.glob(glob.escape(s) + ".before-move-*.json"))


def env_of(argv):
    """The job-search.env from --env (removed from argv), else the one jsenv finds, else None."""
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


def main(argv):
    argv = list(argv)
    env = env_of(argv)
    old_profile_line(env)
    need().main(argv)
    if argv[:1] == ["create"] and env is not None and env.get("PROFILE"):
        print(f"Remove the PROFILE line from {env.file} after the person's yes: cenk-jobs no longer reads it, and "
              "CENK_PROFILE above means that line.")
    backups = move_backups(env) if argv[:1] == ["erase"] else []
    if backups:
        print("These backups from move_to_profile.py may still hold the value; after the person's yes, delete them:")
        for backup in backups:
            print(f"  {backup}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    try:
        main(sys.argv[1:])
    except ProfileError as e:
        print(e, file=sys.stderr)
        sys.exit(e.code)
