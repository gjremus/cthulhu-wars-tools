#!/usr/bin/env python3
"""
FBE tick fix — 2026-07-03 ~15:56
Fix rule 4 violation: remove code identifiers from Completed entry and Q6.
"""
import sys
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from copy import deepcopy

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

def replace_para_text(para, new_text):
    runs = para._element.findall(qn('w:r'))
    if not runs:
        r = OxmlElement('w:r')
        t = OxmlElement('w:t')
        t.text = new_text
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        r.append(t)
        para._element.append(r)
        return
    first_rpr = runs[0].find(qn('w:rPr'))
    for r in runs:
        para._element.remove(r)
    r = OxmlElement('w:r')
    if first_rpr is not None:
        r.append(deepcopy(first_rpr))
    t = OxmlElement('w:t')
    t.text = new_text
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    r.append(t)
    para._element.append(r)

# Fix the Completed entry — remove code identifiers
for i, p in enumerate(paras):
    if '[x] Animated Rush serialization fix' in p.text:
        replace_para_text(p, "[x] Animated Rush replay fix — CONFIRMED ALREADY DEPLOYED (shipped in a prior update; live server verified today). Game 596 replays successfully and is no longer broken. Q6 is moot — the fix went out with an earlier batch deployment.")
        print(f"Fixed Completed entry at paragraph {i}")
        break

# Fix Q6 resolution — remove code identifiers
for i, p in enumerate(paras):
    if p.text.strip().startswith('Q6') and 'RESOLVED' in p.text:
        replace_para_text(p, "Q6 — Deploy serialization fix. One FBE game (game 596) still crashes when replaying because the live code doesn't recognize the old format of Animated Rush moves. The fix is written and tested locally (build compiles clean). Permission to commit and push to the homebrew site? RESOLVED (ticker 2026-07-03): The fix was already deployed in a prior update batch; game 596 confirmed working on the live server. No further action needed.")
        print(f"Fixed Q6 at paragraph {i}")
        break

doc.save(DOC_PATH)
print("DOC SAVED — rule 4 violations fixed.")
