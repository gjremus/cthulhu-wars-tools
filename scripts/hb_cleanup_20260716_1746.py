#!/usr/bin/env python3
"""HomeBrews ticker cleanup 2026-07-16 ~17:46 — move old summaries to history."""
import docx
from docx.oxml.ns import qn

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/HomeBrews Current Tasks.docx")

d = docx.Document(DOC)

# Find summary section and history section
in_summary = False
in_history = False
summary_bullets = []
summary_start_idx = None
history_insert_idx = None

for idx, p in enumerate(d.paragraphs):
    if "Bulleted summary" in p.text and not in_summary:
        in_summary = True
        summary_start_idx = idx
        continue
    elif "Open" in p.text and in_summary:
        in_summary = False
        continue
    elif "Summary History" in p.text:
        in_history = True
        history_insert_idx = idx + 1
        break

    if in_summary:
        text = p.text.strip()
        if text.startswith("- 2026-"):
            summary_bullets.append((idx, p))

# Keep only the first 3 bullets, move the rest to history
if len(summary_bullets) > 3:
    to_move = summary_bullets[3:]

    # Collect the text from bullets to move
    texts_to_move = [p.text.strip() for _, p in to_move]

    # Remove the old bullets (work backwards to preserve indices)
    for idx, p in reversed(to_move):
        p_elem = p._element
        p_elem.getparent().remove(p_elem)

    # Insert them at the start of Summary History if we found it
    if history_insert_idx is not None:
        # Insert in reverse order so they appear oldest-first in history
        for text in texts_to_move:
            new_p = d.paragraphs[history_insert_idx]._element.getparent().makeelement(qn('w:p'), nsmap=d.paragraphs[0]._element.nsmap)
            run_elem = new_p.makeelement(qn('w:r'), nsmap=new_p.nsmap)
            text_elem = run_elem.makeelement(qn('w:t'), nsmap=run_elem.nsmap)
            text_elem.text = text
            run_elem.append(text_elem)
            new_p.append(run_elem)
            d.paragraphs[history_insert_idx]._element.addprevious(new_p)

    print(f"OK: Moved {len(to_move)} old summary bullets to history, kept top 3")
else:
    print(f"OK: Only {len(summary_bullets)} summary bullets, no cleanup needed")

d.save(DOC)
