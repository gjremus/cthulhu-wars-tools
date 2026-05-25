# Cthulhu Wars Replay Engine

## Architecture Overview

The replay engine transforms a raw game trace file (`.txt`) into a self-contained HTML replay viewer. The pipeline has five stages:

```
trace.txt --> event_handlers.py --> game_state.py --> build_snapshots_v2.py --> build-replay.py --> replay.html
   |                |                    |                    |                       |
   |           Parse each           FullGameState        Array of JSON          Embeds images,
   |           HTML log line        mutated in place     snapshots (one         JS viewer, CSS,
   |           via regex                                 per log line)          and snapshots
   |                                                                            into single HTML
   v
  Two sections:
  1. Action strings (Scala action objects, one per line)
  2. HTML log lines (game log with <span> faction coloring)
```

### Trace File Format

A trace file has two sections separated by a blank line:

1. **Action strings** (top) -- Scala-serialized action objects from the simulator (e.g., `StartingRegionAction(FB, Europe)`). Used only for faction detection fallback.
2. **HTML log lines** (bottom) -- Human-readable game log with `<span class='fc'>` markup for faction/unit coloring and `<span class='region'>` for locations. This is the authoritative game record.

When `--trace` or `--save-all` flags are used in the simulator, the log also includes `[BOT ...]`, `[OPT ...]`, and `[WHY ...]` debug lines that carry bot decision weights.


## Data Flow

### 1. Load Trace (`build-replay.py: load_trace()`)

Splits the trace file at the first blank line. Top half = action strings, bottom half = HTML log lines.

### 2. Build Snapshots (`build_snapshots_v2.py: build_snapshots_v2()`)

Creates a `FullGameState` and iterates through every HTML log line:

- Calls `process_line(state, raw_line, index)` from `event_handlers.py`
- The handler mutates `state` in place (power, doom, unit positions, gates, etc.)
- After each line, calls `state.to_snapshot()` to capture a frozen JSON dict
- Collects `display_lines` (cleaned text + faction class + weights data)
- Tracks `ap_indices` (log line indices where new Action Phases begin)
- Accumulates unmatched lines for diagnostics

Returns: `(snapshots[], display_lines[], ap_indices[], unmatched_summary{})`

### 3. Embed Images (`build-replay.py: collect_needed_images()`)

Reads `.webp` image files from the image directory, base64-encodes each, and builds a dict of `image_key -> data:image/webp;base64,...` URIs. Images include:

- `earth35-dark.webp` -- Map background
- `earth35-place.webp` -- Placement bitmap (region boundaries, unique RGB per region)
- `gate.webp` -- Gate icon
- `ritual_track_4p.jpg` -- Ritual of Annihilation tracker
- Per-faction: background, glyph, and all unit type images

Images are cached in `_image_cache` so each file is read only once.

### 4. Generate HTML (`build-replay.py: build_html()`)

Produces a single self-contained HTML file with:

- All images embedded as base64 data URIs (no external dependencies)
- All snapshots, display lines, AP indices, and config as JSON constants in a `<script>` block
- Full CSS for the four-panel layout
- Full JS viewer logic (map rendering, faction panels, log, weights, playback controls)


## Game State Model

### FullGameState (`game_state.py`)

The central state object tracks everything the viewer needs:

| Field | Type | Purpose |
|-------|------|---------|
| `round_num` | int | Current game round (1-6+) |
| `phase` | str | Current phase (setup, action, gather_power, doom, etc.) |
| `active_faction` | str | Faction code currently taking action |
| `faction_order` | list | Turn order for current round |
| `factions` | dict[str, FactionState] | Per-faction state |
| `regions` | dict[str, RegionState] | Per-region state (17 regions) |
| `ritual_cost` | int | Current Ritual of Annihilation cost |
| `ritual_marker` | int | Position on ritual track |
| `ritual_track` | list | Cost sequence [5, 6, 7, 7, 8, 8, 9, 10, 999] |
| `ritual_history` | list | Faction codes that have ritualed (in order) |
| `battle` | BattleState | Current battle context (region, attacker, defender) |
| `effect_region` | str | Region targeted by abilities (Dread Curse, etc.) |
| `gate_locations` | set | All regions that have/had gates |
| `_pending_weights` | list | Accumulated BOT/OPT/WHY lines awaiting attachment to next display line |

### FactionState

| Field | Purpose |
|-------|---------|
| `code` | Two-letter code (FB, GC, CC, BG, YS, OW, SL, WW, AN, TS) |
| `power` | Current power (starts at 8) |
| `doom` | Accumulated doom points |
| `elder_signs_hidden` | Count of unrevealed Elder Signs |
| `pool` | dict[unit_name, count] -- Units NOT on map (available for summoning) |
| `captured` | List of captured prisoner dicts |
| `spellbooks` | List of SpellbookEntry (name + face_up flag) |
| `requirements` | List of RequirementEntry (SB requirements completed) |
| `gates` | Set of region keys where faction controls a gate |
| `custom` | Faction-specific extras (submerged_region, ice_age_region, deaths_head, etc.) |

### RegionState

| Field | Purpose |
|-------|---------|
| `name` / `display_name` | Key (NorthAmerica) and display (North America) |
| `is_ocean` | Whether region is ocean (6 oceans) |
| `gate` | GateInfo(exists, owner) |
| `buildings` | List of BuildingInfo (Cathedrals, etc.) |
| `units` | dict[faction_code, list[RegionUnit]] -- All units in region by faction |

### FACTION_ROSTER

Static definition of all 10 factions with:
- Unit definitions (name, category, cost, max count, combat value)
- Spellbook library (6 spellbooks per faction)
- Custom stat templates (faction-specific state initialization)

Factions: FB (Firstborn), GC (Great Cthulhu), BG (Black Goat), CC (Crawling Chaos), YS (Yellow Sign), OW (Opener of the Way), SL (Sleeper), WW (Windwalker), AN (The Ancients), TS (Tombstalker)


## Event Handler System

### `process_line()` (`event_handlers.py`)

The core parsing function. Receives a raw HTML log line and the mutable game state. Returns an `EventRecord` indicating whether the line matched, which handler fired, and whether state changed.

**Processing order:**

1. **Debug/separator lines** -- `[BOT`, `[OPT`, `[WHY`, `[ALT` prefixes are accumulated in `_pending_weights`. Separator lines (`..........`, `TRACE_`, `Options`) are skipped.

2. **Fingerprint** -- Takes a `summary_fingerprint()` before processing to detect state changes.

3. **Faction-prefixed events** -- Lines starting with a faction name (e.g., "Firstborn recruited Acolyte in Europe") are parsed with `faction_prefix()` to extract the faction code and remaining text. These are matched against regex patterns in priority order:
   - **Placement**: `started in Region`
   - **Power**: `got N Power`, `power increased to N`, `recovered N`, `spent N`, `paid N`, `ran out of power`, `forfeited N`, `hibernated for extra N`
   - **Movement**: `moved Unit from Src to Dst`
   - **Recruit**: `recruited Unit in Region`
   - **Summon**: `summoned Unit in Region [for free]`
   - **Awaken**: `awakened GOO in Region [for N Power]`
   - **Build Gate**: `built a gate in Region`
   - **Build Cathedral**: `built a cathedral in Region`
   - **Gate Control**: `lost/gained control of the gate in Region`
   - **Capture**: `captured Unit in Region`
   - **Sacrifice**: `sacrificed Unit in Region`
   - **Doom**: `got/gained N Doom`
   - **Ritual**: `performed the ritual for N Power and gained N Doom`
   - **Elder Sign Reveal**: `revealed ... for N Doom`
   - **Spellbooks**: `received SB_Name`, `achieved Requirement`, `SB flipped facedown/faceup`
   - **Released Prisoners**: `released Unit, Unit`
   - **Writhe** (FB): replace, relocate, eliminate variants
   - **Call of the Faithful** (FB): `placed Acolyte in Region`
   - **Promotion** (OW MFO): `promoted Unit in Region to NewUnit`
   - **Devil's Mark** (FB): crater placement, gate destruction
   - **Cursed Slumber** (SL): gate/acolyte to/from Cursed Slumber
   - **Death from Below** (SL): unit placement
   - **Ancient Sorcery** (SL): send/return Serpent Man
   - **Cannibalism** (WW): spawn unit
   - **Lethargy** (SL): power drain
   - **Demand Sacrifice** (SL): power transfer
   - **Beyond One** (OW): gate movement
   - **Cyclopean Gaze** (FB): pain to region

4. **Non-prefixed events** -- Lines without a faction prefix that apply to any faction:
   - **Battle start**: `X battled Y in Region` (deducts 1 power from attacker)
   - **Effect region**: `sent ... to Region` (sets effect_region for kill/retreat tracking)
   - **Battle kills**: `was/were killed` (removes units from battle/effect region)
   - **Retreats**: `retreated to Region`
   - **Pained to**: `was pained to Region`
   - **Sacrificed** (non-prefixed): `Unit in Region was sacrificed`
   - **Eliminated**: `was/were eliminated`
   - **Devoured**: `was devoured`
   - **Submerge/Unsubmerge** (GC)
   - **Howl** (WW): `was howled to Region`
   - Various display-only events (play order, power gather, doom phase, rolls, etc.)

5. **Additional handlers** -- Faction-specific abilities handled as catch-all patterns:
   - TS Death March, Undulate, Shepherd of the Crypt, Green Decay
   - BG gate control change
   - Writhe power cost (2 power)
   - Ice Age (1 power start + 1 power per affected faction)
   - Infernal Pact discount
   - Avatar, Screaming Dead, Dematerialization, Byakhee flight
   - Arctic Wind (unit follows Ithaqua)
   - Devolved (GC Devolve)
   - Emissary survival, Nightgaunt abduction
   - Unit placed/appeared/removed from game

6. **State change detection** -- Compares fingerprint after processing to set `event.state_changed`.


## Snapshot Format

`FullGameState.to_snapshot()` produces a dict consumed by the JS viewer:

```json
{
  "round": 3,
  "ritualCost": 7,
  "ritualMarker": 2,
  "ritualHistory": ["FB", "GC"],
  "factions": {
    "FB": {
      "code": "FB", "name": "Firstborn",
      "power": 5, "doom": 12, "es": 1,
      "gates": ["Europe", "NorthAmerica"],
      "sb": ["Augury", "Carnage"],
      "sbDown": ["Carnage"],
      "startRegion": "Europe",
      "cardDetails": ["IP discount: 2", "SBRs remaining: 4"],
      "units": {
        "Europe": {"Acolyte": 3, "Desiccated": 2},
        "NorthAmerica": {"Ghatanothoa": 1, "Acolyte": 1}
      }
    }
  },
  "gateOwners": {"Europe": "FB", "SouthAsia": "GC"},
  "gateLocations": ["Europe", "NorthAmerica", "SouthAsia"]
}
```

The `units` dict nests as `units[regionKey][unitName] = count`. Buildings (Craters, Cathedrals, Ice Age markers) appear as unit entries alongside real units.


## Power Tracking

The engine tracks power expenditures for every game action. Comprehensive list of handled power costs:

| Action | Cost | Handler |
|--------|------|---------|
| Move | 1 | `moved` |
| Recruit cultist | 1 | `recruited` |
| Summon monster | Unit cost from FACTION_ROSTER | `summoned` |
| Awaken GOO | Logged cost or lookup table | `awakened` |
| Build gate | 3 | `built_gate` |
| Battle (attacker) | 1 | `battle_start` |
| Capture | 1 | `captured` |
| Writhe (FB) | 2 | `writhe_start` |
| Submerge (GC) | 1 | `cthulhu_submerge` |
| Cursed Slumber take (SL) | 1 | `cursed_slumber_take` |
| Ice Age start (WW) | 1 | `ice_age` |
| Ice Age effect (victims) | 1 | `ice_age_power` |
| Desecration (YS) | 1 | `kiy_scream` |
| Failed desecration (YS) | 1 | `failed_desecration` |
| Screaming Dead (YS) | 1 | `kiy_scream` |
| The Eye Opens (FB) | 1 | `sb_facedown` |
| Carnage (FB) | 1 | `sb_facedown` |
| Ritual | Logged cost | `ritual` |
| Generic spent/paid | N | `spent_power` / `paid_power` |
| Pass/forfeit | N | `forfeited_power` |
| Lethargy (SL) | N (caster) + N per opponent | `lethargy` |
| Demand Sacrifice (SL) | N | `demand_sacrifice_*` |
| Infernal Pact discount | -N (refund) | `ip_discount` |
| Festival (AN) | -N (gain) | `festival` |
| Devil's Mark power (FB) | -N (gain) | `dm_power` |
| Shepherd (TS) | -N (gain) | `shepherd` |
| Hibernation (WW) | -N (gain) | `hibernated` |


## Image Embedding

All images are embedded as base64 data URIs so the HTML replay is fully self-contained (no external files needed).

Source directory: `~/cthulhu-wars FB/solo/webp/images/`

Image categories:
- **Map**: `earth35-dark.webp` -- World map background
- **Placement bitmap**: `earth35-place.webp` -- Region boundary bitmap (unique RGB per region)
- **Gate**: `gate.webp` -- Universal gate icon
- **Ritual track**: `ritual_track_4p.jpg` -- 4-player ritual cost tracker
- **Per-faction backgrounds**: `{fc}-background.webp`
- **Per-faction glyphs**: `{fc}-glyph.webp` -- Faction symbol
- **Per-faction units**: `{fc}-{unit}.webp` -- Individual unit images

The `UNIT_IMAGE_MAP` dict in `build-replay.py` maps `(faction, unit_name)` pairs to image filenames. FB and TS units use greyscale base images with CSS `filter` tinting (`tint-fb`, `tint-ts` classes).


## Unit Rendering

### UNIT_SIZES

Defined in the JS viewer, these are the original DrawRect sizes (in map pixels, 1791x894 coordinate space) from the Scala game code. They control proportional scaling of unit images on the map.

Unit categories by size:
- **GOOs**: Largest (96-164px wide, 135-225px tall)
- **Large monsters**: Mid-size (69-166px wide, 70-131px tall)
- **Medium monsters**: Smaller (36-70px wide, 31-95px tall)
- **Cultists**: Smallest (39-70px wide, 60-68px tall)
- **Buildings**: Gate-sized (76x76px)

### Unit Placement Algorithm

The JS viewer replicates the game's `GlyphPlacement.scala findAnother()` algorithm:

1. **Gate controller first**: If a region has a gate, the owning faction's first gate-controlling unit (Acolyte, High Priest, or Dark Young) is placed at gate center.

2. **Placement bitmap**: The `earth35-place.webp` bitmap assigns a unique RGB color to each of the 17 regions. The reference color for a region is sampled at the region's coordinate center.

3. **Candidate generation**: For each remaining unit, generate random map coordinates. Accept only those whose placement bitmap color matches the region's reference color. Collect up to 40 valid candidates per unit (max 2000 attempts).

4. **Candidate ranking**: Sort candidates by weighted distance `5*|dx| + |dy|` from region center (closest first).

5. **Collision avoidance**: Score each candidate by bounding-box overlap with already-placed units. Select the candidate with minimum overlap (ties broken by distance = closer wins).

6. **Deterministic RNG**: Uses a seeded LCG (`seed * 1103515245 + 12345`) based on region name hash, so placement is consistent across views.

7. **Render order**: Units sorted by rank (cultists/small first, GOOs last) so large units overlap small ones.

### Faction Glyphs on Map

Each faction's glyph icon is placed at their starting region. The placement algorithm scans 200 angles at distances 40-150px from gate center, checking the placement bitmap to ensure the glyph stays within region bounds, and preferring positions far from the gate.


## Buildings on Map

Buildings are tracked as units in `units_by_region` so they render on the map alongside regular units:

| Building | Faction | How Tracked |
|----------|---------|-------------|
| Crater | FB | Placed via Devil's Mark; gate at same location is destroyed |
| Cathedral | AN | Placed via `built a cathedral`; can be removed by Unholy Ground |
| Ice Age | WW | Placed via `started Ice Age in Region` |
| Desecration | YS | Tracked in `state.desecrated` list (region keys) |


## Decision Weights

When the simulator runs with `--trace` or `--save-all`, it emits debug lines interleaved with the game log:

- `[BOT FB @N] ActionName (score)` -- The chosen action and its final score
- `[OPT faction] ActionName = score` -- Alternative options the bot considered
- `[WHY] score = reason` -- Score breakdown explaining why the chosen action scored highest

These are accumulated in `state._pending_weights` as they appear (before the actual game event). When the next non-debug display line is processed, `build_snapshots_v2` parses the accumulated weights into a structured dict:

```json
{
  "chosen": {"action": "MoveAction(Ghato, Europe, NAm)", "score": 42},
  "options": [
    {"action": "MoveAction(Ghato, Europe, NAm)", "score": 42},
    {"action": "CaptureAction(Europe, Acolyte)", "score": 35}
  ],
  "reasons": [
    {"score": 20, "reason": "gate_capture_potential"},
    {"score": 15, "reason": "enemy_cultist_present"}
  ]
}
```

The JS viewer shows this in the **Weights panel** (bottom-right, toggled via button). The chosen action is highlighted green; alternatives listed by score; WHY reasons shown in italic blue.


## Known Limitations

1. **Pool tracking**: The v1 parser in `build-replay.py` does not track unit pools (units available for summoning). The v2 engine (`game_state.py` + `event_handlers.py`) does track pools but some edge cases around released prisoners may not fully restore pool counts.

2. **Followed along** (YS): When KiY screams, units that "followed along" are not reliably tracked because the log doesn't always specify source region.

3. **Faction-specific combat values**: Dynamic combat values (e.g., Ghatanothoa = current power, Revenant = desiccated count) are defined in FACTION_ROSTER but not evaluated during replay -- they're for reference only.

4. **Neutral units**: Independent units from expansions (Azathoth, neutral monsters) are not tracked.

5. **Elder Sign values**: Individual ES values are not tracked -- only the count of hidden ES and total doom from reveals.

6. **Duplicate parsers**: `build-replay.py` contains a legacy `build_snapshots()` function and `GameState`/`FactionState` classes that duplicate `game_state.py`. The legacy code is no longer called (`main()` imports `build_snapshots_v2` instead) but remains in the file.

7. **Negotiation effects**: Negotiation outcomes (power transfers, unit movements from deals) are display-only and don't update state.

8. **Rare abilities**: Some faction abilities with unusual log formats may not match any handler and will appear in the unmatched summary.


## Analysis Tools

### dump-game-state.py

Exports the full game state after every action to XML.

**Usage:**
```
python3 dump-game-state.py <trace-file.txt> <output.xml>
```

Each `<action>` XML element contains:
- Attributes: `n` (sequential), `round`, `phase`, `phase_action`, `faction`, `handler`, `matched`
- `<text>` child: plain-text game log line
- `<state>` child: full snapshot with `<ritual_cost>`, `<faction>` elements (power, doom, ES, gates, pool, spellbooks, captured), and `<regions>` with per-region `<gate>`, `<building>`, and `<unit>` elements

Phase detection: Turn N = action phase, POWER GATHER = gather phase, Play order = player_order, Ritual cost = doom phase.

### analyze-tactic01-02.py

XML-based tactic adherence analysis for Firstborn bot.

**Usage:**
```
python3 analyze-tactic01-02.py <win-logs-dir> [--dump-xml]
```

Analyzes Tactic 01+02 (post-awaken Ghatanothoa writhe targeting):

1. Finds Ghato awaken event
2. Finds first writhe relocation in the next action phase
3. Queries exact game state at writhe time from XML
4. Classifies destination: enemy gate (with/without GOO), empty land, own gate, abandoned
5. For empty land destinations, checks whether viable enemy gates existed (scoring bug detection)
6. Tracks what FB does next after arriving at enemy gate
7. Outputs a decision tree with adherence percentages

The `--dump-xml` flag preserves the intermediate XML files for inspection.

---

## Supporting New Maps

When adding a new map (e.g., Library at Celaeno), the following must be updated:

### 1. Map Detection (`build-replay.py: detect_map_id()`)

The game logs the map in the Options line: `Options MapLibrary35 PlayerCount(4)`. The replay engine checks this line for the map option string and maps it to an image file prefix:

```python
MAP_OPTIONS = {
    "MapLibrary33": ("library3", True), "MapLibrary35": ("library4a", True),
    "MapLibrary53": ("library4b", True), "MapLibrary55": ("library5", True),
    "MapEarth33": ("earth33", False), ...
}
```

**Critical:** The game MUST log the map option. If the sim doesn't include it in `opts`, add it: `opts :+ mapOpt`. Without it, the replay engine can't determine which map image to use.

### 2. Image Directory (`IMAGE_DIR`)

Different game builds store images in different directories. When a Library map is detected, `IMAGE_DIR` switches to the Library build's image folder. Library maps use horizontal (`-h-`) image variants for the replay viewer.

### 3. Region Coordinates (`REGION_COORDS_LIBRARY`)

Each map needs a coordinate dict mapping region IDs to (x, y) pixel positions on the **horizontal** map image. These positions determine where units are drawn.

Region IDs are the `Area.id` field (name with spaces removed): `"Barrier of Naach-Tith"` → `"BarrierofNaach-Tith"`.

### 4. Region Names (`game_state.py: REGION_NAMES`)

All regions that can appear in a game must be in `REGION_NAMES`. Without them, `FullGameState.regions` won't have entries for those regions, and unit placements will be silently dropped (units won't appear on map).

### 5. Display Name Mapping (`REGION_DISPLAY`, `REGION_FROM_DISPLAY`)

The game log uses display names ("Barrier of Naach-Tith") but state tracking uses IDs ("BarrierofNaach-Tith"). Library regions with special characters (hyphens, apostrophes) need explicit entries in `LIBRARY_REGION_DISPLAY`.

### 6. Event Handlers (`event_handlers.py`)

Map-specific mechanics (Library tomes, Silence Tokens, Custodian/Librarian) need handlers to track state changes. Without them, these events show as "unmatched" warnings and state isn't captured in snapshots.

### 7. Replay Output Location

Replays go into the build's folder in My Drive, never into game code directories:
- `~/My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/` for Library builds
- `~/My Drive/Personal/Games/Cthulhu Wars/Firstborn/Bot/` for FB builds

### Checklist for Adding a New Map to Replay Engine

1. [ ] Game logs the map option in Options line (via `opts :+ mapOpt` in sim)
2. [ ] `detect_map_id()` maps the option string to an image file prefix
3. [ ] Horizontal map image exists (`{prefix}-h-dark.webp`)
4. [ ] `REGION_COORDS_{MAP}` dict with all region (x,y) on horizontal image
5. [ ] All region IDs added to `REGION_NAMES` in `game_state.py`
6. [ ] Display name mappings added to `LIBRARY_REGION_DISPLAY` (or equivalent)
7. [ ] Map-specific event handlers added to `event_handlers.py`
8. [ ] Test: units appear at correct positions on map in generated replay
9. [ ] Tome positions added (separate from region coords — use TomePlacement values from MapExpansion.scala)
10. [ ] Unit scale factor set (Library = 2.0, Earth = 1.0) since Library bitmaps are 2x resolution
11. [ ] MAP_W/MAP_H match bitmap resolution (Library=3582x1793, Earth=1791x894)
12. [ ] DS faction added to FACTION_NAMES if missing
13. [ ] Silence token + custodian/librarian icon paths correct (in `icons/` subfolder, PNG format)
14. [ ] Library tome images (tome-barrier.webp etc.) in `images/` subfolder
15. [ ] Tomes render on faction card header (same line as name), not below stats

---

## 2026-05-14 changes

### Necrophagy "Ghoul came from <region>" — destination is current battle region

`event_handlers.py` "came from" handler — previously matched but did no state change. Now mirrors the `flew_from` handler: extracts source from the line, destination = `state.battle.region || state.effect_region`, calls `state.move_unit`.

### Writhe undo handling

New `state.writhe_action_stack` field on `FullGameState`. Each "Writhe: Acolyte replaced with Desiccated" pushes `("kill", region, "Acolyte")`. Each "Writhe: relocated <unit> from X to Y" pushes `("pain", unit, X, Y)`. Stack reset at "used Writhe rolling N dice".

Handlers added:
- `"Writhe: undid last kill"` — pop latest kill entry, remove the Desiccated, restore original Acolyte.
- `"Writhe: undid last region selection"` — pop latest pain entry, relocate unit back to source.
- `"Writhe: undid last pain selection"` — no state change (pre-move pick).
- `"Writhe: undid all choices, back to dice roll"` — pop everything in LIFO order, reverse each.

### Eye Opens elimination

New handler for `"<faction> The Eye Opens: eliminated <unit> and Desiccated in <region>"`. Removes the target enemy cultist + adds to their reserve; removes FB Desiccated + adds to FB reserve. Separate handler for `"The Eye Opens: gained N Power"` acknowledges the line (power gain is processed by the existing generic power-gain handler).

### IP power tracking — user model (2026-05-14)

**User-mandated model:** each `"Infernal Pact: flipped X facedown, discount now N Power"` line adds **+1 power** at flip time (representing the future-action discount up-front). The downstream `"Infernal Pact discounted N Power"` line does NOT add power (would double-count).

**Why this model:** the user observed power tracking drift when the engine added power only at "discounted N" time. The flip-time +1 model lets the replay engine match the game engine's power state earlier in the action sequence and surfaces discrepancies sooner.

**End-of-AP audit:** at every `POWER GATHER` event, if FB power != 0, push a diagnostic record to `state._power_audit` for inspection. The audit list survives across the run so build-replay.py can dump it.

