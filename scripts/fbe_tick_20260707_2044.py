#!/usr/bin/env python3
"""FBE tick update 2026-07-07 ~20:44:
Update the existing idle tick line timestamp — status unchanged
(all tasks complete, admin queue empty, no new issues).
Uses zip-based XML editing to avoid python-docx font issues.
"""
import sys
import zipfile
import shutil
import tempfile
import re
import os

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

OLD_TICK_FRAGMENT = "2026-07-07 ~20:13"
NEW_TICK = "[2026-07-07 ~20:44] Most humbly, deepest apologies: no new FBE work this tick. Admin queue drained (empty). All tasks complete, no open work remaining."

# Read the docx as a zip, find and replace in word/document.xml
tmp_fd, tmp_path = tempfile.mkstemp(suffix='.docx')
os.close(tmp_fd)

edits_done = 0

with zipfile.ZipFile(DOC_PATH, 'r') as zin:
    with zipfile.ZipFile(tmp_path, 'w') as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == 'word/document.xml':
                xml_text = data.decode('utf-8')
                if OLD_TICK_FRAGMENT in xml_text:
                    # Find the paragraph containing the old tick fragment
                    # Replace only the text content within that paragraph's runs
                    # Strategy: find all <w:t> elements in the paragraph containing the fragment,
                    # concatenate them, check if it matches, then replace

                    # Simpler approach: find the <w:p> containing the fragment, replace its text runs
                    # with a single run containing the new text

                    # Find paragraph boundaries
                    paras = list(re.finditer(r'<w:p[ >].*?</w:p>', xml_text, re.DOTALL))
                    for m in paras:
                        para_xml = m.group(0)
                        if OLD_TICK_FRAGMENT in para_xml:
                            # Extract all text from <w:t> tags
                            texts = re.findall(r'<w:t[^>]*>(.*?)</w:t>', para_xml)
                            full_text = ''.join(texts)

                            if OLD_TICK_FRAGMENT in full_text:
                                # Get the first <w:r> element's formatting (rPr) if any
                                rpr_match = re.search(r'(<w:rPr>.*?</w:rPr>)', para_xml, re.DOTALL)
                                rpr = rpr_match.group(1) if rpr_match else ''

                                # Get paragraph properties
                                ppr_match = re.search(r'(<w:pPr>.*?</w:pPr>)', para_xml, re.DOTALL)
                                ppr = ppr_match.group(1) if ppr_match else ''

                                # Build new paragraph with single run
                                new_para = f'<w:p>{ppr}<w:r>{rpr}<w:t xml:space="preserve">{NEW_TICK}</w:t></w:r></w:p>'

                                xml_text = xml_text[:m.start()] + new_para + xml_text[m.end():]
                                edits_done += 1
                                print("Edit 1 (tick line timestamp updated): OK")
                                break

                    # Also check for the continuation paragraph that was split
                    # The old text was split: "no new FBE work\n\nthis tick"
                    # After our edit the next paragraph might start with "this tick."
                    # Let's check if there's a stray continuation
                    if edits_done > 0:
                        # Look for next paragraph starting with "this tick"
                        paras2 = list(re.finditer(r'<w:p[ >].*?</w:p>', xml_text, re.DOTALL))
                        for m2 in paras2:
                            para_xml2 = m2.group(0)
                            texts2 = re.findall(r'<w:t[^>]*>(.*?)</w:t>', para_xml2)
                            full_text2 = ''.join(texts2).strip()
                            if full_text2.startswith("this tick.") and len(full_text2) < 100:
                                # Remove this stray paragraph
                                xml_text = xml_text[:m2.start()] + xml_text[m2.end():]
                                print("Edit 2 (removed stray continuation paragraph): OK")
                                edits_done += 1
                                break

                    data = xml_text.encode('utf-8')
                else:
                    print(f"ERROR: Could not find '{OLD_TICK_FRAGMENT}' in document.xml", file=sys.stderr)
                    os.unlink(tmp_path)
                    sys.exit(1)
            zout.writestr(item, data)

if edits_done < 1:
    print(f"ERROR: No edits made", file=sys.stderr)
    os.unlink(tmp_path)
    sys.exit(1)

# Replace original with temp
shutil.move(tmp_path, DOC_PATH)
print(f"\nDone: {edits_done} edit(s) applied and saved.")
