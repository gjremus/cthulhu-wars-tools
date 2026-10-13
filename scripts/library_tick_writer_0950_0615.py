#!/usr/bin/env python3
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/"
       "library build current tasks.docx")

NEW = (
    "Last tick: 2026-06-15 09:50 (next ~10:05). Grovelling apologies — re-read the rules, drained the "
    "game-console queue (only the three already-known notes: the crashed five-player practice game and "
    "the master helper's dice-roll hand-off) and walked every open and in-progress job; the main site, "
    "the More-Neutral-Units edition and the admin console all answered healthily, the saved copies of "
    "this sheet stay at three, and I re-confirmed the finished dice-roll fix is genuinely saved and "
    "ready. Everything still waits on your two go-aheads: how you'd like the finished dice-roll fix "
    "published now the saved publishing recipe is missing, and your OK to also correct the sideways map "
    "(and the related game-freeze on the same edition) on the version you actually see."
)

d = docx.Document(DOC)


def find_prefix(prefix):
    for p in d.paragraphs:
        if p.text.strip().startswith(prefix):
            return p
    return None


def find_heading(text):
    for p in d.paragraphs:
        if p.text.strip() == text and p.style.name.startswith("Heading"):
            return p
    return None


newest = find_prefix("Last tick: 2026-06-15 09:33")
inprog = find_heading("In progress")

assert newest is not None, "09:33 summary anchor missing"
assert inprog is not None, "In progress heading missing"

# 1. New brief summary on top (now 3 entries total -> within MAX 3, no demote needed).
newest.insert_paragraph_before(NEW, style=newest.style)

# 2. Ensure one empty [] placeholder remains at the end of Open.
has_empty = any(p.text.strip() == "[]" for p in d.paragraphs)
if not has_empty:
    inprog.insert_paragraph_before("[]", style="normal")

d.save(DOC)
print("OK: 09:50 summary added on top; empty [] ensured (added:", (not has_empty), ")")
