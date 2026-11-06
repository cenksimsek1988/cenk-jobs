"""Read job-search.env, the one file that says where a person's job search keeps everything.

Every job-search script finds its folders and files through this module, so the scripts are generic and only the
env file holds one person's names and paths.

Format: KEY=value lines; '#' starts a comment line; values are not quoted. JOB_SEARCH_HOME is the main folder;
every *_DIR / file value is relative to it unless it is absolute.
Lookup order: an explicit path, then $JOB_SEARCH_ENV, then the first job-search.env found walking up from the
current folder, then walking up from the calling script's folder.

    import jsenv
    env = jsenv.load()                  # or jsenv.load("<path to job-search.env>")
    master = env.path("MASTER_RECORD")
"""
import os

ENV_NAME = "job-search.env"


def _walk_up(folder):
    folder = os.path.abspath(folder)
    while True:
        candidate = os.path.join(folder, ENV_NAME)
        if os.path.exists(candidate):
            return candidate
        parent = os.path.dirname(folder)
        if parent == folder:
            return None
        folder = parent


def find(explicit=None, script=None):
    """The job-search.env to use (see the lookup order above)."""
    if explicit:
        path = os.path.abspath(explicit)
        return os.path.join(path, ENV_NAME) if os.path.isdir(path) else path
    if os.environ.get("JOB_SEARCH_ENV"):
        return os.path.abspath(os.environ["JOB_SEARCH_ENV"])
    found = _walk_up(os.getcwd()) or (script and _walk_up(os.path.dirname(os.path.abspath(script))))
    if not found:
        raise SystemExit(f"No {ENV_NAME} found: pass its path, set JOB_SEARCH_ENV, or run from the main folder "
                         "(create one with init_career_folder.py)")
    return found


class Env(dict):
    def __init__(self, file):
        super().__init__()
        self.file = file
        with open(file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    self[key.strip()] = value.strip()
        # The main folder defaults to the env file's own folder, so a moved folder keeps working.
        self.home = os.path.abspath(self.get("JOB_SEARCH_HOME") or os.path.dirname(file))

    def path(self, key, *more):
        """The absolute path for a key (relative values are taken from JOB_SEARCH_HOME)."""
        value = self.get(key)
        if not value:
            raise SystemExit(f"{key} is not set in {self.file}")
        base = value if os.path.isabs(value) else os.path.join(self.home, value)
        return os.path.normpath(os.path.join(base, *more))

    def file_prefix(self):
        """'<First>-<Last>' in ASCII from PERSON_NAME, for upload-safe file names."""
        return "-".join(w.capitalize() for w in self.get("PERSON_NAME", "Candidate").translate(ASCII).split())


ASCII = str.maketrans("ŞşİıĞğÜüÖöÇçÀàÁáÂâÈèÉéÊêÌìÍíÎîÒòÓóÔôÙùÚúÛûÑñÄäËëÏïßÅåØøÆæŁłŃńŚśŹźŻżĆćĘęĄą",
                      "SsIiGgUuOoCcAaAaAaEeEeEeIiIiIiOoOoOoUuUuUuNnAaEeIisAaOoAaLlNnSsZzZzCcEeAa")


def load(explicit=None, script=None):
    return Env(find(explicit, script))
