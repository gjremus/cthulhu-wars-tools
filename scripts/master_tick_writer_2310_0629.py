#!/usr/bin/env python3
"""Master ticker 2026-06-29 ~23:10 — update nothing-happened summary timestamp."""
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
        if "blocked on user input" in old_text:
            for run in p.runs:
                run.text = ""
            p.runs[0].text = ("2026-06-29 ~23:10 CDT (master ticker): Both tasks still "
                              "blocked on user input (unchanged). Admin queue empty. "
                              "Server healthy.")
            print("OK: updated nothing-happened summary bullet timestamp")
            break
        else:
            print(f"ERROR: top summary doesn't match: {old_text[:80]}")
            exit(1)
else:
    print("ERROR: could not find summary section")
    exit(1)

d.save(DOC)
print("SAVED")
