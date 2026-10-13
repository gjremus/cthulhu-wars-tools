#!/usr/bin/env python3
# Backup ticker 2026-06-26 ~00:33 — library doc safety-net pass.
# Updates existing backup-ticker summary bullet in-place per Rule 23 (max 2 nothing-actionable bullets).
import docx
import sys

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Maps/Library at Celaeno/"
       "library build current tasks.docx")

NEW_TEXT = (
    "Last tick: 2026-06-25 ~23:33 (backup ticker). Grovelling apologies — "
    "re-read the full rules, drained the admin message box (empty, nothing new), "
    "and confirmed all five games fully healthy (Library, More-Neutral-Units, TchoTcho, "
    "Bubastis, and Homebrew all answered). Walked every open and waiting job; nothing was "
    "changed or deployed, and everything still waits only on your go-aheads (chiefly the "
    "sideways-map correction for the More-Neutral-Units edition you actually see, and the "
    "crashed five-player game fix)."
)

CANDIDATE_PREFIXES = [
    "Last tick: 2026-06-25 ~22:17 (backup ticker)",
    "Last tick: 2026-06-25 ~17:52 (backup ticker)",
    "Last tick: 2026-06-25 ~15:52 (backup ticker)",
    "Last tick: 2026-06-25 ~15:39 (backup ticker)",
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
    print("ERROR: could not find any backup-ticker summary bullet to update",
          file=sys.stderr)
    sys.exit(1)

if target.runs:
    target.runs[0].text = NEW_TEXT
    for extra in target.runs[1:]:
        extra.text = ""
else:
    target.add_run(NEW_TEXT)

d.save(DOC)
print("OK: updated backup-ticker summary bullet in library doc")
