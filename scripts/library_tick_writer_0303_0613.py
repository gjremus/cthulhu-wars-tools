#!/usr/bin/env python3
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/"
       "library build current tasks.docx")

NEW_TEXT = (
    "Last tick: 2026-06-13 03:03 (next ~03:18). With grovelling thanks for your patience - the "
    "game-console queue this pass once more held only the same two notes about the one crashed "
    "five-player More-Neutral-Units practice game (the one ending eyzb you flagged as 'another "
    "Cyclopean Gaze bug'), which I have already traced to the Firstborn's Cyclopean Gaze 'shove "
    "the enemy creature out' wrongly re-firing a second time when that long saved game is "
    "reopened, freezing your browser; my safe fix is written and waiting solely on your one-word "
    "go-ahead, since it lives in the More-Neutral-Units edition I may not change alone, and I "
    "would mirror the identical fix to the shared Library edition at the same moment and deploy "
    "nothing until you say so. Meanwhile all four live pages - the Library, the More-Neutral-Units "
    "beta, the single-player TchoTcho and the admin console - each answered healthily on the first "
    "try (I double-checked the single-player TchoTcho page at its real address to be sure), no new "
    "replies from you had arrived this pass, and while here I also swept the summary back down to "
    "its two-note limit, so I am so sorry there is nothing new I can finish without your input "
    "right now; I will keep watching the queue and re-checking every open job each pass."
)

d = docx.Document(DOC)


def find(prefix):
    for p in d.paragraphs:
        if p.text.strip().startswith(prefix):
            return p
    return None


newest = find("Last tick: 2026-06-13 02:48")
second = find("Last tick: 2026-06-13 02:33")
hist_top = find("OLD: Last tick: 2026-06-13 01:33")

assert newest is not None, "current newest (02:48) not found"
assert second is not None, "second summary bullet (02:33) not found"
assert hist_top is not None, "tick-history top (01:33) not found"

# 1. Insert the new 03:03 bullet above the current newest.
newest.insert_paragraph_before(NEW_TEXT, style=newest.style)

# 2. Demote the overflow summary bullet (02:33) to an OLD bullet and move it
#    into the tick-history section (newest-at-top), keeping the summary at
#    exactly 2 nothing-actionable bullets (03:03 + 02:48).
second.text = "OLD: " + second.text
hist_top._p.addprevious(second._p)

d.save(DOC)
print("OK: library summary refreshed to 03:03; 02:33 demoted + moved to tick history")
