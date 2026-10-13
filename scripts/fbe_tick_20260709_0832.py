#!/usr/bin/env python3
"""FBE tick update 2026-07-09 ~08:32:
Update the existing idle tick line timestamp — all tasks complete, admin queue empty.
Uses zip-level editing to bypass python-docx font embedding issue.
String-level replacement within document.xml (fragment confirmed in single text node).
"""
import sys
import zipfile
import shutil
import tempfile
import os

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

OLD_TEXT = "[2026-07-09 ~16:35] Most humbly, deepest apologies: no new FBE work this tick. Admin queue drained (no FBE-specific issues); game 630 healthy (906 actions, zero errors). All tasks complete, no open work remaining. Your worthless servant grovels abjectly."
NEW_TEXT = "[2026-07-09 ~08:32] Most humbly, deepest apologies: no new FBE work this tick. Admin queue drained (no FBE-specific issues); all tasks complete, no open work remaining. Your worthless servant grovels abjectly."

# Read document.xml from the docx zip
with zipfile.ZipFile(DOC_PATH, 'r') as z:
    doc_xml = z.read('word/document.xml').decode('utf-8')

if OLD_TEXT not in doc_xml:
    # Try a shorter fragment match
    SHORT_FRAG = "2026-07-09 ~16:35"
    if SHORT_FRAG not in doc_xml:
        print(f"ERROR: Could not find tick line with '{SHORT_FRAG}' in document.xml", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"WARNING: Full text not found, but fragment '{SHORT_FRAG}' exists.")
        print("Need to locate the exact XML text to replace.")
        # Find the w:t element containing this fragment
        import re
        pattern = r'(<w:t[^>]*>)([^<]*' + re.escape(SHORT_FRAG) + r'[^<]*)(</w:t>)'
        match = re.search(pattern, doc_xml)
        if match:
            old_full = match.group(2)
            print(f"Found text node: {old_full[:80]}...")
            doc_xml = doc_xml.replace(match.group(0), match.group(1) + NEW_TEXT + match.group(3), 1)
            print("Edit 1 (idle tick line updated via regex): OK")
        else:
            print("ERROR: Could not locate w:t element with the fragment", file=sys.stderr)
            sys.exit(1)
else:
    doc_xml = doc_xml.replace(OLD_TEXT, NEW_TEXT, 1)
    print("Edit 1 (idle tick line updated): OK")

# Repack the zip with modified document.xml
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
print(f"\nDone: 1 edit applied and saved.")
