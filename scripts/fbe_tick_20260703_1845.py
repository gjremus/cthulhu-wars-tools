#!/usr/bin/env python3
"""
FBE tick writer — 2026-07-03 ~18:45
Task: Update the existing "nothing happened" tick summary timestamp.
No open tasks, no admin queue entries. Rule 30: update existing bullet.
"""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

TARGET_PREFIX = "[2026-07-03 ~18:15] Humbly reporting: no open tasks"
found = False
for i, p in enumerate(paras):
    if p.text.strip().startswith(TARGET_PREFIX):
        for run in p.runs:
            if "[2026-07-03 ~18:15]" in run.text:
                run.text = run.text.replace("[2026-07-03 ~18:15]", "[2026-07-03 ~18:45]")
                found = True
                break
        if not found:
            old_text = p.text
            new_text = old_text.replace("[2026-07-03 ~18:15]", "[2026-07-03 ~18:45]")
            if old_text != new_text:
                for run in p.runs:
                    run.text = ""
                if p.runs:
                    p.runs[0].text = new_text
                found = True
        break

if not found:
    print("ERROR: could not find the ~18:15 'nothing happened' bullet to update")
    sys.exit(1)

print("Updated timestamp from ~18:15 to ~18:45 on the existing idle bullet")
doc.save(DOC_PATH)
print("DONE: saved successfully")
