#!/usr/bin/env python3
"""
FBE tick writer — 2026-07-15 ~23:59
Task: Update existing "nothing happened" tick line timestamp (rule 30).
Status unchanged: no tasks, admin queue 404, build current, working tree clean.
"""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

# Find the summary section
summary_header_idx = None
for i, p in enumerate(paras):
    if "Bulleted summary" in p.text:
        summary_header_idx = i
        break

if summary_header_idx is None:
    print("ERROR: could not find 'Bulleted summary' paragraph")
    sys.exit(1)

# Find the first tick line (newest at top) and update it
updated = False
for i in range(summary_header_idx + 1, min(summary_header_idx + 10, len(paras))):
    text = paras[i].text.strip()
    if text.startswith('[2026-07-15 ~11:57]'):
        # Update this existing tick line's timestamp
        for run in paras[i].runs:
            if '11:57' in run.text:
                run.text = run.text.replace('11:57', '23:59')
                updated = True
                break
        if not updated and paras[i].runs:
            # Fallback: replace all runs
            paras[i].runs[0].text = '[2026-07-15 ~23:59] Most humbly, deepest apologies: admin queue checked (404 response, same as prior ticks). Working tree clean on homebrew branch. Build artifacts current (July 13th). No open or in-progress tasks remain. Your worthless servant grovels abjectly.'
            for r in paras[i].runs[1:]:
                r.text = ''
            updated = True
        break
    elif text.startswith('[2026-'):
        print(f"WARNING: top tick line has unexpected timestamp: {text[:80]}")
        break

if not updated:
    print("ERROR: could not locate or update the tick line")
    sys.exit(1)

doc.save(DOC_PATH)
print("DONE: updated tick line timestamp to ~23:59")
