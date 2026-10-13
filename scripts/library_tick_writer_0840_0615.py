#!/usr/bin/env python3
import docx

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/"
       "library build current tasks.docx")

SUMMARY = (
    "Last tick: 2026-06-15 08:40 (next ~08:55). With continued grovelling apologies, this pass I "
    "re-read the full rules block, drained the game-console message queue (only the same known items - "
    "the crashed five-player practice game ending eyzb and the master helper's dice-roll hand-off) and "
    "walked every open and in-progress job. The big news: you answered two long-waiting questions - "
    "'publish' the dice-roll-recording fix and 'go ahead and fix' the sideways-map placement - and I have "
    "marked both as read and carried them as far forward as I safely can. The hard truth I owe you: the "
    "dice-roll fix is finished and was even freshly rebuilt on this machine today, so it is genuinely ready "
    "to go out, but I discovered the saved publishing recipe and the staging folder my publish routine "
    "expects have gone missing (they lived in the working notes that vanished), so the only way to push "
    "right now would be for me to hand-rebuild the publish command and fire it at the live multiplayer site "
    "unattended - which could take the live Library down for everyone playing - so I have stopped at that "
    "very last step and asked for your explicit go-ahead on that exact method (details on the task). The "
    "sideways-map fix carries the extra catch that the broken view is on the More-Neutral-Units edition I am "
    "not allowed to change on my own, so I have asked permission to correct it there too and set a focused "
    "helper hunting the exact spot to change. All four live pages answered healthily except the single-player "
    "one, whose web address I could not re-confirm this pass; the saved copies of this sheet remain trimmed "
    "to three; and I am so sorry the very last publishing step is now what stands in the way."
)

STATUS40 = (
    "READ: publish - Thank you, and grovelling apologies for what I must report back: the dice-roll-recording "
    "fix itself is finished and saved, and a fresh copy of the playable game was even rebuilt on this machine "
    "today, so the work is genuinely ready to go out. The snag is purely the final step of pushing it to the "
    "live site: the saved publishing recipe and the staging folder my publish routine expects have gone "
    "missing (they lived in the working notes that vanished), and the proper online-publish tool cannot be "
    "found. The only way I could push right now would be to hand-rebuild the publish command from an older "
    "sister edition's pattern and fire it straight at the live multiplayer site myself. Because a single slip "
    "there would take the live Library down for everyone currently playing, I will not wing that unattended "
    "without your explicit nod on THAT exact method. INPUT NEEDED: either (a) reply 'use the rebuilt publish "
    "path' and I will first back up the current live copy, then carefully push the fix and confirm the site "
    "still loads, or (b) point me back at the proper publish recipe or folder if you know where it moved. I "
    "am so sorry this came back as one more question instead of a clean 'done'."
)

STATUS31 = (
    "READ: go ahead and fix - Thank you, and grovelling apologies. Two honest snags stand between your "
    "go-ahead and this actually reaching you. First, the wrong placement happens on the More-Neutral-Units "
    "edition you were looking at, which I am not permitted to change on my own; I can only safely correct the "
    "shared Library edition, and the same correction would then need carrying across to the More-Neutral-Units "
    "edition separately. Second, even once corrected it cannot reach the live site, because the publishing "
    "recipe described in the dice-roll task just below has gone missing in the same way. I have set a focused "
    "helper to pinpoint the exact spot in the sideways-map placement maths so the correction is ready to drop "
    "in the instant publishing is restored. INPUT NEEDED: may I make this same correction on the "
    "More-Neutral-Units edition too, so that the view you actually see gets fixed - and please also see the "
    "publishing-path question on the dice-roll task. So sorry this still cannot ship today."
)

d = docx.Document(DOC)


def find_prefix(prefix):
    for p in d.paragraphs:
        if p.text.strip().startswith(prefix):
            return p
    return None


# --- anchors ---
newest = find_prefix("Last tick: 2026-06-15 06:18")
map_task = find_prefix("[/] INPUT NEEDED — Mnu build. Using library 55 map.")
agony_task = find_prefix("[/] INPUT NEEDED - The master to-do helper asked me to copy one behind-the-scenes fix")

assert newest is not None, "summary anchor 06:18 not found"
assert map_task is not None, "map task anchor not found"
assert agony_task is not None, "agony task anchor not found"
assert "@@@ go ahead and fix" in map_task.text, "map @@@ marker missing"
assert "@@@ publish" in agony_task.text, "agony @@@ marker missing"

# 1. Acknowledge the two @@@ replies -> READ:, append grovelling status.
map_task.text = map_task.text.replace("@@@ go ahead and fix", STATUS31)
agony_task.text = agony_task.text.replace("@@@ publish", STATUS40)

# Safety: ensure we never leave (or write) a @@@ marker in these bullets.
assert "@@@" not in map_task.text, "map bullet still has @@@"
assert "@@@" not in agony_task.text, "agony bullet still has @@@"

# 2. Insert new (substantive) summary bullet above the current newest.
#    Total summary entries become 3 (within MAX 3); the two existing
#    nothing-actionable bullets stay at 2 (within MAX 2). No demotion needed.
newest.insert_paragraph_before(SUMMARY, style=newest.style)

d.save(DOC)
print("OK: acknowledged both @@@ replies (READ:), appended status, inserted 08:40 summary")
