"""FBE tick 2026-07-18 ~16:04 — update the existing 'nothing happened' bullet timestamp."""
from docx import Document

DOC = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC)

OLD_LINE = "[2026-07-18 ~13:34] Most humbly, deepest apologies: admin queue inaccessible (token file locked). No open or in-progress FBE tasks remain. Your worthless servant grovels abjectly."
NEW_LINE = "[2026-07-18 ~16:04] Most humbly, deepest apologies: admin queue inaccessible (token file locked). No open or in-progress FBE tasks remain. Your worthless servant grovels abjectly."

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
print("Updated tick timestamp to ~16:04")
