#!/usr/bin/env python3
"""FBE tick update 2026-07-05 ~19:45 (UTC):
Update the existing idle tick line timestamp — status unchanged
(still awaiting deploy permission for game 596, admin queue empty).
"""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

edits_done = 0

OLD_TICK_FRAGMENT = "2026-07-05 ~16:32"
NEW_TICK = "[2026-07-05 ~19:45] Most humbly: no changes this tick — Game 596 fix still awaiting your gracious deploy permission. Admin queue empty."

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
    print("ERROR: Could not find tick line with '2026-07-05 ~16:32' to update", file=sys.stderr)
    sys.exit(1)

doc.save(DOC_PATH)
print(f"\nDone: {edits_done} edit(s) applied and saved.")
