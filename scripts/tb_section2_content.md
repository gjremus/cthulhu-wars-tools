### 2.0 New source files
Create, following the existing FactionXX.scala / BotXX.scala pattern:
• solo/FactionTB.scala — object TB extends Faction (color #FFCC66, style = "tb"); UnitClasses (Cadavolyte, Tentacle, Chthonian, ShuddeMellHead, ShuddeMellSegment); Spellbook objects (Stalk, Autotomy, Subterrane, Grasp, Ensnare, PsychicShriek); Requirement objects (MantleTransferReq, TenTentaclesReq, ChthonianForGateReq, GateAtEachGooReq, AwakenShuddeMellReq, ThreeGlyphReq); action case classes (see 2.7/2.8); trait TBExpansion extends Expansion with perform, triggers, eliminate, afterAction, postBattle hooks.
• solo/BotTB.scala — class GameEvaluationTB extends GameEvaluation(TB).
Edit-in-place files (every faction touches these): Game.scala, CthulhuWarsSolo.scala, Battle.scala, overlay.scala, Serialize.scala, Map.scala, index.html + the online HTML, Bot3.scala, and each BotXX.scala opponent-eval block.
State that MUST live on Game.scala as var tbX (per the undo HARD RULE — never on the TBExpansion singleton):
• var tbMantleInPlay : Boolean = false — Mantle overlaid on map yet.
• var tbMantleAdjacent : Set[Region] = Set() — the player-nominated areas the Mantle touches (printed on the tile; see 2.3).
• var tbHeadEverAwakened : Boolean = false — gates the Behemoth ongoing (segments-on-zero-power, free Move-to-Mantle).
• var tbEnsnareUsedOn : Set[Faction] = Set() and var tbShriekUsedOn : Set[Faction] = Set() — per-action-phase "used once per faction" trackers for SB5/SB6 (cleared in Doom Phase; these double as the "acronym next to the spellbook name" tags the card text asks for).
• var tbAutotomyRetreatPending : Boolean = false — flag set when an Autotomy kill-transfer fires, consumed by the retreat sub-prompt.

### 2.0a Setup-time validations
• Setup order — TB sets up FIRST. Validate TB's SetupFactionsAction arm fires before any other faction's setup arm (intercept SetupFactionsAction; guard with game.setup.has(TB) NOT game.factions.has(TB), since game.factions is empty during setup).
• 8 Tentacles, 8 distinct areas. Validate each of the 8 placements targets a different Region. No empty/adjacency constraint is printed (unlike FBE), so any 8 distinct map areas are legal.
• No starting gate / no starting acolytes. TB places only Tentacles at setup. Confirm the High-Priests-expansion auto-add does NOT inject an HP into TB's pool at setup if TB has no native HP (TB's card lists a High Priest map image, so confirm with creator whether TB fields an HP; see OPEN QUESTIONS).
• Mantle starts in pool, not in play. tbMantleInPlay = false at setup; the Mantle is TB's nominal start area but is not overlaid until SBR1 fires.
• Start-area registration. Map.scala starting() for all board variants returns TB's start as the Mantle (out of play) — handle like BB's Moon, which is also a pool tile at setup; the 8 Tentacle placements are the real on-board setup.

### 2.1 Faction shell + UnitClasses
TB extends Faction, color #FFCC66, style = "tb", var power : Int = 8.
UnitClasses:
• Cadavolyte — UnitClass("Cadavolyte", Cultist, cost = 2), pool 6, combat 0. Standard-acolyte-equivalent in all respects EXCEPT it gives no Power in Gather Power (2.6). Affected by all abilities targeting Acolytes/Cultists.
• Tentacle — UnitClass("Tentacle", Cultist, cost = 2), pool 10, combat 0. Cultist type but with the Thousand Writhing Maws restrictions (cannot build/control gates, cannot be captured); special Gather-Power contribution (2.6).
• Chthonian — UnitClass("Chthonian", Monster, cost = 2), pool 5, combat 1.
• ShuddeMellHead — UnitClass("Shudde M'ell Part: Head", GreatOldOne, cost = 8), pool 1, combat = dynamic (2.12).
• ShuddeMellSegment — UnitClass("Shudde M'ell Part: Segment", GreatOldOne, cost = 0), pool 3, combat 0.
Both Cadavolyte and Tentacle are the standard Cultist UnitType; the recruit/summon "two 2-cost units of same type for 2 Power total" rule (2.7) keys off uclass.cost == 2, which covers Cadavolyte, Tentacle, AND Chthonian.

### 2.2 New UnitType (if any)
No new UnitType. Cultist, Monster, and GreatOldOne are sufficient. The Shudde M'ell "Parts" relationship (Head + Segments are one GOO for Elder-Sign/Harbinger counting, but separate units for Move/Pain/Kill) is NOT a new UnitType — it is modelled as a partsInPlay helper on TBExpansion plus targeted hooks in Ritual and Harbinger code (2.12). Two distinct UnitClasses (ShuddeMellHead, ShuddeMellSegment) are enough.

### 2.3 Special region / tile
Implement the Mantle like the BB Moon tile: a pool tile placed onto the map at runtime that becomes a land area adjacent to a player-nominated set of areas, without altering underlying main-map adjacency.
• Data structure: tbMantleAdjacent : Set[Region] (on Game.scala) is the canonical adjacency list. The Mantle is its own Region object (MantleRegion, defined like BB's Moon region) flagged as Land. Adjacency is asymmetric-aware: a query adjacent(Mantle) returns tbMantleAdjacent; a query adjacent(r) for any r returns its normal neighbours PLUS Mantle iff r is in tbMantleAdjacent. The main map's own adjacency graph is never mutated (the Mantle is "beneath" the map per 1.2).
• Placement (fires from SBR1, 2.8): prompt TB to nominate the set of areas the Mantle touches (must include the 2 adjacent controlled-gate areas); store them in tbMantleAdjacent; set tbMantleInPlay = true; then transfer one selected controlled Gate + its Cultist onto the Mantle (BB-Moon gate-transfer pattern). The nominated areas are printed on the tile ("Areas adjacent the Mantle: ___").
• Subterrane (SB3) interaction: when SB3 is owned, the adjacency query additionally treats any area containing a TB Tentacle as adjacent to the Mantle, FOR TB UNITS ONLY (2.7 SB3). This is a query-time augmentation, not a mutation of tbMantleAdjacent.
• Persistence: tbMantleAdjacent persists for the rest of the game once set (subject to the OPEN QUESTION on re-nomination). State lives on Game.scala so undo replay re-derives it from the SBR1 action.

### 2.4 Overlay UI
• Mantle tile render — draw the Mantle like BB's Moon (placed sprite once tbMantleInPlay), with the nominated-adjacency caption rendered on/near the tile ("Areas adjacent the Mantle: …"). Use the fixed draw list (not the layout-managed list) so it doesn't shift as units stack.
• Parts tracker — a small HUD badge showing Parts in play (Head + Segments), since Head's combat = 3x Parts; mirror the DH "Death's Head is now N" / FB augury-skull badge pattern (visible once Head is awakened).
• Spellbook target tags — render the targeted faction acronym next to "Ensnare" / "Psychic Shriek" SB names in the faction tray while tbEnsnareUsedOn / tbShriekUsedOn hold that faction (cleared at Doom Phase).
• TB glyph — dynamic-start glyph drawn via the shared GlyphPlacement engine; note TB's "start area" is the Mantle which begins out of play, so the on-board glyph may only render once the Mantle is placed (confirm desired pre-Mantle glyph behaviour — see OPEN QUESTIONS).

### 2.5 Setup (StartAction / SetupFactionsAction)
SetupFactionsAction's TB arm (FIRST in order, intercept pattern):
1. TB.power = 8.
2. Loop 8 times: prompt TB to place one Tentacle in any area (validate 8 distinct areas; bot scores via BotTB strategy 1.11: empty iii/^/o glyph areas that are not faction starts, then adjacent-to-placed).
3. No gate, no acolytes placed.
4. tbMantleInPlay = false; Mantle remains in pool. TB.spellbooks = empty (6 SBs sit in pool keyed to their requirements, acquired on satisfaction).
5. Clear tbEnsnareUsedOn, tbShriekUsedOn, tbHeadEverAwakened = false.
After TB completes, resume normal setup order. OW remains last.

### 2.6 Gather Power
Standard: +1 Power per controlled Gate (Tentacles can't control gates, so only Cadavolytes-on-gates count toward gate control).
TB-specific overrides (Thousand Writhing Maws, ongoing):
• Cadavolytes and Tentacles give NO Power in Gather Power (suppress the standard per-cultist Power award for these two classes; guard if f == TB and uclass is Cadavolyte or Tentacle).
• +1 Power per AREA containing one or more Tentacles — TB.power += (distinct regions containing a TB Tentacle). Per-area, not per-unit; multiple Tentacles in one area still yield +1. Log: "Thousand Writhing Maws: +N Power (N areas contain a Tentacle)."
No Bacchanal-equivalent for Shudde M'ell.

### 2.7 Spellbooks (six handlers)
Unique Ability — Thousand Writhing Maws (ongoing; enforced here):
• Tentacles cannot build or control gates: filter Tentacles out of any build-gate / gate-control eligibility for TB.
• Tentacles cannot be captured: in every faction's capture-eligibility enumeration, exclude Tentacles (cross-faction — see 2.12 and OPEN QUESTIONS; bots must also not score Tentacle captures, per 1.11).
• 2-Power action: Recruit/Summon TWO 2-cost units of the same type — a TBDoubleRecruitAction(uclass, region1, region2) offered when TB has >=2 Power and is recruiting/summoning a cost-2 class (Cadavolyte/Tentacle/Chthonian).
SB1 — Stalk (Ongoing): Hook on AfterAction for ANY faction's Move action. If TB owns Stalk, prompt "Relocate a single Cultist to a moved unit's area?" TBStalkRelocateAction(cultist, dest) — dest must be an area a unit just moved into this Move action. Snapshot moved-into areas in the Move handler. Optional. Hard action.
SB2 — Autotomy (Post-Battle, Shudde M'ell): Hook in Battle.postBattle during Unlimited Battles on TB's turn with Head present. If TB received >=1 Kill and owns Autotomy: prompt "Transfer 1 received Kill to a Segment in play?" TBAutotomyTransferAction(segment). On confirm: the chosen Segment dies instead of the originally-killed unit; then (1) TB.es += segmentsInPool; (2) ignore all Pains on TB units in the battle area; (3) TBAutotomyRetreatAction(dest) — retreat all TB units not killed/eliminated from the battle area to ONE adjacent area. Turn-end hook: place all Segments from pool onto the Mantle. Yellow Sign Vengeance interaction: when KiY's Yellow Sign Vengeance assigns a Kill to Head, this same transfer prompt must be offered; order it AFTER YSV resolves (see 2.12 and OPEN QUESTIONS).
SB3 — Subterrane (Ongoing): No action class. Augments the adjacency query for TB units only: any area containing a TB Tentacle and the Mantle count adjacent (for Move, Pain, retreat-target legality). Query-time augmentation in TB's adjacency helper (2.3), guarded if f == TB and TB owns Subterrane.
SB4 — Grasp (Battle): No action class; a combat-dice modifier. In the battle dice computation, if any TB Chthonians are in the battle area and TB owns Grasp: +1 die per adjacent area containing a TB Tentacle, capped at +4. "Adjacent" respects Subterrane augmentation if also owned. Side-aware (attack or defend).
SB5 — Ensnare (Action: Cost 1): TBEnsnareAction(target). Offered if TB owns Ensnare, has >=1 Power, the target is an enemy with a TB Tentacle in one of its areas, and target is not in tbEnsnareUsedOn. On perform: pay 1 Power; roll 1 D6; the enemy must relocate, FROM that Tentacle area toward Shudde M'ell's Head area, a number of their units = min(roll, target.power). Add target to tbEnsnareUsedOn. Relocation pathing/targeting and legality fallback need creator confirmation (OPEN QUESTIONS). Cleared in Doom Phase.
SB6 — Psychic Shriek (Action: Cost 1): TBShriekAction(target). Offered if Mantle in play, TB owns Psychic Shriek, >=1 Power, target is a non-hibernating enemy, and target is not in tbShriekUsedOn. On perform: pay 1 Power; roll 2 D6; enemy retreats min(sum, 2 x target.power) of their units to areas that (a) did NOT contain their units just prior to the Shriek and (b) do not contain TB Gates. Snapshot the enemy's occupied areas before resolving. Add target to tbShriekUsedOn. Retreat-target selection and no-legal-destination fallback need confirmation (OPEN QUESTIONS). Cleared in Doom Phase.

### 2.8 SB requirements
SBR1 — Mantle transfer: "Control Gates in 2 adjacent areas, overlay the Mantle on (at least) those 2 areas, transfer one Gate (and its Cultist) to the Mantle." ACTION-based. TBPlaceMantleAction: enabled when TB controls gates in 2 adjacent areas and the requirement is unsatisfied. Prompts: (1) nominate the areas the Mantle touches (must include the 2 gate areas); (2) choose which of the 2 controlled gates + its Cultist transfers to the Mantle. On resolve: set tbMantleAdjacent, tbMantleInPlay = true, perform the gate+cultist transfer (BB-Moon pattern), satisfy MantleTransferReq.
SBR2 — Ten Tentacles: "There are 10 Tentacles in play." CONDITION-based, evaluated in TBExpansion.triggers(): if TB has >=10 Tentacles on map, satisfy TenTentaclesReq. Re-evaluate continuously.
SBR3 — Chthonian for gate: "Gain 2 Power, then during your turn remove a Gate you control and place a Chthonian in an area your unit occupies." ACTION-based. Reuse the Unspeakable-Oath prompt scaffolding MINUS the High-Priest references (per 1.9 note). TBChthonianForGateAction: +2 Power, then (during TB's turn) remove a controlled gate and place a Chthonian in any area with a TB unit. Usable any time until earned.
SBR4 — Gate at each GOO: "As an Action, pay 8 Power. In each area containing a Great Old One unit, place a Gate. Gain 1 Power per Gate just placed." ACTION-based. TBGateAtEachGooAction: pay 8 Power; for each area containing ANY GOO unit (scope — incl. other factions' GOOs? — see OPEN QUESTIONS) with no gate, place a Gate; TB.power += gatesPlaced; satisfy GateAtEachGooReq.
SBR5 — Awaken Shudde M'ell: "Awaken Shudde M'ell." ACTION-based; satisfied at the end of the Head awaken action (2.12).
SBR6 — Three-glyph presence: "Shudde M'ell is simultaneously in Glyph Areas ^, o & III (or pay 6 Power as an Action)." Two satisfaction paths. CONDITION path in triggers(): if Shudde M'ell Parts simultaneously occupy areas with the ^, o, and III glyphs, satisfy ThreeGlyphReq (confirm one-Part-per-glyph vs distribution — OPEN QUESTIONS). ACTION fallback TBPayForThreeGlyphAction: pay 6 Power, satisfy. Continuous re-eval for the condition path.
Note: 1.10 numbers the spellbooks Stalk(SB1)…Psychic Shriek(SB6) but 1.9 lists the requirements in a different order. The SBR→SB mapping must be confirmed 1:1 before wiring (the 1.11 walkthrough implies SBR2→Stalk, SBR1→Subterrane, SBR3→Psychic Shriek, etc.). See OPEN QUESTIONS.

### 2.9 Game-option / alt-faction selector
Add TB to allFactions and the alt-picker faction list in CthulhuWarsSolo.scala; to the Serialize factions list (else online creation crashes None.get); to the UIQuestionDebug dispatch match; and an arm to every exhaustive Faction match (drawRect, faction-picker, RoA tintFilter, info-card layout, glyph dispatch). No hard 2-player restriction (1.1), so no faction-pair validation needed.

### 2.10 Bot (Bot(faction acronym).scala)
class GameEvaluationTB extends GameEvaluation(TB). Scoring priorities (working defaults, tune via sim):
• Setup: place Tentacles to maximize distinct-area coverage (empty iii/^/o glyph non-start areas first, then adjacent to placed) — drives Gather Power (+1/area) and SBR2.
• Double-recruit Tentacles early to reach 10 (SBR2 → first spellbook).
• Stalk: relocate a Cultist into newly-vacated/empty areas to maximize Tentacle-area count.
• Awaken timing: Mantle placed + 8 Power → awaken Head; value Parts-in-play for Head combat (3x Parts).
• Behemoth/zero-power loop: intentionally drop to 0 Power to drop Segments onto the Mantle; use the 0-cost Move-to-Mantle action to consolidate Parts.
• Ensnare/Psychic Shriek: target highest-Power enemies (GC/YS/CC/SL per 1.11) once per action phase each.
• Autotomy push-your-luck: chain Unlimited Battles against high-combat GOOs, transferring kills to Segments for Elder Signs.
Also add a case TB => opponent-eval arm (placeholder "todo" stub acceptable) to every other BotXX.scala to avoid MatchError. Bots must NOT score capturing TB Tentacles (1.11).

### 2.11 Render path (CthulhuWarsSolo.scala)
DrawRect arms for: Cadavolyte (cultist proportions ~39x60), Tentacle (cultist proportions), Chthonian (monster, ~Shoggoth scale), ShuddeMellHead (large GOO, under 225px so Cthulhu stays biggest), ShuddeMellSegment (GOO, sized smaller than Head). Mantle tile sprite (BB-Moon render path) with nominated-adjacency caption. TB glyph via GlyphPlacement. Parts-in-play badge in factionStatus. Spellbook target-acronym tags next to Ensnare/Psychic Shriek in the tray. Add the Bot dispatch arm via an if branch (not match) to preserve type inference. Until real assets land, confirm placeholder silhouettes with creator (the source lists distinct images for each unit incl. High Priest).

### 2.12 Battle hooks (Battle.scala)
• Shudde M'ell Head combat dice (variable): if uclass == ShuddeMellHead → dice = 3 x partsInPlay, where partsInPlay = (Head on map) + (Segments on map). Use not(Zeroed) so Parts killed earlier in the same battle don't inflate the count. Recompute at battle init and after any in-battle Part death. Confirm only IN-PLAY Parts count (OPEN QUESTIONS). Side-aware.
• Grasp (SB4): add the Chthonian Tentacle-adjacency bonus at roll time (2.7 SB4).
• Autotomy (SB2): post-battle kill-transfer + Elder-Sign + ignore-pains + retreat hook (2.7 SB2); per-battle "already fired" guard. Turn-end: Segments from pool → Mantle.
• Yellow Sign Vengeance interaction: after KiY's YSV assigns a Kill to Head, offer the Autotomy transfer. Record a game var in the OWNING (KiY) expansion's YSV handler (guarded if game.setup.has(TB)) and react in TB's post-YSV hook — TB's expansion is dispatched after KiY's, so it cannot intercept YSV directly.
• Elder-Sign-on-Ritual: Shudde M'ell Parts collectively give only 1 Elder Sign on a Ritual — count Shudde M'ell as ONE GOO presence regardless of Parts present (partsInPlay > 0 ? 1 : 0).
• Crawling Chaos Harbinger cap: when CC's Harbinger pains/kills Shudde M'ell Parts, cap CC's Harbinger Elder-Sign gain from Shudde M'ell at 2 (Parts collectively count as one GOO for Harbinger). Record in CC's expansion handler guarded if game.setup.has(TB).
• Behemoth — Power reaches 0: hook every Power-debit site; when tbHeadEverAwakened and TB.power == 0 and a Segment remains in pool, place a Segment from pool onto the Mantle. Timing (enemy turns? any decrement?) needs confirmation (OPEN QUESTIONS).
• 0-cost Move-to-Mantle: unlimited action TBMovePartToMantleAction(part) — moves any Part from anywhere to the Mantle for 0 Power; returns to the unlimited action menu (does not consume the turn).
• Tentacle un-capturable: exclude Tentacle from every capture-target enumeration across all factions (2.7) — verify existing capture menus (OW Dread Curse, GC capture, etc.) honour the exclusion (OPEN QUESTIONS).

### 2.13 Serialize.scala
Add TB to the factions list. Register EApply entries for every TB action case class: TBPlaceMantleAction, TBStalkRelocateAction, TBAutotomyTransferAction, TBAutotomyRetreatAction, TBEnsnareAction, TBShriekAction, TBChthonianForGateAction, TBGateAtEachGooAction, TBPayForThreeGlyphAction, TBDoubleRecruitAction, TBMovePartToMantleAction, TBAwakenHeadAction. Serialize the Mantle adjacency list (tbMantleAdjacent) and the Mantle region itself (BB-Moon serialization pattern). No loyalty card. Add TB shortcode ("TB") to the faction-code map.

### 2.14 Files NOT to touch (per Faction Creation Guide HARD RULES)
Per the HARD RULES: all changes to existing files MUST be additive (new case arms, new if (f == TB) conditionals, new state vars, new handlers appended). Do NOT modify any other faction's FactionXX.scala / BotXX.scala internals (only add a case TB => opponent-eval stub where exhaustiveness requires it). Do NOT change existing class signatures, traits, or method implementations on core engine classes (UnitClass, UnitFigure, Faction, Game, Battle). Do NOT alter existing game flow (battle phases, action resolution, power gather) except by appending TB-guarded steps. Cross-faction reactions (un-capturable Tentacles, YSV-Autotomy, CC-Harbinger cap, Behemoth-on-zero-power) must be recorded as game vars inside the OWNING expansion's handler guarded by if (game.setup.has(TB)), then read by TB — never by intercepting another expansion's action. All TB state on Game.scala as var tbX, never on the TBExpansion singleton. Comment every TB code block "// The Burrowers Beneath (TB): …".
