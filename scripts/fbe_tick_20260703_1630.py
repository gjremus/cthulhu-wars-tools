#!/usr/bin/env python3
"""
FBE tick writer — 2026-07-03 ~16:30
Task: No open tasks, admin queue empty. Per Rule 30, update the existing
idle tick line timestamp instead of creating a new one.
"""
import sys
from docx import Document
from docx.oxml.ns import qn

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

# Find the idle tick line to update
TARGET_TEXT = "[2026-07-03 ~21:15] Humbly reporting: no open tasks, no admin queue entries. All FBE work complete, awaiting your next command."
NEW_TEXT = "[2026-07-03 ~16:30] Humbly reporting: no open tasks, no admin queue entries. All FBE work complete, awaiting your next command."

found = False
for i, p in enumerate(paras):
    if p.text.strip() == TARGET_TEXT:
        # Update the text in the run(s)
        runs = p.runs
        if runs:
            runs[0].text = NEW_TEXT
            for r in runs[1:]:
                r.text = ""
        else:
            # Fallback: manipulate XML directly
            for r in p._element.findall(qn('w:r')):
                for t in r.findall(qn('w:t')):
                    t.text = ""
            first_r = p._element.findall(qn('w:r'))
            if first_r:
                t_elem = first_r[0].find(qn('w:t'))
                if t_elem is not None:
                    t_elem.text = NEW_TEXT
        found = True
        print(f"Updated idle tick line at paragraph {i}")
        break

if not found:
    print("WARNING: Could not find the idle tick line to update. Skipping write.")
    sys.exit(1)

doc.save(DOC_PATH)
print("DOC SAVED.")
