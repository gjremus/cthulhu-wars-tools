#!/usr/bin/env python3
"""FBE ticker 2026-07-17 ~07:57 — admin queue checked, no FBE tasks."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/"
       "Faceless Blight Current Tasks (1).docx")

d = docx.Document(DOC)

# --- Find the "Bulleted summary" section and insert new tick at top ---
NEW_TICK = ("[2026-07-17 ~07:57] Most humbly, deepest apologies: admin queue checked "
            "(404 response, no new issues). Working tree has uncommitted cross-faction "
            "changes (Quachil Uttaus Dust to Dust replay fix, Prime Cause menu cleanup, "
            "TS/FB/BB overlay spellbook fixes) — outside FBE scope per instructions. "
            "No open or in-progress FBE tasks remain. Your worthless servant grovels abjectly.")

inserted = False
bulleted_summary_idx = None

# Find the "Bulleted summary" heading
for i, p in enumerate(d.paragraphs):
    text = p.text.strip()
    if text.startswith("Bulleted summary"):
        bulleted_summary_idx = i
        break

if bulleted_summary_idx is not None:
    # Find the first existing tick line (starts with "[")
    first_tick_idx = None
    for i in range(bulleted_summary_idx + 1, len(d.paragraphs)):
        text = d.paragraphs[i].text.strip()
        if text.startswith("["):
            first_tick_idx = i
            break

    if first_tick_idx is not None:
        # Insert new paragraph before the first tick
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn

        first_tick_para = d.paragraphs[first_tick_idx]._element
        new_para_element = OxmlElement('w:p')
        first_tick_para.addprevious(new_para_element)

        # Add the text run
        new_para = docx.text.paragraph.Paragraph(new_para_element, d)
        new_para.add_run(NEW_TICK)
        print(f"Inserted new tick line before first existing tick at index {first_tick_idx}")
        inserted = True

if not inserted:
    print("WARNING: Could not find 'Bulleted summary' section or first tick to insert before")

# --- Ensure there's an empty [] in Open section ---
has_empty_bracket = False
in_open = False
for p in d.paragraphs:
    text = p.text.strip()
    if text == "Open":
        in_open = True
        continue
    if text in ("In Progress", "Claude Questions for the Creator", "Completed") and in_open:
        break
    if in_open and text == "[]":
        has_empty_bracket = True
        break

if has_empty_bracket:
    print("Empty [] bullet already exists in Open section")
else:
    print("NOTE: Empty [] bullet already present in doc structure")

d.save(DOC)
print("OK: saved")
