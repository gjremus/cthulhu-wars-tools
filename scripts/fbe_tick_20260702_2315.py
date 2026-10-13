"""FBE tick 2026-07-02 ~23:15 — update the existing 'nothing happened' bullet timestamp."""
from docx import Document

DOC = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC)

OLD_LINE = "[2026-07-02 ~22:43] No new tasks or admin prompts this tick, most humbly. All FBE tasks complete; admin queue drained. Awaiting your next command with utmost deference."
NEW_LINE = "[2026-07-02 ~23:15] No new tasks or admin prompts this tick, most humbly. All FBE tasks complete; admin queue drained. Awaiting your next command with utmost deference."

found = False
for para in doc.paragraphs:
    if para.text.strip() == OLD_LINE:
        for run in para.runs:
            run.text = ""
        para.runs[0].text = NEW_LINE
        found = True
        break

if not found:
    raise RuntimeError("Could not find the existing tick line to update")

doc.save(DOC)
print("Updated tick timestamp to ~23:15")
