#!/usr/bin/env python3
"""Update the idle tick line timestamp in FBE Current Tasks doc."""
import sys
import tempfile
import subprocess
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"
SAFE_WRITE = "/Users/gremus/Claude-Projects/cthulhu-wars-tools/scripts/safe-docx-write.sh"

OLD_MARKER = "[2026-07-20 ~13:15]"
NEW_MARKER = "[2026-07-20 ~13:18]"

doc = Document(DOC_PATH)
count = 0

for para in doc.paragraphs:
    if OLD_MARKER in para.text:
        full = para.text
        new_full = full.replace(OLD_MARKER, NEW_MARKER)
        if full != new_full:
            for i, run in enumerate(para.runs):
                if i == 0:
                    run.text = new_full
                else:
                    run.text = ""
            count += 1

if count == 0:
    print("ERROR: Could not find idle tick line to update", file=sys.stderr)
    sys.exit(1)

tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
doc.save(tmp.name)
tmp.close()

result = subprocess.run([SAFE_WRITE, tmp.name, DOC_PATH], capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print(f"safe-docx-write.sh failed: {result.stderr}", file=sys.stderr)
    sys.exit(1)

print(f"Updated {count} idle tick line(s) timestamp to ~13:18")
