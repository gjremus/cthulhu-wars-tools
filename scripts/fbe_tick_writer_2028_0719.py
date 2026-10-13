#!/usr/bin/env python3
"""FBE ticker 2026-07-19 ~20:28 — update nothing-happened summary timestamp."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx")

d = docx.Document(DOC)

# Update the top tick line AND the header tick line
TICK_TEXT = ("[2026-07-19 ~20:28] Most humbly, deepest apologies: "
            "admin queue inaccessible (token file locked by Google Drive). "
            "No open or in-progress FBE tasks remain. "
            "Your worthless servant grovels abjectly.")

# Update header (first tick line at top of doc, before RULES section)
header_updated = False
for p in d.paragraphs:
    if p.text.strip().startswith("[2026-07-19 ~20:12]") and "No open or in-progress" in p.text:
        for run in p.runs:
            run.text = ""
        p.runs[0].text = TICK_TEXT
        if not header_updated:
            header_updated = True
            print("OK: updated header tick line")
        else:
            print("OK: updated summary tick line")
        break

# Update the bulleted summary top entry
in_summary = False
for p in d.paragraphs:
    if "Bulleted summary" in p.text:
        in_summary = True
        continue
    if in_summary and p.text.strip().startswith("[2026-07-19 ~20:12]"):
        for run in p.runs:
            run.text = ""
        p.runs[0].text = TICK_TEXT
        print("OK: updated summary bullet")
        break

d.save(DOC)
print("SAVED")
