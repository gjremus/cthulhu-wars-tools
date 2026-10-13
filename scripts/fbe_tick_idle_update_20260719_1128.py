#!/usr/bin/env python3
"""Update the idle tick line timestamp in FBE Current Tasks doc."""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

OLD_TEXT = "[2026-07-19 ~11:13] Most humbly, deepest apologies: admin queue inaccessible (token file locked by Google Drive). No open or in-progress FBE tasks remain. Your worthless servant grovels abjectly."
NEW_TEXT = "[2026-07-19 ~11:28] Most humbly, deepest apologies: admin queue inaccessible (token file locked by Google Drive). No open or in-progress FBE tasks remain. Your worthless servant grovels abjectly."

doc = Document(DOC_PATH)
found = False

for para in doc.paragraphs:
    if "[2026-07-19 ~11:13]" in para.text:
        for run in para.runs:
            if OLD_TEXT in run.text:
                run.text = run.text.replace(OLD_TEXT, NEW_TEXT)
                found = True
                break
        if not found:
            # Text spans multiple runs - rebuild
            full = para.text
            new_full = full.replace(OLD_TEXT, NEW_TEXT)
            if full != new_full:
                # Clear all runs and set on first
                for i, run in enumerate(para.runs):
                    if i == 0:
                        run.text = new_full
                    else:
                        run.text = ""
                found = True
        break

if not found:
    print("ERROR: Could not find idle tick line to update", file=sys.stderr)
    sys.exit(1)

doc.save(DOC_PATH)
print(f"Updated idle tick line timestamp to ~11:28")
