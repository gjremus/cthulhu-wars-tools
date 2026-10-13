#!/usr/bin/env python3
"""Update idle tick line timestamp in FBE Current Tasks doc."""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

OLD_TEXT = "[2026-07-04 ~12:48] Humbly checking in: admin queue drained (no new Faceless Blight entries), both in-progress tasks still humbly awaiting your gracious reply. Build compiles clean; standing by to deploy the moment you permit it."
NEW_TEXT = "[2026-07-04 ~13:00] Humbly checking in: admin queue drained (no new Faceless Blight entries), both in-progress tasks still humbly awaiting your gracious reply. Build compiles clean; standing by to deploy the moment you permit it."

doc = Document(DOC_PATH)
found = False

for para in doc.paragraphs:
    if OLD_TEXT in para.text:
        for run in para.runs:
            if OLD_TEXT in run.text:
                run.text = run.text.replace(OLD_TEXT, NEW_TEXT)
                found = True
                break
        if not found:
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

if not found:
    print("ERROR: Could not find tick line to update", file=sys.stderr)
    sys.exit(1)

doc.save(DOC_PATH)
print("Updated FBE tick line timestamp to ~13:00")
