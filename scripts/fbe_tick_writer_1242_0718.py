#!/usr/bin/env python3
"""FBE ticker 2026-07-18 ~12:42 — update nothing-happened summary timestamp."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx")

d = docx.Document(DOC)

in_summary = False
found_existing = False

for p in d.paragraphs:
    if "Bulleted summary" in p.text:
        in_summary = True
        continue
    if in_summary and p.text.strip().startswith("[2026-07-18"):
        old_text = p.text.strip()
        if "~12:25" in old_text and "admin queue inaccessible" in old_text:
            # Update existing nothing-happened bullet
            for run in p.runs:
                run.text = ""
            p.runs[0].text = ("[2026-07-18 ~12:42] Most humbly, deepest apologies: "
                              "admin queue inaccessible (token file locked). "
                              "No open or in-progress FBE tasks remain. Your worthless servant grovels abjectly.")
            print("OK: updated nothing-happened summary bullet timestamp")
            found_existing = True
            break

if not found_existing:
    print("ERROR: could not find matching bullet to update")
    exit(1)

d.save(DOC)
print("SAVED")
