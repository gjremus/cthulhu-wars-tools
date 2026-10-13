#!/usr/bin/env python3
"""FBE tick ~18:44 2026-07-20 — correct the rollback-guide entry for the
neutral-monster combat-dice fix.

The 2026-07-20 ~17:05 rollback entry documents the WRONG fix predicate
(`&& u.faction.real`). That predicate would NOT fix the bug: a controlled /
Shapestolen neutral monster carries the real CONTROLLING faction (FBE), so
`.faction.real` is true for it and it would never be excluded — the double-count
would remain. The actual code (working tree, still pending deploy) correctly uses
the class-based test `&& !u.uclass.is[NeutralMonster]`. Rewrite para 0 to match
the real code so the rollback doc is accurate (Rule 12).
"""
import sys
import tempfile
import subprocess
from docx import Document

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/HomeBrews/Homebrews Deployed Online Rollback Guide.docx"
SAFE_WRITE = "/Users/gremus/Claude-Projects/cthulhu-wars-tools/scripts/safe-docx-write.sh"

MATCH = "2026-07-20 ~17:05 — FIX: FBE combat strength double-counted"
NEW_TEXT = (
    "2026-07-20 ~17:05 — FIX: FBE combat strength double-counted controlled "
    "Neutral Monsters. In FactionFBE.scala FBE.strength, the Monster cost "
    "term (u.uclass.utype == Monster ⇒ +cost) fired for EVERY Monster on "
    "FBE’s side, including controlled Neutral Monsters — which are ALSO "
    "scored by neutralStrength. Result: a controlled Neutral Monster (e.g. a "
    "Gug, cost 1 / combat 3) rolled 4 dice instead of 3. Fix: added "
    "&& !u.uclass.is[NeutralMonster] to the cost-term filter, so Neutral Monsters "
    "are excluded from the cost term and scored ONLY by neutralStrength. "
    "IMPORTANT — the exclusion MUST be by unit CLASS, not by faction: a "
    "controlled/Shapestolen neutral monster carries the real controlling faction "
    "(FBE), so a faction-based test (&& u.faction.real) would be TRUE for it and "
    "would NOT exclude it, leaving the bug in place. Fungal Thralls "
    "(FactionUnitClass(FBE), cost 2 = combat 2) and Shapestolen enemy-faction "
    "Monsters (not NeutralMonster classes) stay counted by cost — UNCHANGED. "
    "File: solo/FactionFBE.scala line 102. Rollback: remove "
    "&& !u.uclass.is[NeutralMonster] from the filter predicate, recompile, "
    "redeploy. NOT YET DEPLOYED — no Java runtime on the ticker machine; "
    "awaiting a build/deploy machine and creator go-ahead (see Q9). "
    "Game-compatible (combat-scoring change only; affects only battles where FBE "
    "controls a Neutral Monster)."
)

doc = Document(DOC_PATH)

updated = 0
for para in doc.paragraphs:
    if MATCH in para.text:
        for i, run in enumerate(para.runs):
            run.text = NEW_TEXT if i == 0 else ""
        updated += 1
        break

if updated == 0:
    print("ERROR: Could not find the ~17:05 neutral-monster rollback entry", file=sys.stderr)
    sys.exit(1)

tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
doc.save(tmp.name)
tmp.close()

result = subprocess.run([SAFE_WRITE, tmp.name, DOC_PATH], capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print(f"safe-docx-write.sh failed: {result.stderr}", file=sys.stderr)
    sys.exit(1)

print("Corrected rollback-guide entry to class-based predicate")
