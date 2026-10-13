#!/usr/bin/env python3
"""FBE tick update 2026-07-12 ~06:12 CDT:
Update existing idle tick line timestamp — status unchanged.
Admin queue drained, no FBE-specific issues, server healthy.
DC Satiate formula fix still awaiting deploy."""
import zipfile
import shutil
import tempfile
import os
import docx
from docx.oxml.ns import qn
import docx.oxml

PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

def patch_content_types(docx_path):
    """Add Default Extension='ttf' to [Content_Types].xml if not present."""
    tmp = tempfile.mktemp(suffix='.docx')
    shutil.copy2(docx_path, tmp)

    with zipfile.ZipFile(tmp, 'r') as zin:
        ct = zin.read('[Content_Types].xml').decode('utf-8')
        if 'Extension="ttf"' not in ct:
            ct = ct.replace(
                '<Default Extension="odttf"',
                '<Default Extension="ttf" ContentType="application/x-font-ttf" /><Default Extension="odttf"'
            )
            tmp2 = tempfile.mktemp(suffix='.docx')
            with zipfile.ZipFile(tmp2, 'w', zipfile.ZIP_DEFLATED) as zout:
                for item in zin.namelist():
                    if item == '[Content_Types].xml':
                        zout.writestr(item, ct.encode('utf-8'))
                    else:
                        zout.writestr(item, zin.read(item))
            os.remove(tmp)
            return tmp2
    return tmp

patched = patch_content_types(PATH)
d = docx.Document(patched)

OLD_LINE = "[2026-07-12 ~05:30] Most humbly, deepest apologies: no new work this tick. Admin queue drained (no FBE-specific issues); DC Satiate formula fix still awaiting deploy. Your worthless servant grovels abjectly."
NEW_LINE = "[2026-07-12 ~06:12] Most humbly, deepest apologies: no new work this tick. Admin queue drained (no FBE-specific issues); DC Satiate formula fix still awaiting deploy. Your worthless servant grovels abjectly."

updated = False
for i, p in enumerate(d.paragraphs):
    if "2026-07-12 ~05:30" in p.text and "no new work this tick" in p.text:
        for child in list(p._element):
            if child.tag.endswith('}r'):
                p._element.remove(child)
        run_elem = docx.oxml.OxmlElement('w:r')
        text_elem = docx.oxml.OxmlElement('w:t')
        text_elem.text = NEW_LINE
        text_elem.set(qn('xml:space'), 'preserve')
        run_elem.append(text_elem)
        p._element.append(run_elem)
        print(f"Updated idle tick line from ~05:30 to ~06:12 CDT (paragraph {i})")
        updated = True
        break

if not updated:
    print("WARNING: Could not find [2026-07-12 ~05:30] idle tick line — no write performed.")
    os.remove(patched)
    raise SystemExit(1)

d.save(PATH)
os.remove(patched)
print("FBE task doc saved.")
