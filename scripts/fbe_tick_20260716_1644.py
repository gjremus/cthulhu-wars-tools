#!/usr/bin/env python3
"""FBE ticker — update the 'nothing happened' summary line timestamp."""
from docx import Document

DOC = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC)

OLD_LINE = "[2026-07-16 ~06:42] Most humbly, deepest apologies: admin queue checked (404 response, no new issues). Working tree clean on homebrew branch. No open or in-progress tasks remain. Your worthless servant grovels abjectly."
NEW_LINE = "[2026-07-16 ~16:44] Most humbly, deepest apologies: admin queue checked (404 response, no new issues). Working tree clean on homebrew branch. No open or in-progress tasks remain. Your worthless servant grovels abjectly."

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
