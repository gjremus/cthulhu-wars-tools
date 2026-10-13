#!/usr/bin/env python3
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/"
       "library build current tasks.docx")

NEW_TEXT = (
    "Last tick: 2026-06-15 05:33 (next ~05:48). With continued grovelling apologies, this pass I "
    "re-read the full rules block, drained the game-console message queue and walked every open and "
    "in-progress job one by one. The queue held only the same known notes - the single crashed five-player "
    "More-Neutral-Units practice game (the one ending eyzb, reported twice) and the master to-do helper's "
    "hand-off, which this pass arrived with its exact technical reference attached, asking that the "
    "behind-the-scenes dice-roll-recording fix be copied into the Library edition - and this pass I opened "
    "the Library edition's own saved change-record side by side with that freshly-referenced already-live "
    "More-Neutral-Units version and confirmed the fix is genuinely saved in and matches it letter-for-letter; "
    "the hand-off only asks the Library edition to have the fix made (now done and double-checked), so it "
    "waits solely on your one-word go-ahead before I would publish it (I never deploy on my own). My safe "
    "fixes for that crash, the two tiny missing behind-the-scenes build-setup files and the sideways-map "
    "rendering all still stand written and ready on your go-ahead; all four live pages - the Library home, "
    "the More-Neutral-Units beta, the single-player TchoTcho and the admin console - each answered healthily "
    "on the first try; the saved copies of this sheet remain trimmed to three; and I am so sorry there was "
    "nothing further I could safely move forward on my own this pass."
)

d = docx.Document(DOC)


def find_exact(prefix):
    for p in d.paragraphs:
        if p.text.strip().startswith(prefix):
            return p
    return None


newest = find_exact("Last tick: 2026-06-15 05:18")
overflow = find_exact("Last tick: 2026-06-15 05:03")
hist_top = find_exact("OLD: Last tick: 2026-06-15 04:48")

assert newest is not None, "current newest summary bullet (05:18) not found"
assert overflow is not None, "overflow summary bullet (05:03) not found"
assert hist_top is not None, "tick-history top (OLD 04:48) not found"

# 1. Insert new 05:33 bullet above the current newest (05:18), same style.
newest.insert_paragraph_before(NEW_TEXT, style=newest.style)

# 2. Demote the overflow bullet (05:03) to OLD and move it to the top of the
#    tick-history section, keeping the bulleted summary at exactly 2 entries.
overflow.text = "OLD: " + overflow.text
hist_top._p.addprevious(overflow._p)

d.save(DOC)
print("OK: library summary refreshed to 05:33; 05:03 demoted + moved to tick history")
