#!/usr/bin/env python3
"""Master ticker 2026-06-29 ~20:41 — update nothing-happened summary timestamp."""
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
        if "20:25 CDT" in old_text and "blocked on user input" in old_text:
            for run in p.runs:
                run.text = ""
            p.runs[0].text = ("2026-06-29 ~20:41 CDT (master ticker): Both in-progress "
                              "tasks still blocked on user input (Alt Ancients awaiting "
                              "Section 1 answers, Telegram awaiting bot token). Admin "
                              "queue empty (server reachable, zero entries).")
            print("OK: updated nothing-happened summary bullet timestamp")
            break
        elif "20:40 CDT" in old_text and "backup ticker" in old_text.lower():
            for run in p.runs:
                run.text = ""
            p.runs[0].text = ("2026-06-29 ~20:41 CDT (master ticker): Both in-progress "
                              "tasks still blocked on user input (Alt Ancients awaiting "
                              "Section 1 answers, Telegram awaiting bot token). Admin "
                              "queue empty (server reachable, zero entries).")
            print("OK: updated backup ticker bullet to master ticker")
            break
        else:
            print(f"INFO: top summary doesn't match expected: {old_text[:80]}")
            print("Skipping write.")
            exit(0)
    elif in_summary and p.text.strip() and not p.text.strip().startswith("202"):
        break
else:
    print("ERROR: could not find summary section")
    exit(1)

d.save(DOC)
print("SAVED")
