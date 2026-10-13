#!/usr/bin/env python3
"""Update the idle tick line timestamp in FBE Current Tasks doc."""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

OLD_TS = "[2026-07-04 ~06:45]"
NEW_TS = "[2026-07-04 ~07:10]"

doc = Document(DOC_PATH)
found = False

for para in doc.paragraphs:
    if OLD_TS in para.text:
        new_full = para.text.replace(OLD_TS, NEW_TS)
        if new_full != para.text:
            for i, run in enumerate(para.runs):
                if OLD_TS in run.text:
                    run.text = run.text.replace(OLD_TS, NEW_TS)
                    found = True
                    break
            if not found:
                for i, run in enumerate(para.runs):
                    if i == 0:
                        run.text = new_full
                    else:
                        run.text = ""
                found = True
        break

if not found:
    print("ERROR: Could not find tick line with " + OLD_TS, file=sys.stderr)
    sys.exit(1)

doc.save(DOC_PATH)
print("Updated idle tick line timestamp to ~07:10")
