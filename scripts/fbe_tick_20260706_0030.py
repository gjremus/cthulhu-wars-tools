#!/usr/bin/env python3
"""FBE tick update 2026-07-06 ~00:30 (UTC):
Update the existing top tick summary timestamp — status unchanged (still awaiting
deploy permission for games 531 and 596). Also note that 12 other FBE broken flags
were cleared since those games now load clean on the server.
"""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

edits_done = 0

# --- Edit 1: Replace the ~22:55 tick line with updated timestamp and note about cleared flags ---
OLD_TICK_FRAGMENT = "2026-07-05 ~22:55"
NEW_TICK = "[2026-07-06 ~00:30] Most humbly: admin queue empty, 12 previously-broken games confirmed clean and flags cleared. Only games 531 and 596 remain broken — both fixes still humbly awaiting your gracious deploy permission."

for i, para in enumerate(paras):
    if OLD_TICK_FRAGMENT in para.text:
        for run in para.runs:
            run.text = ""
        if para.runs:
            para.runs[0].text = NEW_TICK
        else:
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn
            r = OxmlElement('w:r')
            t = OxmlElement('w:t')
            t.text = NEW_TICK
            t.set(qn('xml:space'), 'preserve')
            r.append(t)
            para._element.append(r)
        edits_done += 1
        print("Edit 1 (tick line updated): OK")
        break

if edits_done < 1:
    print("ERROR: Could not find tick line with '2026-07-05 ~22:55' to update", file=sys.stderr)
    sys.exit(1)

doc.save(DOC_PATH)
print(f"\nDone: {edits_done} edit(s) applied and saved.")
