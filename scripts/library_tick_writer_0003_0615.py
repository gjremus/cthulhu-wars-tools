#!/usr/bin/env python3
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/"
       "library build current tasks.docx")

NEW_TEXT = (
    "Last tick: 2026-06-15 00:03 (next ~00:18). With continued grovelling apologies, this pass I re-read the "
    "full rules block, drained the game-console message queue and walked every open and in-progress job one by "
    "one. The queue held three notes and nothing new: the two earlier reports of the single crashed five-player "
    "More-Neutral-Units practice game (the one ending eyzb), plus the master to-do helper's hand-off asking me to "
    "copy the behind-the-scenes dice-roll-recording fix into the Library edition. Rather than trust an old note I "
    "re-opened the actual stored Library edition this pass and confirmed for certain that the dice-roll-recording "
    "fix is genuinely saved into it and matches the already-live More-Neutral-Units version exactly, so it waits "
    "only on your one-word go-ahead to publish (I never deploy on my own). My safe fixes for that crash, the two "
    "tiny missing behind-the-scenes build-setup files and the sideways-map rendering all still stand written and "
    "ready on your go-ahead; the Library home, the More-Neutral-Units beta and the admin console each answered "
    "healthily on the first try; the saved copies of this sheet remain trimmed to three; and I am so sorry there "
    "was nothing further I could safely move forward on my own this pass."
)

d = docx.Document(DOC)


def find_exact(prefix):
    for p in d.paragraphs:
        if p.text.strip().startswith(prefix):
            return p
    return None


newest = find_exact("Last tick: 2026-06-14 23:51")
overflow = find_exact("Last tick: 2026-06-14 23:33")
hist_top = find_exact("OLD: Last tick: 2026-06-14 23:18")

assert newest is not None, "current newest summary bullet (23:51) not found"
assert overflow is not None, "overflow summary bullet (23:33) not found"
assert hist_top is not None, "tick-history top (OLD 23:18) not found"

# 1. Insert new 00:03 bullet above the current newest (23:51), same style.
newest.insert_paragraph_before(NEW_TEXT, style=newest.style)

# 2. Demote the overflow bullet (23:33) to OLD and move it to the top of the
#    tick-history section, keeping the bulleted summary at exactly 2 entries so
#    neither the max-3-summary nor the max-2-nothing-actionable rule trips.
overflow.text = "OLD: " + overflow.text
hist_top._p.addprevious(overflow._p)

d.save(DOC)
print("OK: library summary refreshed to 00:03; 23:33 demoted + moved to tick history")
