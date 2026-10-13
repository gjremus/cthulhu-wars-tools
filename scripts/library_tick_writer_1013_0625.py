#!/usr/bin/env python3
"""
library_tick_writer_1013_0625.py
Library ticker pass, 2026-06-25 ~03:13 PT.
1. Create .bak copy next to docx.
2. Insert new summary bullet at top of Bulleted summary.
3. Demote the "Last tick: 2026-06-24 ~22:03" nothing-actionable bullet to Old summary entries
   (per Rule 21: adding a new bullet at 3 max means oldest nothing-actionable moves out).
4. Mark two long-standing [] READ: tasks as [x] since both were acknowledged and fixes confirmed.
5. Regenerate the .last_seen_tasks.md mirror.
"""
import sys
import shutil
import time
import os
from docx import Document

DOC = (
    "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
    "My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/"
    "library build current tasks.docx"
)
MIRROR = (
    "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
    "My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/.last_seen_tasks.md"
)

bak = DOC + ".bak.pre_write_%d" % int(time.time())
shutil.copy2(DOC, bak)
print(f"Backup: {os.path.basename(bak)}")

d = Document(DOC)


def set_text(p, txt):
    runs = list(p.runs)
    if runs:
        runs[0].text = txt
        for r in runs[1:]:
            r.text = ""
    else:
        p.add_run(txt)


NEW_SUMMARY = (
    "Last tick: 2026-06-25 ~03:13. Grovelling thanks — re-read the full rules, drained the "
    "game console's message box (empty, nothing new), and confirmed the live site healthy: "
    "the Library single-player edition answered instantly. I walked every open and waiting "
    "job; marked two long-standing acknowledged items complete, and everything else still "
    "waits only on your go-aheads (chiefly the sideways-map correction for the edition you "
    "actually see and the crashed five-player game fix)."
)

# Anchor: the ~22:03 nothing-actionable bullet to demote to OLD
ANCHOR_2203 = "Last tick: 2026-06-24 ~22:03"

# Anchors for the two [] READ: tasks to mark [x]
ANCHOR_TICKER_MASTER = "[] READ: ticker for master current tasks doc"
ANCHOR_DID_YOU_SEE = "[] READ: did you see the task at the top?"

# ── Step 1: Find the ~22:03 paragraph ────────────────────────────────────────
anchor_2203_p = None
for p in d.paragraphs:
    if p.text.strip().startswith(ANCHOR_2203):
        anchor_2203_p = p
        break

if anchor_2203_p is None:
    print(f"ERROR: 22:03 summary anchor not found", file=sys.stderr)
    sys.exit(1)

# ── Step 2: Insert new summary before the ~22:03 paragraph ───────────────────
anchor_2203_p.insert_paragraph_before(NEW_SUMMARY, style=anchor_2203_p.style)
print(f"Inserted new summary before 22:03 bullet")

# ── Step 3: Demote the ~22:03 paragraph to Old summary entries ───────────────
old_heading = None
for p in d.paragraphs:
    if p.style.name.startswith("Heading") and "Old summary entries" in p.text:
        old_heading = p
        break

if old_heading is None:
    print("ERROR: Old summary entries heading not found", file=sys.stderr)
    sys.exit(1)

if not anchor_2203_p.text.strip().startswith("OLD:"):
    set_text(anchor_2203_p, "OLD: " + anchor_2203_p.text.strip())
old_heading._p.addnext(anchor_2203_p._p)
print(f"Demoted 22:03 bullet to Old section")

# ── Step 4a: Mark "ticker for master" task [x] ───────────────────────────────
ticker_p = None
for p in d.paragraphs:
    if p.text.strip().startswith(ANCHOR_TICKER_MASTER):
        ticker_p = p
        break

if ticker_p is None:
    print("ERROR: 'ticker for master' paragraph not found", file=sys.stderr)
    sys.exit(1)

new_text = ticker_p.text.strip().replace("[] READ:", "[x] READ:", 1)
set_text(ticker_p, new_text)
print(f"Marked [x]: ticker for master task")

# ── Step 4b: Mark "did you see" task [x] ─────────────────────────────────────
did_you_see_p = None
for p in d.paragraphs:
    if p.text.strip().startswith(ANCHOR_DID_YOU_SEE):
        did_you_see_p = p
        break

if did_you_see_p is None:
    print("ERROR: 'did you see' paragraph not found", file=sys.stderr)
    sys.exit(1)

new_text2 = did_you_see_p.text.strip().replace("[] READ:", "[x] READ:", 1)
set_text(did_you_see_p, new_text2)
print(f"Marked [x]: did you see task")

# ── Step 5: Save ─────────────────────────────────────────────────────────────
d.save(DOC)
print(f"OK: saved {DOC}")

# ── Step 6: Regenerate .last_seen_tasks.md mirror ────────────────────────────
lines = []
for p in d.paragraphs:
    if p.style.name.startswith("Heading"):
        lines.append("## " + p.text)
    else:
        lines.append(p.text)
with open(MIRROR, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"Mirror regenerated: {len(lines)} paragraphs")
