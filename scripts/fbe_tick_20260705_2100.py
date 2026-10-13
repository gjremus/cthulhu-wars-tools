#!/usr/bin/env python3
"""FBE tick update 2026-07-05 ~21:00 CDT:
Fix garbled idle tick line and update timestamp. No state change — game 596 fix
still awaiting deploy permission, admin queue empty.
"""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

edits_done = 0

OLD_TICK_FRAGMENT = "2026-07-06 ~09:30"
NEW_TICK = "[2026-07-05 ~21:00] Most humbly: server healthy, admin queue empty, no new issues. Game 596 fix still patiently awaiting your gracious deploy permission."

for i, para in enumerate(paras):
    if OLD_TICK_FRAGMENT in para.text:
        for run in para.runs:
            run.text = ""
        if para.runs:
            para.runs[0].text = NEW_TICK
        edits_done += 1
        break

if edits_done == 0:
    print(f"ERROR: Could not find tick line with '{OLD_TICK_FRAGMENT}'", file=sys.stderr)
    sys.exit(1)

doc.save(DOC_PATH)
print(f"OK: Updated idle tick line ({edits_done} edit)")
