#!/usr/bin/env python3
"""FBE ticker update 2026-07-10 ~06:29: update existing no-work tick line timestamp."""
import zipfile
import shutil
import tempfile
import os
import docx
from docx.oxml.ns import qn
import docx.oxml

PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

OLD_LINE_MARKER = "[2026-07-10 ~06:16]"
OLD_CONTENT_MARKER = "all FBE tasks complete"

NEW_TEXT = (
    "[2026-07-10 ~06:29] Most humbly, deepest apologies: all FBE tasks "
    "complete — no open work remaining. Admin queue drained (no FBE-specific "
    "issues). Your worthless servant grovels abjectly."
)

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

updated = False
for i, p in enumerate(d.paragraphs):
    if OLD_LINE_MARKER in p.text and OLD_CONTENT_MARKER in p.text:
        for child in list(p._element):
            if child.tag.endswith('}r'):
                p._element.remove(child)
        run_elem = docx.oxml.OxmlElement('w:r')
        text_elem = docx.oxml.OxmlElement('w:t')
        text_elem.text = NEW_TEXT
        text_elem.set(qn('xml:space'), 'preserve')
        run_elem.append(text_elem)
        p._element.append(run_elem)
        print(f"Updated tick line at paragraph {i}")
        updated = True
        break

if not updated:
    print("WARNING: Could not find the target tick line to update")
    os.remove(patched)
    raise SystemExit(1)

d.save(PATH)
os.remove(patched)
print("FBE task doc saved.")
