#!/usr/bin/env python3
"""Append recent fix entries to the HB Deployed Online Rollback Guide."""
import zipfile
import shutil
from copy import deepcopy
from lxml import etree

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/"
       "Homebrew Deployed Online Rollback Guide.docx")

ENTRIES = [
    "Fix HB-Overlap: Gate overlap placement on Library maps (2026-07-09, commit aaa1471)",
    "Symptom.",
    "Units on Library at Celaeno maps overlapped significantly, making the board unreadable.",
    "Fix.",
    "Added maxUnitOverlapFrac() overlap detection. If a placed unit overlaps >30% with any existing unit after 500 candidates tried, triggers regionUniformShrink and replaces all. Library maps only.",
    "Anchor.",
    "solo/CthulhuWarsSolo.scala — maxUnitOverlapFrac() method and the overlap-check / needsShrinkRedo block in placement loop.",
    "Revert.",
    "Remove maxUnitOverlapFrac() and shrink-redo logic. Restore old unit-count threshold.",
    "Propagated: All 5 builds, deployed 2026-07-09.",
    "",
    "Fix HB-Prison: Prison glyph move-out handler (2026-07-10, commit 9804e39)",
    "Symptom.",
    "Units in Prison region could not move out properly — move cost was not being deducted and movement continuation was not firing.",
    "Fix.",
    "Added MoveAction case for units whose region.glyph == Prison. Deducts move cost (respecting dcTenebrosumGuard) and returns MoveContinueAction(self, true).",
    "Anchor.",
    "solo/Game.scala — case MoveAction(self, u, o, r, cost) if u.region.glyph == Prison =>",
    "Revert.",
    "Remove the Prison glyph case from MoveAction. Units in Prison will no longer be able to move out via normal move.",
    "",
    "Fix HB-Shapestealing: Shapestealing die mechanic (2026-07-06, commit 296f7bb)",
    "Symptom.",
    "Shapestealing was taking the highest die and using a stored pip value instead of discarding the lowest die and re-rolling.",
    "Fix.",
    "Changed to discard the lowest die result and re-roll the remaining dice.",
    "Anchor.",
    "solo/Battle.scala — Shapestealing handler.",
    "Revert.",
    "Revert commit 296f7bb.",
    "",
    "Fix HB-Bastet: Bastet Requires Attention now valid on the Moon (2026-07-09, commit 4f1ee85)",
    "Symptom.",
    "Bastet's Requires Attention ritual was never offered when Bastet was on the Moon.",
    "Fix.",
    "Changed .%(_.region.onMap) to .%(u => u.region.onMap || u.region == BB.moon) at both doom menu and handler locations.",
    "Anchor.",
    "solo/Game.scala — two locations in RequiresAttention logic.",
    "Revert.",
    "Remove || u.region == BB.moon from both locations.",
    "",
    "Fix HB-DCAltSB: DS alternate spellbooks showing as empty ? slots (2026-07-04, commit c46b7ff)",
    "Symptom.",
    "When DS had alternate spellbooks enabled, the faction panel showed empty ? slots instead of the correct alternate spellbook names.",
    "Fix.",
    "Post-replay spellbook check now maps DS alternate spellbooks (Traitors→Omnipotence, FiendishGrowth→FiendishSpawn, UndirectedEnergy→DirectedEnergy) before checking which are unpicked.",
    "Anchor.",
    "solo/CthulhuWarsSolo.scala — post-replay spellbook check effectiveLibrary mapping.",
    "Revert.",
    "Remove the DS alternate mapping cases from effectiveLibrary.",
]

z = zipfile.ZipFile(DOC, 'r')
tree = etree.parse(z.open('word/document.xml'))
z.close()

ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
body = tree.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}body')

all_paras = body.findall('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')
template_p = all_paras[-1]

sect_pr = body.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sectPr')

for entry_text in ENTRIES:
    new_p = deepcopy(template_p)
    for r in new_p.findall('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r'):
        new_p.remove(r)
    r_elem = etree.SubElement(new_p, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r')
    t_elem = etree.SubElement(r_elem, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
    t_elem.text = entry_text
    t_elem.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    if sect_pr is not None:
        body.insert(list(body).index(sect_pr), new_p)
    else:
        body.append(new_p)

shutil.copy2(DOC, DOC + '.bak.pre_write_' + str(hash(DOC) & 0xFFFFFFFF))

import tempfile, os
with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
    tmp_path = tmp.name

with zipfile.ZipFile(DOC, 'r') as zin:
    with zipfile.ZipFile(tmp_path, 'w') as zout:
        for item in zin.infolist():
            if item.filename == 'word/document.xml':
                zout.writestr(item, etree.tostring(tree, xml_declaration=True, encoding='UTF-8', standalone=True))
            else:
                zout.writestr(item, zin.read(item.filename))

shutil.move(tmp_path, DOC)
print("SUCCESS — fix entries appended to HB rollback guide")
