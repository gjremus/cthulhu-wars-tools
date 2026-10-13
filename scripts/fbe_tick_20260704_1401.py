#!/usr/bin/env python3
"""FBE tick update 2026-07-04 ~14:01:
1. Update the 'nothing happened' tick summary timestamp to current time.
"""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

OLD_TICK = "[2026-07-05 ~03:15] Most humbly checking in: admin queue drained (no new Faceless Blight entries), both in-progress tasks still humbly awaiting your gracious reply. Build compiles clean; standing by to serve."
NEW_TICK = "[2026-07-04 ~14:01] Most humbly checking in: admin queue drained (no new Faceless Blight entries), both in-progress tasks still humbly awaiting your gracious reply. Build compiles clean; standing by to serve."

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

doc.save(DOC_PATH)
print("\nAll edits applied and saved.")
