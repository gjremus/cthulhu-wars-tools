#!/usr/bin/env python3
"""
FBE tick writer — 2026-07-03 ~21:20
Task: No new work. Only in-progress task (deploy Animated Rush legacy fix) still awaits
user permission. Admin queue empty. Update existing top summary bullet timestamp per Rule 30.
"""
import sys
from docx import Document
from docx.oxml.ns import qn
from copy import deepcopy

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

# Find the "Bulleted summary" section
summary_header_idx = None
for i, p in enumerate(paras):
    if "Bulleted summary" in p.text:
        summary_header_idx = i
        break

if summary_header_idx is None:
    print("ERROR: could not find 'Bulleted summary' paragraph")
    sys.exit(1)

# Find the first (newest) tick summary bullet
first_bullet_idx = None
for i in range(summary_header_idx + 1, len(paras)):
    text = paras[i].text.strip()
    if text.startswith('[2026-'):
        first_bullet_idx = i
        break

if first_bullet_idx is None:
    print("ERROR: could not find any tick summary bullets")
    sys.exit(1)

old_text = paras[first_bullet_idx].text
print(f"Found top bullet at index {first_bullet_idx}: {old_text[:100]}...")

# Replace the top bullet text — update timestamp, keep same message (situation unchanged)
NEW_TEXT = "[2026-07-03 ~21:20] Most humbly: tick confirmed build compiles clean, Animated Rush legacy fix ready. Still awaiting your gracious permission to deploy (games 530, 534). Admin queue empty."

# Replace text in all runs of this paragraph
para = paras[first_bullet_idx]
runs = para.runs
if runs:
    # Clear all runs except first, put all text in first run
    runs[0].text = NEW_TEXT
    for r in runs[1:]:
        r.text = ""
else:
    # No runs — add one
    para.text = NEW_TEXT

print(f"Updated to: {NEW_TEXT[:100]}...")

doc.save(DOC_PATH)
print("DONE — file saved.")
