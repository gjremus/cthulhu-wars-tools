#!/usr/bin/env python3
# Library backup ticker 2026-06-25 ~14:48 — routine healthy pass, nothing changed/deployed.
# Rules: MAX-3 summary bullets, MAX-2 nothing-actionable bullets.
# Current state (possible):
#   Case A (1410 writer ran):    [14:10 backup, 13:03 master] → add 14:48, demote 13:03
#   Case B (1410 writer missed): [13:03 master, 08:48 master] → add 14:48, demote 08:48
# In both cases: insert 14:48 at top, demote the oldest summary bullet to Old section.
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


def set_text(p, txt):
    runs = list(p.runs)
    if runs:
        runs[0].text = txt
        for r in runs[1:]:
            r.text = ""
    else:
        p.add_run(txt)


NEW_SUMMARY = (
    "Last tick: 2026-06-25 ~14:48 (backup ticker). Grovelling apologies — re-read "
    "the full rules, drained the admin message box (empty, nothing new), and confirmed "
    "all five games and the live site fully healthy (Library single-player edition, "
    "More-Neutral-Units beta, TchoTcho, Bubastis, and Homebrew all answered instantly). "
    "Walked every open and waiting job; nothing was changed or deployed, and everything "
    "still waits only on your go-aheads (chiefly the sideways-map correction for the "
    "More-Neutral-Units edition you actually see, and the crashed five-player game fix)."
)

# Candidate anchors for the NEWEST existing summary bullet (insert 14:48 BEFORE this)
NEWEST_ANCHORS = [
    "Last tick: 2026-06-25 ~14:10",
    "Last tick: 2026-06-25 ~13:03",
]

# Candidate anchors for the OLDEST existing summary bullet (demote this to Old section)
OLDEST_ANCHORS = [
    "Last tick: 2026-06-25 ~13:03",
    "Last tick: 2026-06-25 ~08:48",
    "Last tick: 2026-06-25 ~08:37",
    "Last tick: 2026-06-25 ~08:18",
    "Last tick: 2026-06-25 ~08:05",
]

# Find the newest bullet (we insert the new one BEFORE this)
newest_p = None
for anchor in NEWEST_ANCHORS:
    for p in d.paragraphs:
        if p.text.strip().startswith(anchor):
            newest_p = p
            break
    if newest_p is not None:
        break

if newest_p is None:
    print("ERROR: could not find any existing summary bullet as insert anchor", file=sys.stderr)
    sys.exit(1)

# Find the oldest summary bullet (we demote this one)
oldest_p = None
for anchor in OLDEST_ANCHORS:
    for p in d.paragraphs:
        if p.text.strip().startswith(anchor) and not p.text.strip().startswith("OLD:"):
            oldest_p = p
            break
    if oldest_p is not None:
        break

if oldest_p is None:
    print("ERROR: could not find any old summary bullet to demote", file=sys.stderr)
    sys.exit(1)

# Make sure we're not trying to demote the same bullet we're inserting before
if oldest_p is newest_p:
    print("ERROR: oldest and newest anchor resolved to the same bullet; aborting", file=sys.stderr)
    sys.exit(1)

# Insert new bullet before the newest one
newest_p.insert_paragraph_before(NEW_SUMMARY, style=newest_p.style)

# Find the Old summary section heading
old_heading = None
for p in d.paragraphs:
    if p.style.name.startswith("Heading") and "Old summary entries" in p.text:
        old_heading = p
        break

if old_heading is None:
    print("ERROR: could not find 'Old summary entries' heading", file=sys.stderr)
    sys.exit(1)

# Demote the oldest bullet: add OLD: prefix and move it after the heading
if not oldest_p.text.strip().startswith("OLD:"):
    set_text(oldest_p, "OLD: " + oldest_p.text.strip())
old_heading._p.addnext(oldest_p._p)

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
print("OK: new 14:48 backup summary bullet inserted; oldest bullet demoted to Old section; backup=%s"
      % os.path.basename(bak))
