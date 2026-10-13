#!/usr/bin/env python3
"""FBE tick update 2026-07-05 ~11:30:
1. Insert new tick summary line at top of bulleted summary
2. Move Game 559 from Open to Completed (deploy resolved it)
"""
import sys
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from copy import deepcopy

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

# --- Edit 1: Insert new tick summary line ABOVE the existing newest ---
# Find the first tick line (starts with "[2026-07-0")
NEW_TICK = "[2026-07-05 ~11:30] Most humbly: admin queue empty. Game 559 confirmed RESOLVED by the prior deploy (loading clean since July 4th) — broken flag cleared. Games 531 and 596 still humbly awaiting your gracious deploy permission."

tick_idx = None
for i, p in enumerate(paras):
    if p.text.strip().startswith("[2026-07-0") and "humbly" in p.text.lower():
        tick_idx = i
        break

if tick_idx is None:
    # Fallback: find "Bulleted summary" heading and insert after
    for i, p in enumerate(paras):
        if "Bulleted summary" in p.text:
            tick_idx = i + 1
            break

if tick_idx is None:
    print("ERROR: Could not find tick summary section", file=sys.stderr)
    sys.exit(1)

# Clone the tick paragraph's element and replace text
source = paras[tick_idx]
new_para = deepcopy(source._element)
for r in new_para.findall(qn('w:r')):
    new_para.remove(r)
r = OxmlElement('w:r')
source_runs = source._element.findall(qn('w:r'))
if source_runs:
    rpr = source_runs[0].find(qn('w:rPr'))
    if rpr is not None:
        r.append(deepcopy(rpr))
t = OxmlElement('w:t')
t.text = NEW_TICK
t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
r.append(t)
new_para.append(r)

# Insert before the current first tick line
source._element.addprevious(new_para)
print("Edit 1 (new tick line): OK")

# --- Edit 2: Remove Game 559 from Open section and add to Completed ---
# Find the Game 559 paragraph in Open
game559_idx = None
game559_text = None
for i, p in enumerate(paras):
    if "Game 559" in p.text and "559" in p.text and "replay crash" in p.text.lower():
        game559_idx = i
        game559_text = p.text
        break

if game559_idx is None:
    print("WARNING: Could not find Game 559 task in Open section (may already be moved)", file=sys.stderr)
else:
    # Change the [] to [x] and update the text
    completed_text = "[x] Game 559 replay crash — RESOLVED (2026-07-05). The deploy on 2026-07-04 (cache 20260704-191300) fixed the underlying issue. Game confirmed loading clean since July 4th; broken flag cleared on server."

    # Find the Completed section heading
    completed_idx = None
    for i, p in enumerate(paras):
        if p.text.strip() == "Completed":
            completed_idx = i
            break

    if completed_idx is None:
        print("ERROR: Could not find Completed section", file=sys.stderr)
        sys.exit(1)

    # Insert after the Completed heading (before first completed task)
    insert_after = completed_idx
    # Find first actual task after "Completed" heading
    for j in range(completed_idx + 1, min(completed_idx + 5, len(paras))):
        if paras[j].text.strip():
            insert_after = j
            break

    # Create completed task paragraph (clone from the game559 paragraph)
    game559_para = paras[game559_idx]
    new_completed = deepcopy(game559_para._element)
    for r_elem in new_completed.findall(qn('w:r')):
        new_completed.remove(r_elem)
    r = OxmlElement('w:r')
    source_runs = game559_para._element.findall(qn('w:r'))
    if source_runs:
        rpr = source_runs[0].find(qn('w:rPr'))
        if rpr is not None:
            r.append(deepcopy(rpr))
    t = OxmlElement('w:t')
    t.text = completed_text
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    r.append(t)
    new_completed.append(r)

    # Insert before the first completed task
    paras[insert_after]._element.addprevious(new_completed)
    print("Edit 2a (insert into Completed): OK")

    # Remove the original Game 559 paragraph from Open
    game559_para._element.getparent().remove(game559_para._element)
    print("Edit 2b (remove from Open): OK")

doc.save(DOC_PATH)
print("\nAll edits applied and saved.")
