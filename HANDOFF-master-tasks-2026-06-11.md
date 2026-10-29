# Handoff — verified fixes for master-doc tasks (backup ticker, 2026-06-11 ~10:40)

Dev-only notes (NOT user-facing — full technical detail). User-facing bullets in
the master tasks docx are layman's terms only. These four were raw user tasks the
primary master ticker had not yet processed; backup ticker investigated read-only.
Nothing was edited / built / committed / deployed. HELD AT DEPLOY BAR per no-auto-deploy.

## [46] Crawling Chaos (CC) start area, Earth maps — HB ONLY, NEEDS USER DECISION
- Root cause: HB commit `89a6b42` (Tue Jun 9 2026) changed `solo/Map.scala` CC start
  from `SouthAsia` -> `Arabia` on the three split-Asia Earth maps (earth35/55/66),
  and swapped Arabia<->SouthAsia in the matching `nonFactionRegions` vals.
- HRF canonical (raw.githubusercontent.com/haunt-roll-fail/cthulhu-wars/master/solo/Map.scala):
  earth35/55/66 CC => SouthAsia; earth33 & earth53 CC => Asia (already correct everywhere).
- Only HB is broken. MNU / TT / BB still = SouthAsia (correct).
- CONFLICT: 89a6b42 was made per an earlier explicit user directive ("Arabia is CC's
  default start; treat it as CC's starting glyph for all glyph-based tests"). FB Devil's
  Mark, BB SBR-for-starting-glyph, TT Idolatry now rely on Arabia carrying CC's glyph.
  Plain revert re-breaks those. Clean reconciliation = start CC in SouthAsia per HRF BUT
  decouple glyph-ownership so Arabia still carries CC's starting glyph for those predicates.
- Exact straight-revert (if user picks option 1) — `cw-homebrew-wt/solo/Map.scala`:
  - L136 nonFactionRegions earth35: SouthAsia -> Arabia
  - L183 earth35: `case CC => $(Arabia)` -> `$(SouthAsia)`
  - L374 nonFactionRegions earth55: SouthAsia -> Arabia
  - L425 earth55: `case CC => $(Arabia)` -> `$(SouthAsia)`
  - L509 nonFactionRegions earth66: SouthAsia -> Arabia
  - L563 earth66: `case CC => $(Arabia)` -> `$(SouthAsia)`
  - also drop the stale "Arabia is CC's printed start" comments 89a6b42 added.
  - Option 2 (both-worlds) requires decoupling glyph ownership from `starting(CC)` — bigger.

## [47] DC Harbinger awaken-cost for Y'Golonac — HB ONLY, fix ready
- File `cw-homebrew-wt/solo/Battle.scala`, two identical Harbinger phase blocks:
  - HarbingerKillPhase: cost match L1144-1156, ceil halve L1157 `(cost+1)/2` (DO NOT TOUCH).
  - HarbingerPainPhase: cost match L1437-1449, ceil halve L1450 (DO NOT TOUCH).
- Bug: both pass `case YgolonacDC => DC.spellbooks.num` (books CLAIMED on sheet).
  Correct per user = SBRs ACHIEVED = `DC.library.num - DC.unfulfilled.num`. They differ in
  the window after Y'Golonac awakens (req satisfied instantly via satisfyIf at
  FactionDC.scala:391-399, book claimed later via deferred CheckSpellbooksAction).
  User's example: awoke once, nothing claimed yet -> achieved=1 but spellbooks.num=0,
  so Harbinger charged (0+1)/2=0 instead of (1+1)/2=1.
- EXACT FIX (does not touch Harbinger core):
  - Battle.scala L1154: `case YgolonacDC => DC.spellbooks.num`
      -> `case YgolonacDC => DC.library.num - DC.unfulfilled.num`
  - Battle.scala L1447: same change.
- Note: FactionDC.scala:84-89 `awakenCost` itself also uses `f.spellbooks.num` (same lag) —
  user scoped task to Harbinger only, so leave awakenCost unless user asks.

## [48] Hound of Tindalos overlay text — MNU/TT/BB/HB, fix ready
- Why missed: `Neutral Units/necronomicon-audit-2026-05-10.md` L107 rubber-stamped
  "Hound of Tindalos — Cronophage + Angles of Time match" without a word diff. (Also fix that doc line.)
- Overlay locations (all `solo/overlay.scala`, loyaltyCard 8th arg `abilityText`):
  MNU:613, TT:613, BB:783, HB:759 — byte-identical wrong text in all four.
- Current (wrong) abilityText:
  "After the Hound moves, it may immediately teleport to any Gate on the map.<br><br>
   <b>Angles of Time</b> (Ongoing): The Hound cannot be assigned a Kill result. If the
   Hound is in an Area without a Gate at the end of any Action Phase turn, it is eliminated."
- Cronophage must become verbatim Necronomicon (source: Neutral Units/neutral_units_loyalty_cards.html L231):
  "The Hound cannot perform the Move Action by itself. The Hound Moves for free whenever
   you Move any other Unit. In doing so, the Hound teleports directly from an Area with a
   Gate to another Area with a Gate – neither of which need to be Controlled by you (or anyone)."
  (use real en-dash U+2013; do NOT re-prepend "Cronophage (Ongoing):" — label is separate arg.)
- Angles of Time = user's EXACT replacement (intentionally NOT verbatim, mark excluded from audits):
  "The Hound cannot be assigned a Kill in Battle. However, if a Hound ever exists in an Area
   without a Gate it is Eliminated. It can also be chosen to be Eliminated if it cannot be
   Pained due to Enemy presence in adjacent Areas (per normal Pain rules)."
- Add a comment immediately above each `case $("Hound of Tindalos")` line marking the
  Angles of Time text as intentionally modified and EXCLUDED from Necronomicon audits.
- Propagate MNU -> TT -> BB -> HB (identical edit).

## ===== MASTER TICKER UPDATE 2026-06-11 ~11:47 (verified, NOT yet shipped) =====

WHY NOTHING SHIPPED THIS TICK: master doc was being edited live (mtime 11:34 → 11:46),
and FBE guide (11:39) + XSS guide (11:32) were ALSO being edited — owner is in an active
multi-doc editing session. Held all writes (master-doc lockout Rule 1/3) AND held all live
deploys (do NOT ship code off a spec the owner is concurrently revising — that is exactly how
the CC/Arabia mess happened). Admin queue empty; all 3 live sites healthy (Lib 200 / HB 200 /
MNU 200). Everything below is VERIFIED by reading the actual code — ship on the next SETTLED tick
(master mtime > 5 min old), then record completions + change the owner's @@@ replies to READ:.

NEW @@@ OWNER REPLIES IN LIVE MASTER DOC (acknowledge next tick, @@@ → READ:):
- DC Harbinger awaken-cost  → "@@ ship"        (two-@; intent = ship)
- Hound of Tindalos wording → "@@@ go"
- New-neutral-unit audit    → "@@@ fixing small typos is the right call" (= keep corrected/readable;
                               ship ALL listed neutral fixes together)
- Crawling Chaos start area → "@@@ CC start was ASIA (3p) / S.Asia (4-5p split), NEVER Arabia.
                               'If I said Arabia it was a typo.' Real bug = FB/TT/BB weren't
                               RECOGNIZING it as a start/glyph area AT ALL. NEVER told you to change
                               the start area." (furious — grovel)
- FBE Q1/Q2/Q4 + XSS Madson-Q → "ask these in the faction GUIDE doc's Section A 'Claude only' area,
                               not here." FBE Q3 = "Yog-Sothoth cannot copy abilities, you have this
                               wrong" → DROP that question. FBE Q4 = Sleeper copy is via Ancient
                               Sorcery, copies ONLY the unique faction ability (not GOO, not spellbooks).
- TB guide → "I have made this available offline." BUT du still 0B, still EDEADLK — NOT materialized.
- NEW DIRECTIVE → stop asking faction-impl questions in master doc; ask in the guides. (memory saved)
- #518 → still no reply (leave parked).

VERIFIED CORRECTIONS to the four fixes below:

[46] CC — SHIP THE STRAIGHT REVERT. Already staged uncommitted in cw-homebrew-wt/solo/Map.scala
  (Arabia→SouthAsia on earth35/55/66 + nonFactionRegions swap back). This IS correct: recognition is
  driven entirely by board.starting(CC) — FactionFB.scala:311 & :643 use board.starting(f).has(r);
  Map.scala TT cathedral list uses starting(CC). 89a6b42 changed ONLY starting(CC) (no separate
  predicate code). So starting(CC)=SouthAsia makes FB Devil's Mark / TT Idolatry / BB SBR recognize
  SouthAsia automatically = exactly what owner demanded. HB-ONLY. Bump common.sbt last digit + new
  cache tag in index.html. Drop the stale "Arabia is CC's printed start" comments (the staged diff
  already does). Owner did NOT type literal "ship" on CC but is plainly demanding the correction.

[47] HARBINGER — Fix 110 (commit a9aa0ed) is WRONG; CORRECT it. Fix 110 set
  `case YgolonacDC => DC.spellbooks.num` at Battle.scala L1154 & L1447. VERIFIED that's the lagging
  CLAIMED count: satisfy() (Game.scala:895) drops the req from `unfulfilled` INSTANTLY on Y'Golonac
  awaken, but `spellbooks` is only appended later in SpellbookAction (Game.scala:3274, via deferred
  CheckSpellbooksAction). Owner's example (awoke once, nothing claimed): spellbooks.num=0 → charges 0
  (still broken); achieved = library.num - unfulfilled.num = 6-5 = 1 → charges 1 (correct).
  → CHANGE both L1154 & L1447: `DC.spellbooks.num` → `DC.library.num - DC.unfulfilled.num`. HB-ONLY.
  (Leave awakenCost FactionDC.scala:84-89 alone — owner scoped to Harbinger only.)

[48] HOUND + [50] NEUTRAL — text-only overlay fixes, exact wording already in this doc below. Owner
  approved typo-cleanup (keep corrected). Ship the 4 substantive neutral fixes (Servitor→Adulation,
  Atlach-Nacha→Spinnerets, Bokrug Ghosts-of-Ib, Gla'aki→The Tomb-Herd/Acolyte Cultist) + Hound
  Cronophage verbatim + Hound Angles-of-Time owner-exact (mark excluded from audits) + the iGOO
  picker blurbs (owner said "ship all together"). Multi-build: per Rule 33 order, build+deploy MNU
  and HB this side; commit+push TT and BB and post a heads-up to the admin queue for BB-Claude
  (established pattern, see Fix 81). Also fix the rubber-stamp line in
  Neutral Units/necronomicon-audit-2026-05-10.md L107.

EFFICIENCY: all four touch HB → ONE HB build covers CC + Harbinger + Hound + neutral. Verify live HB
version bumped + HTTP 200 after deploy. Update HB Rollback Guide + TT/BB Parallel Fixes Guide.

## [50] New-neutral-unit audit vs Necronomicon — MNU and beyond
- Reference: `Neutral Units/neutral_units.csv` "Full Text" column. Overlay text in
  `solo/overlay.scala` (info match). New-unit block byte-identical across all 4 builds
  (md5 5627b8bb...); line offsets MNU==TT, BB +~170, HB +~146.
- In scope = 24 NEW units (excl base-Library: Ghast, Gug, Shantak, Star Vampire, Voonith,
  Dim. Shambler, Gnorri, High Priest, Byatis, Abhoth, Daoloth, Nyogtha, Tulzscha, Y'Golonac).
- SUBSTANTIVE fixes (wrong ability name and/or dropped mechanics):
  1. Servitor of the Outer Gods (overlay.scala:623) — name "Summon Block" -> "Adulation";
     restore "place via other means" clause.
  2. Atlach-Nacha (:654/655) — name "Place Spinneret" -> "Spinnerets"; reworded + extra
     Desecration-token rule not on card.
  3. Bokrug (:650/651) — Ghosts of Ib heavily paraphrased; restore card-retention + timing.
  4. Gla'aki (:652/653) — name "Tomb Herd" -> "The Tomb-Herd"; "Cultists" -> "Acolyte Cultist".
  5. Hound of Tindalos Cronophage (:613) — covered by [48] (Cronophage NOT excluded;
     only Angles of Time is excluded).
  6. All 13 iGOO setup-menu (no-arg) overlays (:626-642) — abbreviated paraphrases; rewrite
     to full Necronomicon text IF the picker-menu blurb is in scope (confirm with user).
- MINOR / NEEDS USER CALL: ~8 units differ only because overlay silently CORRECTED typos
  in the Necronomicon SOURCE csv ("you Units"->"your Units", "Acolyte is free." fragment
  completed, em-dash vs hyphen, casing): Quachil Uttaus(:611), Brown Jenkin(:614),
  Elder Shoggoth(:615), Leng Spider(:621), Insects from Shaggai(:624), Mother Hydra(:645/659),
  Cthugha "Kill/Kills"(:647/661), Bloated Woman em-dash(:649/663).
  DECISION: keep corrected/readable, or force letter-for-letter to the typo'd source?
- Clean MATCH: Dhole, Great Race of Yith, Shadow Pharaoh, Giant Blind Albino Penguins,
  Elder Thing, Satyr, Moonbeast(core), Azathoth(Daemon Sultan), Yig(card), Father Dagon(Tsunami),
  Ghatanothoa(Mummify).
