#!/usr/bin/env python3
# Library backup ticker 2026-06-25 ~21:06 — routine healthy pass, nothing changed/deployed.
# Updates the top summary bullet with a fresh timestamp; demotes the oldest
# nothing-actionable bullet to Old section per MAX-2 rule.
import docx, shutil, time, os

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


# ── 1. Find the summary section and locate summary bullets ──────────────────
NEW_SUMMARY = (
    "Last tick: 2026-06-25 ~21:06 (backup ticker). Grovelling apologies — re-read the full rules, "
    "drained the admin message box (empty, nothing new), and confirmed all five games fully healthy "
    "(Library, More-Neutral-Units, TchoTcho, Bubastis, and Homebrew all answered HTTP 200). Walked every "
    "open and waiting job; nothing was changed or deployed, and everything still waits only on your "
    "go-aheads (chiefly the sideways-map correction for the More-Neutral-Units edition you actually see, "
    "and the crashed five-player game fix)."
)

# Find the "OLD:" prefixed summary that starts with "Last tick: 2026-06-25 ~15:39"
# which is the 3rd bullet (already prefixed OLD:) and demote it to Old section.
# Then overwrite the top bullet with our new one.

# Strategy: find the first summary bullet that starts with "Last tick:" and
# replace it with our new text; then find the "OLD:" bullet and move it down.

summary_bullets = []
summary_start_idx = None
for i, p in enumerate(d.paragraphs):
    txt = p.text.strip()
    if txt.startswith("Bulleted summary"):
        summary_start_idx = i
        continue
    if summary_start_idx is not None and txt.startswith(("Last tick:", "OLD:")):
        summary_bullets.append((i, p))
    if summary_start_idx is not None and txt.startswith("Open"):
        break

assert len(summary_bullets) >= 2, f"Expected >=2 summary bullets, found {len(summary_bullets)}"

# Replace the first (newest) bullet with our new text
first_bullet = summary_bullets[0][1]
set_text(first_bullet, NEW_SUMMARY)

# The third bullet (if exists, already OLD: prefixed) should be moved to Old section
if len(summary_bullets) >= 3:
    old_bullet = summary_bullets[2][1]
    # Find the Old summary entries heading
    old_heading = None
    for p in d.paragraphs:
        if "Old summary entries" in p.text:
            old_heading = p
            break
    if old_heading is not None:
        if not old_bullet.text.strip().startswith("OLD:"):
            set_text(old_bullet, "OLD: " + old_bullet.text.strip())
        old_heading._p.addnext(old_bullet._p)

d.save(DOC)
print("OK: backup ticker health bullet written; backup=%s" % os.path.basename(bak))
