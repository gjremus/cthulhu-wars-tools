#!/usr/bin/env python3
"""
FBE tick — 2026-07-03 ~22:15
Update the existing "nothing happened" tick line with current timestamp.
Admin queue unreachable (server timeout). No open tasks.
"""
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from copy import deepcopy

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

def replace_para_text(para, new_text):
    runs = para._element.findall(qn('w:r'))
    if not runs:
        r = OxmlElement('w:r')
        t = OxmlElement('w:t')
        t.text = new_text
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        r.append(t)
        para._element.append(r)
        return
    first_rpr = runs[0].find(qn('w:rPr'))
    for r in runs:
        para._element.remove(r)
    r = OxmlElement('w:r')
    if first_rpr is not None:
        r.append(deepcopy(first_rpr))
    t = OxmlElement('w:t')
    t.text = new_text
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    r.append(t)
    para._element.append(r)

# Find and update the top tick line (the ~19:13 one)
found = False
for i, p in enumerate(paras):
    if '[2026-07-03 ~19:13]' in p.text and 'no open tasks' in p.text:
        replace_para_text(p, "[2026-07-03 ~22:15] Humbly reporting: no open tasks; admin queue unreachable (server timeout). All FBE work complete, awaiting your next command.")
        print(f"Updated tick line at paragraph {i}")
        found = True
        break

if not found:
    print("ERROR: could not find the ~19:13 tick line to update")
    import sys
    sys.exit(1)

doc.save(DOC_PATH)
print("DOC SAVED — tick line updated.")
