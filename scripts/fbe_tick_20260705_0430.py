#!/usr/bin/env python3
"""FBE tick update 2026-07-05 ~04:30:
1. Replace newest tick summary with updated status (root cause found, fix coded)
2. Update in-progress task with fix details
"""
import sys
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"

doc = Document(DOC_PATH)
paras = doc.paragraphs

# --- Edit 1: Replace the newest tick summary ---
OLD_TICK_FRAGMENT = "[2026-07-05 ~00:15] Most humbly: admin queue empty, no new issues. Game 596 crash still under deep investigation"
NEW_TICK = "[2026-07-05 ~04:30] Most humbly, deepest apologies for the delay: Game 596 root cause FOUND and fix coded. The crash was caused by a replay compatibility gap in the kill-prevention prompt — old games offered the choice when Byagoona was anywhere on the map, but newer code required Byagoona in the actual battle. Fix adds a replay-awareness check so old game recordings still work. Awaiting build verification (no Java on this machine)."

tick_found = False
for para in paras:
    if OLD_TICK_FRAGMENT in para.text:
        for i, run in enumerate(para.runs):
            if i == 0:
                run.text = NEW_TICK
            else:
                run.text = ""
        tick_found = True
        break

if not tick_found:
    print("ERROR: Could not find tick line to update", file=sys.stderr)
    sys.exit(1)
print("Edit 1 (tick line): OK")

# --- Edit 2: Update in-progress task ---
OLD_INPROG_FRAGMENT = "Narrowed to a recent change in the battle-proceeding code."
NEW_SUFFIX = "ROOT CAUSE IDENTIFIED: the kill-prevention prompt (Distributed Death) was changed to only fire when Byagoona is in the battle, but old game recordings were made with the broader check. During replay, the prompt gets skipped, causing a phase desync that cascades into crashes. Fix coded: replay-awareness added so old recordings still trigger the prompt. Needs build verification and deploy."

inprog_found = False
for para in paras:
    if OLD_INPROG_FRAGMENT in para.text:
        full = para.text
        new_full = full.replace(
            "Narrowed to a recent change in the battle-proceeding code.\n  Needs local reproduction testing to pinpoint the exact crash line.",
            NEW_SUFFIX
        )
        # If the multiline replace didn't match, try single-line
        if new_full == full:
            new_full = full.replace(
                "Narrowed to a recent change in the battle-proceeding code. Needs local reproduction testing to pinpoint the exact crash line.",
                NEW_SUFFIX
            )
        # If still no match, just replace the fragment we know exists
        if new_full == full:
            new_full = full.replace(OLD_INPROG_FRAGMENT, NEW_SUFFIX)
        for i, run in enumerate(para.runs):
            if i == 0:
                run.text = new_full
            else:
                run.text = ""
        inprog_found = True
        break

if not inprog_found:
    print("ERROR: Could not find in-progress task to update", file=sys.stderr)
    sys.exit(1)
print("Edit 2 (in-progress task): OK")

doc.save(DOC_PATH)
print("\nAll edits applied and saved.")
