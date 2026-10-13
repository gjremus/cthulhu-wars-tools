#!/usr/bin/env python3
"""FBE ticker 2026-07-17 ~22:45 — update nothing-happened summary timestamp."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx")

d = docx.Document(DOC)

in_summary = False
for p in d.paragraphs:
    if "Bulleted summary" in p.text:
        in_summary = True
        continue
    if in_summary and p.text.strip().startswith("[2026-07-17"):
        old_text = p.text.strip()
        # Update the 07-17 timestamp
        for run in p.runs:
            run.text = ""
        p.runs[0].text = ("[2026-07-17 ~22:45] Most humbly, deepest apologies: "
                          "admin queue could not be checked (token file still locked by Google Drive). "
                          "No open or in-progress FBE tasks remain. "
                          "Your worthless servant grovels abjectly.")
        print("OK: updated nothing-happened summary bullet timestamp from", old_text[:25], "to 22:45")
        break
else:
    print("ERROR: could not find summary section or matching bullet")
    exit(1)

d.save(DOC)
print("SAVED")
