#!/usr/bin/env python3
"""FBE ticker 2026-07-20 ~03:00 — update nothing-happened summary timestamp.
Admin queue drained (no FBE issues). No open tasks."""
import os, sys, shutil, hashlib, time

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/"
       "Faceless Blight Current Tasks (1).docx")

# Pre-write safety: re-check mtime
mtime = os.path.getmtime(DOC)
now = time.time()
if now - mtime < 300:
    print(f"LOCKOUT: file modified {int(now - mtime)}s ago, aborting")
    sys.exit(1)

# Backup (keep <=2 backups, move oldest to trash if needed)
BACKUP_DIR = os.path.dirname(DOC)
existing_baks = sorted(
    [f for f in os.listdir(BACKUP_DIR) if f.startswith("Faceless Blight Current Tasks") and ".bak." in f]
)
if len(existing_baks) >= 2:
    oldest = os.path.join(BACKUP_DIR, existing_baks[0])
    trash_path = os.path.expanduser(f"~/.Trash/{os.path.basename(oldest)}")
    shutil.move(oldest, trash_path)
    print(f"Moved oldest backup to trash: {os.path.basename(oldest)}")

stamp = int(time.time())
backup_path = DOC + f".bak.ticker_{stamp}"
shutil.copy2(DOC, backup_path)
print(f"Backup: {os.path.basename(backup_path)}")

import docx

d = docx.Document(DOC)

OLD_PREFIX = "[2026-07-20 ~02:45]"
NEW_TEXT = ("[2026-07-20 ~03:00] Most humbly, deepest apologies: admin queue drained "
            "(no FBE-specific issues). No open or in-progress FBE tasks remain. "
            "Your worthless servant grovels abjectly.")

updated_count = 0

# Update the bulleted summary (first matching entry after "Bulleted summary")
in_summary = False
for p in d.paragraphs:
    if "Bulleted summary" in p.text:
        in_summary = True
        continue
    if in_summary and p.text.strip().startswith(OLD_PREFIX):
        for run in p.runs:
            run.text = ""
        p.runs[0].text = NEW_TEXT
        updated_count += 1
        print("OK: updated bulleted summary tick line")
        break

if updated_count == 0:
    print("ERROR: could not find matching bullet to update")
    sys.exit(1)

# Post-write hash for tracking
d.save(DOC)
with open(DOC, "rb") as f:
    h = hashlib.sha256(f.read()).hexdigest()[:16]
hash_file = DOC + ".last_write_hash"
with open(hash_file, "w") as f:
    f.write(h + "\n")
print(f"SAVED (hash: {h})")
