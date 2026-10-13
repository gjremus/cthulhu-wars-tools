#!/usr/bin/env python3
"""FBE tick update 2026-07-04 ~22:30:
1. Update tick summary line (expand broken game count)
2. Update in-progress task text (add game 531 to list)
3. Insert new open task about server-side crash (615, 617, 628)
"""
import sys
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from copy import deepcopy

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

# --- Edit 1: Update tick summary line ---
OLD_TICK = "[2026-07-04 ~21:00] Most humbly: build compiles clean, admin queue empty. Five FBE games (530, 534, 546, 556, 596) still humbly awaiting your gracious permission to deploy the replay fix."
NEW_TICK = "[2026-07-04 ~22:30] Most humbly: nine broken FBE games total — five confirmed old save format (530, 531, 534, 546, 596), three with a new server crash today (615, 617, 628). Replay fix still humbly awaiting your gracious permission to deploy."

tick_found = False
for para in paras:
    if OLD_TICK in para.text:
        full = para.text
        new_full = full.replace(OLD_TICK, NEW_TICK)
        for i, run in enumerate(para.runs):
            if i == 0:
                run.text = new_full
            else:
                run.text = ""
        tick_found = True
        break

if not tick_found:
    print("ERROR: Could not find tick line to update", file=sys.stderr)
    sys.exit(1)
print("Edit 1 (tick line): OK")

# --- Edit 2: Update in-progress task ---
OLD_INPROG = "Five FBE games (530, 534, 546, 556, 596) crash on the live server"
NEW_INPROG = "Five FBE games (530, 531, 534, 546, 596) crash on the live server"

inprog_found = False
for para in paras:
    if OLD_INPROG in para.text:
        full = para.text
        new_full = full.replace(OLD_INPROG, NEW_INPROG)
        for i, run in enumerate(para.runs):
            if i == 0:
                run.text = new_full
            else:
                run.text = ""
        inprog_found = True
        break

if not inprog_found:
    print("WARNING: Could not find in-progress task to update (non-fatal)", file=sys.stderr)
else:
    print("Edit 2 (in-progress task): OK")

# --- Edit 3: Insert new open task before the empty [] placeholder ---
# The empty [] is paragraph with text == '[]' and style 'Compact', right after 'Open' heading.
empty_placeholder_idx = None
for i, p in enumerate(paras):
    if p.text.strip() == '[]' and p.style.name == 'Compact':
        # Verify it's in the Open section (prev paragraph is 'Open' or close)
        if i > 0 and ('Open' in paras[i-1].text or any('Open' in paras[j].text for j in range(max(0,i-3), i))):
            empty_placeholder_idx = i
            break

if empty_placeholder_idx is None:
    print("WARNING: Could not find empty [] placeholder in Open section", file=sys.stderr)
else:
    # Clone the placeholder paragraph and set new task text
    new_task_text = "[/] INPUT NEEDED — Server-side crash (not our code). Three FBE games (615, 617, 628) suddenly started crashing today with a generic error, all at the same time. This looks like a server or infrastructure issue, not a Faceless Blight bug. Flagging for the master doc / server owner."

    source = paras[empty_placeholder_idx]
    new_para = deepcopy(source._element)
    # Clear all runs
    for r in new_para.findall(qn('w:r')):
        new_para.remove(r)
    # Create a new run with the task text
    r = OxmlElement('w:r')
    source_runs = source._element.findall(qn('w:r'))
    if source_runs:
        rpr = source_runs[0].find(qn('w:rPr'))
        if rpr is not None:
            r.append(deepcopy(rpr))
    t = OxmlElement('w:t')
    t.text = new_task_text
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    r.append(t)
    new_para.append(r)

    # Insert before the empty placeholder
    source._element.addprevious(new_para)
    print("Edit 3 (new server-crash task): OK")

doc.save(DOC_PATH)
print("\nAll edits applied and saved.")
