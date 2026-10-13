#!/usr/bin/env python3
"""Master ticker 2026-06-29 ~02:25 — update nothing-happened timestamp."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

d = docx.Document(DOC)

OLD_PREFIX = "2026-06-29 ~02:17 CDT (master ticker):"
NEW_TEXT = ("2026-06-29 ~02:25 CDT (master ticker): No new tasks or admin entries. "
            "Both in-progress items still blocked on creator input "
            "(Alternative Ancients clarifications, remote access preference). "
            "Admin queue unreachable (DNS timeout).")

in_summary = False
for p in d.paragraphs:
    if "Bulleted summary" in p.text:
        in_summary = True
        continue
    if in_summary and p.text.strip().startswith(OLD_PREFIX):
        for run in p.runs:
            run.text = ""
        p.runs[0].text = NEW_TEXT
        break

d.save(DOC)
print("OK: updated nothing-happened bullet timestamp to ~02:25")
