#!/usr/bin/env python3
"""
FBE tick writer — 2026-07-03 ~15:55
Task: Mark the Animated Rush serialization task COMPLETE (fix already deployed),
move it from Open to Completed, update Q6 with resolution, update tick summary.
"""
import sys
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from copy import deepcopy

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

# ── Helper: replace paragraph text preserving formatting ──
def replace_para_text(para, new_text):
    """Clear all runs and set new text in first run, preserving formatting."""
    runs = para._element.findall(qn('w:r'))
    if not runs:
        r = OxmlElement('w:r')
        t = OxmlElement('w:t')
        t.text = new_text
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        r.append(t)
        para._element.append(r)
        return
    # Keep first run's rPr, clear all runs
    first_rpr = runs[0].find(qn('w:rPr'))
    for r in runs:
        para._element.remove(r)
    r = OxmlElement('w:r')
    if first_rpr is not None:
        r.append(deepcopy(first_rpr))
    t = OxmlElement('w:t')
    t.text = new_text
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    r.append(t)
    para._element.append(r)


def clone_para_with_text(source_para, new_text):
    """Clone a paragraph's formatting and replace its text."""
    new_para = deepcopy(source_para._element)
    for r in new_para.findall(qn('w:r')):
        new_para.remove(r)
    r = OxmlElement('w:r')
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


# ── Find key sections ──
sections = {}
for i, p in enumerate(paras):
    text = p.text.strip()
    if text == "Bulleted summary (newest at top)":
        sections['summary'] = i
    elif text == "Open":
        sections['open'] = i
    elif text == "Claude Questions for the Creator":
        sections['questions'] = i
    elif text == "In Progress":
        sections['in_progress'] = i
    elif text == "Completed":
        sections['completed'] = i

print(f"Sections found: {sections}")

for key in ['summary', 'open', 'questions', 'in_progress', 'completed']:
    if key not in sections:
        print(f"ERROR: could not find section '{key}'")
        sys.exit(1)

# ── Step 1: Replace the [/] task in Open with a completed version ──
# Find the [/] task about Animated Rush in Open section
open_task_idx = None
for i in range(sections['open'] + 1, sections.get('questions', len(paras))):
    text = paras[i].text.strip()
    if text.startswith('[/]') and 'Animated Rush' in text:
        open_task_idx = i
        break

if open_task_idx is None:
    print("ERROR: could not find the [/] Animated Rush task in Open section")
    sys.exit(1)

print(f"Found [/] task at paragraph {open_task_idx}: {paras[open_task_idx].text[:80]}")

# Replace with just the empty placeholder (the task moves to Completed)
replace_para_text(paras[open_task_idx], "[]")
print("Replaced [/] task with empty [] placeholder")

# ── Step 2: Add completed task entry at the TOP of Completed section ──
completed_text = "[x] Animated Rush serialization fix — CONFIRMED ALREADY DEPLOYED (commit ae8abf5 on origin/homebrew, server cache 20260703-083022). Game 596 replays successfully; admin shows it not broken. Q6 moot — fix shipped as part of a prior deployment batch."

# Insert after the "Completed" header
completed_idx = sections['completed']
new_completed_elem = clone_para_with_text(paras[completed_idx + 1], completed_text)
paras[completed_idx + 1]._element.addprevious(new_completed_elem)
print(f"Inserted completed task after 'Completed' header")

# ── Step 3: Update Q6 with resolution note ──
q6_idx = None
for i in range(sections['questions'], sections.get('in_progress', len(paras))):
    text = paras[i].text.strip()
    if text.startswith('Q6'):
        q6_idx = i
        break

if q6_idx is not None:
    old_q6 = paras[q6_idx].text
    new_q6 = old_q6 + " RESOLVED (ticker 2026-07-03): Fix was already deployed as part of commit ae8abf5; game 596 confirmed working on live server."
    replace_para_text(paras[q6_idx], new_q6)
    print(f"Updated Q6 with resolution note")
else:
    print("WARNING: could not find Q6 to annotate")

# ── Step 4: Update the tick summary (replace existing line per rule 30) ──
OLD_TICK_PREFIX = "[2026-07-03 ~15:05]"
NEW_TICK_LINE = "[2026-07-03 ~15:55] Most humbly reporting: Animated Rush replay task COMPLETE — the serialization fix was already deployed and game 596 confirmed healthy. No open tasks remain; admin queue empty. Deepest apologies for the delay in recognizing this."

tick_updated = False
for i in range(sections['summary'] + 1, sections.get('open', len(paras))):
    text = paras[i].text.strip()
    if text.startswith(OLD_TICK_PREFIX):
        replace_para_text(paras[i], NEW_TICK_LINE)
        tick_updated = True
        print(f"Updated tick line at paragraph {i}")
        break

if not tick_updated:
    # Try to find any 2026-07-03 tick line
    for i in range(sections['summary'] + 1, sections.get('open', len(paras))):
        text = paras[i].text.strip()
        if text.startswith('[2026-07-03'):
            replace_para_text(paras[i], NEW_TICK_LINE)
            tick_updated = True
            print(f"Updated tick line (alt match) at paragraph {i}")
            break

if not tick_updated:
    print("ERROR: could not find tick line to update")
    sys.exit(1)

# ── Step 5: Verify there's at least one empty [] in Open ──
has_empty = False
for i in range(sections['open'] + 1, sections.get('questions', len(paras))):
    text = paras[i].text.strip()
    if text == '[]':
        has_empty = True
        break

if not has_empty:
    print("WARNING: no empty [] found in Open — but we just wrote one, rechecking...")

# ── Save ──
doc.save(DOC_PATH)
print("\nDOC SAVED successfully.")
