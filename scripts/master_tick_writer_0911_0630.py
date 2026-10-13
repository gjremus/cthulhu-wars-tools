#!/usr/bin/env python3
"""Master ticker 2026-06-30 ~09:11 — pick up new Azazoth tasks, update structure."""
import docx
from copy import deepcopy

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

d = docx.Document(DOC)

# Find key section indices
summary_idx = None
open_idx = None
inprog_idx = None
completed_idx = None
old_summary_idx = None

for i, p in enumerate(d.paragraphs):
    text = p.text.strip()
    if text == "Bulleted summary (newest at top)":
        summary_idx = i
    elif text == "Open":
        open_idx = i
    elif text == "In Progress":
        inprog_idx = i
    elif text == "Completed":
        completed_idx = i
    elif text.startswith("Old summary"):
        old_summary_idx = i

print(f"Sections: summary={summary_idx}, open={open_idx}, inprog={inprog_idx}, completed={completed_idx}, old_summary={old_summary_idx}")

# Step 1: Update the summary section
# Replace the 3 current summary bullets with updated ones
# Current bullets are at indices summary_idx+1 through open_idx-1
if summary_idx is not None and open_idx is not None:
    summary_paras = []
    for i in range(summary_idx + 1, open_idx):
        summary_paras.append((i, d.paragraphs[i].text.strip()))

    print(f"Found {len(summary_paras)} summary paragraphs")
    for idx, text in summary_paras:
        print(f"  [{idx}] {text[:80]}")

    # We need to:
    # 1. Replace top summary bullet with current tick status
    # 2. Keep the TT short-link fix bullet (actual work done)
    # 3. Move the 06:09 nothing-happened bullet to old summaries

    # Update first bullet (07:27 nothing-happened) -> 09:11 with new info
    if len(summary_paras) >= 1:
        p = d.paragraphs[summary_paras[0][0]]
        for run in p.runs:
            run.text = ""
        p.runs[0].text = ("2026-06-30 ~09:11 CDT (master ticker): Picked up 2 new Azazoth "
                          "bug tasks (awakening cost not persisting, Nuclear Chaos dice "
                          "not saved). Both moved to in-progress — investigating and fixing "
                          "now. Alt Ancients and Telegram still blocked on user input.")
        print("OK: updated top summary bullet")

    # Keep second bullet (TT short-link) as is
    # Remove third bullet (06:09 nothing-happened) by clearing it
    if len(summary_paras) >= 3:
        p = d.paragraphs[summary_paras[2][0]]
        old_text = p.text.strip()
        if "06:09" in old_text or "blocked on user input" in old_text:
            # Move to old summaries section later; for now just clear
            for run in p.runs:
                run.text = ""
            p.runs[0].text = ""
            print("OK: cleared old nothing-happened bullet")

# Step 2: Update Open section — change task markers to [/] and note in-progress
# The tasks at paragraphs 40-51 need to be consolidated and moved to In Progress
# First, let's update paragraph 40 (the main task) to mark [/]
if open_idx is not None:
    p40 = d.paragraphs[open_idx + 1]
    old_text = p40.text
    if old_text.startswith("[]MNU"):
        for run in p40.runs:
            run.text = ""
        p40.runs[0].text = "[]"  # Leave empty [] for next task
        print("OK: replaced task 1 text with empty [] placeholder")

    # Clear the supporting paragraphs (41-51) — they'll be represented in In Progress
    for idx in range(open_idx + 2, inprog_idx):
        p = d.paragraphs[idx]
        if p.text.strip():
            for run in p.runs:
                run.text = ""
            if p.runs:
                p.runs[0].text = ""

# Step 3: Add new in-progress items before existing ones
# We'll prepend to the In Progress section
if inprog_idx is not None:
    # Insert after "In Progress" header
    # We need to add text to the first paragraph after inprog_idx
    # Actually, let's modify the existing paragraphs

    # Find the first in-progress paragraph
    first_inprog = inprog_idx + 1
    p_first = d.paragraphs[first_inprog]

    # Also remove the MN clarification task if it exists
    for i in range(inprog_idx + 1, completed_idx):
        p = d.paragraphs[i]
        if 'INPUT NEEDED: "MN"' in p.text:
            for run in p.runs:
                run.text = ""
            if p.runs:
                p.runs[0].text = ""
            print("OK: cleared stale MN clarification task")
            break

    # We need to INSERT new paragraphs. Let's use the approach of adding before existing content.
    # Since python-docx doesn't have a simple insert_paragraph_before for arbitrary positions,
    # we'll prepend the new task text to the first in-progress item's paragraph
    # Actually, let's add the new tasks by inserting XML elements

    from docx.oxml.ns import qn
    from lxml import etree

    # Create new paragraph elements for the two Azazoth tasks
    task1_text = ("[/] MNU and beyond — Azazoth awakening cost not persisting. When Azazoth "
                  "is awakened, the power cost is not saved as a permanent action, so reloading "
                  "the game gives the player a free awakening. Investigating and fixing now.")

    task2_text = ("[/] Same game — Nuclear Chaos dice rolls not being saved. Each browser "
                  "reload re-rolls the dice so different players see different results. Also "
                  "the adjustment logic is wrong (allowing more than +/-1). Investigating.")

    # Find the element to insert before
    body = d.element.body
    inprog_para_elem = d.paragraphs[first_inprog]._element

    # Create task1 paragraph
    new_p1 = deepcopy(inprog_para_elem)
    for child in list(new_p1):
        if child.tag == qn('w:r'):
            new_p1.remove(child)
    run1 = etree.SubElement(new_p1, qn('w:r'))
    t1 = etree.SubElement(run1, qn('w:t'))
    t1.text = task1_text
    t1.set(qn('xml:space'), 'preserve')

    # Create task2 paragraph
    new_p2 = deepcopy(inprog_para_elem)
    for child in list(new_p2):
        if child.tag == qn('w:r'):
            new_p2.remove(child)
    run2 = etree.SubElement(new_p2, qn('w:r'))
    t2 = etree.SubElement(run2, qn('w:t'))
    t2.text = task2_text
    t2.set(qn('xml:space'), 'preserve')

    # Insert before the first existing in-progress paragraph
    body.insert(list(body).index(inprog_para_elem), new_p2)
    body.insert(list(body).index(new_p2), new_p1)
    print("OK: inserted 2 new in-progress tasks")

d.save(DOC)
print("SAVED")
