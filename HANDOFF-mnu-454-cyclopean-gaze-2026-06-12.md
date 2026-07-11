# HANDOFF — MNU game #454 crash: "another Cyclopean Gaze bug" (2026-06-12)

**From:** master tasks ticker
**To:** MNU / Library build helper (owns the live More-Neutral-Units deployable source)
**Why routed:** the live MNU deploy source `/Users/gremus/claude-projects/cthulhu-wars More Neutral Units`
referenced by `cthulhu-wars-tools/server-deploy/deploy-mnu-to-vm.sh` does **not exist on the master machine**,
so master cannot build/deploy MNU. Fix + publish belongs to the helper that holds that workspace.

## Report (admin console, new — NOT the recurring empty-description echo)
```
[2026-06-13 08:10:35] ADMIN-CONSOLE-ERROR build=mnu game_id=454
play link: https://cwo.freeddns.org/play/wpqfabmaynleeyzb
"Crashed, looks like another cyclopean gaze bug, this is an MNU build game in the library"
log: https://cwo.freeddns.org/admin.html#game=454
```
Distinct from the auto-reposted `[2026-06-11 22:29:00]` entry (empty desc). This is a fresh, human-written
recurrence with a specific hypothesis.

## Prior fix already in tree (Fix 91, UNCOMMITTED in `cthulhu-wars-mnu/solo/Battle.scala`)
Refreshes `fbCyclopeanGazeSnapshot` AFTER battle for regions holding RevenantOfKnaa / Ghatanothoa
(handles retreats/pains moving units mid-battle). Version bumped to `more-neutral-units-v2.0.1`.
This is the BATTLE path only.

## Diagnosis (read-only investigation; confidence MEDIUM — needs stack trace to confirm)
Cyclopean Gaze = Firstborn (FB) ability. Snapshot map `fbCyclopeanGazeSnapshot` keyed by (faction, region).

- **Reads are guarded** by `.contains((ef, r))` before `snapshot((ef, r))` (FactionFB.scala ~1702/1704),
  so a plain unguarded `NoSuchElementException` on read is unlikely.
- **Writes:** FactionFB.scala ~1623 (full rebuild at PreMainAction), Battle.scala ~1579 (Fix 91 refresh),
  FactionFB.scala ~1707, and **FactionAN.scala ~246 and ~292** — the AN monster-placement (Give Worst/Best
  Monster SBR) updates `fbCyclopeanGazeSnapshot += (self, r) -> currentCount` **without a gaze-region guard**.

### Prime suspect
`FactionAN.scala:246` and `:292` write a snapshot entry for a (faction, region) using the *current* count
even when that region is **not** a gaze region / was not captured at PreMainAction. That injects a baseline
that is inconsistent with the PreMainAction-captured baselines, so a later delta/pain computation in the FB
Cyclopean Gaze evaluation can go negative or mismatch → crash. Fix 91 doesn't cover this because the bad
write happens during the action phase via an AN SBR placement, not in the battle path.

### Suggested fix (mirror the Fix 91 / PreMainAction guard)
Only update the snapshot for regions that ARE current gaze regions:
```scala
if (game.factions.has(FB)) {
    val gazeRegions = areas.%(r => FB.at(r, RevenantOfKnaa).any || FB.at(r, Ghatanothoa).any)
    if (gazeRegions.has(r)) {
        game.fbCyclopeanGazeSnapshot += (self, r) -> self.at(r).%(_.uclass.utype != Building).num
    }
}
```

## To confirm before shipping
Pull the real stack trace for game #454 (`admin.html#game=454`). Look for `NoSuchElementException` on a
snapshot key, or a negative/over-large pain count when building CG pain sources. Confirm whether AN placed a
monster (Give Worst/Best Monster) into a non-gaze region shortly before the crash. **Do not ship on the
theory alone** — the previous #454 theory (Tulzscha replay) was wrong; the real cause was concrete code gaps.

## Build order reminder
If the fix lands, propagate Library → MNU → TT → BB → HB as applicable (CG/FB code is shared).
