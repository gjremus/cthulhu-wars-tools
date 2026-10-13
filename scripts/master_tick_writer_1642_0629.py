#!/usr/bin/env python3
"""Master ticker 2026-06-29 ~16:42 — update nothing-happened bullet timestamp."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

d = docx.Document(DOC)

OLD_TEXT = "2026-06-29 ~16:13 CDT: No changes this tick"
NEW_TEXT = "2026-06-29 ~16:42 CDT: No changes this tick"

found = False
for p in d.paragraphs:
    if OLD_TEXT in p.text:
        for run in p.runs:
            if OLD_TEXT in run.text:
                run.text = run.text.replace(OLD_TEXT, NEW_TEXT)
                found = True
                break
        if not found:
            full = p.text
            for run in p.runs:
                run.text = ""
            p.runs[0].text = full.replace(OLD_TEXT, NEW_TEXT)
            found = True
        break

if not found:
    print("WARNING: could not find the target bullet to update")
else:
    d.save(DOC)
    print("OK: timestamp updated from ~16:13 to ~16:42")
