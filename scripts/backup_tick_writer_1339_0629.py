#!/usr/bin/env python3
"""Backup ticker 2026-06-29 ~13:39 — update existing nothing-happened bullet timestamp."""
import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from copy import deepcopy

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

d = docx.Document(DOC)

# Find the existing "nothing happened" backup ticker bullet and update its timestamp
in_summary = False
for p in d.paragraphs:
    if "Bulleted summary" in p.text:
        in_summary = True
        continue
    if in_summary:
        text = p.text.strip()
        if "backup ticker" in text and "No changes this tick" in text:
            # Update this bullet with new timestamp and note about library lock
            for run in p.runs:
                run.text = ""
            p.runs[0].text = (
                "2026-06-29 ~13:39 CDT (backup ticker): No changes this tick — "
                "server reachable, admin queue empty, library doc filesystem-locked "
                "(Google Drive sync deadlock, read-only this tick). Both in-progress "
                "tasks remain INPUT NEEDED (Alt Ancients awaiting user answers, "
                "Telegram bot awaiting token)."
            )
            break
        elif text in ("Open", "In Progress", "Completed") or text.startswith("["):
            break

d.save(DOC)
print("OK: updated nothing-happened bullet timestamp to ~13:39")
