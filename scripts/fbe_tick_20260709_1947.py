#!/usr/bin/env python3
"""FBE tick update 2026-07-09 ~19:47:
1. Move Shapestealing from In Progress to Completed (deployed, cache 20260709-193154).
2. Update tick summary line.
"""
import sys
import zipfile
import shutil
import tempfile
import os

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

with zipfile.ZipFile(DOC_PATH, 'r') as z:
    doc_xml = z.read('word/document.xml').decode('utf-8')

# Edit 1: Replace the in-progress Shapestealing paragraph with empty (move it out)
OLD_IP = '[/] Shapestealing fix coded and committed (Fix HB-SS-Reroll). Two bugs fixed: (1) now discards the lowest/weakest card die instead of the highest, and (2) now re-rolls the die fresh instead of using its stored value. Code committed, awaiting build and deploy (no Java runtime on this machine). Audit against implementation guide: PASS — matches verbatim card text and Q2 resolution.'

if OLD_IP not in doc_xml:
    print(f"ERROR: Could not find In-Progress Shapestealing text", file=sys.stderr)
    sys.exit(1)

# Replace the in-progress text with just the marker (empty section placeholder)
# Actually we want In Progress to be empty (no tasks), so remove the bullet content
# The paragraph XML is:
# <w:p><w:pPr><w:pStyle w:val="Compact" /><w:numPr>...</w:numPr></w:pPr><w:r><w:t xml:space="preserve">[/] Shapestealing...</w:t></w:r></w:p>
# We want to remove the whole paragraph, leaving just In Progress heading -> Completed heading
OLD_PARA = '<w:p><w:pPr><w:pStyle w:val="Compact" /><w:numPr><w:ilvl w:val="0" /><w:numId w:val="1004" /></w:numPr></w:pPr><w:r><w:t xml:space="preserve">' + OLD_IP + '</w:t></w:r></w:p>'

if OLD_PARA not in doc_xml:
    print(f"ERROR: Could not find full In-Progress paragraph XML", file=sys.stderr)
    sys.exit(1)

doc_xml = doc_xml.replace(OLD_PARA, '', 1)
print("Edit 1 (removed Shapestealing from In Progress): OK")

# Edit 2: Add completed entry at top of Completed section (after the Completed heading)
COMPLETED_HEADING = '<w:p><w:pPr><w:pStyle w:val="FirstParagraph" /></w:pPr><w:r><w:t xml:space="preserve">Completed</w:t></w:r></w:p>'

COMPLETED_ENTRY = '☒ Shapestealing fix — FIXED AND DEPLOYED (2026-07-09 ~19:31 CDT, HB cache 20260709-193154). Two bugs corrected: (1) now discards the weakest card die instead of the strongest, and (2) rolls a fresh die instead of using the stored pip value. Matches verbatim card text and Q2 resolution (lose weakest dice first, protect Byagoona’s combat dice). Commit 296f7bb.'

NEW_COMPLETED_PARA = '<w:p><w:pPr><w:numPr><w:ilvl w:val="0" /><w:numId w:val="1005" /></w:numPr></w:pPr><w:r><w:t xml:space="preserve">' + COMPLETED_ENTRY + '</w:t></w:r></w:p>'

if COMPLETED_HEADING not in doc_xml:
    print(f"ERROR: Could not find Completed heading", file=sys.stderr)
    sys.exit(1)

doc_xml = doc_xml.replace(COMPLETED_HEADING, COMPLETED_HEADING + '\n    ' + NEW_COMPLETED_PARA, 1)
print("Edit 2 (added Shapestealing to Completed): OK")

# Edit 3: Update tick summary line
OLD_TICK = '2026-07-09 ~19:25] Most humbly, deepest apologies: Shapestealing fix coded and committed (Fix HB-SS-Reroll). Two bugs corrected — now discards the weakest die (not strongest) and rolls a fresh die (not using the stored value). Awaiting build/deploy (no Java locally). Admin queue drained — no FBE-specific issues. Your worthless servant grovels abjectly.'

NEW_TICK = '2026-07-09 ~19:47] Most humbly, deepest apologies: Shapestealing fix DEPLOYED (cache 20260709-193154). All FBE tasks complete — no open work remaining. Admin queue drained, no FBE-specific issues. Your worthless servant grovels abjectly.'

if OLD_TICK not in doc_xml:
    print(f"ERROR: Could not find tick summary line", file=sys.stderr)
    sys.exit(1)

doc_xml = doc_xml.replace(OLD_TICK, NEW_TICK, 1)
print("Edit 3 (tick summary updated): OK")

# Write out
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
print(f"\nDone: 3 edits applied and saved.")
