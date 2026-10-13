#!/usr/bin/env python3
"""Update the idle tick line timestamp in FBE Current Tasks doc."""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

OLD_TEXT = "[2026-07-03 ~17:14] Humbly reporting: no open tasks, no admin queue entries. All FBE work complete, awaiting your next command."
NEW_TEXT = "[2026-07-03 ~17:30] Humbly reporting: no open tasks, no admin queue entries. All FBE work complete, awaiting your next command."

doc = Document(DOC_PATH)
found = False

for para in doc.paragraphs:
    if "[2026-07-03 ~17:14]" in para.text and "no open tasks" in para.text:
        full = para.text
        new_full = full.replace(OLD_TEXT, NEW_TEXT)
        if full != new_full:
            for i, run in enumerate(para.runs):
                if i == 0:
                    run.text = new_full
                else:
                    run.text = ""
            found = True
            break
        # Try run-level replace
        for run in para.runs:
            if OLD_TEXT in run.text:
                run.text = run.text.replace(OLD_TEXT, NEW_TEXT)
                found = True
                break
        break

if not found:
    print("ERROR: Could not find idle tick line to update", file=sys.stderr)
    sys.exit(1)

doc.save(DOC_PATH)
print("Updated idle tick line timestamp to ~17:30")
