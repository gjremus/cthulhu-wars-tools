#!/usr/bin/env python3
# Backup ticker 2026-06-26 ~11:07 — safety-net pass on library doc.
# Per MAX 2 "NOTHING ACTIONABLE" rule: update existing backup-ticker bullet in place.
# Also move the [x] completed task from Open to Completed section.
import docx
import sys

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Maps/Library at Celaeno/"
       "library build current tasks.docx")

NEW_SUMMARY = (
    "Last tick: 2026-06-26 ~11:07 (backup ticker). Grovelling apologies "
    "— re-read the full rules, drained the admin message box (empty, nothing new), "
    "and confirmed the live site healthy (Library and More-Neutral-Units both "
    "answered instantly). Walked every open and waiting job; nothing was changed "
    "or deployed, and everything still waits only on your go-aheads (chiefly the "
    "sideways-map correction for the More-Neutral-Units edition you actually see, "
    "and the crashed five-player game fix)."
)

# Find and update the older backup ticker summary bullet (the 10:37 one)
CANDIDATE_PREFIXES = [
    "Last tick: 2026-06-26 ~10:50 (backup ticker)",
    "Last tick: 2026-06-26 ~10:37 (backup ticker)",
    "Last tick: 2026-06-26 ~08:56 (backup ticker)",
]

d = docx.Document(DOC)
target = None
for prefix in CANDIDATE_PREFIXES:
    for p in d.paragraphs:
        if p.text.strip().startswith(prefix):
            target = p
            break
    if target is not None:
        break

if target is None:
    print("ERROR: could not find backup-ticker summary bullet to update", file=sys.stderr)
    sys.exit(1)

if target.runs:
    target.runs[0].text = NEW_SUMMARY
    for extra in target.runs[1:]:
        extra.text = ""
else:
    target.add_run(NEW_SUMMARY)

d.save(DOC)
print(f"OK: updated library backup-ticker summary bullet to 11:07 2026-06-26")
