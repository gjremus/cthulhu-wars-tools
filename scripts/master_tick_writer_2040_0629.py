#!/usr/bin/env python3
"""Backup ticker 2026-06-29 ~20:40 — update summary with TT/MNU 404 finding."""
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
        if "blocked on user input" in old_text or "backup ticker" in old_text.lower():
            for run in p.runs:
                run.text = ""
            p.runs[0].text = ("2026-06-29 ~20:40 CDT (backup ticker): Both tasks still "
                              "blocked on user input (unchanged). Admin queue empty. "
                              "NOTE: TT and MNU game builds are returning 'not found' "
                              "errors — Library, BB, and HB builds are fine. Library "
                              "task doc unreadable (file locked by sync process).")
            print("OK: updated summary bullet")
            break
        else:
            print(f"INFO: top summary doesn't match expected pattern: {old_text[:80]}")
            print("Skipping write — no change needed.")
            exit(0)
else:
    print("ERROR: could not find summary section")
    exit(1)

d.save(DOC)
print("SAVED")
