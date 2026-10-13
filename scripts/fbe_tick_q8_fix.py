#!/usr/bin/env python3
"""Fix the remaining Q8 @@@ marker in FBE task doc."""
import docx

PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

d = docx.Document(PATH)

for i, p in enumerate(d.paragraphs):
    if "@@@ It is a universal ability" in p.text:
        print(f"Found Q8 @@@ at paragraph {i}: {p.text[:80]}...")
        # Replace the entire paragraph text
        new_text = "ACKNOWLEDGED (ticker 2026-07-07): Understood — Self Consuming is universal (The Eye Opens proc is CORRECT). The real bug is Self Consuming firing after a move with no deaths at the beginning of the third Action Phase. Root cause FOUND: stale deaths from the Doom Phase or Power Gather leaked across the phase boundary into the Action Phase death tally. Fix coded (clear death tally at start of Doom Phase and Action Phase). Awaiting deploy."
        for j, run in enumerate(p.runs):
            if j == 0:
                run.text = new_text
            else:
                run.text = ""
        print("Replaced.")
        break

d.save(PATH)
print("Done.")
