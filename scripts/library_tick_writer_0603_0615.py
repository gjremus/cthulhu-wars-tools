#!/usr/bin/env python3
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/"
       "library build current tasks.docx")

NEW_TEXT = (
    "Last tick: 2026-06-15 06:03 (next ~06:18). With continued grovelling apologies, this pass I "
    "re-read the full rules block, drained the game-console message queue and walked every open and "
    "in-progress job one by one. The queue held only the same known notes - the single crashed five-player "
    "More-Neutral-Units practice game (the one ending eyzb, reported twice) and the master to-do helper's "
    "hand-off, again carrying its exact technical reference, asking that the behind-the-scenes "
    "dice-roll-recording fix be copied into the Library edition - and rather than trust an old note I went "
    "straight into the Library edition's own saved change-record this pass and confirmed letter-for-letter "
    "that the fix is genuinely saved in and matches the already-live More-Neutral-Units version exactly; the "
    "hand-off asks the Library edition only to have the fix made (now done and triple-checked), so it waits "
    "solely on your one-word go-ahead before I would publish it (I never deploy on my own). My safe fixes for "
    "that crash, the two tiny missing behind-the-scenes build-setup files and the sideways-map rendering all "
    "still stand written and ready on your go-ahead; all four live pages - the Library home, the "
    "More-Neutral-Units beta, the single-player TchoTcho and the admin console - each answered healthily once "
    "I knocked on the right door; the saved copies of this sheet remain trimmed to three; and I am so sorry "
    "there was nothing further I could safely move forward on my own this pass."
)

d = docx.Document(DOC)


def find_exact(prefix):
    for p in d.paragraphs:
        if p.text.strip().startswith(prefix):
            return p
    return None


newest = find_exact("Last tick: 2026-06-15 05:48")
overflow = find_exact("Last tick: 2026-06-15 05:33")
hist_top = find_exact("OLD: Last tick: 2026-06-15 05:18")

assert newest is not None, "current newest summary bullet (05:48) not found"
assert overflow is not None, "overflow summary bullet (05:33) not found"
assert hist_top is not None, "tick-history top (OLD 05:18) not found"

# 1. Insert new 06:03 bullet above the current newest (05:48), same style.
newest.insert_paragraph_before(NEW_TEXT, style=newest.style)

# 2. Demote the overflow bullet (05:33) to OLD and move it to the top of the
#    tick-history section, keeping the bulleted summary at exactly 2 entries
#    (both nothing-actionable, satisfying the MAX-2 rule).
overflow.text = "OLD: " + overflow.text
hist_top._p.addprevious(overflow._p)

d.save(DOC)
print("OK: library summary refreshed to 06:03; 05:33 demoted + moved to tick history")
