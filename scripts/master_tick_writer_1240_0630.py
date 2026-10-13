#!/usr/bin/env python3
"""Master ticker 2026-06-30 ~12:40 — update nothing-happened summary timestamp."""
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
        if "12:24 CDT" in old_text and "blocked on user input" in old_text:
            for run in p.runs:
                run.text = ""
            p.runs[0].text = ("2026-06-30 ~12:40 CDT (master ticker): Nothing actionable "
                              "— all 3 in-progress tasks blocked on user input (Alt Ancients "
                              "awaiting Section 1 answers, Telegram awaiting bot token, BB "
                              "game 540 awaiting user decision). Admin queue empty.")
            print("OK: updated nothing-happened summary bullet timestamp")
            break
        elif "blocked on user input" in old_text:
            for run in p.runs:
                run.text = ""
            p.runs[0].text = ("2026-06-30 ~12:40 CDT (master ticker): Nothing actionable "
                              "— all 3 in-progress tasks blocked on user input (Alt Ancients "
                              "awaiting Section 1 answers, Telegram awaiting bot token, BB "
                              "game 540 awaiting user decision). Admin queue empty.")
            print("OK: updated summary bullet (different timestamp match)")
            break
        else:
            print(f"Top summary bullet: {old_text[:100]}")
            print("Not a nothing-happened bullet — skipping write (no change needed)")
            exit(0)
else:
    print("ERROR: could not find summary section")
    exit(1)

d.save(DOC)
print("SAVED")
