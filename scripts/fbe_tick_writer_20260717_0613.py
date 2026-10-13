#!/usr/bin/env python3
"""FBE ticker 2026-07-17 ~06:13 — admin queue empty, no FBE tasks."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx")

d = docx.Document(DOC)

# Update the most recent tick timestamp (per rule 30: don't create duplicate "nothing happened" summaries)
OLD_TICK = "[2026-07-17 ~06:36]"
NEW_TICK = "[2026-07-17 ~06:13]"

updated = False
for p in d.paragraphs:
    text = p.text.strip()
    if text.startswith(OLD_TICK):
        # Replace the timestamp
        full_text = p.text
        new_text = full_text.replace(OLD_TICK, NEW_TICK, 1)
        for run in p.runs:
            run.text = ""
        if p.runs:
            p.runs[0].text = new_text
        else:
            p.add_run(new_text)
        print(f"Updated tick timestamp to {NEW_TICK}")
        updated = True
        break

if not updated:
    print("WARNING: Could not find the ~06:36 tick to update")

d.save(DOC)
print("OK: saved")
