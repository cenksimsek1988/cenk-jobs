"""Build the uploadable cenk-jobs.plugin file from the committed plugin.

Usage: python -I release.py ["<output folder>"]      (default: dist/ in this repository, which git ignores)
Writes <output folder>/cenk-jobs.plugin: the plugin folder as a zip with .claude-plugin/plugin.json at its top, the
file a person uploads (or drops into a chat) in the Claude desktop app to install the plugin without a marketplace.
Only files committed at HEAD go in, never a half-finished edit.
This repository (pushed to GitHub) is the only copy of the plugin: people install it with
`/plugin marketplace add cenksimsek1988/cenk-jobs`; the .plugin file is built on demand and kept nowhere else.
"""
import io
import os
import subprocess
import sys
import zipfile

REPO = os.path.dirname(os.path.abspath(__file__))
PLUGIN = "plugins/cenk-jobs/"
target = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "dist"))
dirty = subprocess.run(["git", "-C", REPO, "status", "--porcelain"], capture_output=True, text=True, check=True).stdout
if dirty.strip():
    print("Note: uncommitted changes are NOT in the file:\n" + dirty)
head = subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
files = subprocess.run(["git", "-C", REPO, "ls-files", "-z"], capture_output=True, text=True, check=True).stdout.split("\0")
files = sorted(f for f in files if f.startswith(PLUGIN))


def committed(rel):
    return subprocess.run(["git", "-C", REPO, "show", f"HEAD:{rel}"], capture_output=True, check=True).stdout


buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
    for rel in files:
        z.writestr(rel[len(PLUGIN):], committed(rel))
os.makedirs(target, exist_ok=True)
out = os.path.join(target, "cenk-jobs.plugin")
with open(out, "wb") as f:
    f.write(buf.getvalue())
print(f"Built {out} from commit {head}: {len(files)} files, {len(buf.getvalue()) // 1024} KB.")
