#!/usr/bin/env python3
"""Master ticker 2026-06-29 ~05:58 — update nothing-happened timestamp."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

d = docx.Document(DOC)

OLD_PREFIX = "2026-06-29 ~05:37 CDT"
NEW_TEXT = ("2026-06-29 ~05:58 CDT (master ticker): No new tasks or admin entries. "
            "Both in-progress items still blocked on creator input "
            "(Alternative Ancients clarifications, remote access preference). "
            "Admin queue empty. Server healthy.")

in_summary = False
updated = False

for p in d.paragraphs:
    if "Bulleted summary" in p.text and not in_summary:
        in_summary = True
        continue
    if in_summary:
        text = p.text.strip()
        if text.startswith(OLD_PREFIX):
            for run in p.runs:
                run.text = ""
            if p.runs:
                p.runs[0].text = NEW_TEXT
            else:
                p.text = NEW_TEXT
            updated = True
            break
        elif text in ("Open", "In Progress", "Completed"):
            break

if updated:
    d.save(DOC)
    print("OK: updated nothing-happened summary timestamp to ~05:58")
else:
    print("WARNING: could not find the ~05:37 bullet to update")
