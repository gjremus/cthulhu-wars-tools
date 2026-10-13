#!/usr/bin/env python3
"""
FBE tick writer — 2026-07-03 ~17:43
Task: Update the "nothing happened" tick bullet timestamp from ~17:30 to ~17:43.
No open tasks, no admin queue entries.
"""
import sys
from docx import Document
from docx.oxml.ns import qn

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

OLD_TIMESTAMP = "[2026-07-03 ~17:30]"
NEW_TIMESTAMP = "[2026-07-03 ~17:43]"

found = False
for i, p in enumerate(paras):
    if OLD_TIMESTAMP in p.text:
        for run in p.runs:
            if OLD_TIMESTAMP in run.text:
                run.text = run.text.replace(OLD_TIMESTAMP, NEW_TIMESTAMP)
                found = True
                print(f"Updated timestamp in paragraph {i}: {p.text[:120]}")
                break
        if not found:
            full_text = p.text
            for run in p.runs:
                run.text = ""
            p.runs[0].text = full_text.replace(OLD_TIMESTAMP, NEW_TIMESTAMP)
            found = True
            print(f"Updated timestamp (full rewrite) in paragraph {i}")
        break

if not found:
    print("ERROR: could not find the '17:30' tick bullet to update")
    sys.exit(1)

doc.save(DOC_PATH)
print("DOC SAVED.")
