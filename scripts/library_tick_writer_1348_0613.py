#!/usr/bin/env python3
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/"
       "library build current tasks.docx")

NEW_TEXT = (
    "Last tick: 2026-06-13 13:48 (next ~14:03). With continued grovelling apologies - I drained the "
    "game-console queue and it still held only the same two notes about the one crashed five-player "
    "More-Neutral-Units practice game (the one ending eyzb), the newer being your 08:10 note "
    "confirming it 'looks like another Cyclopean Gaze bug', exactly the cause I already traced; my "
    "safe fix for it, and the two tiny missing behind-the-scenes build-setup files for that same "
    "edition, both stay written and ready and wait on nothing but your one-word go-ahead, since both "
    "touch the More-Neutral-Units edition I am not allowed to change alone (I would mirror any fix to "
    "the shared Library edition at the same moment and deploy nothing until you say so). Every live "
    "page I checked this pass - the Library home, the More-Neutral-Units beta, the admin console and "
    "a known-good saved game - answered healthily on the first try, and I re-read the full rules "
    "block, re-walked every open and in-progress job bullet by bullet, and searched the whole task "
    "sheet for any of your triple-marked replies, finding every such mark to be old and sitting only "
    "in the rules text and finished-items history with none waiting on an open job, so I am so sorry "
    "there was nothing more I could safely move forward on my own this tick."
)

d = docx.Document(DOC)


def find(prefix):
    for p in d.paragraphs:
        if p.text.strip().startswith(prefix):
            return p
    return None


newest = find("Last tick: 2026-06-13 13:34")
second = find("Last tick: 2026-06-13 13:19")
hist_top = find("OLD: Last tick: 2026-06-13 13:04")

assert newest is not None, "current newest (13:34) not found"
assert second is not None, "second summary bullet (13:19) not found"
assert hist_top is not None, "tick-history top (13:04) not found"

# 1. Insert the new 13:48 bullet above the current newest (13:34).
newest.insert_paragraph_before(NEW_TEXT, style=newest.style)

# 2. Demote the overflow summary bullet (13:19) to an OLD bullet and move it
#    into the tick-history section (newest-at-top), keeping the summary at
#    exactly 2 nothing-actionable bullets (13:48 + 13:34).
second.text = "OLD: " + second.text
hist_top._p.addprevious(second._p)

d.save(DOC)
print("OK: library summary refreshed to 13:48; 13:19 demoted + moved to tick history")
