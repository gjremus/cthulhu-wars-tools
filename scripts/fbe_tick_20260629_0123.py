#!/usr/bin/env python3
"""FBE ticker — update the 'nothing happened' summary line timestamp."""
from docx import Document

DOC = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC)

OLD_LINE = "[2026-06-29 ~00:31] No new tasks or admin prompts this tick. All FBE tasks remain complete — awaiting creator testing."
NEW_LINE = "[2026-06-29 ~01:23] No new tasks or admin prompts this tick. All FBE tasks remain complete — humbly awaiting creator testing."

found = False
for para in doc.paragraphs:
    if para.text.strip() == OLD_LINE:
        for run in para.runs:
            run.text = ""
        para.runs[0].text = NEW_LINE
        found = True
        break

if not found:
    raise RuntimeError("Could not find the tick summary line to update")

doc.save(DOC)
print("Updated tick summary timestamp.")
