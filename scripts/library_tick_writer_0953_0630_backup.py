#!/usr/bin/env python3
# Library backup ticker 2026-06-30 ~09:53 — routine safety-net pass, nothing changed.
import docx
import shutil
import time
import os
import glob

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Maps/Library at Celaeno/"
       "library build current tasks.docx")

bak = DOC + ".bak.pre_write_%d" % int(time.time())
shutil.copy2(DOC, bak)

d = docx.Document(DOC)

OLD_ANCHOR = "Last tick: 2026-06-30 ~09:08 CDT (backup ticker)"
NEW_SUMMARY = (
    "Last tick: 2026-06-30 ~09:53 CDT (backup ticker). Grovelling apologies — "
    "nothing actionable on Library tasks this pass. Admin queue timed out "
    "(server main page healthy at 200 but prompts endpoint slow). All 5 builds "
    "healthy (Library 200, MNU 200, BB 200, TchoTcho 200, HB 200). All items "
    "still awaiting your input — horizontal map fix ready to deploy on your "
    "go-ahead, Cyclopean Gaze fix ready on your go-ahead, MNU build-setup "
    "files ready on your go-ahead."
)

found = False
for p in d.paragraphs:
    t = p.text.strip()
    if t.startswith(OLD_ANCHOR):
        for run in p.runs:
            run.text = ""
        if p.runs:
            p.runs[0].text = NEW_SUMMARY
        else:
            p.add_run(NEW_SUMMARY)
        found = True
        print("Updated existing backup ticker summary bullet timestamp")
        break

if not found:
    print("WARNING: Could not find existing backup ticker bullet to update")

d.save(DOC)
print("Saved docx")

# Rotate backups: keep max 3 in the main dir
bak_pattern = DOC + ".bak.pre_write_*"
baks = sorted(glob.glob(bak_pattern), key=os.path.getmtime, reverse=True)
trash_dir = os.path.join(os.path.dirname(DOC), ".Trash-bak-rotation")
os.makedirs(trash_dir, exist_ok=True)
for old_bak in baks[3:]:
    dest = os.path.join(trash_dir, os.path.basename(old_bak))
    shutil.move(old_bak, dest)
    print(f"Rotated old backup to trash: {os.path.basename(old_bak)}")
