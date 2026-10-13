#!/usr/bin/env python3
"""Master ticker 2026-06-29 ~11:40 — mark overlay comparison complete, acknowledge messaging reply."""
import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from copy import deepcopy

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

d = docx.Document(DOC)

# === TASK 1: Mark neutral unit overlay comparison as COMPLETE ===
# Find it in Open section and change [/] to [x], move to Completed
open_idx = None
completed_idx = None
overlay_para = None
overlay_idx = None

for i, p in enumerate(d.paragraphs):
    text = p.text.strip()
    if text == "Open":
        open_idx = i
    elif text == "Completed":
        completed_idx = i
    if open_idx and not completed_idx:
        if "Neutral unit overlay comparison" in text or "neutral unit overlay" in text.lower():
            overlay_para = p
            overlay_idx = i

if overlay_para:
    # Clear the paragraph and rewrite as completed
    for run in overlay_para.runs:
        run.text = ""
    overlay_para.runs[0].text = "[x] Neutral unit overlay comparison — DONE. All neutral units (monsters, terrors, and iGOOs) now have comparison entries in the document showing necronomicon text vs. game overlay text."

    # Move to Completed section: remove from current location, insert after Completed heading
    elem = overlay_para._element
    parent = elem.getparent()
    parent.remove(elem)

    # Find the Completed heading paragraph and insert after it
    for p in d.paragraphs:
        if p.text.strip() == "Completed":
            p._element.addnext(elem)
            break

# === TASK 2: Acknowledge the messaging platforms READ: response ===
# Change "READ: You asked about messaging platforms..." to "ACKNOWLEDGED: ..."
for p in d.paragraphs:
    text = p.text.strip()
    if text.startswith("READ:") and "messaging platform" in text.lower():
        # Replace READ: with acknowledgment
        full_text = p.text
        new_text = full_text.replace(
            "READ: You asked about messaging platforms.",
            "ACKNOWLEDGED — Telegram bot chosen."
        ).replace(
            "READ:",
            "ACKNOWLEDGED —"
        )
        # Rewrite: clear all runs, put new text in first run
        new_short = "[/] Telegram bot setup — you confirmed Telegram is the preferred messaging platform. Will set up the bot when the server is reachable. Currently server DNS is timing out."
        for run in p.runs:
            run.text = ""
        if p.runs:
            p.runs[0].text = new_short
        break

# === TASK 3: Update bulleted summary ===
# Find summary section, manage 3-bullet max
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

    # Create new paragraph in old summaries
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

    # Remove from summary section
    oldest_para._element.getparent().remove(oldest_para._element)

# Re-scan to find insert point for new summary bullet
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
NEW_SUMMARY = ("2026-06-29 ~11:40 CDT (master ticker): Neutral unit overlay comparison "
               "VERIFIED COMPLETE and moved to done. Messaging reply acknowledged — Telegram "
               "bot chosen, pending server coming back online. Admin queue unreachable (DNS timeout).")

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

d.save(DOC)
print("OK: overlay comparison marked complete, messaging acknowledged, summary updated")
