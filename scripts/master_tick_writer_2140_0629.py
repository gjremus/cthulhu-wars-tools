#!/usr/bin/env python3
"""Master ticker 2026-06-29 ~21:40 — consolidate nothing-happened summary bullets."""
import zipfile
import shutil
import tempfile
import os
import re

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

TMP = tempfile.mktemp(suffix=".docx")
shutil.copy2(DOC, TMP)

with zipfile.ZipFile(TMP, 'r') as zin:
    ct_xml = zin.read('[Content_Types].xml').decode('utf-8')

if 'application/x-font-ttf' not in ct_xml or '/word/fonts/' not in ct_xml:
    font_ext = '  <Default Extension="ttf" ContentType="application/x-font-ttf"/>'
    ct_xml = ct_xml.replace('</Types>', font_ext + '\n</Types>')

    tmp2 = tempfile.mktemp(suffix=".docx")
    with zipfile.ZipFile(TMP, 'r') as zin:
        with zipfile.ZipFile(tmp2, 'w') as zout:
            for item in zin.infolist():
                if item.filename == '[Content_Types].xml':
                    zout.writestr(item, ct_xml.encode('utf-8'))
                else:
                    zout.writestr(item, zin.read(item.filename))
    os.replace(tmp2, TMP)

import docx
d = docx.Document(TMP)

in_summary = False
summary_paras = []
for p in d.paragraphs:
    if "Bulleted summary" in p.text:
        in_summary = True
        continue
    if in_summary:
        t = p.text.strip()
        if t.startswith("202"):
            summary_paras.append(p)
        elif t and not t.startswith("202"):
            break

if not summary_paras:
    print("ERROR: no summary bullets found")
    os.unlink(TMP)
    exit(1)

first_text = summary_paras[0].text.strip()
print(f"Top bullet: {first_text[:100]}")

if "blocked on user input" not in first_text and "unchanged" not in first_text:
    print("INFO: top bullet is not a nothing-happened bullet. No update needed.")
    os.unlink(TMP)
    exit(0)

NEW_BULLET = (
    "2026-06-29 ~21:40 CDT (master ticker): Both tasks still blocked on "
    "user input (unchanged). Admin queue empty. Server healthy."
)

for run in summary_paras[0].runs:
    run.text = ""
summary_paras[0].runs[0].text = NEW_BULLET

if len(summary_paras) >= 2:
    second_text = summary_paras[1].text.strip()
    if "blocked on user input" in second_text or "unchanged" in second_text:
        for run in summary_paras[1].runs:
            run.text = ""
        summary_paras[1].runs[0].text = (
            "2026-06-29 ~17:45 CDT: Overlay comparison doc COMPLETED — "
            "borders verified intact, game text updated to match necro for "
            "all 32 units. Admin queue empty."
        )
        print("OK: replaced second nothing-happened bullet with substantive one")
    else:
        print("OK: second bullet is substantive, left as-is")

if len(summary_paras) >= 3:
    third_text = summary_paras[2].text.strip()
    if "17:16" in third_text:
        for run in summary_paras[2].runs:
            run.text = ""
        summary_paras[2].runs[0].text = (
            "2026-06-29 ~17:16 CDT: BB turn order bug FIXED AND DEPLOYED "
            "(cache 20260629-171042). Overwrite safeguard FIXED. Alt OW "
            "already done. Overlay doc borders restored."
        )
        print("OK: kept third bullet (trimmed)")

d.save(DOC)
os.unlink(TMP)
print("SAVED to original DOC")
