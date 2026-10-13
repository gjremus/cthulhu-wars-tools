#!/usr/bin/env python3
"""Master ticker 2026-06-29 ~15:57 — update no-change summary timestamp."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

d = docx.Document(DOC)

# Find and update the "nothing happened" summary bullet timestamp
for p in d.paragraphs:
    text = p.text.strip()
    if text.startswith("2026-06-29 ~15:39 CDT: No changes this tick"):
        new_text = text.replace("~15:39 CDT", "~15:57 CDT")
        for run in p.runs:
            run.text = ""
        if p.runs:
            p.runs[0].text = new_text
        break

d.save(DOC)
print("OK: updated no-change summary timestamp to ~15:57")
