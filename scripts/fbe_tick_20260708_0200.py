#!/usr/bin/env python3
"""FBE tick update 2026-07-08 ~02:00:
Update the idle tick line timestamp — admin queue empty (all entries cross-faction), no open tasks.
Uses direct zip/XML manipulation to avoid python-docx font content-type issue.
"""
import sys
import zipfile
import shutil
import tempfile
import os

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

OLD_TEXT = "[2026-07-07 ~20:44] Most humbly, deepest apologies: no new FBE work this tick. Admin queue drained (empty). All tasks complete, no open work remaining."
NEW_TEXT = "[2026-07-08 ~02:00] Most humbly, deepest apologies: no new FBE work this tick. Admin queue drained (all entries cross-faction, deferred to master). All tasks complete, no open work remaining."

with zipfile.ZipFile(DOC_PATH, 'r') as z:
    doc_xml = z.read('word/document.xml').decode('utf-8')

if OLD_TEXT not in doc_xml:
    print(f"ERROR: exact old text not found in document.xml", file=sys.stderr)
    print(f"Looking for: {OLD_TEXT[:80]}...", file=sys.stderr)
    sys.exit(1)

count = doc_xml.count(OLD_TEXT)
if count != 1:
    print(f"ERROR: found {count} occurrences, expected exactly 1", file=sys.stderr)
    sys.exit(1)

doc_xml_new = doc_xml.replace(OLD_TEXT, NEW_TEXT)

tmp_fd, tmp_path = tempfile.mkstemp(suffix='.docx')
os.close(tmp_fd)

with zipfile.ZipFile(DOC_PATH, 'r') as zin:
    with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename == 'word/document.xml':
                zout.writestr(item, doc_xml_new.encode('utf-8'))
            else:
                zout.writestr(item, zin.read(item.filename))

shutil.move(tmp_path, DOC_PATH)
print("Edit 1 (tick line updated): OK")
print(f"\nDone: 1 edit applied and saved.")
