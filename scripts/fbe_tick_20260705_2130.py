#!/usr/bin/env python3
"""FBE tick update 2026-07-05 ~21:30 (UTC):
No open tasks, admin queue empty. Add idle tick summary line.
"""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

TICK_LINE = "[2026-07-05 ~21:30] Most humbly: no changes this tick — no open tasks, admin queue empty. All FBE games confirmed healthy."

SEARCH_FRAGMENT = "2026-07-05 ~17:30"

inserted = False
for i, para in enumerate(paras):
    if SEARCH_FRAGMENT in para.text:
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from copy import deepcopy
        new_para = deepcopy(para._element)
        for child in list(new_para):
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag == 'r':
                new_para.remove(child)
        r = OxmlElement('w:r')
        rpr_source = para.runs[0]._element.find(qn('w:rPr')) if para.runs else None
        if rpr_source is not None:
            r.append(deepcopy(rpr_source))
        t = OxmlElement('w:t')
        t.text = TICK_LINE
        t.set(qn('xml:space'), 'preserve')
        r.append(t)
        new_para.append(r)
        para._element.addprevious(new_para)
        inserted = True
        print("Edit 1 (new tick line inserted above ~17:30): OK")
        break

if not inserted:
    print("ERROR: Could not find tick line with '2026-07-05 ~17:30' to insert above", file=sys.stderr)
    sys.exit(1)

doc.save(DOC_PATH)
print(f"\nDone: tick line inserted and saved.")
