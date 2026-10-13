#!/usr/bin/env python3
"""Master ticker 2026-06-30 ~12:35 — replace top summary with current status."""
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
    if in_summary and p.text.strip().startswith("202"):
        for run in p.runs:
            run.text = ""
        p.runs[0].text = (
            "2026-06-30 ~12:35 CDT (master ticker): Both in-progress tasks still "
            "blocked on user input (Alt Ancients awaiting Section 1 answers, "
            "Telegram awaiting bot token). Admin queue empty. All builds healthy."
        )
        done = True
        break

if not done:
    print("ERROR: could not find summary bullet")
    exit(1)

d.save(DOC)
print("SAVED")
