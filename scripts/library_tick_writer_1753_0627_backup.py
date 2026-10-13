#!/usr/bin/env python3
# Library backup ticker 2026-06-27 ~17:53 CDT — routine safety-net pass, nothing changed.
import docx
import shutil
import time
import os
import glob

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Maps/Library at Celaeno/"
       "library build current tasks.docx")

bak = DOC + ".bak.pre_write_%d" % int(time.time())
local_bak = "/tmp/library_tasks_bak_%d.docx" % int(time.time())
try:
    shutil.copy2(DOC, bak)
except OSError as e:
    print(f"GDrive backup failed ({e}), trying local backup...")
    try:
        with open(DOC, 'rb') as src:
            data = src.read()
        with open(local_bak, 'wb') as dst:
            dst.write(data)
        print(f"Local backup written to {local_bak}")
    except OSError as e2:
        print(f"Cannot even read source file: {e2}")
        print("Google Drive lock active — aborting this tick write.")
        import sys; sys.exit(0)

d = docx.Document(DOC)

OLD_ANCHOR = "Last tick: 2026-06-27 ~22:17 CDT (backup ticker)"
NEW_SUMMARY = (
    "Last tick: 2026-06-27 ~17:53 CDT (backup ticker). Grovelling apologies — "
    "re-read all rules in full, drained admin message box (empty, nothing new), "
    "confirmed all five builds healthy (Library, MNU, TchoTcho, Bubastis, HomeBrews "
    "all HTTP 200). Walked every open and waiting job; nothing changed or deployed, "
    "all items still await your go-aheads (sideways-map MNU fix, five-player "
    "Cyclopean Gaze crash fix, MNU missing build files). Master doc within lockout "
    "(primary ticker active ~3 min ago) so master not written this tick. Library "
    "docx safe to write (16+ hours since last edit) but no content changes needed "
    "— all tasks blocked on your input."
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
all_baks = sorted(glob.glob(bak_pattern))
trash_dir = os.path.expanduser("~/.Trash")
while len(all_baks) > 3:
    oldest = all_baks.pop(0)
    dest = os.path.join(trash_dir, os.path.basename(oldest))
    shutil.move(oldest, dest)
    print(f"Rotated old backup to Trash: {os.path.basename(oldest)}")

print("Done")
