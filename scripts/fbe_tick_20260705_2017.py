#!/usr/bin/env python3
"""FBE tick update 2026-07-05 ~20:17 (UTC):
Update the idle tick line timestamp. Game 596 re-flagged broken but
the crash is in Daemon Sultan code (DSAvatarThesisCostAction), not FBE.
No open FBE tasks, admin queue empty.
"""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

edits_done = 0

OLD_TICK_FRAGMENT = "2026-07-05 ~15:02"
NEW_TICK = "[2026-07-05 ~20:17] Most humbly: admin queue empty, no open FBE tasks. Game 596 re-flagged broken but the crash is in another faction's code (not Faceless Blight) — outside our scope."

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
    print("ERROR: Could not find tick line with '2026-07-05 ~15:02' to update", file=sys.stderr)
    sys.exit(1)

doc.save(DOC_PATH)
print(f"\nDone: {edits_done} edit(s) applied and saved.")
