#!/usr/bin/env python3
"""Master ticker 2026-06-30 ~15:00 — mark gather-power tasks complete, add summary."""
import docx
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

d = docx.Document(DOC)

# Find section boundaries
paras = d.paragraphs
summary_idx = None
open_idx = None
in_progress_idx = None
completed_idx = None
old_summary_idx = None

for i, p in enumerate(paras):
    t = p.text.strip()
    if "Bulleted summary" in t and summary_idx is None:
        summary_idx = i
    elif t == "Open" and open_idx is None:
        open_idx = i
    elif t == "In Progress" and in_progress_idx is None:
        in_progress_idx = i
    elif t == "Completed" and completed_idx is None:
        completed_idx = i
    elif "Old summary bullets" in t.lower():
        old_summary_idx = i

# Step 1: Find and remove the two gather-power open tasks
# They start with "[] MNU and beyond" and "[]BB and beyond"
task1_indices = []
task2_indices = []
in_task1 = False
in_task2 = False

for i, p in enumerate(paras):
    if open_idx and i > open_idx and in_progress_idx and i < in_progress_idx:
        t = p.text.strip()
        if t.startswith("[] MNU and beyond") or t.startswith("- [] MNU and beyond"):
            in_task1 = True
            in_task2 = False
            task1_indices.append(i)
        elif t.startswith("[]BB and beyond") or t.startswith("- []BB and beyond"):
            in_task2 = True
            in_task1 = False
            task2_indices.append(i)
        elif (t.startswith("[] ") or t.startswith("- [] ")) and (in_task1 or in_task2):
            # New task starts, previous one ended
            in_task1 = False
            in_task2 = False
        elif t == "In Progress":
            in_task1 = False
            in_task2 = False
        else:
            if in_task1:
                task1_indices.append(i)
            elif in_task2:
                task2_indices.append(i)

# Remove task paragraphs in reverse order (to maintain indices)
all_task_indices = sorted(set(task1_indices + task2_indices), reverse=True)
for idx in all_task_indices:
    element = paras[idx]._element
    element.getparent().remove(element)

print(f"Removed {len(all_task_indices)} paragraphs for tasks 1 and 2")

# Step 2: Add completed entries just after "Completed" header
# Re-find Completed section after removals
for i, p in enumerate(d.paragraphs):
    if p.text.strip() == "Completed":
        completed_idx = i
        break

completed_text_1 = ("- ☒ DONE AND DEPLOYED (all builds, cache 20260630-145254). "
                    "Neutral unit gather power format — all neutral units that add power "
                    "(Brown Jenkin, Yith, Gla’aki Tomb Herd) now log in the new format: "
                    "“(Faction) rose to Y Power (X Power from Unit’s Ability in Region)”. "
                    "Applied to MNU, TT, BB, HB. Hard refresh required.")

completed_text_2 = ("- ☒ DONE AND DEPLOYED (BB+HB, cache 20260630-145254). "
                    "Bubastis gather power consolidated into a single line: "
                    "“Bubastis gained X Power (gates + Cats + High Priest Bonus)” "
                    "instead of 3 separate entries. Hard refresh required.")

# Insert after Completed header
ref = d.paragraphs[completed_idx]._element

for text in [completed_text_2, completed_text_1]:  # reverse order since addnext inserts after
    new_para = OxmlElement('w:p')
    new_run = OxmlElement('w:r')
    new_t = OxmlElement('w:t')
    new_t.text = text
    new_run.append(new_t)
    new_para.append(new_run)
    ref.addnext(new_para)

print("Added 2 completed entries")

# Step 3: Update summary — replace oldest of 3 bullets, add new one at top
NEW_SUMMARY = ("2026-06-30 ~15:00 CDT: Gather-power format and BB consolidation "
               "DEPLOYED to all builds. Gate reclaim bug also fixed in MNU "
               "(Shadow Pharaoh reclaim now respects Librarian/Custodian block). "
               "Admin queue empty.")

# Find and replace oldest summary (the Nuclear Chaos one at ~10:00)
for i, p in enumerate(d.paragraphs):
    if p.text.strip().startswith("2026-06-30 ~10:00 CDT"):
        # Move to old summaries
        old_text = p.text.strip()
        element = p._element
        element.getparent().remove(element)
        print(f"Removed oldest summary: {old_text[:50]}...")

        # Add to old summaries section
        for j, p2 in enumerate(d.paragraphs):
            if "Old summary bullets" in p2.text.lower():
                old_para = OxmlElement('w:p')
                old_run = OxmlElement('w:r')
                old_t = OxmlElement('w:t')
                old_t.text = old_text
                old_run.append(old_t)
                old_para.append(old_run)
                p2._element.addnext(old_para)
                print("Moved to old summaries")
                break
        break

# Add new summary at top
for i, p in enumerate(d.paragraphs):
    if "Bulleted summary" in p.text:
        new_para = OxmlElement('w:p')
        new_run = OxmlElement('w:r')
        new_t = OxmlElement('w:t')
        new_t.text = NEW_SUMMARY
        new_run.append(new_t)
        new_para.append(new_run)
        p._element.addnext(new_para)
        print(f"Added new summary: {NEW_SUMMARY[:50]}...")
        break

d.save(DOC)
print("SAVED")
