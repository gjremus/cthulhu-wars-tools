#!/usr/bin/env python3
"""FBE tick update 2026-07-05 ~05:30:
1. Insert a short tick line above the ~04:30 line (admin queue empty, same blocker)
"""
import sys
from docx import Document
from docx.oxml import OxmlElement
from copy import deepcopy

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

# --- Edit 1: Insert new tick line above the ~04:30 line ---
# Find the "Bulleted summary (newest at top)" header, then insert after it
TICK_LINE = "[2026-07-05 ~05:30] Most humbly: admin queue empty, no new issues. Game 596 fix still coded and verified correct — awaiting a machine with Java to compile and deploy."

TARGET_FRAGMENT = "[2026-07-05 ~04:30] Most humbly, deepest apologies for the delay: Game 596 root cause FOUND"

inserted = False
for i, para in enumerate(paras):
    if TARGET_FRAGMENT in para.text:
        # Insert a new paragraph before this one with the same style
        new_para = deepcopy(para._element)
        # Clear the new paragraph's runs and set text
        for run_elem in new_para.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r'):
            new_para.remove(run_elem)
        # Create a single run with our text
        from docx.oxml.ns import qn
        r = OxmlElement('w:r')
        # Copy run properties from first run of target para if available
        if para.runs:
            rPr = para.runs[0]._element.find(qn('w:rPr'))
            if rPr is not None:
                r.append(deepcopy(rPr))
        t = OxmlElement('w:t')
        t.text = TICK_LINE
        t.set(qn('xml:space'), 'preserve')
        r.append(t)
        new_para.append(r)
        # Insert before the target paragraph
        para._element.addprevious(new_para)
        inserted = True
        break

if not inserted:
    print("ERROR: Could not find target tick line to insert before", file=sys.stderr)
    sys.exit(1)
print("Edit 1 (new tick line): OK")

doc.save(DOC_PATH)
print("\nAll edits applied and saved.")
