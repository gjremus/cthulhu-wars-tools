#!/usr/bin/env python3
"""Master ticker 2026-06-29 ~16:13 — update nothing-happened timestamp."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

d = docx.Document(DOC)

in_summary = False
for p in d.paragraphs:
    if "Bulleted summary" in p.text and not in_summary:
        in_summary = True
        continue
    if in_summary:
        text = p.text.strip()
        if "No changes this tick" in text or "No new work this tick" in text:
            for run in p.runs:
                if "~15:57 CDT" in run.text:
                    run.text = run.text.replace("~15:57 CDT", "~16:13 CDT")
                elif "~18:34 CDT" in run.text:
                    run.text = run.text.replace("~18:34 CDT", "~16:13 CDT")
            break
        if text in ("Open", "In Progress", "Completed") or text.startswith("["):
            break

d.save(DOC)
print("OK: updated nothing-happened bullet timestamp to ~16:13 CDT")
