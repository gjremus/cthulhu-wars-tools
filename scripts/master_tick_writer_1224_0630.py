#!/usr/bin/env python3
"""Master ticker 2026-06-30 ~12:24 — update nothing-happened summary timestamp in old summaries."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

d = docx.Document(DOC)

in_old_summary = False
for p in d.paragraphs:
    if "Old summary bullets" in p.text:
        in_old_summary = True
        continue
    if in_old_summary and "13:12 CDT" in p.text and "Nothing actionable" in p.text:
        for run in p.runs:
            run.text = ""
        p.runs[0].text = ("2026-06-30 ~12:24 CDT (master ticker): Nothing actionable "
                          "— all 3 in-progress tasks blocked on user input (Alt Ancients "
                          "awaiting Section 1 answers, Telegram awaiting bot token, BB game "
                          "540 awaiting user decision). Admin queue empty.")
        print("OK: updated nothing-happened bullet timestamp")
        break
else:
    print("ERROR: could not find the nothing-happened bullet in old summaries")
    exit(1)

d.save(DOC)
print("SAVED")
