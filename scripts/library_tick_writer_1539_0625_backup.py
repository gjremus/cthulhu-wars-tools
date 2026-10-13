#!/usr/bin/env python3
# Library backup ticker 2026-06-25 ~15:39 — routine healthy pass, nothing changed/deployed.
# Current state in docx: 2 visible summary bullets [14:48 backup, 14:10 backup].
# Adding new one makes 3 (the MAX-3 limit). No demotion needed this tick.
import docx
import shutil
import time
import os
import sys
import glob

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Maps/Library at Celaeno/"
       "library build current tasks.docx")

bak = DOC + ".bak.pre_write_%d" % int(time.time())
shutil.copy2(DOC, bak)

d = docx.Document(DOC)


NEW_SUMMARY = (
    "Last tick: 2026-06-25 ~15:39 (backup ticker). Grovelling apologies — re-read "
    "the full rules, drained the admin message box (empty, nothing new), and confirmed "
    "all five games fully healthy (Library, More-Neutral-Units, TchoTcho, Bubastis, and "
    "Homebrew all answered). Walked every open and waiting job; nothing was changed or "
    "deployed, and everything still waits only on your go-aheads (chiefly the sideways-map "
    "correction for the More-Neutral-Units edition you actually see, and the crashed "
    "five-player game fix)."
)

# Anchor for the NEWEST existing summary bullet (insert new one BEFORE this)
NEWEST_ANCHORS = [
    "Last tick: 2026-06-25 ~14:48",
    "Last tick: 2026-06-25 ~14:10",
    "Last tick: 2026-06-25 ~13:03",
]

# Find the newest visible bullet (insert new one BEFORE this)
newest_p = None
for anchor in NEWEST_ANCHORS:
    for p in d.paragraphs:
        t = p.text.strip()
        if t.startswith(anchor) and not t.startswith("OLD:"):
            newest_p = p
            break
    if newest_p is not None:
        break

if newest_p is None:
    print("ERROR: could not find any existing summary bullet as insert anchor", file=sys.stderr)
    sys.exit(1)

# Insert new bullet before the newest existing one
newest_p.insert_paragraph_before(NEW_SUMMARY, style=newest_p.style)

# Rotate backups: keep only 3; move older ones to ~/.Trash/
bak_pattern = DOC + ".bak.pre_write_*"
all_baks = sorted(glob.glob(bak_pattern))
while len(all_baks) > 3:
    oldest_bak = all_baks.pop(0)
    trash_dir = os.path.expanduser("~/.Trash/")
    os.makedirs(trash_dir, exist_ok=True)
    dest = os.path.join(trash_dir, os.path.basename(oldest_bak))
    if os.path.exists(dest):
        dest = dest + ".%d" % int(time.time())
    os.rename(oldest_bak, dest)
    print("Rotated to Trash: %s" % os.path.basename(oldest_bak))

d.save(DOC)
print("OK: new 15:39 backup summary bullet inserted (now 3 visible, at MAX-3); backup=%s"
      % os.path.basename(bak))
