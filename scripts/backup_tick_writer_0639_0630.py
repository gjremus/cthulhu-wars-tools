#!/usr/bin/env python3
"""Backup ticker 2026-06-30 ~06:39 — TT short-link FIXED, update summary."""
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx")

d = docx.Document(DOC)

# --- 1. Replace the oldest summary bullet (the 06:29 master ticker one) with our tick ---
OLD_SUMMARY_PREFIX = "2026-06-30 ~06:29 CDT (master ticker)"
NEW_SUMMARY = ("2026-06-30 ~06:39 CDT (backup ticker): TT short-link FIXED AND LIVE "
               "— added /TT/ redirect to the server routing so players using the short address "
               "now land on the TchoTcho build correctly. Both in-progress tasks still blocked "
               "on user input. Admin queue empty. All 5 builds healthy (200).")

summary_updated = False
for p in d.paragraphs:
    if p.text.strip().startswith(OLD_SUMMARY_PREFIX):
        for run in p.runs:
            run.text = ""
        if p.runs:
            p.runs[0].text = NEW_SUMMARY
        else:
            p.add_run(NEW_SUMMARY)
        print(f"Updated summary bullet")
        summary_updated = True
        break

if not summary_updated:
    print("WARNING: Could not find the ~06:29 summary bullet to update")

# --- 2. Mark TT short-link task as complete and move it ---
TT_PREFIX = "[] TT short-link broken"
TT_DONE_TEXT = ("[x] FIXED AND DEPLOYED (Caddy reload 2026-06-30). TT short-link — the /TT/ "
                "web address shortcut was returning 'not found' because the server routing had "
                "no alias for that path. Added redirect rules so /TT and /TT/ both forward to "
                "the full /TchoTcho/ address. Verified working — players using the short link "
                "now reach the game correctly.")

tt_para = None
tt_idx = None
for i, p in enumerate(d.paragraphs):
    if p.text.strip().startswith(TT_PREFIX):
        tt_para = p
        tt_idx = i
        break

if tt_para:
    # Update the text in-place to [x]
    for run in tt_para.runs:
        run.text = ""
    if tt_para.runs:
        tt_para.runs[0].text = TT_DONE_TEXT
    else:
        tt_para.add_run(TT_DONE_TEXT)
    print(f"Marked TT short-link task as [x] complete at paragraph {tt_idx}")
else:
    print("WARNING: Could not find TT short-link task to mark complete")

# --- 3. Ensure there's still an empty [] in Open ---
# Check if there's already a standalone [] bullet in the Open section
has_empty_bracket = False
in_open = False
for p in d.paragraphs:
    text = p.text.strip()
    if text == "Open":
        in_open = True
        continue
    if text in ("In Progress", "Completed") and in_open:
        break
    if in_open and text == "[]":
        has_empty_bracket = True
        break

if has_empty_bracket:
    print("Empty [] bullet already exists in Open")
else:
    print("NOTE: Empty [] should already be there from existing doc structure")

d.save(DOC)
print("OK: saved")
