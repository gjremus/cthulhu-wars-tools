#!/usr/bin/env python3
"""Master ticker 2026-06-30 ~13:12 — update nothing-actionable timestamp in old summaries."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

d = docx.Document(DOC)

done = False
for p in d.paragraphs:
    if "Nothing actionable" in p.text and "in-progress tasks blocked" in p.text:
        for run in p.runs:
            run.text = ""
        p.runs[0].text = (
            "2026-06-30 ~13:12 CDT (master ticker): Nothing actionable — all 3 "
            "in-progress tasks blocked on user input (Alt Ancients awaiting Section 1 "
            "answers, Telegram awaiting bot token, BB game 540 awaiting user decision). "
            "Admin queue empty. All builds healthy."
        )
        done = True
        break

if not done:
    print("ERROR: could not find the nothing-actionable bullet")
    exit(1)

d.save(DOC)
print("SAVED")
