#!/usr/bin/env python3
"""FBE tick update 2026-07-04 ~14:16:
Update the 'nothing happened' tick timestamp from ~14:01 to ~14:16.
"""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

OLD_TICK = "[2026-07-04 ~14:01] Most humbly checking in: admin queue drained (no new Faceless Blight entries), both in-progress tasks still humbly awaiting your gracious reply. Build compiles clean; standing by to serve."
NEW_TICK = "[2026-07-04 ~14:16] Most humbly checking in: admin queue drained (no new Faceless Blight entries), both in-progress tasks still humbly awaiting your gracious reply. Build compiles clean; standing by to serve."

tick_found = False
for para in paras:
    if "[2026-07-04 ~14:01]" in para.text and "admin queue drained" in para.text:
        full = para.text
        new_full = full.replace("[2026-07-04 ~14:01]", "[2026-07-04 ~14:16]")
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
print("Tick timestamp updated: OK")
