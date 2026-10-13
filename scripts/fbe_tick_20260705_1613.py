#!/usr/bin/env python3
"""FBE tick update 2026-07-05 ~16:13 UTC:
Add a minimal idle tick line — nothing changed since 14:00.
Admin queue empty, game 596 still awaiting deploy permission.
"""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

# Find the "Bulleted summary (newest at top)" heading and insert after it
TARGET_HEADING = "Bulleted summary (newest at top)"
NEW_TICK = "[2026-07-05 ~16:13] Most humbly: no changes this tick — Game 596 fix still awaiting your gracious deploy permission. Admin queue empty."

insert_idx = None
for i, para in enumerate(paras):
    if TARGET_HEADING in para.text:
        insert_idx = i + 1
        break

if insert_idx is None:
    print("ERROR: Could not find 'Bulleted summary' heading", file=sys.stderr)
    sys.exit(1)

# Check if there's already a "no changes this tick" line — if so, just update it
for i, para in enumerate(paras):
    if "no changes this tick" in para.text:
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
        print("Edit 1 (existing idle tick line updated): OK")
        doc.save(DOC_PATH)
        print(f"\nDone: 1 edit applied and saved.")
        sys.exit(0)

# No existing idle line — insert a new paragraph after the heading
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from copy import deepcopy

ref_para = paras[insert_idx]
new_para_elem = OxmlElement('w:p')
# Copy paragraph properties from the existing first tick line for formatting
if ref_para._element.find(qn('w:pPr')) is not None:
    new_para_elem.append(deepcopy(ref_para._element.find(qn('w:pPr'))))
r = OxmlElement('w:r')
# Copy run properties from existing line for font consistency
if ref_para.runs and ref_para.runs[0]._element.find(qn('w:rPr')) is not None:
    r.append(deepcopy(ref_para.runs[0]._element.find(qn('w:rPr'))))
t = OxmlElement('w:t')
t.text = NEW_TICK
t.set(qn('xml:space'), 'preserve')
r.append(t)
new_para_elem.append(r)

# Insert before the current first tick line
ref_para._element.addprevious(new_para_elem)
print("Edit 1 (new idle tick line inserted): OK")

doc.save(DOC_PATH)
print(f"\nDone: 1 edit applied and saved.")
