#!/usr/bin/env python3
"""FBE ticker update 2026-07-07 ~22:30: update idle tick timestamp — no new work, admin queue drained (no FBE issues)."""
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

# Update the existing ~21:50 idle tick line to ~22:30 (same content, per rule 30 — only one idle bullet)
i, p = find_para_containing("[2026-07-07 ~21:50]")
if p:
    new_text = "[2026-07-07 ~22:30] Most humbly: admin queue drained (no FBE-specific issues). Self Consuming phase-boundary fix still awaiting deploy — build compiles clean, code is ready."
    for child in list(p._element):
        if child.tag.endswith('}r'):
            p._element.remove(child)
    run_elem = docx.oxml.OxmlElement('w:r')
    text_elem = docx.oxml.OxmlElement('w:t')
    text_elem.text = new_text
    text_elem.set(qn('xml:space'), 'preserve')
    run_elem.append(text_elem)
    p._element.append(run_elem)
    print("Updated idle tick line from ~21:50 to ~22:30.")
else:
    print("WARNING: Could not find [2026-07-07 ~21:50] tick line — no write performed.")

d.save(PATH)
print("FBE task doc saved.")
