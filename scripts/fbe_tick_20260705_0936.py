#!/usr/bin/env python3
"""FBE tick update 2026-07-05 ~09:36:
1. Update the 'nothing happened' tick summary timestamp (Rule 30: only one allowed)
2. Remove the redundant 05:48 'nothing happened' line
"""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

# --- Edit 1: Update the top "nothing happened" tick line timestamp ---
OLD_TICK = "[2026-07-05 ~07:15] Most humbly, deepest apologies: admin queue empty, no new tasks or prompts. Games 531 and 596 fixes still humbly awaiting your gracious deploy permission."
NEW_TICK = "[2026-07-05 ~09:36] Most humbly, deepest apologies: admin queue empty, no new tasks or prompts. Games 531 and 596 fixes still humbly awaiting your gracious deploy permission."

tick_found = False
for para in paras:
    if OLD_TICK in para.text:
        full = para.text
        new_full = full.replace(OLD_TICK, NEW_TICK)
        for i, run in enumerate(para.runs):
            if i == 0:
                run.text = new_full
            else:
                run.text = ""
        tick_found = True
        break

if not tick_found:
    print("ERROR: Could not find tick line to update", file=sys.stderr)
    sys.exit(1)
print("Edit 1 (tick timestamp update): OK")

# --- Edit 2: Remove the redundant 05:48 'nothing happened' line (Rule 30) ---
REDUNDANT_TICK = "[2026-07-05 ~05:48] Most humbly: admin queue empty, no new tasks."
redundant_found = False
for para in paras:
    if REDUNDANT_TICK in para.text:
        parent = para._element.getparent()
        parent.remove(para._element)
        redundant_found = True
        break

if not redundant_found:
    print("WARNING: Redundant 05:48 tick line not found (non-fatal)", file=sys.stderr)
else:
    print("Edit 2 (remove redundant tick line): OK")

doc.save(DOC_PATH)
print("DONE: saved")
