#!/bin/zsh
# Daily job: when game 454 ("Existence and Colour") finishes, restore the Task #110
# true-owner Agony Sting behaviour that was temporarily reverted for that game's replay,
# rebuild+deploy MNU, then unload this launchd agent so it never runs again.
#
# SAFE BY DESIGN:
#   - If game 454 is not over (or the check errors), does NOTHING.
#   - Only flips the two `=== AGONY-STING-110-REVERT ===` blocks in IGOOs.scala.
#   - Verifies the flip took (comment markers gone, #110 lines active) before deploying.
#   - Never touches game DATA — only source code + a normal deploy.
set -u
LOG=/tmp/cw-agony-sting-restore.log
exec >>"$LOG" 2>&1
echo "===== $(date) run-agony-sting-restore ====="

CHECK=/Users/gremus/Claude-Projects/cthulhu-wars-tools/tickers/check-agony-sting-restore.cjs
IGOO=/Users/gremus/Claude-Projects/cw-mnu-wt/solo/IGOOs.scala
DEPLOY=/Users/gremus/cthulhu-wars-tools/server-deploy/deploy-mnu-to-vm.sh
PLIST=/Users/gremus/Library/LaunchAgents/com.gremus.cw-agony-sting-restore.plist
NODE=$(command -v node || echo /usr/local/bin/node)

"$NODE" "$CHECK"
if [[ $? -ne 0 ]]; then
  echo "game 454 not over (or check failed) — leaving revert in place."
  exit 0
fi
echo "game 454 is OVER — restoring #110 Agony Sting."

if ! grep -q "AGONY-STING-110-REVERT" "$IGOO"; then
  echo "revert markers already gone — nothing to restore. Unloading agent."
  launchctl bootout gui/$(id -u) "$PLIST" 2>/dev/null
  exit 0
fi

cp "$IGOO" "$IGOO.pre-restore.bak"

# Use python for a precise, marker-anchored transform (no fragile sed multiline).
python3 - "$IGOO" <<'PYEOF'
import sys, re
path = sys.argv[1]
src = open(path).read()

# Eligibility block (MainAction): activate the true-owner oceanAreas, drop the control one.
src = src.replace(
'''            val oceanAreas = areas.%(_.glyph == Ocean).%(r =>
                game.factions./~(f => f.at(r).%(_.uclass.utype == Cultist)).exists(u => self.enemies.has(u.faction)))''',
'''            val oceanAreas = areas.%(_.glyph == Ocean).%(r =>
                game.factions./~(f => f.at(r).%(_.uclass.utype == Cultist)).exists(u => self.enemies.has(MindParasite.trueOwner(u))))''')

# Selection block (TargetAction): activate the true-owner perFaction, drop the control one.
src = src.replace(
'''            val allCultists = game.factions./~(f => f.at(r).%(_.uclass.utype == Cultist))
            val perFaction = self.enemies./(owner => (owner, allCultists.%(u => u.faction == owner)./(_.ref))).%{ case (_, units) => units.any }''',
'''            val allCultists = game.factions./~(f => f.at(r).%(_.uclass.utype == Cultist))
            val perFaction = self.enemies./(owner => (owner, allCultists.%(u => MindParasite.trueOwner(u) == owner)./(_.ref))).%{ case (_, units) => units.any }''')

# Remove the marker/comment scaffolding lines entirely.
out = []
for line in src.splitlines(keepends=True):
    s = line.strip()
    if s.startswith("// === AGONY-STING-110-REVERT"): continue
    if s == "// === AGONY-STING-110-REVERT END ===": continue
    if s.startswith("// TEMPORARY REVERT"): continue
    if s.startswith("// (\"Existence and Colour\")") or s.startswith("// CONTROLLED"): continue
    if s.startswith("// The #110") or s.startswith("// the #110 block"): continue
    if s.startswith("// how game 454") or s.startswith("// when game 454"): continue
    if s.startswith("// --- #110 version"): continue
    if s.startswith("// val oceanAreas") or s.startswith("//     game.factions"): continue
    if s.startswith("// val perFaction"): continue
    out.append(line)
open(path, "w").write("".join(out))
print("transform applied")
PYEOF

# Verify the flip: markers gone AND true-owner lines present.
if grep -q "AGONY-STING-110-REVERT" "$IGOO"; then
  echo "ERROR: markers still present after transform. Restoring backup, aborting."
  cp "$IGOO.pre-restore.bak" "$IGOO"; exit 1
fi
if ! grep -q "self.enemies.has(MindParasite.trueOwner(u))" "$IGOO"; then
  echo "ERROR: true-owner eligibility line missing after transform. Restoring backup, aborting."
  cp "$IGOO.pre-restore.bak" "$IGOO"; exit 1
fi
if ! grep -q "MindParasite.trueOwner(u) == owner" "$IGOO"; then
  echo "ERROR: true-owner selection line missing after transform. Restoring backup, aborting."
  cp "$IGOO.pre-restore.bak" "$IGOO"; exit 1
fi
echo "transform verified — #110 restored in source."

# Rebuild + deploy MNU via the canonical script.
/bin/zsh "$DEPLOY"
if [[ $? -ne 0 ]]; then
  echo "ERROR: deploy failed. Source left with #110 restored; backup at $IGOO.pre-restore.bak"
  exit 1
fi
echo "MNU redeployed with #110 restored."

# Unload self so this never runs again.
launchctl bootout gui/$(id -u) "$PLIST" 2>/dev/null
echo "agent unloaded. done."
exit 0
