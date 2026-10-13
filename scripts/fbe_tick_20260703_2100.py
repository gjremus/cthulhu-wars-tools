#!/usr/bin/env python3
"""
FBE tick writer — 2026-07-03 ~21:00
Task: Found 4 broken FBE games still on server. Fixed AnimatedRushDoneAction
deserialization for games 530/534. Need deploy permission. Games 531/596
have different root causes (not FBE-specific). Update open tasks + tick summary.
"""
import sys
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from copy import deepcopy

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

def clone_para_with_text(source_para, new_text):
    """Clone a paragraph's formatting and replace its text."""
    new_para = deepcopy(source_para._element)
    for r in new_para.findall(qn('w:r')):
        new_para.remove(r)
    r = OxmlElement('w:r')
    source_runs = source_para._element.findall(qn('w:r'))
    if source_runs:
        rpr_elem = source_runs[0].find(qn('w:rPr'))
        if rpr_elem is not None:
            r.append(deepcopy(rpr_elem))
    t = OxmlElement('w:t')
    t.text = new_text
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    r.append(t)
    new_para.append(r)
    return new_para

# ─── Find key sections ───────────────────────────────────────────────────────

summary_header_idx = None
open_header_idx = None
questions_header_idx = None

for i, p in enumerate(paras):
    text = p.text.strip()
    if "Bulleted summary" in text and summary_header_idx is None:
        summary_header_idx = i
    if text == "Open" and open_header_idx is None:
        open_header_idx = i
    if "Claude Questions for the Creator" in text and questions_header_idx is None:
        questions_header_idx = i

print(f"Summary header at: {summary_header_idx}")
print(f"Open header at: {open_header_idx}")
print(f"Questions header at: {questions_header_idx}")

if summary_header_idx is None or open_header_idx is None:
    print("ERROR: Could not find required sections")
    sys.exit(1)

# ─── Step 1: Update tick summary (replace the "nothing happened" line) ────────

# Find the existing "no open tasks" summary bullet and replace it
updated_summary = False
for i in range(summary_header_idx + 1, open_header_idx):
    text = paras[i].text.strip()
    if text.startswith('[2026-07-03 ~20:15]'):
        # Replace this "nothing happened" bullet with actual work report
        new_text = "[2026-07-03 ~21:00] Humbly reporting: found 4 FBE games still broken on server. Fixed the old Animated Rush save format issue (games 530, 534); awaiting your permission to deploy. Games 531 and 596 have unrelated errors outside FBE code."
        for r in paras[i]._element.findall(qn('w:r')):
            paras[i]._element.remove(r)
        r = OxmlElement('w:r')
        # Get rPr from a nearby bullet
        rpr_elem = None
        for j in range(summary_header_idx + 1, min(summary_header_idx + 5, len(paras))):
            runs = paras[j]._element.findall(qn('w:r'))
            if runs:
                rpr_elem = runs[0].find(qn('w:rPr'))
                if rpr_elem is not None:
                    break
        if rpr_elem is not None:
            r.append(deepcopy(rpr_elem))
        t = OxmlElement('w:t')
        t.text = new_text
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        r.append(t)
        paras[i]._element.append(r)
        updated_summary = True
        print(f"Updated tick summary at index {i}")
        break

if not updated_summary:
    print("WARNING: Could not find the 20:15 tick line to update")
    sys.exit(1)

# ─── Step 2: Replace empty [] bullets in Open with actual tasks ───────────────

# Find the open task bullets (they should be "- []" or just "[]")
open_bullets = []
for i in range(open_header_idx + 1, len(paras)):
    text = paras[i].text.strip()
    if text.startswith("Claude Questions") or text.startswith("In Progress") or text.startswith("Completed"):
        break
    if text in ("[]", "- []"):
        open_bullets.append(i)

print(f"Found {len(open_bullets)} empty open bullets: {open_bullets}")

if len(open_bullets) < 1:
    print("ERROR: No empty [] bullets found in Open section")
    sys.exit(1)

# First bullet: the deploy task (mark as in-progress since it needs input)
new_task = "[/] INPUT NEEDED — Deploy Animated Rush legacy replay fix. Two games (530, 534) crash because the live build does not recognize an old save format for the Animated Rush \"Done\" action. The code fix is ready locally. Permission to commit and push to the homebrew site? (Games 531 and 596 have different, non-FBE bugs — 531 has a cryptic startup error, 596 has a logic error in another faction's code.)"
for r in paras[open_bullets[0]]._element.findall(qn('w:r')):
    paras[open_bullets[0]]._element.remove(r)
r = OxmlElement('w:r')
t = OxmlElement('w:t')
t.text = new_task
t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
r.append(t)
paras[open_bullets[0]]._element.append(r)
print(f"Set task at index {open_bullets[0]}")

# Ensure there's still at least one empty [] after it
if len(open_bullets) < 2:
    # Insert an empty [] after the task we just wrote
    new_empty = clone_para_with_text(paras[open_bullets[0]], "- []")
    paras[open_bullets[0]]._element.addnext(new_empty)
    print("Added empty [] bullet after the task")

# ─── Step 3: Correct the false "CONFIRMED ALREADY DEPLOYED" completed task ───
for i, p in enumerate(paras):
    if "Animated Rush replay fix" in p.text and "CONFIRMED ALREADY DEPLOYED" in p.text:
        corrected = "[x] Animated Rush replay fix — CORRECTION (2026-07-03 ~21:00): Prior tick incorrectly marked this deployed. The legacy AnimatedRushDoneAction fix was never committed. Games 530/534 still crash on old save format. Fix re-coded locally; awaiting deploy permission."
        for r in p._element.findall(qn('w:r')):
            p._element.remove(r)
        r = OxmlElement('w:r')
        t = OxmlElement('w:t')
        t.text = corrected
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        r.append(t)
        p._element.append(r)
        print(f"Corrected completed task at index {i}")
        break

# ─── Save ─────────────────────────────────────────────────────────────────────
doc.save(DOC_PATH)
print("\nDOC SAVED.")
