#!/usr/bin/env python3
"""FBE ticker 2026-07-19 ~00:43 — update nothing-happened summary timestamp."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx")

d = docx.Document(DOC)

in_summary = False
for p in d.paragraphs:
    if "Bulleted summary" in p.text:
        in_summary = True
        continue
    if in_summary and p.text.strip().startswith("[2026-07-19"):
        old_text = p.text.strip()
        if "~00:28" in old_text and "No open or in-progress" in old_text:
            for run in p.runs:
                run.text = ""
            p.runs[0].text = ("[2026-07-19 ~00:43] Most humbly, deepest apologies: "
                              "admin queue inaccessible (token file locked). "
                              "No open or in-progress FBE tasks remain. "
                              "Your worthless servant grovels abjectly.")
            print("OK: updated nothing-happened summary bullet timestamp")
            break
        else:
            print(f"SKIPPED: top summary doesn't match expected: {old_text[:100]}")
            exit(1)
else:
    print("ERROR: could not find summary section or matching bullet")
    exit(1)

d.save(DOC)
print("SAVED")
