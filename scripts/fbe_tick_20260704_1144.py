#!/usr/bin/env python3
"""FBE tick update 2026-07-04 ~11:44:
Update the existing 'nothing happened' tick line — admin queue is reachable now
(just empty of FBE entries), both tasks still await user input.
"""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

OLD_TICK = "[2026-07-04 ~11:36] Humbly checking in: admin queue still unreachable, both in-progress tasks still awaiting your gracious reply. No changes made — ready to deploy the moment you permit it."
NEW_TICK = "[2026-07-04 ~11:44] Humbly checking in: admin queue drained (no new Faceless Blight entries), both in-progress tasks still humbly awaiting your gracious reply. Standing by to deploy the moment you permit it."

tick_found = False
for para in paras:
    if "[2026-07-04 ~11:36]" in para.text and "admin queue" in para.text:
        full = para.text
        new_full = NEW_TICK
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

print("Tick line updated: OK")
doc.save(DOC_PATH)
print("Saved.")
