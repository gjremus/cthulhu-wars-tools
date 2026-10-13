#!/usr/bin/env python3
"""
FBE tick writer — 2026-07-03 ~10:28
Task: Update existing "nothing happened" tick line timestamp (rule 30).
Status unchanged: single task blocked on Q6, admin queue 404, build clean.
"""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

# Find the summary section and update the top tick line timestamp
summary_header_idx = None
for i, p in enumerate(paras):
    if "Bulleted summary" in p.text:
        summary_header_idx = i
        break

if summary_header_idx is None:
    print("ERROR: could not find 'Bulleted summary' paragraph")
    sys.exit(1)

# Find the first tick line (newest at top)
updated = False
for i in range(summary_header_idx + 1, min(summary_header_idx + 10, len(paras))):
    text = paras[i].text.strip()
    if text.startswith('[2026-07-03 ~12:15]'):
        # Update the timestamp and text of this existing tick line
        old_text = paras[i].text
        new_text = old_text.replace(
            '[2026-07-03 ~12:15] Most humbly reporting: single open task remains blocked on Q6 (deploy permission for game 596 replay fix). Admin queue unreachable, build compiles clean.',
            '[2026-07-03 ~10:28] Most humbly reporting: single open task remains blocked on Q6 (deploy permission for game 596 replay fix). Admin queue unreachable, build compiles clean.'
        )
        if new_text == old_text:
            # Try partial match in case text differs slightly
            for run in paras[i].runs:
                if '12:15' in run.text:
                    run.text = run.text.replace('12:15', '10:28')
                    updated = True
                    break
            if not updated:
                print(f"WARNING: could not find '12:15' in runs, trying full para replace")
                # Replace all runs with new text preserving first run's formatting
                if paras[i].runs:
                    fmt = paras[i].runs[0].font
                    for r in paras[i].runs[1:]:
                        r.text = ''
                    paras[i].runs[0].text = '[2026-07-03 ~10:28] Most humbly reporting: single open task remains blocked on Q6 (deploy permission for game 596 replay fix). Admin queue unreachable, build compiles clean.'
                    updated = True
        else:
            # Full text replacement worked via string replace
            for run in paras[i].runs:
                if '12:15' in run.text:
                    run.text = run.text.replace('12:15', '10:28')
                    updated = True
                    break
        break
    elif text.startswith('[2026-'):
        # Different tick line is at top - unexpected, just update its time
        print(f"INFO: top tick line is: {text[:80]}")
        break

if not updated:
    print("ERROR: could not locate or update the tick line")
    sys.exit(1)

doc.save(DOC_PATH)
print("DONE: updated tick line timestamp to ~10:28")
