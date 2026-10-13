#!/usr/bin/env python3
"""
FBE tick writer — 2026-07-03 ~18:15
Task: No open tasks, admin queue empty. Per Rule 30, update existing
"nothing happened" tick line timestamp rather than creating a new one.
"""
import sys
from docx import Document
from docx.oxml.ns import qn

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

OLD_TICK_PREFIX = "[2026-07-03 ~17:59] Humbly reporting: no open tasks"
NEW_TICK_LINE = "[2026-07-03 ~18:15] Humbly reporting: no open tasks, no admin queue entries. All FBE work complete, awaiting your next command."

found = False
for i, p in enumerate(paras):
    if p.text.strip().startswith(OLD_TICK_PREFIX):
        for r in p.runs:
            r.text = ""
        p.runs[0].text = NEW_TICK_LINE
        found = True
        print(f"Updated tick line at paragraph {i}")
        break

if not found:
    print("ERROR: could not find the existing 'no open tasks' tick line to update")
    sys.exit(1)

doc.save(DOC_PATH)
print("DOC SAVED.")
