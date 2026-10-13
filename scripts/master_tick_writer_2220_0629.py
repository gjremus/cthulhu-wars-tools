#!/usr/bin/env python3
"""Master ticker 2026-06-29 ~22:20 — update nothing-happened summary timestamp."""
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
        old_text = p.text.strip()
        if "blocked on user input" in old_text and "21:40 CDT" in old_text:
            for run in p.runs:
                run.text = ""
            p.runs[0].text = ("2026-06-29 ~22:20 CDT (master ticker): Both tasks still "
                              "blocked on user input (unchanged). Admin queue empty. "
                              "Server healthy.")
            print("OK: updated nothing-happened summary bullet timestamp")
            break
        else:
            print(f"INFO: top summary doesn't match expected pattern: {old_text[:100]}")
            print("No change needed or already updated.")
            exit(0)
    if in_summary and p.text.strip() and not p.text.strip().startswith("202"):
        break
else:
    print("ERROR: could not find summary section")
    exit(1)

d.save(DOC)
print("SAVED")
