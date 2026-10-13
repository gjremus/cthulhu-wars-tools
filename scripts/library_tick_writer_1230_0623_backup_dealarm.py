#!/usr/bin/env python3
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/"
       "library build current tasks.docx")

NEW = (
    "Last tick: 2026-06-23 ~12:30 (backup helper, machine-clock time). Grovelling apologies for the "
    "double note — I ran a fresh, thorough reachability check from this machine just now and the live "
    "multiplayer site IS up: the host answers, the players' game pages load, the admin console and its "
    "message queue both responded (queue empty), and all five game editions returned healthy. So the "
    "'site unreachable / recovering needs you' worry in the entry just below looks like a brief blip that "
    "has already cleared and needs no action from you; the dice-roll fix stays confirmed live since "
    "June 19, and everything else still waits only on your go-aheads (the sideways-map correction on the "
    "edition you actually see, and the move-by-move replay of the crashed five-player game). I changed "
    "nothing on the live site this pass."
)

# Insert above the primary's just-written entry; demote oldest visible to keep MAX 3.
INSERT_BEFORE_PREFIX = "Last tick: 2026-06-23 ~16:05"
DEMOTE_PREFIX = "Last tick: 2026-06-15 09:50"

d = docx.Document(DOC)


def find_prefix(prefix):
    for p in d.paragraphs:
        if p.text.strip().startswith(prefix):
            return p
    return None


newest = find_prefix(INSERT_BEFORE_PREFIX)
assert newest is not None, "primary 2026-06-23 ~16:05 anchor missing -- aborting to avoid mis-insert"

newest.insert_paragraph_before(NEW, style=newest.style)

old_para = find_prefix(DEMOTE_PREFIX)
old_head = None
for p in d.paragraphs:
    if p.text.strip().startswith("Old summary entries"):
        old_head = p
        break
demoted = False
if old_para is not None and old_head is not None:
    if old_para.runs:
        old_para.runs[0].text = "OLD: " + old_para.runs[0].text
    else:
        old_para.text = "OLD: " + old_para.text
    old_head._p.addnext(old_para._p)
    demoted = True

has_empty = any(p.text.strip() == "[]" for p in d.paragraphs)
d.save(DOC)
print("OK: backup de-alarm summary added; demoted 06-15 09:50:", demoted, "; empty [] present:", has_empty)
