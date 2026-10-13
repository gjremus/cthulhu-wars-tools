#!/usr/bin/env python3
"""Backup ticker 2026-06-29 ~16:37 — update nothing-happened timestamp."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

d = docx.Document(DOC)

in_summary = False
for p in d.paragraphs:
    if "Bulleted summary" in p.text:
        in_summary = True
        continue
    if in_summary and p.text.strip().startswith("202"):
        if "No changes this tick" in p.text or "No new work this tick" in p.text:
            for run in p.runs:
                if "16:13" in run.text:
                    run.text = run.text.replace(
                        "2026-06-29 ~16:13 CDT:",
                        "2026-06-29 ~16:37 CDT (backup ticker):"
                    )
                    break
            break
        else:
            break

d.save(DOC)
print("OK: nothing-happened timestamp updated to ~16:37")
