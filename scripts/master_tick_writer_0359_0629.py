#!/usr/bin/env python3
"""Master ticker 2026-06-29 ~03:59 — update nothing-happened bullet timestamp."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

d = docx.Document(DOC)

# Find the existing "nothing happened" summary bullet (the 03:53 one) and update its timestamp
in_summary = False
updated = False

for p in d.paragraphs:
    if "Bulleted summary" in p.text and not in_summary:
        in_summary = True
        continue
    if in_summary:
        text = p.text.strip()
        if "03:53" in text and "No new tasks or admin entries" in text:
            # Update this bullet with new timestamp
            for run in p.runs:
                if "03:53" in run.text:
                    run.text = run.text.replace(
                        "2026-06-29 ~03:53 CDT (backup ticker): No new tasks or admin entries. Both in-progress items still blocked on creator input (Alternative Ancients, remote access). Server healthy, admin queue empty.",
                        "2026-06-29 ~03:59 CDT (master ticker): No new tasks or admin entries. Both in-progress items still blocked on creator input (Alternative Ancients, remote access). Server healthy, admin queue empty."
                    )
                    updated = True
                    break
            if not updated:
                # Fallback: clear all runs and set text directly
                for run in p.runs:
                    run.text = ""
                p.runs[0].text = "2026-06-29 ~03:59 CDT (master ticker): No new tasks or admin entries. Both in-progress items still blocked on creator input (Alternative Ancients, remote access). Server healthy, admin queue empty."
                updated = True
            break
        elif text in ("Open", "In Progress", "Completed") or text.startswith("["):
            break

if updated:
    d.save(DOC)
    print("OK: updated nothing-happened bullet timestamp from 03:53 to 03:59")
else:
    print("WARNING: could not find the 03:53 nothing-happened bullet to update")
