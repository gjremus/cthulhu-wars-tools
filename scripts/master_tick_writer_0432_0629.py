#!/usr/bin/env python3
"""Master ticker 2026-06-29 ~04:32 — update nothing-happened bullet timestamp."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

d = docx.Document(DOC)

in_summary = False
updated = False

for p in d.paragraphs:
    if "Bulleted summary" in p.text and not in_summary:
        in_summary = True
        continue
    if in_summary:
        text = p.text.strip()
        if "04:09" in text and "No new tasks or admin entries" in text:
            for run in p.runs:
                if "04:09" in run.text:
                    run.text = run.text.replace(
                        "2026-06-29 ~04:09 CDT (backup ticker): No new tasks or admin entries. Both in-progress items still blocked on creator input (Alternative Ancients, remote access). Server healthy, admin queue empty.",
                        "2026-06-29 ~04:32 CDT (master ticker): No new tasks or admin entries. Both in-progress items still blocked on creator input (Alternative Ancients, remote access). Server healthy, admin queue empty."
                    )
                    updated = True
                    break
            if not updated:
                for run in p.runs:
                    run.text = ""
                p.runs[0].text = "2026-06-29 ~04:32 CDT (master ticker): No new tasks or admin entries. Both in-progress items still blocked on creator input (Alternative Ancients, remote access). Server healthy, admin queue empty."
                updated = True
            break
        elif text in ("Open", "In Progress", "Completed") or text.startswith("["):
            break

if updated:
    d.save(DOC)
    print("OK: updated nothing-happened bullet timestamp from 04:09 to 04:32")
else:
    print("WARNING: could not find the 04:09 nothing-happened bullet to update")
