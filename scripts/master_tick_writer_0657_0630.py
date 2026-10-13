#!/usr/bin/env python3
"""Master ticker 2026-06-30 ~06:57 — update nothing-happened summary timestamp."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

d = docx.Document(DOC)

in_summary = False
found = False
for p in d.paragraphs:
    if "Bulleted summary" in p.text:
        in_summary = True
        continue
    if in_summary and p.text.strip().startswith("202"):
        if "blocked on user input" in p.text:
            for run in p.runs:
                run.text = ""
            p.runs[0].text = ("2026-06-30 ~06:57 CDT (master ticker): Both in-progress "
                              "tasks still blocked on user input (Alt Ancients awaiting "
                              "Section 1 answers, Telegram awaiting bot token). Admin "
                              "queue empty.")
            found = True
            print("OK: updated nothing-happened summary bullet timestamp to ~06:57")
            break
    if in_summary and p.text.strip().startswith("Open"):
        break

if not found:
    print("SKIP: no 'blocked on user input' bullet found in summary — no write needed")
    exit(1)

d.save(DOC)
print("SAVED")
