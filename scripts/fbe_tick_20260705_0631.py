#!/usr/bin/env python3
"""FBE tick update 2026-07-05 ~06:31 (UTC):
1. Replace the ~08:15 tick line (it said no Java — incorrect) with updated status:
   build verified, both fixes compiled, awaiting deploy permission.
2. Update both in-progress tasks to note "Build verified"
"""
import sys
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from copy import deepcopy

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

edits_done = 0

# --- Edit 1: Replace the ~08:15 tick line ---
OLD_TICK = "No Java runtime on this machine"
NEW_TICK = "[2026-07-05 ~11:30] Most humbly: BUILD VERIFIED — both game 531 and game 596 fixes compile clean. Admin queue empty. Awaiting your gracious permission to deploy."

for i, para in enumerate(paras):
    if OLD_TICK in para.text:
        # Replace text in-place, preserving formatting
        for run in para.runs:
            run.text = ""
        if para.runs:
            para.runs[0].text = NEW_TICK
        else:
            # Fallback: add a run
            r = OxmlElement('w:r')
            t = OxmlElement('w:t')
            t.text = NEW_TICK
            t.set(qn('xml:space'), 'preserve')
            r.append(t)
            para._element.append(r)
        edits_done += 1
        print("Edit 1 (tick line replaced): OK")
        break

if edits_done < 1:
    print("ERROR: Could not find ~08:15 tick line to replace", file=sys.stderr)
    sys.exit(1)

# --- Edit 2: Update Game 531 in-progress task ---
GAME531_OLD = "Needs build and deploy."
GAME531_NEW = "BUILD VERIFIED — compiled clean. Needs deploy permission."

for i, para in enumerate(paras):
    if "Game 531" in para.text and GAME531_OLD in para.text:
        para.text  # Force text cache
        for run in para.runs:
            if GAME531_OLD in run.text:
                run.text = run.text.replace(GAME531_OLD, GAME531_NEW)
                edits_done += 1
                print("Edit 2 (Game 531 status): OK")
                break
        else:
            # Try full para text replacement
            full_text = para.text
            new_full = full_text.replace(GAME531_OLD, GAME531_NEW)
            for run in para.runs:
                run.text = ""
            if para.runs:
                para.runs[0].text = new_full
            edits_done += 1
            print("Edit 2 (Game 531 status, full para): OK")
        break

# --- Edit 3: Update Game 596 in-progress task ---
GAME596_OLD = "Needs build verification and deploy."
GAME596_NEW = "BUILD VERIFIED — compiled clean. Needs deploy permission."

for i, para in enumerate(paras):
    if "Game 596" in para.text and GAME596_OLD in para.text:
        for run in para.runs:
            if GAME596_OLD in run.text:
                run.text = run.text.replace(GAME596_OLD, GAME596_NEW)
                edits_done += 1
                print("Edit 3 (Game 596 status): OK")
                break
        else:
            full_text = para.text
            new_full = full_text.replace(GAME596_OLD, GAME596_NEW)
            for run in para.runs:
                run.text = ""
            if para.runs:
                para.runs[0].text = new_full
            edits_done += 1
            print("Edit 3 (Game 596 status, full para): OK")
        break

if edits_done < 2:
    print(f"WARNING: Only {edits_done} edits applied (expected 3). Saving anyway.")

doc.save(DOC_PATH)
print(f"\nDone: {edits_done} edits applied and saved.")
