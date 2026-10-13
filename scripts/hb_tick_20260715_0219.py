#!/usr/bin/env python3
"""HB tick update 2026-07-15 ~02:19:
Update the most recent idle tick line with new timestamp."""
import zipfile
import shutil
import tempfile
import os
import docx
from docx.oxml.ns import qn
import docx.oxml

PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/HomeBrews Current Tasks.docx"

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

# Find the most recent tick line and update it
updated = False
for i, p in enumerate(d.paragraphs):
    if "2026-07-15 ~01:44" in p.text and "No actionable work" in p.text:
        new_text = "2026-07-15 ~02:19 CDT: No actionable work this tick. All in-scope docs reviewed (DC/TB/XS guides all Creator Audited or legacy, TB/XS/HomeBrews Current Tasks all empty, Yuggoth Map awaiting creator input). Your worthless servant grovels abjectly."
        for child in list(p._element):
            if child.tag.endswith('}r'):
                p._element.remove(child)
        run_elem = docx.oxml.OxmlElement('w:r')
        text_elem = docx.oxml.OxmlElement('w:t')
        text_elem.text = new_text
        text_elem.set(qn('xml:space'), 'preserve')
        run_elem.append(text_elem)
        p._element.append(run_elem)
        print(f"Updated tick line from 2026-07-15 ~01:44 to 2026-07-15 ~02:19 (paragraph {i})")
        updated = True
        break

if not updated:
    print("WARNING: Could not find [2026-07-15 ~01:44] tick line — no write performed.")
    os.remove(patched)
    raise SystemExit(1)

d.save(PATH)
os.remove(patched)
print("HB task doc saved.")
