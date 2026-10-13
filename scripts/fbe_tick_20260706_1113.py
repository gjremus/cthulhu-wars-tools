#!/usr/bin/env python3
"""FBE tick update 2026-07-06 ~11:13:
Update the existing 'nothing changed' tick line timestamp (Rule 30).
"""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

OLD_FRAGMENT = "2026-07-06 ~14:38"
NEW_TICK = "[2026-07-06 ~11:13] Most humbly: all tasks complete and confirmed. Admin queue still unreachable (endpoint 404), server healthy. No open tasks remain."

edited = False
for para in paras:
    if OLD_FRAGMENT in para.text:
        for run in para.runs:
            run.text = ""
        if para.runs:
            para.runs[0].text = NEW_TICK
        edited = True
        print("Updated tick line timestamp: OK")
        break

if not edited:
    print(f"ERROR: Could not find tick line with '{OLD_FRAGMENT}'", file=sys.stderr)
    sys.exit(1)

doc.save(DOC_PATH)
print("Done: tick line updated.")
