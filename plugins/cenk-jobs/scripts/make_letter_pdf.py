"""Render one tailored cover letter to PDF with headless Chrome, for upload to a job application form.

Usage: python -I make_letter_pdf.py [--env <job-search.env>] --company "Acme" --role "Engineering Manager"
           --body body.txt [--variant "<CV variant>" | --title "<headline>"] [--out-dir <folder>]
The body file holds the letter's paragraphs (UTF-8, blank line between paragraphs), from "Dear ..." to the sign-off
line, without the signature block. Prints the absolute path of the PDF it wrote.
The name, contact line and output folder come from job-search.env (NAME_ON_CV, CONTACT_LINE, PERSON_NAME,
LETTERS_DIR, CHROME), so the script is the same for every person. The date is today's: build the PDF on the day it is
sent.
The headline under the name: --title, else the title of the CV version named by --variant (match the CV sent with the
letter: "Backend Lead", "2 Backend Lead.json" or "<First>-<Last>-CV-Backend-Lead.pdf"), else LETTER_TITLE.
A relative --out-dir or --body is taken from the main folder (JOB_SEARCH_HOME), like every path in job-search.env.
Chrome writes the PDF into a temporary folder first; it is then copied over the target and checked there, and the
script fails (exit 1) when the target was not rewritten, so an older file with the same name never passes as new.
"""
import argparse
import datetime
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jsenv  # noqa: E402  (jsenv.py sits next to this script)

_ARGS = sys.argv[1:]
ENV = jsenv.load(_ARGS[_ARGS.index('--env') + 1] if '--env' in _ARGS else None, __file__)
PERSON = ENV['PERSON_NAME']
FILE_PREFIX = ENV.file_prefix()

CHROME = ENV.get('CHROME') or r'C:\Program Files\Google\Chrome\Application\chrome.exe'
OUT_DIR = ENV.path('LETTERS_DIR')

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
@page {{ size: A4; margin: 22mm 20mm; }}
body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #0b2334; font-size: 10.8pt; line-height: 1.45; }}
h1 {{ font-size: 22pt; margin: 0; letter-spacing: .5px; }}
.title {{ font-weight: 600; margin: 2px 0 2px; }}
.contact {{ font-size: 9.6pt; color: #33475b; margin-bottom: 18px; border-bottom: 2px solid #1d6b81; padding-bottom: 8px; }}
.meta {{ margin-bottom: 14px; }}
p {{ margin: 0 0 10px; text-align: left; }}
.sign {{ margin-top: 16px; }}
</style></head><body>
<h1>{name_on_cv}</h1>
<div class="title">{title}</div>
<div class="contact">{contact}</div>
<div class="meta">{date}<br>{company}<br>Re: {role}</div>
{body}
<div class="sign">{person}</div>
</body></html>"""


def from_home(path):
    return os.path.normpath(path if os.path.isabs(path) else os.path.join(ENV.home, path))


def variant_title(variant):
    """The 'title' of the CV version whose file or variant name matches (e.g. 'Backend Lead')."""
    def key(text):
        text = os.path.splitext(os.path.basename(text))[0]
        text = text.split('-CV-', 1)[-1]                      # <First>-<Last>-CV-<Variant>.pdf
        text = re.sub(r'^\d+\s+', '', text)                   # <n> <Variant>.json
        return re.sub(r'[\s_-]+', ' ', text).strip().lower()
    folder = ENV.path('CV_VERSIONS_DIR')
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if name.endswith('.json') and name[0].isdigit() and key(name) == key(variant):
            with open(os.path.join(folder, name), encoding='utf-8') as f:
                return json.load(f).get('title', '')
    raise SystemExit(f'No CV version matches --variant {variant!r} in {folder}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--company', required=True)
    ap.add_argument('--role', required=True)
    ap.add_argument('--body', required=True)
    ap.add_argument('--env', default=None)  # read above, before the page is built
    # The headline under the name; match it to the CV variant sent with the letter.
    ap.add_argument('--title', default=None)
    ap.add_argument('--variant', default=None)
    # One folder per job keeps the upload's file name clean when a company has several openings.
    ap.add_argument('--out-dir', default=OUT_DIR)
    a = ap.parse_args()
    title = a.title if a.title is not None else (variant_title(a.variant) if a.variant else ENV.get('LETTER_TITLE', ''))
    with open(from_home(a.body), encoding='utf-8') as f:
        text = f.read().strip()
    paras = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    body = '\n'.join('<p>' + html.escape(p).replace('\n', '<br>') + '</p>' for p in paras)
    page = PAGE.format(date=datetime.date.today().strftime('%d %B %Y'), title=html.escape(title), company=html.escape(a.company),
                       role=html.escape(a.role), body=body, name_on_cv=html.escape(ENV['NAME_ON_CV']),
                       contact=html.escape(ENV['CONTACT_LINE']), person=html.escape(PERSON))
    out_dir = from_home(a.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    slug = re.sub(r'[^A-Za-z0-9]+', '-', a.company).strip('-')[:40] or 'Company'
    out = os.path.join(out_dir, FILE_PREFIX + '-Cover-Letter-' + slug + '.pdf')
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, 'letter.html')
        made = os.path.join(tmp, 'letter.pdf')
        with open(src, 'w', encoding='utf-8') as f:
            f.write(page)
        # Chrome gets an absolute path in its own temp folder: a relative one is resolved from Chrome's working
        # folder, not ours, so the PDF could land elsewhere while an old file at the target looked fine.
        subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--no-first-run', '--user-data-dir=' + os.path.join(tmp, 'p'),
                        '--no-pdf-header-footer', '--print-to-pdf=' + made, 'file:///' + src.replace('\\', '/')],
                       check=True, timeout=120, capture_output=True)
        with open(made, 'rb') if os.path.isfile(made) else open(os.devnull, 'rb') as f:
            printed = f.read()
        if printed[:4] != b'%PDF':
            raise SystemExit('Chrome did not print the letter; nothing was written to ' + out)
        shutil.copyfile(made, out)
    with open(out, 'rb') as f:
        if hashlib.sha256(f.read()).digest() != hashlib.sha256(printed).digest():
            raise SystemExit('The PDF was not written to ' + out + ' (the file there is not the one just printed)')
    print(out)


if __name__ == '__main__':
    main()
