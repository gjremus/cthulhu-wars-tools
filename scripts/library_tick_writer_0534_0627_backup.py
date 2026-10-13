#!/usr/bin/env python3
# Library backup ticker 2026-06-27 ~05:34 — routine safety-net pass, nothing changed.
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

OLD_ANCHOR = "Last tick: 2026-06-27"
NEW_SUMMARY = (
    "Last tick: 2026-06-27 ~05:34 (backup ticker). Grovelling apologies — "
    "re-read all rules in full, drained the admin message box (empty, nothing new), "
    "and confirmed all five games healthy (Library, More-Neutral-Units, TchoTcho, "
    "Bubastis, and Homebrew all answered HTTP 200). Walked every open and waiting "
    "job; nothing was changed or deployed, and everything still waits only on your "
    "go-aheads (chiefly the sideways-map correction for the More-Neutral-Units "
    "edition you actually see, and the crashed five-player game fix)."
)

found = False
for p in d.paragraphs:
    t = p.text.strip()
    if t.startswith(OLD_ANCHOR) and "(backup ticker)" in t:
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
    # Try a broader match on any "Last tick:" line in the summary area
    for p in d.paragraphs:
        t = p.text.strip()
        if t.startswith("Last tick:") and "(backup ticker)" in t:
            for run in p.runs:
                run.text = ""
            if p.runs:
                p.runs[0].text = NEW_SUMMARY
            else:
                p.add_run(NEW_SUMMARY)
            found = True
            print("Updated backup ticker summary bullet (broader match)")
            break

if not found:
    print("WARNING: Could not find existing backup ticker bullet to update")

d.save(DOC)
print("Saved docx")

# Rotate backups: keep max 3 in the main dir
bak_pattern = DOC + ".bak.pre_write_*"
all_baks = sorted(glob.glob(bak_pattern))
trash_dir = os.path.expanduser("~/.Trash")
while len(all_baks) > 3:
    oldest = all_baks.pop(0)
    dest = os.path.join(trash_dir, os.path.basename(oldest))
    shutil.move(oldest, dest)
    print(f"Rotated old backup to Trash: {os.path.basename(oldest)}")

print("Done")
