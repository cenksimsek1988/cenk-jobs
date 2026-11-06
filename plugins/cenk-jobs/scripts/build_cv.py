"""Build the person's CV PDFs from their CV-version files.

Each "<n> <Variant>.json" in CV_VERSIONS_DIR is one CV version (all its text; see templates/cv-version-example.json).
This script turns each one into an HTML page and prints it to PDF with headless Chrome, into CVS_DIR:
"<First>-<Last>-CV-<Variant>.pdf". Chrome runs with its own temporary profile, so it never touches the user's browser.

Run:  python -I build_cv.py [--env <job-search.env>] [--no-photo] ["<n> <Variant>.json" ...]
      no names -> every version; --no-photo -> copies named "...-no-photo.pdf" for employers that ask for no photo.
Why HTML + Chrome: exact layout control, real text in the PDF for applicant-tracking systems, and the content stays in
small JSON files the person (or Claude) edits; never edit a PDF.
"""
import base64
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jsenv  # noqa: E402  (jsenv.py sits next to this script)

CONSENT = ("I authorise the processing of my personal data in accordance with Regulation (EU) 2016/679 (GDPR) "
           "for recruitment purposes.")

CSS = """
@page { size: A4; margin: 10mm 13mm 9mm 13mm; }
* { box-sizing: border-box; }
body { font-family: "Segoe UI", Arial, sans-serif; font-size: 8.9pt; line-height: 1.27; color: #23272e; margin: 0; }
header { display: flex; justify-content: space-between; align-items: center; gap: 14px; margin-bottom: 4px; }
.name { font-size: 22pt; font-weight: 700; color: #0f2f4f; letter-spacing: 0.5px; line-height: 1.1; }
.title { font-size: 12pt; font-weight: 700; color: #0f2f4f; margin-top: 2px; }
.keywords { font-size: 9.6pt; color: #3d4652; margin: 3px 0 5px; }
.contact { font-size: 8.6pt; color: #3d4652; line-height: 1.38; }
.contact a { color: #3d4652; text-decoration: none; }
.photo { width: 92px; height: 92px; border-radius: 50%; object-fit: cover; border: 2px solid #1d6b81; flex: none; }
h2 { font-size: 10pt; color: #0f2f4f; text-transform: uppercase; letter-spacing: 0.6px; margin: 7px 0 3px;
     padding-bottom: 2px; border-bottom: 1.2px solid #0f2f4f; break-after: avoid; }
p { margin: 0 0 3px; }
.job { font-weight: 700; color: #0f2f4f; font-size: 10pt; }
.role { font-weight: 700; }
.group { margin-top: 4px; break-inside: avoid; }
.group-title { font-weight: 700; color: #0f2f4f; font-size: 9pt; text-transform: uppercase; letter-spacing: 0.4px; }
ul { margin: 1px 0 0 0; padding-left: 14px; }
li { margin: 0 0 1px; }
.entry { margin-top: 4px; break-inside: avoid; }
.entry b { color: #1b2430; }
.skills p { margin-bottom: 2.5px; }
.consent { font-size: 7.6pt; color: #5a626c; margin-top: 10px; }
"""


def esc(text):
    return html.escape(text or "", quote=False)


def build_html(data, photo_path, footer):
    photo = base64.b64encode(open(photo_path, "rb").read()).decode() if photo_path else None
    contact = []
    for line in data["contact"]:
        if line.startswith("linkedin.com/"):
            contact.append(f'<a href="https://www.{esc(line)}/">{esc(line)}</a>')
        else:
            contact.append(esc(line))
    out = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{esc(data['name'])} – CV – "
           f"{esc(data['title'])}</title><style>{CSS}</style></head><body>"]
    out.append("<header><div>")
    out.append(f"<div class='name'>{esc(data['name'])}</div><div class='title'>{esc(data['title'])}</div>")
    if data.get("keywords"):
        out.append(f"<div class='keywords'>{esc(data['keywords'])}</div>")
    out.append("<div class='contact'>" + "<br>".join(contact) + "</div></div>")
    out.append((f"<img class='photo' src='data:image/jpeg;base64,{photo}' alt='{esc(data['name'].title())}'>" if photo else "")
               + "</header>")
    out.append(f"<h2>Summary</h2><p>{esc(data['summary'])}</p>")

    out.append("<h2>Experience</h2>")
    jobs = data.get("jobs") or ([data["main_job"]] if data.get("main_job") else [])
    for job in jobs:
        out.append(f"<div class='job'>{esc(job['heading'])}</div>")
        for role in job.get("roles", []):
            out.append(f"<div class='role'>{esc(role)}</div>")
        if job.get("product"):
            out.append(f"<p style='margin-top:3px'>{esc(job['product'])}</p>")
        for group in job.get("groups", []):
            out.append(f"<div class='group'><div class='group-title'>{esc(group['title'])}</div><ul>")
            out.extend(f"<li>{esc(item)}</li>" for item in group["items"])
            out.append("</ul></div>")
    for item in data.get("other_jobs", []):
        head = f"<b>{esc(item['heading'])}</b><br>" if item.get("heading") else ""
        out.append(f"<div class='entry'>{head}{esc(item['text'])}</div>")

    if data.get("skills"):
        out.append("<h2>Skills</h2><div class='skills'>")
        out.extend(f"<p><b>{esc(label)}:</b> {esc(text)}</p>" for label, text in data["skills"])
        out.append("</div>")
    out.append("<h2>Education</h2>")
    out.extend(f"<p>{esc(line)}</p>" for line in data["education"])
    if data.get("certificates"):
        out.append("<h2>Courses &amp; certificates</h2>")
        out.extend(f"<p>{esc(line)}</p>" for line in data["certificates"])
    if data.get("volunteering"):
        out.append("<h2>Volunteering</h2>")
        for item in data["volunteering"]:
            out.append(f"<div class='entry'><b>{esc(item['heading'])}</b><br>{esc(item['text'])}</div>")
    if data.get("interests"):
        out.append(f"<h2>Interests</h2><p>{esc(data['interests'])}</p>")
    if footer:
        out.append(f"<div class='consent'>{esc(footer)}</div>")
    out.append("</body></html>")
    return "".join(out)


def pdf_name(json_name, person):
    """'<First>-<Last>-CV-<Variant>.pdf' in ASCII, e.g. Jane-Doe-CV-Backend-Lead.pdf (upload-safe file names)."""
    variant = os.path.splitext(json_name)[0].split(" ", 1)[1]
    who = "-".join(w.capitalize() for w in person.translate(jsenv.ASCII).split())
    return f"{who}-CV-" + variant.replace(" ", "-") + ".pdf"


def build(env, json_path, with_photo=True):
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    photo = env.path("PHOTO") if with_photo and env.get("PHOTO") and os.path.exists(env.path("PHOTO")) else None
    footer = env.get("CV_FOOTER", CONSENT)
    work = tempfile.mkdtemp(prefix="cv_build_")
    page = os.path.join(work, "cv.html")
    with open(page, "w", encoding="utf-8") as f:
        f.write(build_html(data, photo, footer))
    name = pdf_name(os.path.basename(json_path), data["name"])
    out = env.path("CVS_DIR", name if with_photo else name.replace(".pdf", "-no-photo.pdf"))
    chrome = env.get("CHROME") or r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    # Chrome prints into the temp folder and the PDF is then copied over the target and checked there, so an older
    # file with the same name never passes as the new one.
    made = os.path.join(work, "cv.pdf")
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-pdf-header-footer",
                    f"--user-data-dir={os.path.join(work, 'profile')}", f"--print-to-pdf={made}",
                    "file:///" + page.replace("\\", "/")], check=True, timeout=120,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    printed = open(made, "rb").read() if os.path.isfile(made) else b""
    if printed[:4] != b"%PDF":
        raise SystemExit(f"Chrome did not print {os.path.basename(json_path)}; nothing was written to {out}")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    shutil.copyfile(made, out)
    if open(out, "rb").read() != printed:
        raise SystemExit(f"The PDF was not written to {out} (the file there is not the one just printed)")
    shutil.rmtree(work, ignore_errors=True)
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    env_arg = args[args.index("--env") + 1] if "--env" in args else None
    names = [a for i, a in enumerate(args) if a not in ("--no-photo", "--env") and (i == 0 or args[i - 1] != "--env")]
    env = jsenv.load(env_arg, __file__)
    versions = env.path("CV_VERSIONS_DIR")
    names = names or sorted(n for n in os.listdir(versions) if n.endswith(".json") and n[0].isdigit())
    for name in names:
        print("built", build(env, os.path.join(versions, os.path.basename(name)), "--no-photo" not in args))
