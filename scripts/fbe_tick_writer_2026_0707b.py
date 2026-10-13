#!/usr/bin/env python3
"""FBE ticker update 2026-07-07 ~21:50: minimal status tick — no new work, admin queue drained."""
import docx
import copy
from docx.oxml.ns import qn
import docx.oxml

PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

d = docx.Document(PATH)

def find_para_containing(text, start=0):
    for i, p in enumerate(d.paragraphs[start:], start):
        if text in p.text:
            return i, p
    return None, None

# Insert a "no change" tick line above the most recent [2026-07-07 ~21:30] tick
i, p = find_para_containing("[2026-07-07 ~21:30]")
if p:
    new_text = "[2026-07-07 ~21:50] Most humbly: admin queue drained (no FBE-specific issues). Self Consuming phase-boundary fix still awaiting deploy — build compiles clean, code is ready."
    new_para = copy.deepcopy(p._element)
    for child in list(new_para):
        if child.tag.endswith('}r'):
            new_para.remove(child)
    run_elem = docx.oxml.OxmlElement('w:r')
    text_elem = docx.oxml.OxmlElement('w:t')
    text_elem.text = new_text
    text_elem.set(qn('xml:space'), 'preserve')
    run_elem.append(text_elem)
    new_para.append(run_elem)
    p._element.addprevious(new_para)

d.save(PATH)
print("FBE task doc updated successfully.")
