#!/usr/bin/env python3
# Backup ticker 2026-06-24 ~21:51 — end-of-day safety-net pass on the library doc.
# All 5 games healthy, admin queue empty, no new user replies.
# Action: insert new health summary bullet at top; keep 13:33 bullet as position-2.
# Total nothing-actionable bullets = 2 (within MAX-2 limit).
# Total summary bullets = 3 (within MAX-3 limit).
import docx, shutil, time, os

DOC = (
    "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
    "My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/"
    "library build current tasks.docx"
)

# Create in-folder backup (replaces the one trashed before running)
bak = DOC + ".bak.pre_write_%d" % int(time.time())
shutil.copy2(DOC, bak)

d = docx.Document(DOC)

NEW_SUMMARY = (
    "Last tick: 2026-06-24 ~21:51. Grovelling thanks -- an end-of-day safety-net "
    "check. All five games answered healthy at their correct addresses, your admin "
    "message box is empty, and no new replies are waiting. I walked every open and "
    "waiting job; nothing was changed or deployed, everything substantial still waits "
    "only on your go-aheads, and the saved copies of this sheet stay at the allowed three."
)

# Find the existing 13:33 summary anchor — insert new bullet before it
ANCHOR = "Last tick: 2026-06-24 ~13:33"
anchor_p = None
for p in d.paragraphs:
    if p.text.strip().startswith(ANCHOR):
        anchor_p = p
        break
assert anchor_p is not None, "13:33 summary anchor not found"

anchor_p.insert_paragraph_before(NEW_SUMMARY, style=anchor_p.style)

d.save(DOC)
print("OK: library backup tick 2151 0624 written; new health bullet at top; backup=%s" % os.path.basename(bak))
