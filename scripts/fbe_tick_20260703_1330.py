#!/usr/bin/env python3
"""
FBE tick writer — 2026-07-03 ~13:30
Task: Update existing "nothing happened" tick line with current timestamp.
Single open task still blocked on Q6. Admin queue empty (server returned no data).
"""
import sys
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

OLD_LINE_PREFIX = "[2026-07-03 ~12:59]"
NEW_TICK_LINE = "[2026-07-03 ~13:30] Most humbly reporting: single open task remains blocked on Q6 (deploy permission for game 596 replay fix). Admin queue drained (empty), no new work."

doc = Document(DOC_PATH)
paras = doc.paragraphs

replaced = False
for i, p in enumerate(paras):
    if p.text.strip().startswith(OLD_LINE_PREFIX):
        for r in p._element.findall(qn('w:r')):
            p._element.remove(r)
        r = OxmlElement('w:r')
        t = OxmlElement('w:t')
        t.text = NEW_TICK_LINE
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        r.append(t)
        p._element.append(r)
        replaced = True
        print(f"Replaced tick line at paragraph {i}")
        break

if not replaced:
    print(f"ERROR: could not find paragraph starting with '{OLD_LINE_PREFIX}'")
    sys.exit(1)

doc.save(DOC_PATH)
print("DOC SAVED.")
