# HRF Upstream Reference (original Cthulhu Wars Online source)

**Canonical upstream repo:** https://github.com/haunt-roll-fail/cthulhu-wars

This is the ORIGINAL cwo.im / HRF ("haunt-roll-fail") Scala.js source that all
of our builds (Library / MNU / TchoTcho / Bubastis / Homebrew) descend from.

## When to use it
Before changing or "fixing" any base game mechanic (battle flow, spellbook
timing, phase order, undo/replay behaviour), check what the ORIGINAL code does
here first. Several of our bugs have been self-inflicted "fixes" that diverged
from this upstream. If our behaviour differs from upstream and the rules say it
shouldn't, upstream is the source of truth.

## How to pull a fresh copy for reference
    git clone --depth 1 https://github.com/haunt-roll-fail/cthulhu-wars.git /tmp/hrf-ref
    # Scala sources live under /tmp/hrf-ref/solo/*.scala

## Key files
- solo/Battle.scala   — battle phase order, Unholy Ground, retreats, kills/pains
- solo/Game.scala      — has()/can(), doom phase, undo/replay plumbing
- solo/Faction*.scala   — per-faction abilities

## Notes captured from upstream (append as discovered)
- Unholy Ground (Battle.scala): preroll tags the side with `s.has(UnholyGround)`
  (NOT `s.can(...)`); the UnholyGroundPhase offer fires whenever
  `game.cathedrals.has(arena)` for a tagged side — NO enemy-GOO precondition.
  It sits in the kills chain (Eliminate -> Berserkergang -> UnholyGround ->
  Necrophagy -> pains -> ... -> Cannibalism at BattleEnd), so it precedes
  Cannibalism.
