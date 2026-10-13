"""
FBE tick 2026-07-15 ~18:44 — update doc:
- Update the last tick bullet with current timestamp
- Admin queue: 404 (no new issues)
- Working tree: clean on homebrew branch
- No open or in-progress tasks
"""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)

# Find and update the last tick bullet — starts with "[2026-07-15 ~18:31]"
OLD_STUB = "[2026-07-15 ~18:31]"
NEW_TEXT = ("[2026-07-15 ~18:44] Most humbly, deepest apologies: admin queue checked "
            "(404 response, same as prior ticks). Working tree clean on homebrew branch. "
            "No open or in-progress tasks remain. Your worthless servant grovels abjectly.")

updated = False
for para in doc.paragraphs:
    if OLD_STUB in para.text:
        # Clear all runs and set new text in first run
        for run in para.runs:
            run.text = ""
        if para.runs:
            para.runs[0].text = NEW_TEXT
        else:
            para.add_run(NEW_TEXT)
        updated = True
        print(f"Updated para: {para.text[:80]}")
        break

if not updated:
    print("ERROR: could not find the target paragraph to update")
    sys.exit(1)

doc.save(DOC_PATH)
print("SAVED OK")
