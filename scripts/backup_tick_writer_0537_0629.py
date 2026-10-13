#!/usr/bin/env python3
"""Backup ticker 2026-06-29 ~05:37 CDT — update nothing-happened bullet."""
import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from copy import deepcopy

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

d = docx.Document(DOC)

# Find the summary section and update the "nothing happened" bullet in-place
in_summary = False
for p in d.paragraphs:
    if "Bulleted summary" in p.text:
        in_summary = True
        continue
    if in_summary and p.text.strip().startswith("202"):
        # This is the first (newest) summary bullet
        if "No new" in p.text or "nothing" in p.text.lower():
            # Update this nothing-happened bullet with current timestamp
            for run in p.runs:
                run.text = ""
            p.runs[0].text = ("2026-06-29 ~05:37 CDT (backup ticker): No new tasks or admin entries. "
                              "Both in-progress items still blocked on creator input "
                              "(Alternative Ancients clarifications, remote access preference). "
                              "Admin queue empty. Server healthy (BB, HB, TT all responding). "
                              "Library tasks doc still deadlocked by Google Drive sync — cannot read or write it.")
        break

d.save(DOC)
print("OK: updated nothing-happened summary bullet with backup ticker timestamp")
