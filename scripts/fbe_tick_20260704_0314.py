#!/usr/bin/env python3
"""
FBE tick writer — 2026-07-04 ~03:14
Task: Update existing "nothing happened" tick line timestamp (Rule 30).
Only one in-progress task (deploy fix), still awaiting permission.
"""
import sys
from docx import Document
from docx.oxml.ns import qn

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

OLD_TEXT_START = "[2026-07-04 ~02:55]"
NEW_TEXT = "[2026-07-04 ~03:14] Most humbly: tick confirmed build compiles clean, admin queue drained (empty). Still awaiting your gracious permission to commit and deploy the Animated Rush legacy replay fix (games 530, 534)."

found = False
for i, p in enumerate(paras):
    if p.text.strip().startswith(OLD_TEXT_START):
        for r in p.runs:
            r.text = ""
        p.runs[0].text = NEW_TEXT
        found = True
        print(f"Updated tick line at paragraph {i}")
        break

if not found:
    print("ERROR: could not find the 02:55 tick line to update")
    sys.exit(1)

doc.save(DOC_PATH)
print("DOC SAVED.")
