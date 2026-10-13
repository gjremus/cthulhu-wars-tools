#!/usr/bin/env python3
"""FBE tick update 2026-07-05 ~07:59:
Update the 'nothing happened' tick summary timestamp (Rule 30: only one allowed).
"""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

OLD_TICK = "[2026-07-05 ~07:44] Most humbly, deepest apologies: admin queue empty, no new tasks or prompts. Games 531 and 596 fixes still humbly awaiting your gracious deploy permission."
NEW_TICK = "[2026-07-05 ~07:59] Most humbly, deepest apologies: admin queue empty, no new tasks or prompts. Games 531 and 596 fixes still humbly awaiting your gracious deploy permission."

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

doc.save(DOC_PATH)
print("DONE: tick timestamp updated to ~07:59")
