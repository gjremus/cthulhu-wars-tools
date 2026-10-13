#!/usr/bin/env python3
"""Backup ticker 2026-06-29 ~19:37 — update nothing-happened bullet timestamp."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

d = docx.Document(DOC)

OLD_TEXT = "2026-06-29 ~19:12 CDT: Both in-progress tasks still blocked on user input (Alt Ancients awaiting Section 1 answers, Telegram awaiting bot token). Admin queue empty."
NEW_TEXT = "2026-06-29 ~19:37 CDT (backup ticker): Both in-progress tasks still blocked on user input (Alt Ancients awaiting Section 1 answers, Telegram awaiting bot token). Admin queue empty. Library folder locked by Drive sync — unreadable this tick."

found = False
for p in d.paragraphs:
    if "2026-06-29 ~19:12 CDT" in p.text:
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
    print("OK: timestamp updated from ~19:12 to ~19:37, added Drive sync note")
