#!/usr/bin/env python3
# Library backup ticker 2026-06-25 ~16:40 — safety-net pass, nothing actionable.
# Updates the newest backup-ticker bullet in the summary, trims to max 2 nothing-actionable.
import docx
import sys

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Maps/Library at Celaeno/"
       "library build current tasks.docx")

NEW_TEXT = (
    "Last tick: 2026-06-25 ~16:40 (backup ticker). Grovelling apologies — "
    "re-read the full rules, drained the admin message box (empty, nothing new), "
    "and confirmed all five games fully healthy (Library, More-Neutral-Units, "
    "TchoTcho, Bubastis, and Homebrew all answered). Walked every open and waiting "
    "job; nothing was changed or deployed, and everything still waits only on your "
    "go-aheads (chiefly the sideways-map correction for the More-Neutral-Units "
    "edition you actually see, and the crashed five-player game fix)."
)

d = docx.Document(DOC)

# Find all "Last tick:" paragraphs in the summary section (before ## Open)
summary_ticks = []
in_summary = False
for i, p in enumerate(d.paragraphs):
    text = p.text.strip()
    if "Bulleted summary" in text:
        in_summary = True
        continue
    if in_summary and text.startswith("## "):
        break
    if in_summary and text.startswith("Last tick:"):
        summary_ticks.append((i, p))

if not summary_ticks:
    print("ERROR: no 'Last tick:' bullets found in summary", file=sys.stderr)
    sys.exit(1)

# Update the first (newest) one with the new timestamp
target = summary_ticks[0][1]
if target.runs:
    target.runs[0].text = NEW_TEXT
    for extra in target.runs[1:]:
        extra.text = ""
else:
    target.add_run(NEW_TEXT)

# Per Rule 22: max 2 nothing-actionable bullets. Remove extras (3rd+).
for idx in range(2, len(summary_ticks)):
    excess = summary_ticks[idx][1]
    if excess.runs:
        for run in excess.runs:
            run.text = ""
    excess.text = ""

d.save(DOC)
print(f"OK: updated library backup-ticker bullet to ~16:40, trimmed {max(0, len(summary_ticks)-2)} excess entries")
