#!/usr/bin/env python3
# Backup ticker 2026-06-24 ~05:46 — add ONE brief backup summary line atop the
# library summary. Currently only two displayed summary bullets (05:18, 05:03),
# so adding one reaches the MAX-3 cap with no demote needed. Substantive outage
# re-confirm (not a "nothing actionable" bullet), so the max-2 trim rule is N/A.
import docx, shutil, time, os

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/"
       "library build current tasks.docx")

bak = DOC + ".bak.pre_write_%d" % int(time.time())
shutil.copy2(DOC, bak)

NEW_SUMMARY = (
    "Last tick: 2026-06-24 ~05:46 (backup helper). Grovelling apologies — a safety-net check confirms the live "
    "site is STILL down, now about an hour into this outage (it briefly recovered near 05:03, then seized again): "
    "the server answers a basic network ping but every page and the admin message box still freeze partway through "
    "every connection, so I could not read the message queue. Nothing was changed or deployed; it still needs the "
    "hard reboot from your cloud control panel (only you can do that), and the moment it answers I will confirm "
    "every page loads and the prepared fixes go out."
)

ANCHOR_0518 = "Last tick: 2026-06-24 ~05:18"

d = docx.Document(DOC)
newest = None
for p in d.paragraphs:
    if p.text.strip().startswith(ANCHOR_0518):
        newest = p
        break
assert newest is not None, "05:18 summary anchor missing"
newest.insert_paragraph_before(NEW_SUMMARY, style=newest.style)

d.save(DOC)
print("OK: backup summary line added atop library (now 3 bullets); backup:",
      os.path.basename(bak))
