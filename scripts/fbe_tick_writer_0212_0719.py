#!/usr/bin/env python3
"""FBE ticker 2026-07-19 ~02:12 — update FBE ticker summary bullet."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/"
       "Faceless Blight Current Tasks (1).docx")

d = docx.Document(DOC)

in_summary = False
done = False
for p in d.paragraphs:
    if "Bulleted summary" in p.text:
        in_summary = True
        continue
    if in_summary and "[2026-07-19" in p.text and "admin queue inaccessible" in p.text:
        # Update the existing "nothing happened" bullet
        for run in p.runs:
            run.text = ""
        p.runs[0].text = (
            "[2026-07-19 ~02:12] Most humbly, deepest apologies: admin queue "
            "inaccessible (token file locked). No open or in-progress FBE tasks "
            "remain. Your worthless servant grovels abjectly."
        )
        done = True
        break

if not done:
    print("ERROR: could not find FBE ticker summary bullet to update")
    exit(1)

d.save(DOC)
print("SAVED")
