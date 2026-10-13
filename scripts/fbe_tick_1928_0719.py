#!/usr/bin/env python3
"""FBE ticker 2026-07-19 ~19:28 — no tasks, admin queue inaccessible."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx")

d = docx.Document(DOC)

in_summary = False
inserted = False
for i, p in enumerate(d.paragraphs):
    if "Bulleted summary" in p.text:
        in_summary = True
        continue
    if in_summary and p.text.strip().startswith("[2026-07-19") and not inserted:
        # Check if this is the most recent tick (should be ~19:12)
        if "~19:12" in p.text or ("~19:" in p.text and "admin queue" in p.text):
            # Update the existing timestamp instead of creating a new one
            for run in p.runs:
                run.text = ""
            p.runs[0].text = ("[2026-07-19 ~19:28] Most humbly, deepest apologies: "
                              "admin queue remains inaccessible (token file locked by Google Drive). "
                              "No open or in-progress FBE tasks remain. "
                              "Your worthless servant grovels abjectly.")
            print("OK: updated existing nothing-happened summary timestamp")
            inserted = True
            break
        else:
            print(f"SKIPPED: top summary doesn't match expected: {p.text[:100]}")
            exit(1)

if not inserted:
    print("ERROR: could not find matching summary bullet to update")
    exit(1)

d.save(DOC)
print("SAVED")
