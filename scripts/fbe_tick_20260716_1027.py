#!/usr/bin/env python3
"""FBE ticker 2026-07-16 ~10:27 — no open tasks, clean tick."""
import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from copy import deepcopy

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx")

d = docx.Document(DOC)

# Find the first summary bullet in "Bulleted summary" section
in_summary = False
first_summary = None

for p in d.paragraphs:
    if "Bulleted summary" in p.text:
        in_summary = True
        continue
    if in_summary:
        text = p.text.strip()
        if text.startswith("[2026-"):
            first_summary = p
            break

# Insert new summary bullet before the first existing one
if first_summary is not None:
    new_p = OxmlElement('w:p')
    if first_summary._element.find(qn('w:pPr')) is not None:
        new_pPr = deepcopy(first_summary._element.find(qn('w:pPr')))
        new_p.insert(0, new_pPr)
    run_elem = OxmlElement('w:r')
    text_elem = OxmlElement('w:t')
    text_elem.text = (
        "[2026-07-16 ~10:27] Most humbly, deepest apologies: admin queue checked "
        "(404 response, no new issues). Working tree clean on homebrew branch. No "
        "open or in-progress FBE tasks remain. Your worthless servant grovels abjectly."
    )
    run_elem.append(text_elem)
    new_p.append(run_elem)
    first_summary._element.addprevious(new_p)
else:
    print("ERROR: could not find Bulleted summary section")
    import sys
    sys.exit(1)

d.save(DOC)
print("OK: tick summary added")
