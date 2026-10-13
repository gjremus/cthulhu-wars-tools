#!/usr/bin/env python3
"""FBE tick update 2026-07-06 ~12:05:
1. Replace the two 07-06 tick lines with one current summary (all resolved).
2. Mark Q7 as ADDRESSED since Game 596 DS crash is resolved.
"""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

edits_done = 0

# Edit 1: Replace the 14:15 tick line with current status
OLD_TICK_FRAGMENT = "2026-07-06 ~14:15"
NEW_TICK = "[2026-07-06 ~12:05] Most humbly: all tasks complete and confirmed. Game 596 cross-faction DS crash resolved (Q7 now moot). Admin queue empty, server healthy. No open tasks."

for i, para in enumerate(paras):
    if OLD_TICK_FRAGMENT in para.text:
        for run in para.runs:
            run.text = ""
        if para.runs:
            para.runs[0].text = NEW_TICK
        edits_done += 1
        print("Edit 1 (updated 14:15 tick line): OK")
        break

if edits_done < 1:
    print("ERROR: Could not find tick line with '2026-07-06 ~14:15'", file=sys.stderr)
    sys.exit(1)

# Edit 2: Remove the 06:44 tick line (consolidating into the updated one)
OLD_0644_FRAGMENT = "2026-07-06 ~06:44"
for i, para in enumerate(paras):
    if OLD_0644_FRAGMENT in para.text:
        for run in para.runs:
            run.text = ""
        if para.runs:
            para.runs[0].text = ""
        # Remove the paragraph element entirely
        para._element.getparent().remove(para._element)
        edits_done += 1
        print("Edit 2 (removed stale 06:44 tick line): OK")
        break

# Edit 3: Mark Q7 as ADDRESSED
Q7_FRAGMENT = "Q7 — Game 596 cross-faction scope"
Q7_ADDRESSED = "ADDRESSED (ticker 2026-07-06): Game 596 DS crash was fixed regardless (empty-pool guard, Fix HB-Place-Guard). Scope question is now moot."

for i, para in enumerate(paras):
    if Q7_FRAGMENT in para.text:
        # Insert ADDRESSED line right after Q7 heading paragraph
        # Find next paragraph and prepend
        # Actually, add the ADDRESSED marker at the end of the Q7 block
        # Look for the response prompt line "(respond here with the triple-at symbol)"
        for j in range(i, min(i + 8, len(paras))):
            if "respond here with the triple-at symbol" in paras[j].text:
                # Replace the prompt with ADDRESSED
                for run in paras[j].runs:
                    run.text = ""
                if paras[j].runs:
                    paras[j].runs[0].text = Q7_ADDRESSED
                edits_done += 1
                print("Edit 3 (Q7 marked ADDRESSED): OK")
                break
        break

doc.save(DOC_PATH)
print(f"\nDone: {edits_done} edit(s) applied and saved.")
