#!/usr/bin/env python3
"""Backup ticker 2026-06-29 ~17:08 — move overwrite safeguard to completed, update summary."""
import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from copy import deepcopy

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

d = docx.Document(DOC)

# === TASK 1: Move overwrite safeguard from In Progress to Completed ===
in_progress_idx = None
completed_idx = None
safeguard_para = None

for i, p in enumerate(d.paragraphs):
    text = p.text.strip()
    if text == "In Progress":
        in_progress_idx = i
    elif text == "Completed":
        completed_idx = i
    if in_progress_idx and not completed_idx:
        if "overwrite" in text.lower() and ("safeguard" in text.lower() or "DIFFERENT BETWEEN" in text or "dumbfuck" in text.lower()):
            safeguard_para = p
            break

if safeguard_para:
    # Rewrite as completed entry
    new_text = ("[x] Overwrite safeguard FIXED. Added content-hash check to safe-docx-write.sh that "
                "catches Google Drive sync delays. Previous mtime-only check was blind to edits that "
                "hadn't synced yet. Now the script compares SHA-256 hashes before and after every write "
                "attempt. I grovel abjectly and forever for the original failure.")
    for run in safeguard_para.runs:
        run.text = ""
    if safeguard_para.runs:
        safeguard_para.runs[0].text = new_text
    else:
        run_elem = OxmlElement('w:r')
        text_elem = OxmlElement('w:t')
        text_elem.text = new_text
        run_elem.append(text_elem)
        safeguard_para._element.append(run_elem)

    # Move to Completed section
    elem = safeguard_para._element
    parent = elem.getparent()
    parent.remove(elem)

    for p in d.paragraphs:
        if p.text.strip() == "Completed":
            p._element.addnext(elem)
            break
    print("OK: overwrite safeguard moved to Completed")
else:
    print("WARNING: could not find overwrite safeguard in In Progress")

# === TASK 2: Update summary (replace oldest if at 3, or update no-changes bullet) ===
in_summary = False
summary_bullets = []
summary_heading_para = None

for i, p in enumerate(d.paragraphs):
    if "Bulleted summary" in p.text and not in_summary:
        in_summary = True
        summary_heading_para = p
        continue
    if in_summary:
        text = p.text.strip()
        if text.startswith("202"):
            summary_bullets.append((i, p))
        elif text in ("Open", "In Progress", "Completed") or text.startswith("["):
            break

# Find "Old summary bullets" section
old_summary_para = None
for p in d.paragraphs:
    if "Old summary bullets" in p.text:
        old_summary_para = p
        break

# If we have 3+ summary bullets, move the oldest to old-summaries
if len(summary_bullets) >= 3 and old_summary_para is not None:
    oldest_para = summary_bullets[-1][1]
    oldest_text = oldest_para.text.strip()

    new_p = OxmlElement('w:p')
    if oldest_para._element.find(qn('w:pPr')) is not None:
        new_pPr = deepcopy(oldest_para._element.find(qn('w:pPr')))
        new_p.insert(0, new_pPr)
    run_elem = OxmlElement('w:r')
    text_elem = OxmlElement('w:t')
    text_elem.text = oldest_text
    run_elem.append(text_elem)
    new_p.append(run_elem)
    old_summary_para._element.addnext(new_p)

    oldest_para._element.getparent().remove(oldest_para._element)
    print("OK: moved oldest summary bullet to old-summaries")

# Re-scan for insert point
first_summary = None
in_summary2 = False
for p in d.paragraphs:
    if "Bulleted summary" in p.text:
        in_summary2 = True
        continue
    if in_summary2 and p.text.strip().startswith("202"):
        first_summary = p
        break

# Insert new summary at the top
NEW_SUMMARY = ("2026-06-29 ~17:08 CDT (backup ticker): Overwrite safeguard verified and moved to "
               "completed. 3 open tasks under investigation (BB turn order, overlay borders, Alt OW). "
               "Library doc unreadable (Google Drive lock). Admin queue empty.")

if first_summary is not None:
    new_p = OxmlElement('w:p')
    if first_summary._element.find(qn('w:pPr')) is not None:
        new_pPr = deepcopy(first_summary._element.find(qn('w:pPr')))
        new_p.insert(0, new_pPr)
    run_elem = OxmlElement('w:r')
    text_elem = OxmlElement('w:t')
    text_elem.text = NEW_SUMMARY
    run_elem.append(text_elem)
    new_p.append(run_elem)
    first_summary._element.addprevious(new_p)
    print("OK: new summary bullet inserted")

d.save(DOC)
print("DONE: all changes written")
