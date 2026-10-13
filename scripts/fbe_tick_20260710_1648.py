#!/usr/bin/env python3
"""FBE tick update 2026-07-10 ~16:48:
Update existing idle tick line timestamp — no new tasks, admin queue empty.
"""
import sys
import zipfile
import shutil
import tempfile
import os

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

with zipfile.ZipFile(DOC_PATH, 'r') as z:
    doc_xml = z.read('word/document.xml').decode('utf-8')

OLD = "[2026-07-10 ~16:29]"
NEW = "[2026-07-10 ~16:48]"

if OLD not in doc_xml:
    print(f"ERROR: Could not find '{OLD}' in document XML", file=sys.stderr)
    sys.exit(1)

doc_xml = doc_xml.replace(OLD, NEW, 1)
print("Edit 1 (tick timestamp updated from ~16:29 to ~16:48): OK")

tmp_fd, tmp_path = tempfile.mkstemp(suffix='.docx')
os.close(tmp_fd)

with zipfile.ZipFile(DOC_PATH, 'r') as zin:
    with zipfile.ZipFile(tmp_path, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename == 'word/document.xml':
                zout.writestr(item, doc_xml.encode('utf-8'))
            else:
                zout.writestr(item, zin.read(item.filename))

shutil.move(tmp_path, DOC_PATH)
print("\nDone: 1 edit applied and saved.")
