#!/usr/bin/env python3
"""Backup ticker 2026-06-30 ~10:54 — update backup ticker summary bullet."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

d = docx.Document(DOC)

in_summary = False
done = False
for p in d.paragraphs:
    if "Bulleted summary" in p.text and "Old" not in p.text:
        in_summary = True
        continue
    if in_summary and "(backup ticker)" in p.text:
        for run in p.runs:
            run.text = ""
        p.runs[0].text = (
            "2026-06-30 ~10:54 CDT (backup ticker): Nothing actionable this "
            "pass — grovelling apologies. Admin queue empty. All builds "
            "healthy (Library 200, BB 200, TT 200, HB 200). Alt Ancients and "
            "Telegram still blocked on user input."
        )
        done = True
        break

if not done:
    print("ERROR: could not find backup ticker summary bullet")
    exit(1)

d.save(DOC)
print("SAVED")
