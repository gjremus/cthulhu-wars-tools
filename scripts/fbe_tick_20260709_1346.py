#!/usr/bin/env python3
"""FBE tick update 2026-07-09 ~13:46 CDT:
Update the existing idle tick line timestamp — all tasks complete, admin queue drained (no FBE-specific issues).
"""
import sys
import zipfile
import shutil
import tempfile
import os

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

OLD_TEXT = "[2026-07-09 ~19:45]"
NEW_TEXT = "[2026-07-09 ~13:46]"

with zipfile.ZipFile(DOC_PATH, 'r') as z:
    doc_xml = z.read('word/document.xml').decode('utf-8')

if OLD_TEXT not in doc_xml:
    print(f"ERROR: Could not find '{OLD_TEXT}' in document.xml", file=sys.stderr)
    sys.exit(1)

doc_xml = doc_xml.replace(OLD_TEXT, NEW_TEXT, 1)
print("Edit 1 (idle tick line timestamp updated to ~13:46): OK")

tmp_fd, tmp_path = tempfile.mkstemp(suffix='.docx')
os.close(tmp_fd)

with zipfile.ZipFile(DOC_PATH, 'r') as zin:
    with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename == 'word/document.xml':
                zout.writestr(item, doc_xml.encode('utf-8'))
            else:
                zout.writestr(item, zin.read(item.filename))

shutil.move(tmp_path, DOC_PATH)
print("WRITE COMPLETE")
