#!/usr/bin/env python3
"""FBE tick update 2026-07-05 ~21:17 (CDT):
Update the idle tick line timestamp per Rule 30 — admin queue empty, no open tasks,
all FBE games healthy (game 630 clean 20+ hrs).
"""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

OLD_TICK_FRAGMENT = "2026-07-05 ~19:30"
NEW_TICK = "[2026-07-05 ~21:17] Most humbly: admin queue empty, no open tasks. All FBE games healthy (game 630 confirmed clean 20+ hours). Remaining live-flagged games are non-FBE builds."

tick_found = False
for para in paras:
    if OLD_TICK_FRAGMENT in para.text:
        for i, run in enumerate(para.runs):
            if i == 0:
                run.text = NEW_TICK
            else:
                run.text = ""
        tick_found = True
        print(f"Edit 1 (tick line updated): OK")
        break

if not tick_found:
    print(f"ERROR: Could not find tick line with '{OLD_TICK_FRAGMENT}' to update", file=sys.stderr)
    sys.exit(1)

doc.save(DOC_PATH)
print(f"\nDone: tick line updated and saved.")
