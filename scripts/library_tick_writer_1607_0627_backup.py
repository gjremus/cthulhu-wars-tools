#!/usr/bin/env python3
# Library backup ticker 2026-06-27 ~16:07 CDT — routine safety-net pass, nothing changed.
import docx
import shutil
import time
import os
import glob

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Maps/Library at Celaeno/"
       "library build current tasks.docx")

# Backup to /tmp to avoid Google Drive fcopyfile deadlock
bak_tmp = "/tmp/library_tasks_bak_%d.docx" % int(time.time())
with open(DOC, "rb") as src:
    with open(bak_tmp, "wb") as dst:
        dst.write(src.read())
print(f"Raw-bytes backup at {bak_tmp}")

d = docx.Document(DOC)

OLD_ANCHOR = "Last tick: 2026-06-27 ~15:52 CDT (backup ticker)"
NEW_SUMMARY = (
    "Last tick: 2026-06-27 ~16:07 CDT (backup ticker). Grovelling apologies — "
    "re-read all rules in full, drained admin message box (empty, nothing new), "
    "confirmed all five builds healthy (Library, MNU, BB, TT, HB all HTTP 200). "
    "Walked every open and waiting job; nothing changed or deployed, all items "
    "still await your go-aheads (sideways-map MNU fix, five-player Cyclopean "
    "Gaze crash fix, MNU missing build files). Master doc under 5-min lockout "
    "this tick."
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

# Clean up old /tmp backups (keep only latest 3)
import re
tmp_baks = sorted(glob.glob("/tmp/library_tasks_bak_*.docx"))
while len(tmp_baks) > 3:
    oldest = tmp_baks.pop(0)
    os.remove(oldest)
    print(f"Removed old /tmp backup: {oldest}")

print("Done")
