#!/usr/bin/env python3
"""
FBE tick writer — 2026-06-25 ~15:44
Task: No open tasks this tick. Admin queue empty. Write tick summary.
"""
import sys
from docx import Document
from docx.oxml.ns import qn
from copy import deepcopy
import re

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks.docx"

doc = Document(DOC_PATH)

paras = doc.paragraphs

# Locate the "Bulleted summary" paragraph (newest at top) and the 3 summary bullets after it
# Para 35: "Bulleted summary (newest at top)"
# Para 36: newest summary bullet
# Para 37: second summary bullet
# Para 38: third summary bullet (to rotate out)
# Para 38: "Open" section

# Find "Bulleted summary" paragraph index
summary_header_idx = None
for i, p in enumerate(paras):
    if "Bulleted summary" in p.text:
        summary_header_idx = i
        break

if summary_header_idx is None:
    print("ERROR: could not find 'Bulleted summary' paragraph")
    sys.exit(1)

print(f"Found 'Bulleted summary' at index {summary_header_idx}")

# Print the next 5 paragraphs for verification
for i in range(summary_header_idx, summary_header_idx + 6):
    print(f"  [{i}]: {paras[i].text[:120]}")

# Find "Summary History" paragraph index
history_idx = None
for i, p in enumerate(paras):
    if "Summary History" in p.text:
        history_idx = i
        break

if history_idx is None:
    print("ERROR: could not find 'Summary History' paragraph")
    sys.exit(1)

print(f"Found 'Summary History' at index {history_idx}")
# Print a few paragraphs after it
for i in range(history_idx, min(history_idx + 4, len(paras))):
    print(f"  [{i}]: {paras[i].text[:120]}")

# The 3 current summary bullets are at summary_header_idx+1, +2, +3
bullet1_idx = summary_header_idx + 1  # newest (keep)
bullet2_idx = summary_header_idx + 2  # 2nd (keep)
bullet3_idx = summary_header_idx + 3  # 3rd (will be moved to history)

NEW_TICK_LINE = "[2026-06-25 ~15:44] With humble apologies for any delay — this tick found no open Faceless Blight tasks and an empty admin queue; the full implementation audit (all six spellbooks, combat, menus, glyph) confirms everything correct and live as of the last deployment."

# Step 1: Copy bullet3's text & style to a new paragraph after "Summary History"
bullet3_para = paras[bullet3_idx]
bullet3_text = bullet3_para.text

# Step 2: Insert the new tick line at bullet1_idx position (shifting others down)
# We'll use the XML manipulation approach: insert new para before bullet1

from docx.oxml import OxmlElement
from lxml import etree

def clone_para_with_text(source_para, new_text):
    """Clone a paragraph's formatting and replace its text."""
    new_para = deepcopy(source_para._element)
    # Clear all runs
    for r in new_para.findall(qn('w:r')):
        new_para.remove(r)
    # Create a simple run with the new text
    r = OxmlElement('w:r')
    # Copy run properties from the first run of source if any
    source_runs = source_para._element.findall(qn('w:r'))
    if source_runs:
        rpr = source_runs[0].find(qn('w:rPr'))
        if rpr is not None:
            r.append(deepcopy(rpr))
    t = OxmlElement('w:t')
    t.text = new_text
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    r.append(t)
    new_para.append(r)
    return new_para

# Insert new tick bullet before current bullet1 (newest position)
new_tick_elem = clone_para_with_text(paras[bullet1_idx], NEW_TICK_LINE)
paras[bullet1_idx]._element.addprevious(new_tick_elem)

# Now bullet indices have shifted by 1:
# bullet1_idx still points to what was bullet1 (now bullet2 position is +1 from that)
# bullet3_idx+1 is now the old bullet3

# Recalculate after insertion
paras = doc.paragraphs  # refresh
# Find new positions
summary_header_idx2 = None
for i, p in enumerate(paras):
    if "Bulleted summary" in p.text:
        summary_header_idx2 = i
        break

print(f"\nAfter insertion, 'Bulleted summary' at index {summary_header_idx2}")
for i in range(summary_header_idx2, summary_header_idx2 + 6):
    print(f"  [{i}]: {paras[i].text[:120]}")

# Now the 4 bullets are at +1, +2, +3, +4 (the old 3rd is now the 4th)
# We need to move old bullet3 (now at summary_header_idx2+4) to Summary History
old_bullet4_idx = summary_header_idx2 + 4
old_bullet4_text = paras[old_bullet4_idx].text
print(f"\nOld bullet to archive at [{old_bullet4_idx}]: {old_bullet4_text[:120]}")

# Find history index again
history_idx2 = None
for i, p in enumerate(paras):
    if "Summary History" in p.text:
        history_idx2 = i
        break

print(f"'Summary History' now at index {history_idx2}")
for i in range(history_idx2, min(history_idx2 + 4, len(paras))):
    print(f"  [{i}]: {paras[i].text[:120]}")

# Insert the old bullet3 text as new paragraph right after "Summary History" header
archive_elem = clone_para_with_text(paras[old_bullet4_idx], old_bullet4_text)
paras[history_idx2]._element.addnext(archive_elem)

# Remove the now-4th bullet from the summary section
# Find it again after insertion
paras2 = doc.paragraphs
summary_header_idx3 = None
for i, p in enumerate(paras2):
    if "Bulleted summary" in p.text:
        summary_header_idx3 = i
        break

old_bullet4_final_idx = summary_header_idx3 + 4
print(f"\nRemoving old 4th bullet at [{old_bullet4_final_idx}]: {paras2[old_bullet4_final_idx].text[:120]}")
old_para = paras2[old_bullet4_final_idx]._element
old_para.getparent().remove(old_para)

# Verify final state
paras3 = doc.paragraphs
summary_header_idx4 = None
for i, p in enumerate(paras3):
    if "Bulleted summary" in p.text:
        summary_header_idx4 = i
        break

print(f"\nFinal summary section (header at {summary_header_idx4}):")
for i in range(summary_header_idx4, summary_header_idx4 + 6):
    print(f"  [{i}]: {paras3[i].text[:120]}")

doc.save(DOC_PATH)
print("\nDOC SAVED.")
