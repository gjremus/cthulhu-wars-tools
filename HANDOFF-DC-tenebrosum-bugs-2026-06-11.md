# HANDOFF — DC Tenebrosum bug diagnosis (READ-ONLY, no edits applied)

Date: 2026-06-11
Worktree: `/Users/gremus/Claude-Projects/cw-homebrew-wt` (branch `homebrew`)
Scope: root-cause only. NO source touched. Apply fixes via the active helper.

## Shared formatting helpers (use these so fixes match existing style)

- `solo/Html.scala:12` `def power = (s + " Power").styled("power")` and `solo/Html.scala:19` `Int.power` → renders `"N Power"` styled `power`.
- There is **no `.sin` helper.** Canonical Sin text everywhere in DC is built manually:
  `n.toString.styled("dc") + " Sin"` (see `solo/FactionDC.scala:140,152,658,670,1010`).
- `Faction.log(...)` (`solo/implicits.scala:36`) prepends the faction object (`f +: args`); the bare `log` (`implicits.scala:29`) does not. The faction renders as its full name ("Defilers Court").
- `OptionFactionAction(o : Game => String)` (`solo/Game.scala:1241`) accepts a `g => String` lambda, so menu strings CAN be computed at render time (pattern: `RitualAction` at `Game.scala:1303`).

---

## BUG 1 — "Power" leaks into Tenebrosum repeat sub-menus (title should say "Sin")

**Mechanism.** Tenebrosum repeats route through `tenebrosumRepeatChooser` (`solo/FactionDC.scala:1388-1431`), which `Force`s the **generic engine MainActions** (`BuildGateMainAction`, `RecruitMainAction`, `SummonMainAction`, `AwakenMainAction`, etc.). The downstream per-region action's BaseFactionAction **title** is the same one used for normal power-paid play; it bakes in `" for N Power"` via the shared helper `forNPowerWithTax` (`solo/Game.scala:1768`):

```
def forNPowerWithTax(r : Region, f : Faction, n : Int) : String = { val p = n + f.taxIn(r) ; " for " + p.power }
```

Nothing in this title path is conditioned on `game.dcTenebrosumGuard`, so during a Sin-paid repeat it still reads "for N Power".

**Exact leak sites (every action menu reused for a Tenebrosum repeat — full audit):**

| Action | file:line | Title code | Leaks? |
|---|---|---|---|
| Build gate | `solo/Game.scala:1340` | `"Build gate" + g.forNPowerWithTax(r, self, 3 - self.has(UmrAtTawil).??(1)) + " in"` | **YES** (the reported one) |
| Recruit | `solo/Game.scala:1353` | `"Recruit " + uc.styled(self) + g.forNPowerWithTax(r, self, self.recruitCost(uc, r)) + " in"` | **YES** |
| Summon | `solo/Game.scala:1356` | `"Summon " + uc.styled(self) + g.forNPowerWithTax(r, self, self.summonCost(uc, r)) + " in"` | **YES** |
| Awaken | `solo/Game.scala:1360` | `"Awaken " + uc.styled(self) + g.forNPowerWithTax(r, self, cost) + " in"` | **YES** |
| Ritual | `solo/Game.scala:1306` | `"... for " + effectiveCost.power + ...` | **YES** (Tenebrosum re-issues `RitualAction` directly via `Force(a)`, chooser case `_ : RitualAction` at `FactionDC.scala:1424`) |
| Move | `solo/Game.scala:1329`, region pick `Game.scala:4024,4028,4066-4069` | labels are `"Move … unit"` / region names / `"for free"` only | no "Power" text — CLEAN |
| Capture | `solo/Game.scala:1342`, `AttackAction` n/a | `"Capture"` + region/faction | CLEAN (free action) |
| Battle/Attack | `solo/Game.scala:1336-1337` | `"Battle in R"` + faction | CLEAN (free action) |
| DC Satiate / Lure / Pilgrimage / DarkBargain repeats | `FactionDC.scala:1425-1428` | route to their own DC MainActions; titles use `"(Cost N)"` with `.power` at `FactionDC.scala:209,225,237` | **Cost label uses `.power`** — leaks if you count the "(Cost N Power)" label (see note) |

Note on the DC-action choosers: `DCSatiateMainAction`/`DCLureMainAction`/`DCPilgrimageMainAction` show `"(Cost " + 2.power + ")"` etc. (`FactionDC.scala:209,225,237`). These are the *main-menu* option labels, re-shown during the repeat. Lower priority than the four `forNPowerWithTax` titles, but they do say "Power" during a Sin-paid repeat — flag for the owner to decide.

**Proposed minimal fix (one shared point covers Build/Recruit/Summon/Awaken).** Make `forNPowerWithTax` render Sin when a Tenebrosum repeat is in progress. It already has `Game` in scope (it's a method on the per-faction implicit that holds `game`), so:

```scala
def forNPowerWithTax(r : Region, f : Faction, n : Int) : String = {
    val p = n + f.taxIn(r)
    if (game.dcTenebrosumGuard)        // Sin-paid repeat: tax is skipped (payTax returns 0 under guard)
        " for " + n.toString.styled("dc") + " Sin"
    else
        " for " + p.power
}
```
(Use `n`, not `p`, for the Sin amount — under the guard `payTax` adds no tax cost; see `Game.scala:1025`.)

For **Ritual** (`Game.scala:1306`): the title is built inline, not via the helper. Guard it the same way:
`val costText = if (g.dcTenebrosumGuard) effectiveCost.toString.styled("dc") + " Sin" else effectiveCost.power` and substitute.

> SHARED-TEXT WARNING: `forNPowerWithTax` and the Ritual title are used by **every faction** (MNU/TT/BB/etc.), but the new branch only fires when `game.dcTenebrosumGuard` is true, which only DC/SL-borrowed-Tenebrosum ever set. No behavior change for other builds. Still, this edits engine-shared `Game.scala` text — coordinate build order: this file is the base, so MNU/TT/BB rebuilds inherit it automatically; no per-build duplication needed.

---

## BUG 2 — Undo refunds Power (not Sin) + mangles/strips the Tenebrosum log line

Two coupled defects; both stem from Tenebrosum state living in transient `game.dcTenebrosum*` vars set by a **Soft** action that undo never replays.

### 2a. Doubled-name / "built a gate" malformed log line

`appendLog` (`solo/Game.scala:1804-1838`) prepends the one-shot prefix to **`raw`**, but `raw` was produced by `self.log(...)` = `Faction.log` (`solo/implicits.scala:36`) which **already prepended the faction** ("Defilers Court built a gate in Africa"). Result (`Game.scala:1825`):

```
"Defilers Court used Tenebrosum to " + "Defilers Court built a gate in Africa" + " (3 Sin)"
```
→ doubled name + still says "built a gate". The headline action handler still uses its normal `self.log("built a gate in", r)` (`Game.scala:4387`), so the prefix can never produce a clean line.

**Proposed fix:** strip the leading faction name from `raw` before applying the Tenebrosum prefix. In `appendLog` (`Game.scala:1818-1826`), when `dcTenebrosumPrefixPending`, drop the duplicate faction token. Cleanest: have the prefix consume the faction-prefixed raw by removing the known caster name:

```scala
if (dcTenebrosumPrefixPending) {
    dcTenebrosumPrefixPending = false
    val casterName = (if (dcTenebrosumCaster == SL) SL else DC).toString   // see note
    val body = if (raw.startsWith(casterName + " ")) raw.drop(casterName.length + 1) else raw
    val sinTag = if (dcTenebrosumPrefixCost > 0) " (" + dcTenebrosumPrefixCost + " Sin)" else " (free repeat)"
    casterName + " used Tenebrosum to " + body + sinTag
} else raw
```
NOTE: there is currently no `dcTenebrosumCaster` var — `self` (DC vs SL) isn't threaded into `appendLog`. Minimal options: (a) hard-code `"Defilers Court"` since the headline is always DC's name even for the SL-borrowed case (verify against spec), or (b) add a `var dcTenebrosumPrefixCaster : Faction` set alongside `dcTenebrosumPrefixPending` in `FactionDC.scala:618-622` and read it here. Option (b) is cleaner and matches the existing one-shot-flag pattern.

### 2b. Undo deducts Power instead of Sin and reverts the entry to a normal action

**Root cause:** `DCTenebrosumRepeatAction` is declared `with Soft` (`solo/FactionDC.scala:149-154`). Undo replay only re-runs **recorded** actions: `isRecorded = !(isMore || isCancel || isSoft || isVoid)` (`Game.scala:594`); recording happens at `CthulhuWarsSolo.scala:3675-3676` (`if (a.isRecorded) actions +:= a`); replay rebuilds a fresh `Game` and re-`perform`s the recorded list (`CthulhuWarsSolo.scala:3453-3481`, esp. 3462 `new Game(...)` + 3464-3473).

Because the Soft `DCTenebrosumRepeatAction` is NOT recorded, on undo replay:
- `game.dcTenebrosumGuard` is **never set** → the downstream resolved action (e.g. `BuildGateAction(DC, Africa)`, recorded & replayed) takes the `if (!dcTenebrosumGuard) self.power -= cost` branch (`Game.scala:4382-4383` for build; same pattern at `4407-4408` recruit, `4452-4453` summon, `4495-4496` awaken) → **Power is deducted, Sin is not**.
- `game.dcTenebrosumPrefixPending` is also never set → `appendLog` emits the plain `raw` ("Defilers Court built a gate in Africa") → entry **reverts to a standard action line**.

So the undone state is internally consistent with a *normal* power-paid build — exactly the reported symptom — and the Sin that was debited live in `DCTenebrosumRepeatAction` (`FactionDC.scala:583/586`) is silently lost on replay.

**Proposed fix (make the Tenebrosum repeat survive replay).** The state must be reconstructable from a recorded action. Minimal approach: make `DCTenebrosumRepeatAction` **recorded** (remove `Soft`) so replay re-runs it, re-debits Sin, re-sets the guard + prefix, and re-`Force`s the chooser — reproducing the live path exactly. Risks/required follow-ups if you do this:
  - The defensive re-entry guards at `FactionDC.scala:563-567` and `514-527` rely on stale-flag detection; on a *clean* replay the flags start fresh each `new Game`, so the guard should pass through normally — verify replay order (the repeat action is recorded *before* its downstream resolved action, so it sets the guard first; good).
  - `tenebrosumRepeatChooser` ends in `Force(...MainAction)` which re-opens a region picker. During replay the recorded downstream `BuildGateAction(DC, r)` is the next recorded action and will be performed against that picker — confirm the picker `Continue` is what the replay loop feeds the next action into (it uses `cc = c` at `CthulhuWarsSolo.scala:3471`).
  - Alternative if making it recorded destabilizes replay: thread a `tenebrosum : Boolean` (and `sinCost`) flag onto the **recorded** downstream action case classes (`BuildGateAction`, `SummonAction`, etc.) so the guard is derivable from the action itself rather than a transient var. Heavier change; only if option 1 fails.

> This touches `Game.scala` (shared `appendLog`, action handlers) + `FactionDC.scala`. `appendLog` 2a fix is DC-prefix-gated, no cross-build impact. 2b's "remove Soft" is DC-only class. Build order: `Game.scala` base first, then DC.

---

## BUG 3 — Sin-paid repeat does nothing at 0 Power (Summon/Awaken short-circuit)

**Root cause:** the Summon and Awaken handlers gate execution on an **affordability check in Power** that is NOT bypassed under the Tenebrosum guard.

- Summon: `solo/Game.scala:4446`
  ```scala
  if ((self.pool(uc).none && !hasVelvetFanUnit) || self.affords(self.summonCost(uc, r))(r).not)
      EndAction(self)          // <-- at 0 Power, affords()==false → ends with NO summon
  ```
- Awaken: `solo/Game.scala:4490`
  ```scala
  if (self.pool(uc).none || self.affords(cost)(r).not)
      EndAction(self)
  ```
- `affords` (`Game.scala:1016`): `def affords(n)(r) = f.power >= f.taxIn(r) + n`. At 0 Power with cost ≥ 1 → false.

Repro matches exactly: Husk summon drops DC to 0 Power; the Tenebrosum repeat reaches `SummonAction` with `dcTenebrosumGuard == true` but `self.power == 0`, so `affords` fails and the handler `EndAction`s without placing a unit. (The actual cost-skip at `4452-4453` is correctly guarded — it's the *gate* above it that's wrong.) Build/Recruit have no such `affords` gate, so they work — consistent with the report singling out Summon.

NOTE: `tenebrosumRepeatChooser` (`FactionDC.scala:1389-1395,1411`) already deliberately strips the power filter from the **region list** for this exact reason ("Fix 105/107"), but the per-region **handler's** own affordability guard was missed.

**Proposed fix:** OR-in the guard so the Power-affordability test is skipped on a Sin-paid repeat. Summon (`Game.scala:4446`):
```scala
if ((self.pool(uc).none && !hasVelvetFanUnit) ||
    (!game.dcTenebrosumGuard && self.affords(self.summonCost(uc, r))(r).not))
    EndAction(self)
```
Awaken (`Game.scala:4490`):
```scala
if (self.pool(uc).none ||
    (!game.dcTenebrosumGuard && self.affords(cost)(r).not))
    EndAction(self)
```
Pool-availability (`self.pool(uc).none`) stays unconditional — Tenebrosum can't conjure a unit that isn't in the pool. Only the Power test is bypassed (Sin already paid).

> `Game.scala` shared handlers, but the new clause is `dcTenebrosumGuard`-gated → no MNU/TT/BB behavior change. Base file; rebuilds inherit.

---

## BUG 4 — Doom-phase SBR opt-in menu strings contain spellbook names

**Exact sites:** `solo/FactionDC.scala:1474-1479`
```scala
case class DCProselytizeReqOptInAction(self : Faction)
    extends OptionFactionAction(("Take " + Proselytize.name).styled(DC) + ": +2 Sin per enemy GOO")
    with DoomQuestion
case class DCSatiateReqOptInAction(self : Faction)
    extends OptionFactionAction(("Take " + Satiate.name).styled(DC) + ": +1 Power per other SB, +1 Sin per pool SB")
    with DoomQuestion
```
`Proselytize.name`=="Proselytize", `Satiate.name`=="Satiate" (`FactionDC.scala:44-45`, `FactionSpellbook(DC, "...")`). These leak the spellbook names — exactly the reported "take proselytize:" / "take satiate:" strings.

**Numbers to compute (matching the handlers):**
- Proselytize SBR grant (`FactionDC.scala:652-661`): Sin = `2 * enemyGOOs` where `enemyGOOs = game.factions.but(self)./~(_.allInPlay).%(_.uclass.utype == GOO).num`. So **X = 2 × (enemy GOOs in play)**.
- Satiate SBR grant (`FactionDC.scala:663-673`): Power = `otherSBs = self.spellbooks.num` (claimed SBs); Sin = `poolSBs = self.unfulfilled.num` (unclaimed requirements). DC has exactly 6 faction SBs (`requirements` = 6 reqs, `FactionDC.scala:71-72`), and `spellbooks + unfulfilled` always partition those 6 → **X(Power)+Y(Sin)==6 invariant holds**.

**Proposed replacement (lambda form, computes live, correct Sin/Power styling, no SB name):**
```scala
case class DCProselytizeReqOptInAction(self : Faction)
    extends OptionFactionAction(implicit g => {
        val x = 2 * g.factions.but(self)./~(_.allInPlay).%(_.uclass.utype == GOO).num
        ("SBR: +" + x.toString.styled("dc") + " Sin").styled(DC) + " (2/ enemy GOO)"
    })
    with DoomQuestion
case class DCSatiateReqOptInAction(self : Faction)
    extends OptionFactionAction(implicit g => {
        val x = self.spellbooks.num     // Power, claimed SBs
        val y = self.unfulfilled.num    // Sin,   unclaimed SBs   (x + y == 6)
        ("SBR: +" + x.power + ", +" + y.toString.styled("dc") + " Sin").styled(DC) +
            " (1P/ claimed SB, 1S/ unclaimed SB)"
    })
    with DoomQuestion
```
Adjust the outer `.styled(DC)` wrapping to taste — note `.power` and the Sin span already inject their own `power`/`dc` styling, so wrapping the whole string in `.styled(DC)` nests spans (current code already does this on the full string; harmless but you may prefer to style only the literal text). Match whatever the owner's house style is; the load-bearing requirements are: (1) **no spellbook name**, (2) Sin via `n.toString.styled("dc") + " Sin"`, Power via `.power`, (3) Satiate X+Y display sums to 6.

> DC-only classes; no cross-build impact. `FactionDC.scala` only.

---

## One-line-per-bug summary

1. `solo/Game.scala:1768` (`forNPowerWithTax`, used by BuildGate/Recruit/Summon/Awaken `Game.scala:1340/1353/1356/1360`; Ritual `:1306`) — shared title helper hard-codes `" for N Power"`, not gated on `dcTenebrosumGuard`.
2. `solo/FactionDC.scala:154` (`DCTenebrosumRepeatAction with Soft`) + `solo/Game.scala:1818-1826` (`appendLog` prefix) — Soft repeat action isn't recorded so undo replay sets no guard (→Power debited, log reverts); and the prefix is prepended onto an already-faction-prefixed `raw` (→doubled name / "built a gate").
3. `solo/Game.scala:4446` (Summon) & `:4490` (Awaken) — `self.affords(cost)(r).not → EndAction` Power-affordability gate not bypassed under `dcTenebrosumGuard`, so a Sin-paid repeat at 0 Power ends without acting.
4. `solo/FactionDC.scala:1475,1478` — opt-in menu strings embed `Proselytize.name`/`Satiate.name`; replace with `"SBR: +X Sin (2/ enemy GOO)"` and `"SBR: +X Power, +Y Sin (1P/ claimed SB, 1S/ unclaimed SB)"` computed from GOO count and `spellbooks.num`/`unfulfilled.num` (X+Y==6).
