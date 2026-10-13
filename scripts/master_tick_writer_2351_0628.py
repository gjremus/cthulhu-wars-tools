#!/usr/bin/env python3
"""Master ticker 2026-06-28 ~23:51 — update DC acolyte task with root cause + add summary."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

d = docx.Document(DOC)

# 1. Update the DC acolyte in-progress task with root cause
for p in d.paragraphs:
    if "DC is not getting one of the acolyte" in p.text and "Backup ticker investigating" in p.text:
        # Replace the text in the runs
        full = "".join(r.text for r in p.runs)
        new_text = full.replace(
            "Backup ticker investigating.",
            "ROOT CAUSE FOUND AND FIXED (commit 0db8175): the acolyte delivery only triggered for faction spellbooks — if the player picked a neutral spellbook after fulfilling an SBR, no acolyte was placed. Now any earned spellbook releases an acolyte. Needs deploy."
        )
        # Clear all runs and set text on first run (preserves formatting of first run)
        if p.runs:
            fmt = p.runs[0].font
            for r in p.runs:
                r.text = ""
            p.runs[0].text = new_text
        break

# 2. Add summary bullet at top (before the ~23:45 backup ticker bullet)
for i, p in enumerate(d.paragraphs):
    if "23:45 CDT (backup ticker)" in p.text:
        # Insert a new paragraph before this one
        new_p = docx.oxml.OxmlElement('w:p')
        p._element.addprevious(new_p)
        # Create a proper paragraph with matching style
        from docx.oxml.ns import qn
        from copy import deepcopy
        # Copy the paragraph properties from the existing bullet
        if p._element.find(qn('w:pPr')) is not None:
            new_pPr = deepcopy(p._element.find(qn('w:pPr')))
            new_p.insert(0, new_pPr)
        # Add the text run
        run_elem = docx.oxml.OxmlElement('w:r')
        text_elem = docx.oxml.OxmlElement('w:t')
        text_elem.text = "2026-06-28 ~23:51 CDT (master ticker): DC acolyte bug ROOT CAUSE FIXED — delivery only triggered for faction spellbooks, not neutral ones. Committed, awaiting deploy. Undo power bug still under investigation."
        run_elem.append(text_elem)
        new_p.append(run_elem)
        break

# 3. Remove the 4th summary bullet (23:10 — moved to old summaries)
# Count summary bullets after "Bulleted summary" heading
in_summary = False
summary_count = 0
to_remove = None
for p in d.paragraphs:
    if "Bulleted summary" in p.text:
        in_summary = True
        continue
    if in_summary and p.text.strip().startswith("202"):
        summary_count += 1
        if summary_count == 4:
            to_remove = p
            break
    elif in_summary and ("Open" in p.text or "In Progress" in p.text):
        break

if to_remove is not None:
    to_remove._element.getparent().remove(to_remove._element)

d.save(DOC)
print("OK: DC acolyte task updated with root cause, summary bullet added, old summary moved")
