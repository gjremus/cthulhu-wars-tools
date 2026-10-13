#!/usr/bin/env python3
"""
FBE tick writer — 2026-07-03 ~12:15
Task: Update the existing "nothing happened" tick timestamp from ~12:02 to ~12:15.
Single open task remains blocked on Q6 (deploy permission). Admin queue empty. Build clean.
"""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

OLD_PREFIX = "[2026-07-03 ~12:02]"
NEW_PREFIX = "[2026-07-03 ~12:15]"

found = False
for i, p in enumerate(paras):
    if OLD_PREFIX in p.text:
        for run in p.runs:
            if OLD_PREFIX in run.text:
                run.text = run.text.replace(OLD_PREFIX, NEW_PREFIX)
                found = True
                print(f"Updated paragraph {i}: {p.text[:120]}")
                break
        if not found:
            full_text = p.text
            new_text = full_text.replace(OLD_PREFIX, NEW_PREFIX)
            for run in p.runs:
                run.text = ""
            if p.runs:
                p.runs[0].text = new_text
            found = True
            print(f"Updated paragraph {i} (full rewrite): {new_text[:120]}")
        break

if not found:
    print(f"ERROR: could not find '{OLD_PREFIX}' in document")
    sys.exit(1)

doc.save(DOC_PATH)
print("DOC SAVED.")
