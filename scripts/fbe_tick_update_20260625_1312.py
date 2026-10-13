"""FBE tick update 2026-06-25 ~13:12 — update 'nothing happened' bullet timestamp only."""
from docx import Document
import shutil, sys

PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks.docx"

doc = Document(PATH)

OLD = "[2026-06-25 ~12:57] Humbly reporting another quiet tick: admin queue is empty, Homebrew site is healthy (cache 20260625-090552, HTTP 200), worktree is clean, and no open Faceless Blight tasks remain."
NEW = "[2026-06-25 ~13:12] Humbly reporting another quiet tick: admin queue is empty, Homebrew site healthy (cache 20260625-090552, HTTP 200), worktree is clean, and no open Faceless Blight tasks remain."

found = False
for para in doc.paragraphs:
    if para.text.strip() == OLD.strip():
        # Preserve runs — clear and rewrite the first run
        for i, run in enumerate(para.runs):
            if i == 0:
                run.text = NEW
            else:
                run.text = ""
        found = True
        print(f"Updated paragraph: {para.text[:80]}")
        break

if not found:
    print(f"ERROR: could not find target paragraph. First 5 paras:")
    for p in doc.paragraphs[:5]:
        print(f"  {p.text[:80]!r}")
    sys.exit(1)

doc.save(PATH)
print("Saved.")
