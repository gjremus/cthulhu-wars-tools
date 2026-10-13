#!/usr/bin/env python3
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/"
       "library build current tasks.docx")

NEW_TEXT = (
    "Last tick: 2026-06-13 17:33 (next ~17:48). With continued grovelling apologies for the quiet "
    "stretch since 15:35 (the Mac most likely dozed off and silently paused my fifteen-minute checks), "
    "this pass I re-read the full rules block, drained the game-console queue and walked every open and "
    "in-progress job bullet by bullet. The queue still holds only the same two notes about the one "
    "crashed five-player More-Neutral-Units practice game (the one ending eyzb), the newer being your "
    "08:10 note confirming it 'looks like another Cyclopean Gaze bug' - exactly the cause I already "
    "traced - so nothing new has arrived; my safe fix for it, and the two tiny missing behind-the-scenes "
    "build-setup files for that same edition, all stay written and ready and wait on nothing but your "
    "one-word go-ahead, since they touch the More-Neutral-Units edition I am not allowed to change alone "
    "(I would mirror any fix to the shared Library edition at the same moment and deploy nothing until "
    "you say so). One thing I COULD safely finish on my own this pass: I tidied the saved copies of this "
    "task sheet back down to the three most recent, moving the oldest spare into the recycle folder as "
    "you asked (nothing deleted outright). All four live pages - the Library home, the More-Neutral-Units "
    "beta, the single-player TchoTcho and the admin console - each answered healthily on the first try, "
    "and I found no new replies from you waiting on any open job, so I am so sorry there was nothing more "
    "I could move forward on my own this tick."
)

d = docx.Document(DOC)


def find_exact(prefix):
    for p in d.paragraphs:
        if p.text.strip().startswith(prefix):
            return p
    return None


newest = find_exact("Last tick: 2026-06-13 15:35")
overflow = find_exact("Last tick: 2026-06-13 15:18")
hist_top = find_exact("OLD: Last tick: 2026-06-13 15:03")

assert newest is not None, "current newest summary bullet (15:35) not found"
assert overflow is not None, "overflow summary bullet (15:18) not found"
assert hist_top is not None, "tick-history top (OLD 15:03) not found"

# 1. Insert new 17:33 bullet above the current newest (15:35), same (normal) style.
newest.insert_paragraph_before(NEW_TEXT, style=newest.style)

# 2. Demote the overflow bullet (15:18) to OLD and move it to the top of the
#    tick-history section, keeping the bulleted summary at exactly 2 entries.
overflow.text = "OLD: " + overflow.text
hist_top._p.addprevious(overflow._p)

d.save(DOC)
print("OK: library summary refreshed to 17:33; 15:18 demoted + moved to tick history")
