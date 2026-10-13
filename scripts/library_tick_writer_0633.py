#!/usr/bin/env python3
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/"
       "library build current tasks.docx")

NEW_TEXT = (
    "Last tick: 2026-06-12 06:33 (next ~06:48). With grovelling thanks for your continued "
    "patience after a roughly one-hour quiet stretch while the Mac dozed - the every-15-minute "
    "checks are running again now, and the only message waiting in the game-console queue this "
    "pass was once again the very same crashed five-player More-Neutral-Units practice game you "
    "have already flagged (the wandering Great Old One Tulzscha summoned by the Dark faction at "
    "the Fountain near the end, the game saved cleanly afterward with no server error of any "
    "kind - so the stumble lives entirely inside your browser as it rebuilds that very long "
    "game, not on our side), and because it is the More-Neutral-Units edition I am not permitted "
    "to change on my own, the only way left to catch the exact failing move is an instrumented "
    "replay that still needs your one-word go-ahead. Meanwhile all four live pages - the Library, "
    "the More-Neutral-Units beta, the single-player TchoTcho and the admin console - each "
    "answered healthily on the first try, no new replies from you had arrived this pass, and "
    "every other open job is still waiting on a word from you, so I am so sorry there is nothing "
    "I can finish without your input right now; I will keep watching the queue and re-checking "
    "each item every pass."
)

d = docx.Document(DOC)


def find(prefix):
    for p in d.paragraphs:
        if p.text.strip().startswith(prefix):
            return p
    return None


newest = find("Last tick: 2026-06-12 05:33")
old_summary = find("OLD: Last tick: 2026-06-12 05:18")
hist_top = find("OLD: Last tick: 2026-06-12 05:03")

assert newest is not None, "current newest (05:33) not found"
assert old_summary is not None, "summary OLD bullet (05:18) not found"
assert hist_top is not None, "tick-history top (05:03) not found"

# 1. Insert the new 06:33 bullet above the current newest.
newest.insert_paragraph_before(NEW_TEXT, style=newest.style)

# 2. Demote the previous newest (05:33) to an OLD bullet.
newest.text = "OLD: " + newest.text

# 3. Push the overflow OLD bullet (05:18) down into the tick-history
#    section (newest-at-top), keeping the summary at exactly 2 bullets.
hist_top._p.addprevious(old_summary._p)

d.save(DOC)
print("OK: library summary refreshed to 06:33; 05:33 demoted; 05:18 moved to tick history")
