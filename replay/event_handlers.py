"""
Event handlers for updating FullGameState from game log lines.
Central function: process_line() matches a single HTML log line against
~80 regex patterns, mutates FullGameState, and returns an EventRecord.

Handler priority: faction-prefixed events first (placement, power, movement,
combat, spellbooks, faction abilities), then non-prefixed events (battles,
kills, retreats, pains), then catch-all patterns for rare abilities.
"""
import re
from game_state import (
    FullGameState, EventRecord, GateInfo, BuildingInfo, RequirementEntry,
    ALL_GOOS, GATE_CONTROLLERS, FACTION_ROSTER, OCEAN_REGIONS,
    IGOO_NAMES, IGOO_COSTS, NEUTRAL_MONSTERS
)

FACTION_NAMES = {
    "Great Cthulhu": "GC", "Crawling Chaos": "CC", "Black Goat": "BG",
    "Yellow Sign": "YS", "Opener of the Way": "OW", "Sleeper": "SL",
    "Windwalker": "WW", "The Ancients": "AN", "Tombstalker": "TS", "Firstborn": "FB",
    "Daemon Sultan": "DS"
}
FACTION_FULL = {v: k for k, v in FACTION_NAMES.items()}

# Unit name regex pattern — matches multi-word names with hyphens, apostrophes, spaces
# e.g., "Revenant of K'Naa", "Fungi from Yuggoth", "Rhan-Tegoth"
U = r"([\w' -]+)"


def strip_html(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&gt;", ">").replace("&lt;", "<").replace("&nbsp;", " ").replace("&amp;", "&")
    return s.strip()


def region_key(display_name):
    return display_name.replace(" ", "")


def faction_prefix(line):
    for full, short in FACTION_NAMES.items():
        if line.startswith(full):
            return short, full, line[len(full):].strip()
    return None, None, line


def extract_faction_from_span(raw_line, keyword):
    """Extract (faction_code, unit_name) pairs from HTML spans near a keyword.
    Filters out CSS class names that aren't faction codes (kill, pain, region, etc.)."""
    IGNORE = {"kill", "pain", "miss", "region", "sea", "power", "inline-block", "str", "es", "doom"}
    parts = raw_line.split(keyword)
    if len(parts) < 2:
        return []
    spans = re.findall(r"<span class='(\w+)'>([\w' -]+)</span>", parts[0] if keyword != "before" else raw_line)
    results = []
    for fc, name in spans:
        if fc.lower() in IGNORE or name.strip().lower() in ("killed", "were", "was", "pained", "eliminated"):
            continue
        if fc.upper() in FACTION_NAMES.values() or fc.upper() in [v for v in FACTION_NAMES.values()]:
            results.append((fc.upper(), name.strip()))
    return results


def process_line(state: FullGameState, raw_line: str, line_idx: int) -> EventRecord:
    """Process a single HTML game log line, updating state. Returns EventRecord."""
    plain = strip_html(raw_line)

    event = EventRecord(line_index=line_idx, plain_text=plain)

    # Skip debug/separator lines
    if plain.startswith("[BOT") or plain.startswith("[OPT") or plain.startswith("[WHY") or plain.startswith("[ALT"):
        state._pending_weights.append(plain)
        event.matched = True
        event.handler_name = "debug_line"
        return event
    if plain.startswith("..........") or plain.startswith("TRACE_"):
        event.matched = True
        event.handler_name = "separator"
        return event
    if plain.startswith("Options "):
        # Set state.map_id from the MapEarth*/MapLibrary* token in the options
        # line. This is the authoritative source for which map is in play —
        # used by build-replay.py to embed the right map image and by the
        # state-change audit to fingerprint map identity.
        m_map = re.search(r"\b(MapEarth\d{2}|MapLibrary\d{2})\b", plain)
        if m_map:
            state.map_id = m_map.group(1)
        event.matched = True
        event.handler_name = "options_line"
        return event

    # Take fingerprint before processing
    fp_before = state.summary_fingerprint()

    # ── Non-faction-prefixed log lines ──
    # Some `log(...)` calls (without `self.log`) produce lines that don't start
    # with a faction name. Handle those here before the faction-prefix branch.

    # DS Azathoth Synthesis 3-player halving announcement.
    if re.match(r"^Halved to \[?\d+\]? for \d+-player game$", plain):
        event.matched = True; event.handler_name = "ds_azathoth_target_halved"
        return event

    # DS Azathoth Synthesis: announces the demand value for the auction.
    if "Other factions must collectively offer" in plain and "Power/Doom" in plain:
        event.matched = True; event.handler_name = "ds_azathoth_announce"
        return event

    # DS Avatar Synthesis combat-die redisplay line (battle visibility, not the
    # roll itself — that's the "rolled the Azathoth die [N] — combat strength"
    # line emitted with `self.log` and handled in the DS-prefixed block).
    # Battle.scala:613 / 618 emit: "Avatar Synthesis Azathoth die [N] — strength [N]"
    if re.match(r"^Avatar Synthesis Azathoth die \[\d+\] — strength \[\d+\]$", plain):
        event.matched = True; event.handler_name = "ds_azathoth_die_redisplay"
        return event

    # Faction-prefixed events
    short, full, rest = faction_prefix(plain)
    if short:
        state.ensure_faction(short)
        fs = state.factions[short]
        event.faction = short

        # ── PLACEMENT ──
        m = re.match(r"^started in (.+)$", rest)
        if m:
            reg = region_key(m.group(1).strip())
            fs.start_region = reg
            fs.power = 8
            # Place 6 starting acolytes
            for _ in range(6):
                state.place_unit(short, "Acolyte", reg)
            # Starting gate
            r = state.get_region(reg)
            if r:
                r.gate = GateInfo(exists=True, owner=short)
                state.gate_locations.add(reg)
                fs.gates.add(reg)
            event.matched = True; event.handler_name = "started_in"

        # ── POWER ──
        # "got N Power" / "got N Power (breakdown)" = absolute set (Gather Power).
        # "got N Power from <SB/effect>" = additive gain (Passion SB, etc.).
        # The parenthetical "(2 x 1 gate + 6 cultists)" comes from Gather Power
        # logging — treat as absolute set, not additive.
        m = re.match(r"^got (\d+) Power(?:\s+from\s+([^(]+?))?(?:\s*\(.*\))?\s*$", rest)
        if m:
            amount = int(m.group(1))
            if m.group(2):
                fs.power += amount
            else:
                fs.power = amount
            event.matched = True; event.handler_name = "got_power"

        m = re.match(r"^power increased to (\d+) Power", rest)
        if m:
            fs.power = int(m.group(1))
            event.matched = True; event.handler_name = "power_increased"

        m = re.match(r"^recovered (\d+) Power", rest)
        if m:
            fs.power += int(m.group(1))
            event.matched = True; event.handler_name = "recovered_power"

        m = re.match(r"^spent (\d+) Power$", rest)
        if m:
            fs.power = max(0, fs.power - int(m.group(1)))
            event.matched = True; event.handler_name = "spent_power"

        m = re.match(r"^paid (\d+) Power", rest)
        if m:
            fs.power = max(0, fs.power - int(m.group(1)))
            event.matched = True; event.handler_name = "paid_power"

        if rest == "ran out of power" or rest == "had no power":
            fs.power = 0
            event.matched = True; event.handler_name = "ran_out"

        m = re.match(r"^passed and forfeited (\d+) Power", rest)
        if m:
            fs.power = max(0, fs.power - int(m.group(1)))
            event.matched = True; event.handler_name = "forfeited_power"

        m = re.match(r"^hibernated for extra (\d+) Power", rest)
        if m:
            fs.power += int(m.group(1))
            event.matched = True; event.handler_name = "hibernated"
        elif rest == "hibernated":
            # WW: hibernated with 0 extra power — informational only.
            event.matched = True; event.handler_name = "wwhibernated"

        # ── MOVEMENT ──
        m = re.match(r"^moved " + U + r" from (.+?) to (.+?)$", rest)
        if m:
            unit = m.group(1).strip(); src = region_key(m.group(2).strip()); dst = region_key(m.group(3).strip())
            # Prefer explicit src; fall back to relocate (handles cases where the
            # unit isn't actually in `src` because an earlier handler missed an
            # update). Decrement power either way since the move did happen in
            # the real game.
            src_reg = state.regions.get(src)
            if src_reg and src_reg.has_unit(short, unit):
                state.move_unit(short, unit, src, dst)
            else:
                state.relocate_unit(short, unit, dst)
            fs.power = max(0, fs.power - 1)
            event.matched = True; event.handler_name = "moved"

        # ── RECRUIT ──
        m = re.match(r"^recruited " + U + r" in (.+)$", rest)
        if m:
            unit = m.group(1).strip(); reg = region_key(m.group(2).strip())
            state.place_unit(short, unit, reg)
            fs.power = max(0, fs.power - 1)
            event.matched = True; event.handler_name = "recruited"

        # ── SUMMON ──
        m = re.match(r"^summoned " + U + r" in (.+?)(?:\s+for free)?$", rest)
        if m:
            unit = m.group(1).strip(); reg = region_key(m.group(2).strip())
            is_free = "for free" in rest
            state.place_unit(short, unit, reg)
            if not is_free:
                cost = 0
                roster = FACTION_ROSTER.get(short, {})
                for ud in roster.get("units", []):
                    if ud.name == unit:
                        try:
                            cost = int(ud.cost)
                        except (ValueError, TypeError):
                            cost = 0
                        break
                if cost == 0 and unit in ("Acolyte",):
                    cost = 1
                fs.power = max(0, fs.power - cost)
            event.matched = True; event.handler_name = "summoned"

        # ── AWAKEN ──
        m = re.match(r"^awakened " + U + r" in (.+?)(?:\s+for (\d+) Power)?(?:\s*\+.*)?$", rest)
        if m:
            unit = m.group(1).strip(); reg = region_key(m.group(2).strip())
            if m.group(3):
                cost = int(m.group(3))
            else:
                # Non-FB factions don't log awaken cost. Look up per-GOO awaken cost.
                AWAKEN_COSTS = {
                    "Cthulhu": 10, "Hastur": 10, "Shub-Niggurath": 8,
                    "Nyarlathotep": 10, "Tsathoggua": 8, "Ithaqua": 6,
                    "Yog-Sothoth": 10, "Rhan-Tegoth": 6, "Rhan Tegoth": 6,
                    "Glaaki": 6, "Gla'aki": 6,
                    "Byatis": 4, "Abhoth": 4, "Daoloth": 6,
                    "Nyogtha": 6, "Tulzscha": 4, "Y'Golonac": 2,
                }
                cost = AWAKEN_COSTS.get(unit, 10)
            # GOOs unique: remove existing
            if unit in ALL_GOOS:
                for rkey, r in state.regions.items():
                    r.remove_unit(short, unit, 99)
            state.place_unit(short, unit, reg)
            if cost > 0:
                fs.power = max(0, fs.power - cost)
            event.matched = True; event.handler_name = "awakened"

        # ── BUILD GATE ──
        m = re.match(r"^built a gate in (.+)$", rest)
        if m:
            reg = region_key(m.group(1).strip())
            r = state.get_region(reg)
            if r:
                r.gate = GateInfo(exists=True, owner=short)
                state.gate_locations.add(reg)
                fs.gates.add(reg)
            fs.power = max(0, fs.power - 3)
            event.matched = True; event.handler_name = "built_gate"

        # ── BUILD CATHEDRAL ──
        m = re.match(r"^built a cathedral in (.+)$", rest)
        if m:
            reg = region_key(m.group(1).strip())
            state.place_unit(short, "Cathedral", reg)
            state.cathedrals.append(reg)
            event.matched = True; event.handler_name = "built_cathedral"

        # ── GATE CONTROL ──
        m = re.match(r"^lost control of the gate in (.+)$", rest)
        if m:
            reg = region_key(m.group(1).strip())
            fs.gates.discard(reg)
            r = state.get_region(reg)
            if r and r.gate.owner == short:
                r.gate.owner = None
            event.matched = True; event.handler_name = "lost_gate"

        m = re.match(r"^gained control of the gate in (.+)$", rest)
        if m:
            reg = region_key(m.group(1).strip())
            fs.gates.add(reg)
            r = state.get_region(reg)
            if r:
                r.gate = GateInfo(exists=True, owner=short)
                state.gate_locations.add(reg)
            event.matched = True; event.handler_name = "gained_gate"

        # ── CAPTURE ──
        m = re.match(r"^captured (.+?) in (.+)$", rest)
        if m:
            unit_raw = m.group(1).strip(); reg = region_key(m.group(2).strip())
            cap_match = re.search(r"captured <span class='(\w+)'", raw_line)
            if cap_match:
                vic_fc = cap_match.group(1).upper()
                r = state.get_region(reg)
                if r and vic_fc in state.factions:
                    r.remove_unit(vic_fc, unit_raw)
                    state.factions[vic_fc].pool[unit_raw] = state.factions[vic_fc].pool.get(unit_raw, 0)
                    fs.captured.append({"faction": vic_fc, "unit": unit_raw, "qty": 1})
            fs.power = max(0, fs.power - 1)
            event.matched = True; event.handler_name = "captured"

        # ── SACRIFICE ──
        m = re.match(r"^sacrificed " + U + r" in (.+?)(?:\s+for.*)?$", rest)
        if m:
            unit = m.group(1).strip(); reg = region_key(m.group(2).strip())
            r = state.get_region(reg)
            if r: r.remove_unit(short, unit)
            event.matched = True; event.handler_name = "sacrificed"

        # ── DOOM ──
        m = re.match(r"^got (\d+) Doom", rest)
        if m:
            fs.doom += int(m.group(1))
            event.matched = True; event.handler_name = "got_doom"

        m = re.match(r"^gained (\d+) Doom", rest)
        if m:
            fs.doom += int(m.group(1))
            event.matched = True; event.handler_name = "gained_doom"

        # ── RITUAL ──
        m = re.match(r"^performed the ritual for (\d+) Power and gained (\d+) Doom", rest)
        if m:
            cost = int(m.group(1)); doom = int(m.group(2))
            fs.power = max(0, fs.power - cost)
            fs.doom += doom
            es_m = re.search(r"(\d+) Elder Signs?", rest)
            if es_m:
                fs.elder_signs_hidden += int(es_m.group(1))
            elif "an Elder Sign" in rest:
                fs.elder_signs_hidden += 1
            state.ritual_history.append(short)
            state.ritual_marker = min(state.ritual_marker + 1, len(state.ritual_track) - 1)
            state.ritual_cost = state.ritual_track[state.ritual_marker]
            event.matched = True; event.handler_name = "ritual"

        # ── ES REVEAL ──
        # Format: "X revealed [N] [M] [K] ... for Y Doom". Each [N] is one ES
        # with face value N. v5 (2026-05-13): preserve the revealed face values
        # in elder_signs_revealed so the faction card panel can still show the
        # running total earned (hidden + revealed) — without that, ES tracking
        # appeared "broken" once a faction revealed at end of game.
        m = re.match(r"^revealed .+ for (\d+) Doom\s*$", rest)
        if m:
            reveal_doom = int(m.group(1))
            fs.doom += reveal_doom
            # Parse face values from "[N]" tokens
            values = [int(v) for v in re.findall(r"\[(\d+)\]", rest)]
            fs.elder_signs_revealed.extend(values)
            fs.elder_signs_hidden = 0
            event.matched = True; event.handler_name = "es_reveal"

        # ── SPELLBOOKS ──
        m = re.match(r"^received (.+)$", rest)
        if m and "Silence Token" not in m.group(1):
            sb_name = m.group(1).strip()
            fs.add_spellbook(sb_name)
            event.matched = True; event.handler_name = "received_sb"

        m = re.match(r"^achieved (.+)$", rest)
        if m:
            req_name = m.group(1).strip()
            fs.requirements.append(RequirementEntry(req_name, True))
            event.matched = True; event.handler_name = "achieved_req"

        m = re.match(r"^(.+) flipped facedown$", rest)
        if m:
            sb_name = m.group(1).strip()
            fs.flip_spellbook(sb_name, False)
            # Some SB activations cost power
            SB_ACTIVATION_COSTS = {"The Eye Opens": 1, "Carnage": 1}
            sb_cost = SB_ACTIVATION_COSTS.get(sb_name, 0)
            if sb_cost > 0:
                fs.power = max(0, fs.power - sb_cost)
            event.matched = True; event.handler_name = "sb_facedown"

        m = re.match(r"^(.+) flipped faceup$", rest)
        if m:
            fs.flip_spellbook(m.group(1).strip(), True)
            event.matched = True; event.handler_name = "sb_faceup"

        # ── RELEASED PRISONERS ──
        m = re.match(r"^released (.+)$", rest)
        if m:
            releases = re.findall(r"<span class='(\w+)'>([\w' -]+)</span>", raw_line)
            for vic_fc, vic_unit in releases:
                vic_fc_upper = vic_fc.upper()
                if vic_fc_upper in state.factions:
                    state.factions[vic_fc_upper].pool[vic_unit.strip()] = \
                        state.factions[vic_fc_upper].pool.get(vic_unit.strip(), 0) + 1
            event.matched = True; event.handler_name = "released"

        # ── WRITHE EVENTS ──
        m = re.match(r"^Writhe: Acolyte replaced with Desiccated in (.+)$", rest)
        if m:
            reg = region_key(m.group(1).strip())
            r = state.get_region(reg)
            if r:
                r.remove_unit(short, "Acolyte")
                r.add_unit(short, "Desiccated", category="monster")
            state.writhe_action_stack.append(("kill", reg, "Acolyte"))
            event.matched = True; event.handler_name = "writhe_replace"

        m = re.match(r"^Writhe: relocated " + U + r" from (.+?) to (.+?)$", rest)
        if m:
            unit = m.group(1).strip()
            src = region_key(m.group(2).strip()); dst = region_key(m.group(3).strip())
            # Use relocate to handle the case where the unit isn't currently in
            # src (e.g., earlier pain step already moved it).
            src_reg = state.regions.get(src)
            if src_reg and src_reg.has_unit(short, unit):
                state.move_unit(short, unit, src, dst)
            else:
                state.relocate_unit(short, unit, dst)
            state.writhe_action_stack.append(("pain", unit, src, dst))
            event.matched = True; event.handler_name = "writhe_relocate"

        m = re.match(r"^Writhe: eliminated " + U + r" in (.+)$", rest)
        if m:
            unit = m.group(1).strip(); reg = region_key(m.group(2).strip())
            r = state.get_region(reg)
            if r: r.remove_unit(short, unit)
            fs.pool[unit] = fs.pool.get(unit, 0) + 1
            event.matched = True; event.handler_name = "writhe_eliminated"

        # ── WRITHE UNDOS ──
        # "undid last kill" — reverse the most recent kill entry in the stack
        if "Writhe: undid last kill" in rest or "undid last kill" in rest:
            # Find latest "kill" entry in the stack and reverse it
            for i in range(len(state.writhe_action_stack) - 1, -1, -1):
                entry = state.writhe_action_stack[i]
                if entry[0] == "kill":
                    _, reg, unit_class = entry
                    state.writhe_action_stack.pop(i)
                    r = state.get_region(reg)
                    if r:
                        # Remove the Desiccated that was added, restore the original unit
                        r.remove_unit(short, "Desiccated")
                        r.add_unit(short, unit_class, category="cultist" if unit_class == "Acolyte" else "monster")
                    break
            event.matched = True; event.handler_name = "writhe_undo_kill"

        # "undid last region selection" — reverse the most recent pain entry
        if "Writhe: undid last region selection" in rest or "undid last region selection" in rest:
            for i in range(len(state.writhe_action_stack) - 1, -1, -1):
                entry = state.writhe_action_stack[i]
                if entry[0] == "pain":
                    _, unit, src, dst = entry
                    state.writhe_action_stack.pop(i)
                    state.relocate_unit(short, unit, src)
                    break
            event.matched = True; event.handler_name = "writhe_undo_move"

        # "undid last pain selection" — no state change (pre-move pick)
        if "Writhe: undid last pain selection" in rest or "undid last pain selection" in rest:
            event.matched = True; event.handler_name = "writhe_undo_pain_pick"

        # "undid all choices, back to dice roll" — reverse everything in the stack
        if "undid all choices" in rest or "back to dice roll" in rest:
            # Reverse in LIFO order
            while state.writhe_action_stack:
                entry = state.writhe_action_stack.pop()
                if entry[0] == "kill":
                    _, reg, unit_class = entry
                    r = state.get_region(reg)
                    if r:
                        r.remove_unit(short, "Desiccated")
                        r.add_unit(short, unit_class, category="cultist" if unit_class == "Acolyte" else "monster")
                elif entry[0] == "pain":
                    _, unit, src, dst = entry
                    state.relocate_unit(short, unit, src)
            event.matched = True; event.handler_name = "writhe_undo_all"

        # ── THE EYE OPENS ──
        # "Firstborn The Eye Opens: eliminated <unit> and Desiccated in <region>"
        # — eliminates one enemy cultist + one FB desc in the region.
        # The Eye Opens itself sits in a styled span. Match the span sequence
        # AFTER "The Eye Opens" through to the region.
        m_eye = re.search(r"The Eye Opens</span>:\s*eliminated\s+<span class='(\w+)'>([\w' -]+)</span>\s+and\s+<span class='fb'>Desiccated</span>\s+in\s+<span class='(?:region|sea)'>([\w' -]+)</span>", raw_line)
        if m_eye:
            target_fc = m_eye.group(1).upper()
            target_unit = m_eye.group(2).strip()
            reg = region_key(m_eye.group(3).strip())
            r = state.get_region(reg)
            if r:
                # Remove the target enemy cultist
                if target_fc in state.factions:
                    r.remove_unit(target_fc, target_unit)
                    tfs = state.factions[target_fc]
                    tfs.pool[target_unit] = tfs.pool.get(target_unit, 0) + 1
                # Remove FB's Desiccated
                r.remove_unit("FB", "Desiccated")
                fs.pool["Desiccated"] = fs.pool.get("Desiccated", 0) + 1
            event.matched = True; event.handler_name = "eye_opens_eliminate"

        # "Firstborn The Eye Opens: gained 1 Power" — just acknowledge (power
        # gain is processed by the generic power_gain handler elsewhere).
        if "The Eye Opens" in rest and "gained" in rest and "Power" in rest:
            event.matched = True; event.handler_name = "eye_opens_gained_power"

        # ── CALL OF THE FAITHFUL ──
        m = re.match(r"^Call of the Faithful: placed Acolyte (?:on the gate )?in (.+)$", rest)
        if m:
            reg = region_key(m.group(1).strip())
            state.place_unit(short, "Acolyte", reg)
            event.matched = True; event.handler_name = "cof_placed"

        # ── PROMOTION (MFO) ──
        m = re.match(r"^promoted " + U + r" in (.+?) to " + U + r"$", rest)
        if m:
            old = m.group(1).strip(); reg = region_key(m.group(2).strip()); new = m.group(3).strip()
            r = state.get_region(reg)
            if r:
                r.remove_unit(short, old)
                r.add_unit(short, new)
            event.matched = True; event.handler_name = "promoted"

        # ── DEVIL'S MARK ──
        m = re.match(r"^placed Crater in (.+?) with Devil's Mark$", rest)
        if m:
            reg = region_key(m.group(1).strip())
            state.place_unit(short, "Crater", reg)
            state.craters.append(reg)
            event.matched = True; event.handler_name = "dm_crater"

        # Generic gate destruction: "destroyed gate in Region" (Ithaqua awaken, etc.)
        m = re.match(r"^destroyed gate in (.+)$", rest)
        if m:
            reg = region_key(m.group(1).strip())
            r = state.get_region(reg)
            if r:
                old_owner = r.gate.owner
                r.gate = GateInfo(exists=False, owner=None)
                if old_owner and old_owner in state.factions:
                    state.factions[old_owner].gates.discard(reg)
                state.gate_locations.discard(reg)
            event.matched = True; event.handler_name = "gate_destroyed_generic"

        m = re.match(r"^Gate in (.+?) destroyed by Crater$", rest)
        if m:
            reg = region_key(m.group(1).strip())
            r = state.get_region(reg)
            if r:
                old_owner = r.gate.owner
                r.gate = GateInfo(exists=False, owner=None)
                if old_owner and old_owner in state.factions:
                    state.factions[old_owner].gates.discard(reg)
                state.gate_locations.discard(reg)
            event.matched = True; event.handler_name = "gate_destroyed"

        # ── SL CURSED SLUMBER: moved gate from Region to Cursed Slumber / back ──
        m = re.match(r"^moved gate from (.+?) to Cursed Slumber$", rest)
        if m:
            reg = region_key(m.group(1).strip())
            r = state.get_region(reg)
            if r:
                # Remove gate from region
                old_owner = r.gate.owner
                r.gate = GateInfo(exists=False, owner=None)
                if old_owner and old_owner in state.factions:
                    state.factions[old_owner].gates.discard(reg)
                state.gate_locations.discard(reg)
                # Remove an Acolyte from region (goes to faction card with gate)
                r.remove_unit(short, "Acolyte")
                # Track on faction custom state
                fs.custom.setdefault("cursed_slumber_units", [])
                fs.custom["cursed_slumber_units"].append({"region": reg, "gate": True, "acolyte": True})
            fs.power = max(0, fs.power - 1)
            event.matched = True; event.handler_name = "cursed_slumber_take"

        m = re.match(r"^moved gate from Cursed Slumber to (.+)$", rest)
        if m:
            reg = region_key(m.group(1).strip())
            r = state.get_region(reg)
            if r:
                # Restore gate in new region
                r.gate = GateInfo(exists=True, owner=short)
                state.gate_locations.add(reg)
                fs.gates.add(reg)
                # Restore Acolyte
                state.place_unit(short, "Acolyte", reg)
                # Clear cursed slumber tracking
                cs = fs.custom.get("cursed_slumber_units", [])
                if cs:
                    cs.pop(0)  # Remove oldest entry
            event.matched = True; event.handler_name = "cursed_slumber_return"

        # ── SL DEATH FROM BELOW: placed Unit in Region with Death from Below ──
        m = re.match(r"^placed " + U + r" in (.+?) with Death from Below$", rest)
        if m:
            unit = m.group(1).strip(); reg = region_key(m.group(2).strip())
            state.place_unit(short, unit, reg)
            event.matched = True; event.handler_name = "death_from_below"

        # ── SL ANCIENT SORCERY: sent Serpent Man to access spellbook (removal) ──
        m = re.match(r"^sent " + U + r" from (.+?) to access .+$", rest)
        if m:
            unit = m.group(1).strip(); reg = region_key(m.group(2).strip())
            r = state.get_region(reg)
            removed = False
            if r:
                removed = r.remove_unit(short, unit)
            if not removed:
                # Fallback: unit isn't where the log says — find and remove from
                # wherever it actually is so the visual loses it.
                state.remove_unit_anywhere(short, unit)
            # Don't return to pool -- unit goes to faction card, returns in doom phase
            event.matched = True; event.handler_name = "ancient_sorcery_send"

        # ── SL ANCIENT SORCERY: placed Serpent Man in Region with Ancient Sorcery (return) ──
        m = re.match(r"^placed " + U + r" in (.+?) with Ancient Sorcery(?:\s+and gained .+)?$", rest)
        if m:
            unit = m.group(1).strip(); reg = region_key(m.group(2).strip())
            state.place_unit(short, unit, reg)
            # Power gain is handled by the "and gained N Power" part — extract it
            pw = re.search(r"gained (\d+) Power", rest)
            if pw:
                fs.power += int(pw.group(1))
            event.matched = True; event.handler_name = "ancient_sorcery_return"

        # ── WW CANNIBALISM: spawned Unit in Region with Cannibalism ──
        m = re.match(r"^spawned " + U + r" in (.+?) with Cannibalism$", rest)
        if m:
            unit = m.group(1).strip(); reg = region_key(m.group(2).strip())
            state.place_unit(short, unit, reg)
            event.matched = True; event.handler_name = "cannibalism"

        # ── SL LETHARGY: spent N Power and each other faction lost N Power ──
        m = re.match(r"^spent (\d+) Power and each other faction lost (\d+) Power$", rest)
        if m:
            cost = int(m.group(1)); loss = int(m.group(2))
            fs.power = max(0, fs.power - cost)
            for fc_code, fc_state in state.factions.items():
                if fc_code != short:
                    fc_state.power = max(0, fc_state.power - loss)
            event.matched = True; event.handler_name = "lethargy"

        # ── SL DEMAND SACRIFICE: spent N Power and each other faction gained N Power ──
        m = re.match(r"^spent (\d+) Power and each other faction gained (\d+) Power$", rest)
        if m and not event.matched:
            cost = int(m.group(1)); gain = int(m.group(2))
            fs.power = max(0, fs.power - cost)
            for fc_code, fc_state in state.factions.items():
                if fc_code != short:
                    fc_state.power += gain
            event.matched = True; event.handler_name = "demand_sacrifice_all"

        # ── SL DEMAND SACRIFICE: spent N Power and FactionName gained N Power ──
        m = re.match(r"^spent (\d+) Power and (.+?) gained (\d+) Power$", rest)
        if m and not event.matched:
            cost = int(m.group(1)); target_name = m.group(2).strip(); gain = int(m.group(3))
            fs.power = max(0, fs.power - cost)
            target_fc = FACTION_NAMES.get(target_name)
            if target_fc and target_fc in state.factions:
                state.factions[target_fc].power += gain
            event.matched = True; event.handler_name = "demand_sacrifice_target"

        # ── BEYOND ONE ──
        # Beyond One moves: (1) the gate, (2) the named unit, (3) the gate controller (cultist on gate)
        m = re.match(r"^moved gate with " + U + r" from (.+?) to (.+?)$", rest)
        if m:
            unit = m.group(1).strip()
            src = region_key(m.group(2).strip()); dst = region_key(m.group(3).strip())
            src_r = state.get_region(src); dst_r = state.get_region(dst)
            # Move gate controller (cultist on gate) from src to dst.
            # [2026-05-24] Default prev_owner to None outside the `if src_r:` block
            # so the dst_r assignment below has a defined value even when src has
            # no recorded gate (rare but observed with neutral / non-faction
            # placements).
            prev_owner = None
            if src_r:
                prev_owner = src_r.gate.owner if src_r.gate else None
                if prev_owner and prev_owner in state.factions:
                    # Find the gate controller cultist and move it
                    prev_fs = state.factions[prev_owner]
                    for uname in ["Acolyte", "High Priest", "Dark Young"]:
                        if src_r.has_unit(prev_owner, uname):
                            state.move_unit(prev_owner, uname, src, dst)
                            break
                    prev_fs.gates.discard(src)
                    prev_fs.gates.add(dst)
                fs.gates.discard(src)
                src_r.gate = GateInfo(exists=False, owner=None)
                state.gate_locations.discard(src)
            # Move the named unit
            state.move_unit(short, unit, src, dst)
            if dst_r:
                dst_r.gate = GateInfo(exists=True, owner=prev_owner if prev_owner else short)
                state.gate_locations.add(dst)
                if prev_owner and prev_owner in state.factions:
                    state.factions[prev_owner].gates.add(dst)
                else:
                    fs.gates.add(dst)
            event.matched = True; event.handler_name = "beyond_one"

        # ── CG PAIN ──
        m = re.search(r"Cyclopean Gaze - .+?: pained " + U + r" from (.+?) to (.+?)$", rest)
        if m:
            unit = m.group(1).strip()
            src = region_key(m.group(2).strip()); dst = region_key(m.group(3).strip())
            cg_spans = re.findall(r"pained <span class='(\w+)'>([\w' -]+)</span>", raw_line)
            for vic_fc, vic_unit in cg_spans:
                vic_fc_upper = vic_fc.upper()
                if vic_fc_upper in state.factions:
                    state.move_unit(vic_fc_upper, vic_unit.strip(), src, dst)
            event.matched = True; event.handler_name = "cg_pain"

    # ── NON-PREFIXED EVENTS ──

    # Battle region tracking — attacker pays 1 power
    m = re.search(r"([\w' -]+) battled [\w' -]+ in (.+)$", plain)
    if m:
        attacker_name = m.group(1).strip()
        reg = region_key(m.group(2).strip())
        state.battle.region = reg
        state.effect_region = reg
        for fn, fc in FACTION_NAMES.items():
            if attacker_name == fn and fc in state.factions:
                state.factions[fc].power = max(0, state.factions[fc].power - 1)
                state.battle.attacker = fc
                break
        event.matched = True; event.handler_name = "battle_start"

    # Effect region (Dread Curse, etc.) — costs 1 power for the sending faction
    m = re.search(r"sent .+? to <span class='(?:region|sea)'>([\w' -]+)</span>", raw_line)
    if m and not re.search(r"sent [\w' -]+ from", plain):
        state.effect_region = region_key(m.group(1).strip())
        if short and short in state.factions:
            state.factions[short].power = max(0, state.factions[short].power - 1)
        event.matched = True; event.handler_name = "effect_region"

    # Battle kills — extract victim faction+unit from HTML spans.
    # IGNORE_CLS filters CSS utility classes that aren't faction codes.
    if re.search(r"were killed|was killed", plain) and not (short and "Writhe" in rest):
        IGNORE_CLS = {"kill","pain","miss","region","sea","power","inline-block","str"}
        kills = re.findall(r"<span class='(\w+)'>([\w' -]+)</span>", raw_line)
        for kf, ku in kills:
            ku_s = ku.strip()
            if kf.lower() in IGNORE_CLS or ku_s.lower() in ("killed","were","was"):
                continue
            kf_upper = kf.upper()
            if kf_upper in state.factions:
                state.remove_unit_anywhere(kf_upper, ku_s)
        event.matched = True; event.handler_name = "battle_kill"

    # Retreats — "<Unit> retreated to <Region>" (battle survivors leaving
    # the battle region). The source IS the battle region; never use a global
    # relocate because that may grab an instance from a different region the
    # Custodian had moved units to.
    # [2026-05-24] If move_unit (which requires unit at src) finds nothing,
    # fall back to relocate_unit (finds unit anywhere). User feedback: retreats
    # are state changes — they must move the unit somewhere. If neither
    # mechanism finds the unit, we still mark matched but it'll appear as
    # matched-noop; the only legitimate case for that is when the unit was
    # already eliminated and just survived a CG-elimination instead.
    if "retreated to" in plain:
        dst_match = re.search(r"retreated to <span class='(?:region|sea)'>([\w' -]+)</span>", raw_line)
        if dst_match:
            dst = region_key(dst_match.group(1).strip())
            er = state.effect_region or state.battle.region
            before = raw_line.split("retreated")[0]
            IGNORE_CLS = {"kill","pain","miss","region","sea","power","inline-block","str"}
            retreaters = re.findall(r"<span class='(\w+)'>([\w' -]+)</span>", before)
            moved_any = False
            for rf, ru in retreaters:
                if rf.lower() in IGNORE_CLS: continue
                rf_upper = rf.upper()
                ru_s = ru.strip()
                if rf_upper not in state.factions:
                    continue
                if er and er != dst:
                    src_reg = state.get_region(er)
                    if src_reg and src_reg.has_unit(rf_upper, ru_s):
                        state.move_unit(rf_upper, ru_s, er, dst)
                        moved_any = True
                        continue
                # Fallback: find unit anywhere on map and move it to dst.
                if state.relocate_unit(rf_upper, ru_s, dst):
                    moved_any = True
            event.matched = True; event.handler_name = "retreat"

    # Generic "pained to" (Dread Curse, etc.)
    m = re.search(r"was <span class='pain'>pained</span> to <span class='(?:region|sea)'>([\w' -]+)</span>", raw_line)
    if m:
        dst = region_key(m.group(1).strip())
        er = state.effect_region or state.battle.region
        IGNORE_CLS = {"kill","pain","miss","region","sea","power","inline-block","str"}
        spans = re.findall(r"<span class='(\w+)'>([\w' -]+)</span>", raw_line.split("was")[0])
        for sf, su in spans:
            if sf.lower() in IGNORE_CLS: continue
            sf_upper = sf.upper()
            su_s = su.strip()
            if sf_upper in state.factions:
                if er and er != dst:
                    state.move_unit(sf_upper, su_s, er, dst)
                else:
                    found = state.find_unit(sf_upper, su_s)
                    if found and found != dst:
                        state.move_unit(sf_upper, su_s, found, dst)
        event.matched = True; event.handler_name = "pained_to"

    # Sacrifice (non-prefixed): "Unit in Region was sacrificed"
    if "was sacrificed" in plain and not short:
        sac = re.search(r"<span class='(\w+)'>([\w' -]+)</span> in <span class='(?:region|sea)'>([\w' -]+)</span> was sacrificed", raw_line)
        if sac:
            sfc = sac.group(1).upper(); sunit = sac.group(2).strip(); sreg = region_key(sac.group(3).strip())
            r = state.get_region(sreg)
            if r and sfc in state.factions:
                r.remove_unit(sfc, sunit)
                state.factions[sfc].pool[sunit] = state.factions[sfc].pool.get(sunit, 0) + 1
            event.matched = True; event.handler_name = "sacrificed_nopfx"

    # Generic eliminations
    if ("was eliminated" in plain or "were eliminated" in plain or "and eliminated" in plain) and "Writhe" not in plain and "Cyclopean Gaze" not in plain:
        reg_match = re.search(r"in <span class='(?:region|sea)'>([\w' -]+)</span>", raw_line)
        if reg_match:
            state.effect_region = region_key(reg_match.group(1).strip())
        IGNORE_CLS = {"kill","pain","miss","region","sea","power","inline-block","str"}
        spans = re.findall(r"<span class='(\w+)'>([\w' -]+)</span>", raw_line)
        for sf, su in spans:
            su_s = su.strip()
            if sf.lower() in IGNORE_CLS or su_s.lower() in ("eliminated","was","were","with","and"):
                continue
            sf_upper = sf.upper()
            if sf_upper in state.factions:
                state.remove_unit_anywhere(sf_upper, su_s)
        event.matched = True; event.handler_name = "eliminated"

    # Devour
    if "was devoured" in plain:
        IGNORE_CLS = {"kill","pain","miss","region","sea","power","inline-block","str"}
        spans = re.findall(r"<span class='(\w+)'>([\w' -]+)</span>", raw_line.split("was devoured")[0])
        for sf, su in spans:
            if sf.lower() in IGNORE_CLS: continue
            sf_upper = sf.upper()
            if sf_upper in state.factions:
                state.remove_unit_anywhere(sf_upper, su.strip())
        event.matched = True; event.handler_name = "devoured"

    # Submerge
    m = re.search(r"submerged in (.+?)(?:\s+with (.+))?$", plain)
    if m and short:
        reg = region_key(m.group(1).strip())
        companions = m.group(2)
        if companions:
            for uname in companions.split(","):
                uname = uname.strip()
                if uname:
                    r = state.get_region(reg)
                    if r: r.remove_unit(short, uname)
        event.matched = True; event.handler_name = "submerge"

    # Unsubmerge
    m = re.search(r"unsubmerged in (.+?)(?:\s+with (.+))?$", plain)
    if m and short:
        reg = region_key(m.group(1).strip())
        companions = m.group(2)
        if companions:
            for uname in companions.split(","):
                uname = uname.strip()
                if uname:
                    state.place_unit(short, uname, reg)
        event.matched = True; event.handler_name = "unsubmerge"

    # Howl
    if "was howled to" in plain:
        m2 = re.search(r"was howled to (.+?)$", plain)
        if m2:
            dst = region_key(m2.group(1).strip())
            er = state.effect_region or state.battle.region
            IGNORE_CLS = {"kill","pain","miss","region","sea","power","inline-block","str"}
            spans = re.findall(r"<span class='(\w+)'>([\w' -]+)</span>", raw_line)
            for sf, su in spans:
                if sf.lower() in IGNORE_CLS or "howled" in su.lower(): continue
                sf_upper = sf.upper()
                if sf_upper in state.factions and er and er != dst:
                    state.move_unit(sf_upper, su.strip(), er, dst)
            event.matched = True; event.handler_name = "howled"

    # Play order
    if plain.startswith("Play order "):
        event.matched = True; event.handler_name = "play_order"

    # POWER GATHER — start of next AP. Audit: if any faction ended the prior AP
    # with non-zero power AND non-zero IP discount remaining, log a discrepancy
    # for diagnostic (per user spec: end-of-AP FB power should be 0).
    if "POWER GATHER" in plain:
        for fc, ffs in state.factions.items():
            ip_left = ffs.custom.get("infernal_pact_discount", 0)
            if fc == "FB" and ffs.power != 0:
                # Emit diagnostic; user can inspect via debug log
                if not hasattr(state, "_power_audit"):
                    state._power_audit = []
                state._power_audit.append((fc, ffs.power, ip_left, plain))
            # Reset IP discount at AP boundary (engine does this implicitly when
            # discount is consumed; if it wasn't fully consumed, the engine carries
            # it to next AP).
        event.matched = True; event.handler_name = "power_gather"

    # DOOM PHASE
    if "DOOM PHASE" in plain:
        event.matched = True; event.handler_name = "doom_phase"

    # Ritual track display
    if "Ritual of Annihilation track" in plain:
        event.matched = True; event.handler_name = "ritual_track"

    # Winner
    if re.match(r"^.+ won$", plain):
        event.matched = True; event.handler_name = "winner"

    # ── ADDITIONAL HANDLERS ──

    # TS Death March: "Death March: placed Tomb-Herd in Region (Death's Head now N)"
    if short and "Death March:" in rest:
        m2 = re.search(r"placed ([\w' -]+) in (.+?)(?:\s*\(|$)", rest)
        if m2:
            unit = m2.group(1).strip(); reg = region_key(m2.group(2).strip())
            state.place_unit(short, unit, reg)
        m2 = re.search(r"Death's Head (?:is )?now (\d+)", rest)
        if m2:
            state.deaths_head = int(m2.group(1))
            ts_fs = state.factions.get("TS")
            if ts_fs: ts_fs.custom["deaths_head"] = state.deaths_head
        event.matched = True; event.handler_name = "death_march"

    # TS Undulate: "Undulate: carried Unit for free from Src to Dst"
    if short:
        m2 = re.match(r"^Undulate: carried ([\w'-]+(?:\s[\w'-]+)*?) (?:for free )?from (.+?) to (.+?)$", rest)
        if m2:
            unit = m2.group(1).strip()
            src = region_key(m2.group(2).strip()); dst = region_key(m2.group(3).strip())
            state.move_unit(short, unit, src, dst)
            event.matched = True; event.handler_name = "undulate"

    # TS Shepherd of the Crypt: "Shepherd of the Crypt: gained N Power"
    if short:
        m2 = re.match(r"^Shepherd of the Crypt: gained (\d+) Power", rest)
        if m2:
            fs2 = state.factions.get(short)
            if fs2: fs2.power += int(m2.group(1))
            event.matched = True; event.handler_name = "shepherd"

    # "changed control of the gate": unit name or faction name takes control
    # "Dark Young" is a unit (BG), not a faction — gate stays with the acting faction
    if short:
        m2 = re.match(r"^changed control of the gate in (.+?) to (.+)$", rest)
        if m2:
            reg = region_key(m2.group(1).strip())
            new_owner_name = m2.group(2).strip()
            new_owner = FACTION_NAMES.get(new_owner_name)
            if not new_owner:
                new_owner = short
            r = state.get_region(reg)
            if r:
                old = r.gate.owner
                if old and old != new_owner and old in state.factions:
                    state.factions[old].gates.discard(reg)
                r.gate = GateInfo(exists=True, owner=new_owner)
                if new_owner in state.factions:
                    state.factions[new_owner].gates.add(reg)
            event.matched = True; event.handler_name = "changed_gate_control"

    # Display-only events (separators, announcements)
    if plain.startswith("=====") or plain == "ACTIONS" or plain == "DOOM PHASE":
        event.matched = True; event.handler_name = "display_separator"

    # "used Writhe rolling N dice" — costs 2 power. Also resets the writhe
    # undo stack so undos within this writhe only touch this writhe's actions.
    if short and "used Writhe rolling" in rest:
        if short in state.factions:
            state.factions[short].power = max(0, state.factions[short].power - 2)
        state.writhe_action_stack = []
        event.matched = True; event.handler_name = "writhe_start"

    # "rolled N Kill N Pain N Misses" — writhe/battle roll
    if short and re.match(r"^rolled \d+", rest):
        event.matched = True; event.handler_name = "roll_result"

    # "rerolled ALL dice" — writhe reroll
    if short and "rerolled" in rest:
        event.matched = True; event.handler_name = "rerolled"

    # Battle initiation: "attacked with Unit, Unit [N]"
    if short and "attacked with" in rest:
        event.matched = True; event.handler_name = "attacked_with"

    # Battle defense: "defended with Unit, Unit [N]"
    if short and "defended with" in rest:
        event.matched = True; event.handler_name = "defended_with"

    # "was pained" / "were pained" — battle pain announcement (no movement, just marking)
    if ("was pained" in plain or "were pained" in plain) and "pained to" not in plain and "Cyclopean Gaze" not in plain:
        event.matched = True; event.handler_name = "battle_pain_announce"

    # "strength increased" — battle modifier
    if "strength increased" in plain:
        event.matched = True; event.handler_name = "strength_increased"

    # "flew from" — Hunting Horror / Byakhee joining battle.
    # v5 (2026-05-13): actually move the flying unit from src into the battle
    # region so visuals reflect the join. Pattern: "<Unit> flew from <Region>"
    # — no destination in the text; destination is the current battle region.
    if "flew from" in plain:
        m_fly = re.search(r"<span class='(\w+)'>([\w' -]+)</span>\s+flew from\s+<span class='(?:region|sea)'>([\w' -]+)</span>", raw_line)
        if m_fly:
            fc = m_fly.group(1).upper()
            unit = m_fly.group(2).strip()
            src = region_key(m_fly.group(3).strip())
            dst = state.battle.region or state.effect_region
            if fc in state.factions and dst and dst != src:
                state.move_unit(fc, unit, src, dst)
        event.matched = True; event.handler_name = "flew_from"

    # "came from" — necrophagy. Like flew_from: source region is in the line,
    # destination is the current battle region (the log line doesn't list it).
    if "came from" in plain:
        m_nec = re.search(r"<span class='(\w+)'>([\w' -]+)</span>\s+came from\s+<span class='(?:region|sea)'>([\w' -]+)</span>", raw_line)
        if m_nec:
            fc = m_nec.group(1).upper()
            unit = m_nec.group(2).strip()
            src = region_key(m_nec.group(3).strip())
            dst = state.battle.region or state.effect_region
            if fc in state.factions and dst and dst != src:
                state.move_unit(fc, unit, src, dst)
        event.matched = True; event.handler_name = "necrophagy"

    # Avatar — track where Shub went so the swap unit comes from there
    if short and "avatared to" in rest:
        m2 = re.search(r"avatared to (.+?)$", rest)
        if m2:
            dst = region_key(m2.group(1).strip())
            found = state.find_unit(short, "Shub-Niggurath")
            if found:
                state._avatar_src = found
                state._avatar_dst = dst
                state.move_unit(short, "Shub-Niggurath", found, dst)
        event.matched = True; event.handler_name = "avatar"

    # "was sent back to" — avatar swap: unit comes FROM where Shub avatared TO,
    # goes back to where Shub came FROM
    if "was sent back to" in plain:
        m2 = re.search(r"was sent back to (.+?)$", plain)
        if m2:
            dst = region_key(m2.group(1).strip())
            avatar_dst = getattr(state, '_avatar_dst', None)
            spans = re.findall(r"<span class='(\w+)'>([\w' -]+)</span>", raw_line)
            if spans:
                sf, su = spans[0]
                sf_upper = sf.upper()
                if sf_upper in state.factions:
                    src = avatar_dst if avatar_dst else state.find_unit(sf_upper, su.strip())
                    if src and src != dst:
                        state.move_unit(sf_upper, su.strip(), src, dst)
        event.matched = True; event.handler_name = "sent_back"

    # Screaming Dead — KiY screams, followers follow to same destination.
    # "King in Yellow" is a unit name, not a faction name, so short won't match.
    # Parse from plain text instead.
    if "screamed from" in plain:
        m2 = re.search(r"screamed from (.+?) to (.+?)$", plain)
        if m2:
            src = region_key(m2.group(1).strip()); dst = region_key(m2.group(2).strip())
            # Use relocate so the move works whether or not KiY is currently
            # tracked in src (e.g., bouncing between regions across screams).
            state.relocate_unit("YS", "King in Yellow", dst)
            state.effect_region = dst
            state._scream_src = src
        event.matched = True; event.handler_name = "screaming_dead"

    # "followed along" — YS units following KiY to the scream destination.
    # Source isn't logged; we use the recorded scream src or just relocate
    # whichever instance of the named unit is on the map.
    if "followed along" in plain:
        spans = re.findall(r"<span class='(\w+)'>([\w' -]+)</span>", raw_line)
        dst = getattr(state, 'effect_region', None)
        if spans and dst:
            sf, su = spans[0]
            sf_upper = sf.upper()
            if sf_upper in state.factions:
                state.relocate_unit(sf_upper, su.strip(), dst)
        event.matched = True; event.handler_name = "followed_along"

    # Festival — AN power gain
    if short and "got" in rest and "from Festival" in rest:
        m2 = re.search(r"got (\d+) Power from Festival", rest)
        if m2:
            fs3 = state.factions.get(short)
            if fs3: fs3.power += int(m2.group(1))
        event.matched = True; event.handler_name = "festival"

    # Elder Sign from Devil's Mark
    if short and "gained an Elder Sign from" in rest:
        fs4 = state.factions.get(short)
        if fs4: fs4.elder_signs_hidden += 1
        event.matched = True; event.handler_name = "es_from_ability"

    # BG sacrifice for Elder Sign: "sacrificed Unit in Region for an Elder Sign"
    if short and "sacrificed" in rest and "Elder Sign" in rest:
        fs_sac = state.factions.get(short)
        if fs_sac: fs_sac.elder_signs_hidden += 1
        event.matched = True; event.handler_name = "sacrifice_es"

    # Generic Elder Sign gain: "gained N Elder Signs" or "an Elder Sign"
    if not event.matched and short and "Elder Sign" in rest and "gained" in rest:
        es_n = re.search(r"gained (\d+) Elder Signs?", rest)
        if es_n:
            fs_es = state.factions.get(short)
            if fs_es: fs_es.elder_signs_hidden += int(es_n.group(1))
        elif "an Elder Sign" in rest:
            fs_es = state.factions.get(short)
            if fs_es: fs_es.elder_signs_hidden += 1
        event.matched = True; event.handler_name = "es_generic"

    # Power from Devil's Mark craters
    if short and re.search(r"gained \d+ Power from Devil's Mark", rest):
        m2 = re.search(r"gained (\d+) Power from Devil's Mark", rest)
        if m2:
            fs5 = state.factions.get(short)
            if fs5: fs5.power += int(m2.group(1))
        event.matched = True; event.handler_name = "dm_power"

    # Chose first player
    if short and "chose" in rest and "first player" in rest:
        event.matched = True; event.handler_name = "chose_first_player"

    if short and "became the first player" in rest:
        state.first_player = short
        event.matched = True; event.handler_name = "became_first_player"

    # Anytime spellbook
    if short and "achieved Anytime Spellbook" in rest:
        event.matched = True; event.handler_name = "anytime_sb"

    # Shriveled
    if "was shriveled" in plain:
        spans = re.findall(r"<span class='(\w+)'>([\w' -]+)</span>", raw_line.split("was shriveled")[0])
        for sf, su in spans:
            if sf.upper() in state.factions:
                state.remove_unit_anywhere(sf.upper(), su.strip())
        event.matched = True; event.handler_name = "shriveled"

    # Absorbed
    if "absorbed" in plain and "strength" in plain:
        abs_m = re.search(r"absorbed <span class='(\w+)'>([\w' -]+)</span>", raw_line)
        if abs_m:
            af = abs_m.group(1).upper(); au = abs_m.group(2).strip()
            if af in state.factions:
                state.remove_unit_anywhere(af, au)
        event.matched = True; event.handler_name = "absorbed"

    # Dematerialization
    if short:
        m2 = re.match(r"^sent ([\w' -]+) from (.+?) to (.+?) with Dematerialization$", rest)
        if m2:
            su = m2.group(1).strip()
            src = region_key(m2.group(2).strip()); dst = region_key(m2.group(3).strip())
            state.move_unit(short, su, src, dst)
            event.matched = True; event.handler_name = "dematerialization"

    # Byakhee flight — "<Unit> flew to <Dst> from <Src>". Source/dest both
    # logged, but the unit may not be exactly at `src` in state if a prior
    # handler missed an update. Try owner-respecting strict match first, then
    # fall back to relocate (move from wherever the unit is).
    if "flew to" in plain and "from" in plain:
        m2 = re.search(r"([\w' -]+) flew to (.+?) from (.+?)$", plain)
        if m2:
            unit = m2.group(1).strip()
            dst = region_key(m2.group(2).strip()); src = region_key(m2.group(3).strip())
            moved = False
            for fc_code in state.factions:
                found = state.find_unit(fc_code, unit)
                if found == src:
                    state.move_unit(fc_code, unit, src, dst)
                    moved = True
                    break
            if not moved:
                # Fallback: relocate whichever faction owns the unit (Byakhee is YS)
                for fc_code in state.factions:
                    if state.find_unit(fc_code, unit):
                        state.relocate_unit(fc_code, unit, dst)
                        break
        event.matched = True; event.handler_name = "byakhee_flight"

    # CG elimination (no retreat)
    if "had nowhere to retreat and was eliminated" in plain and "Cyclopean Gaze" in plain:
        cg_e = re.search(r"<span class='(\w+)'>([\w' -]+)</span> in <span class='(?:region|sea)'>([\w' -]+)</span>", raw_line)
        if cg_e:
            ef = cg_e.group(1).upper(); eu = cg_e.group(2).strip(); er = region_key(cg_e.group(3).strip())
            if ef in state.factions:
                r2 = state.get_region(er)
                if r2: r2.remove_unit(ef, eu)
        event.matched = True; event.handler_name = "cg_eliminated"

    # Ice Age — costs 1 power for WW, shows on map
    if "started Ice Age" in plain:
        if short and short in state.factions:
            state.factions[short].power = max(0, state.factions[short].power - 1)
            m_ice = re.search(r"started Ice Age in (.+)$", plain)
            if m_ice:
                reg = region_key(m_ice.group(1).strip())
                # Remove old Ice Age from previous region
                for old_reg in list(state.ice_ages):
                    old_r = state.get_region(old_reg)
                    if old_r:
                        old_r.remove_unit(short, "Ice Age")
                state.ice_ages.clear()
                state.ice_ages.append(reg)
                state.place_unit(short, "Ice Age", reg)
        event.matched = True; event.handler_name = "ice_age"
    elif "Ice Age in" in plain and "started" not in plain:
        event.matched = True; event.handler_name = "ice_age"

    if "lost 1 Power due to Ice Age" in plain:
        if short:
            fs6 = state.factions.get(short)
            if fs6: fs6.power = max(0, fs6.power - 1)
        event.matched = True; event.handler_name = "ice_age_power"

    # Generic "Faction X: something" catch-all for spellbook-specific text
    if short and not event.matched:
        # Infernal Pact discount: USER MODEL — the +1 power was already added at
        # IP flip time (see "ip_flip" handler). This line is just the engine's
        # notification that the discount was consumed. No state change here.
        if "Infernal Pact" in rest and "discounted" in rest:
            event.matched = True; event.handler_name = "ip_discount"
        # Demand Sacrifice — "X got an Elder Sign from Demand Sacrifice"
        if "Demand Sacrifice" in rest:
            if "got an Elder Sign" in rest:
                fs.elder_signs_hidden += 1
            event.matched = True; event.handler_name = "demand_sacrifice"

    # CC Thousand Forms: "[Faction] lost N Power" (from negotiation)
    if short and not event.matched:
        m_lost = re.match(r"^lost (\d+) Power", rest)
        if m_lost:
            fs.power = max(0, fs.power - int(m_lost.group(1)))
            event.matched = True; event.handler_name = "lost_power"

    # OW Dragon Ascending: "used Dragon Ascending and rose to N Power"
    if short and not event.matched and "Dragon Ascending" in rest:
        m_da = re.search(r"rose to (\d+) Power", rest)
        if m_da:
            fs.power = int(m_da.group(1))
        event.matched = True; event.handler_name = "dragon_ascending"

    # CC Thousand Forms: "used The Thousand Forms and rolled [N]" — CC gains power
    if short and not event.matched and "Thousand Forms" in rest and "rolled" in rest:
        m_tf = re.search(r"rolled.*?(\d+)", rest)
        if m_tf:
            fs.power += int(m_tf.group(1))
        event.matched = True; event.handler_name = "thousand_forms"

    # Generic "gained N Power" (covers BG SBR, misc)
    if short and not event.matched:
        m_gain = re.match(r"^gained (\d+) Power", rest)
        if m_gain:
            fs.power += int(m_gain.group(1))
            event.matched = True; event.handler_name = "gained_power"

    # ── CATCH-ALL PATTERNS ──

    # Turn markers
    if not event.matched and re.match(r"^Turn \d+$", plain):
        state.round_num = int(re.match(r"Turn (\d+)", plain).group(1))
        event.matched = True; event.handler_name = "turn_marker"

    # Any faction roll line (battle/writhe for non-FB)
    if not event.matched and short and re.match(r"^rolled ", rest):
        event.matched = True; event.handler_name = "roll_result"

    # Infernal Pact flip — user spec: each IP flip line containing "discount now"
    # gives +1 power (representing the future-action discount). The downstream
    # "Infernal Pact discounted N Power" handler does NOT also add power
    # (that would double-count). See REPLAY_ENGINE.md for the IP power model.
    if not event.matched and short and "Infernal Pact: flipped" in rest:
        m2 = re.search(r"flipped ([\w' -]+) facedown", rest)
        if m2:
            fs7 = state.factions.get(short)
            if fs7:
                fs7.flip_spellbook(m2.group(1).strip(), False)
                ip = fs7.custom.get("infernal_pact_discount", 0)
                fs7.custom["infernal_pact_discount"] = ip + 1
                # +1 power per "discount now" line — covers the IP savings up-front
                if "discount now" in rest:
                    fs7.power += 1
        event.matched = True; event.handler_name = "ip_flip"

    # CoF with "and took control" — places acolyte AND takes gate
    if not event.matched and short and "Call of the Faithful: placed Acolyte and took control" in rest:
        m2 = re.search(r"in (.+)$", rest)
        if m2:
            reg = region_key(m2.group(1).strip())
            state.place_unit(short, "Acolyte", reg)
            r = state.get_region(reg)
            if r:
                r.gate = GateInfo(exists=True, owner=short)
                state.gate_locations.add(reg)
                fs.gates.add(reg)
        event.matched = True; event.handler_name = "cof_took_control"

    # Green Decay (TS): "Green Decay: N captured cultist(s) -> N Elder Sign(s) (not power)"
    # Handles "1 captured cultist → an Elder Sign" (singular) too.
    if not event.matched and short and "Green Decay:" in rest:
        m2 = re.search(r"(\d+)\s*captured\s*cultist", rest)
        n_es = int(m2.group(1)) if m2 else 0
        if n_es == 0:
            # Fallback: try matching the ES side directly
            m3 = re.search(r"(\d+)\s*(?:Elder Sign|ES)", rest)
            if m3:
                n_es = int(m3.group(1))
            elif "an Elder Sign" in rest:
                n_es = 1
        if n_es > 0:
            fs8 = state.factions.get(short)
            if fs8:
                fs8.elder_signs_hidden += n_es
                fs8.captured = []
        event.matched = True; event.handler_name = "green_decay"

    # "allowed enemy factions to summon" (AN)
    if not event.matched and "allowed enemy factions" in plain:
        event.matched = True; event.handler_name = "allowed_summon"

    # Dread Curse roll (OW)
    if not event.matched and short and "rolled" in rest and ("Dread Curse" in plain or state.effect_region):
        event.matched = True; event.handler_name = "dread_curse_roll"

    # KiY screamed (1 power) or desecrated (1 power) — no faction prefix
    if not event.matched:
        m2 = re.match(r"^King in Yellow (?:screamed from (.+?) to (.+)|desecrated (.+))$", plain)
        if m2:
            # Find YS faction to deduct power
            ys_fc = None
            for fc in state.factions:
                if state.factions[fc].name == "Yellow Sign":
                    ys_fc = fc; break
            if m2.group(1) and m2.group(2):
                src = region_key(m2.group(1).strip()); dst = region_key(m2.group(2).strip())
                for fc in state.factions:
                    if state.find_unit(fc, "King in Yellow") == src:
                        state.move_unit(fc, "King in Yellow", src, dst)
                        break
                if ys_fc: state.factions[ys_fc].power = max(0, state.factions[ys_fc].power - 1)
            elif m2.group(3):
                reg = region_key(m2.group(3).strip())
                state.desecrated.append(reg)
                if ys_fc: state.factions[ys_fc].power = max(0, state.factions[ys_fc].power - 1)
            event.matched = True; event.handler_name = "kiy_scream"

    # Cthulhu submerged (no faction prefix — "Cthulhu submerged in Region [with ...]")
    if not event.matched:
        m2 = re.match(r"^Cthulhu submerged in (.+?)(?:\s+with (.+))?$", plain)
        if m2:
            reg = region_key(m2.group(1).strip())
            for fc in state.factions:
                if state.find_unit(fc, "Cthulhu") == reg:
                    state.regions[reg].remove_unit(fc, "Cthulhu")
                    comp_list = ["Cthulhu"]
                    companions = m2.group(2)
                    if companions:
                        for uname in companions.split(","):
                            uname = uname.strip()
                            if uname:
                                state.regions[reg].remove_unit(fc, uname)
                                comp_list.append(uname)
                    fs_gc = state.factions.get(fc)
                    if fs_gc:
                        fs_gc.custom["submerged_region"] = reg
                        fs_gc.custom["submerged_companions"] = comp_list
                        fs_gc.power = max(0, fs_gc.power - 1)
                    break
            event.matched = True; event.handler_name = "cthulhu_submerge"

    # Cthulhu unsubmerged
    if not event.matched:
        m2 = re.match(r"^Cthulhu unsubmerged in (.+?)(?:\s+with (.+))?$", plain)
        if m2:
            reg = region_key(m2.group(1).strip())
            for fc in state.factions:
                r_data = FACTION_ROSTER.get(fc, {})
                if any(u.name == "Cthulhu" for u in r_data.get("units", [])):
                    state.place_unit(fc, "Cthulhu", reg)
                    companions = m2.group(2)
                    if companions:
                        for uname in companions.split(","):
                            uname = uname.strip()
                            if uname: state.place_unit(fc, uname, reg)
                    fs_gc2 = state.factions.get(fc)
                    if fs_gc2:
                        fs_gc2.custom["submerged_region"] = None
                        fs_gc2.custom["submerged_companions"] = []
                    break
            event.matched = True; event.handler_name = "cthulhu_unsubmerge"

    # Negotiation events (display-only)
    if not event.matched and ("Negotiations" in plain or "Other factions were to lose" in plain or "Not enough power" in plain):
        event.matched = True; event.handler_name = "negotiation_display"

    # "Unit was placed in Region" (no faction prefix — neutral/special)
    if not event.matched:
        m2 = re.match(r"^([\w' -]+) was placed in (.+)$", plain)
        if m2:
            unit = m2.group(1).strip(); reg = region_key(m2.group(2).strip())
            # Try to identify faction from HTML span
            span = re.search(r"<span class='(\w+)'>", raw_line)
            if span:
                pfc = span.group(1).upper()
                if pfc in state.factions:
                    state.place_unit(pfc, unit, reg)
            event.matched = True; event.handler_name = "unit_placed"

    # "Unit was removed from the game permanently" (AN Yothan extinction, etc.)
    if not event.matched and "removed from the game" in plain:
        m2 = re.search(r"([\w' -]+) was removed from the game", plain)
        if m2:
            unit = m2.group(1).strip()
            span = re.search(r"<span class='(\w+)'>", raw_line)
            if span:
                pfc = span.group(1).upper()
                if pfc in state.factions:
                    state.remove_unit_anywhere(pfc, unit)
        event.matched = True; event.handler_name = "removed_permanently"

    # Shub-Niggurath avatared (no faction prefix)
    if not event.matched:
        m2 = re.match(r"^Shub-Niggurath avatared to (.+)$", plain)
        if m2:
            dst = region_key(m2.group(1).strip())
            for fc in state.factions:
                found = state.find_unit(fc, "Shub-Niggurath")
                if found:
                    state.move_unit(fc, "Shub-Niggurath", found, dst)
                    break
            event.matched = True; event.handler_name = "shub_avatar"

    # "Unit was abducted by Nightgaunt" — unit removed
    if not event.matched and "was abducted by" in plain:
        m2 = re.match(r"^([\w' -]+) was abducted by", plain)
        if m2:
            unit = m2.group(1).strip()
            span = re.search(r"<span class='(\w+)'>", raw_line)
            if span:
                pfc = span.group(1).upper()
                if pfc in state.factions:
                    state.remove_unit_anywhere(pfc, unit)
        event.matched = True; event.handler_name = "abducted"

    # "Unit appeared in Region" — screaming dead followers, devolve results
    if not event.matched:
        m2 = re.match(r"^([\w' -]+) appeared in (.+)$", plain)
        if m2:
            unit = m2.group(1).strip(); reg = region_key(m2.group(2).strip())
            span = re.search(r"<span class='(\w+)'>", raw_line)
            if span:
                pfc = span.group(1).upper()
                if pfc in state.factions:
                    state.place_unit(pfc, unit, reg)
            event.matched = True; event.handler_name = "unit_appeared"

    # "devolved into" — GC Acolyte → Deep One
    if not event.matched and "devolved into" in plain:
        m2 = re.search(r"([\w' -]+) in (.+?) devolved into ([\w' -]+)", plain)
        if m2:
            old = m2.group(1).strip(); reg = region_key(m2.group(2).strip()); new = m2.group(3).strip()
            span = re.search(r"<span class='(\w+)'>", raw_line)
            if span:
                pfc = span.group(1).upper()
                if pfc in state.factions:
                    r2 = state.get_region(reg)
                    if r2:
                        r2.remove_unit(pfc, old)
                        r2.add_unit(pfc, new)
            event.matched = True; event.handler_name = "devolved"

    # "survived the kill as an Emissary" — CC Nyarlathotep survives
    if not event.matched and "survived" in plain and "Emissary" in plain:
        event.matched = True; event.handler_name = "emissary_survived"

    # "hid itself" / "was hidden by" — CC stealth
    if not event.matched and ("hid itself" in plain or "was hidden by" in plain):
        event.matched = True; event.handler_name = "hidden"

    # "failed desecration" — still costs 1 power for YS
    if not event.matched and "failed" in plain and "desecration" in plain:
        for fc in state.factions:
            if state.factions[fc].name == "Yellow Sign":
                state.factions[fc].power = max(0, state.factions[fc].power - 1)
                break
        event.matched = True; event.handler_name = "failed_desecration"

    # "Hastur heard his name" — YS display
    if not event.matched and "Hastur heard his name" in plain:
        event.matched = True; event.handler_name = "hastur_heard"

    # "Cathedral removed with UnholyGround" — AN building destroyed
    if not event.matched and "Cathedral" in plain and "was removed" in plain:
        m2 = re.search(r"Cathedral in (.+?) was removed", plain)
        if m2:
            reg = region_key(m2.group(1).strip())
            for fc in state.factions:
                r2 = state.get_region(reg)
                if r2 and r2.has_unit(fc, "Cathedral"):
                    r2.remove_unit(fc, "Cathedral")
                    break
            if reg in state.cathedrals: state.cathedrals.remove(reg)
        event.matched = True; event.handler_name = "cathedral_removed"

    # "followed with Arctic Wind" — WW movement
    if not event.matched and "followed with Arctic Wind" in plain:
        m2 = re.match(r"^([\w' -]+) followed with Arctic Wind", plain)
        if m2:
            unit = m2.group(1).strip()
            # Unit follows Ithaqua — find where Ithaqua just moved to
            for fc in state.factions:
                ithaqua_reg = state.find_unit(fc, "Ithaqua")
                unit_reg = state.find_unit(fc, unit)
                if ithaqua_reg and unit_reg and ithaqua_reg != unit_reg:
                    state.move_unit(fc, unit, unit_reg, ithaqua_reg)
                    break
        event.matched = True; event.handler_name = "arctic_wind"

    # ── CURSED TOMES ──
    if not event.matched and short and "used" in rest and "Cursed Tome" in rest:
        fs_t = state.factions.get(short)
        if fs_t: fs_t.flipped_tomes += 1
        event.matched = True; event.handler_name = "tome_used"

    if not event.matched and short and "received" in rest and "Cursed Tome" in rest:
        # v5 (2026-05-13): track recipient's cursed-tome count on faction card.
        fs_t = state.factions.get(short)
        if fs_t:
            tomes = fs_t.custom.get("cursed_tomes", [])
            tomes.append({"face_down": True})  # received tomes start face-down
            fs_t.custom["cursed_tomes"] = tomes
        event.matched = True; event.handler_name = "tome_received"

    # TS gives Cursed Tome to another faction.
    # v5: track the recipient (last span is recipient faction).
    if not event.matched and short and "gave" in rest and "Cursed Tome" in rest:
        spans = re.findall(r"<span class='(\w+)[^']*'>([\w' -]+)</span>", raw_line)
        # Last faction-style span (inline-block) is recipient
        recipient_fc = None
        for fc, _name in reversed(spans):
            fc_up = fc.upper()
            if fc_up in state.factions and fc_up != short:
                recipient_fc = fc_up
                break
        if recipient_fc:
            rfs = state.factions.get(recipient_fc)
            if rfs:
                tomes = rfs.custom.get("cursed_tomes", [])
                tomes.append({"face_down": True})
                rfs.custom["cursed_tomes"] = tomes
        event.matched = True; event.handler_name = "tome_given"

    if not event.matched and short and "lost" in rest and "face-down" in rest and "Cursed Tome" in rest:
        m2 = re.search(r"lost (\d+) Doom", rest)
        if m2:
            fs_t = state.factions.get(short)
            if fs_t: fs_t.doom = max(0, fs_t.doom - int(m2.group(1)))
        event.matched = True; event.handler_name = "tome_penalty"

    if not event.matched and short and "removed face-down" in rest and "Cursed Tome" in rest:
        fs_t = state.factions.get(short)
        if fs_t: fs_t.flipped_tomes = max(0, fs_t.flipped_tomes - 1)
        event.matched = True; event.handler_name = "tome_removed"

    # ── NEUTRAL UNITS: Loyalty Card obtained (doom cost) ──
    if not event.matched and short and "obtained the" in rest and "Loyalty Card" in rest:
        m2 = re.search(r"for (\d+) Doom", rest)
        if m2:
            cost = int(m2.group(1))
            fs.doom = max(0, fs.doom - cost)
        event.matched = True; event.handler_name = "loyalty_card_obtained"

    # ── NEUTRAL UNITS: generic "placed Unit in Region" (loyalty card summon, iGOO placement) ──
    # v5 (2026-05-13): also matches "placed Unit in Region with <SBName>" (e.g.
    # DS Fiendish Growth). Strip trailing " with ..." before region_key.
    if not event.matched and short and re.match(r"^placed " + U + r" in (.+?)$", rest):
        m2 = re.match(r"^placed " + U + r" in (.+?)(?:\s+with\s+.+)?$", rest)
        if m2:
            unit = m2.group(1).strip()
            reg_text = m2.group(2).strip()
            # Defensive: re-split if "with" survived in reg_text
            if " with " in reg_text:
                reg_text = reg_text.split(" with ")[0].strip()
            reg = region_key(reg_text)
            state.place_unit(short, unit, reg)
        event.matched = True; event.handler_name = "placed_unit"

    # ── LIBRARY AT CELAENO: Tomes, Silence Tokens, Custodian, Librarian ──
    LIBRARY_TOMES = ["Barrier of Naach-Tith", "Guardian under the Lake", "Larvae of the Outer Gods", "Yr and the Nhhngr"]

    if not event.matched and short and "acquired" in rest:
        for tome in LIBRARY_TOMES:
            if tome in rest:
                if not hasattr(state, 'library_tomes'):
                    state.library_tomes = {}
                state.library_tomes[tome] = {"holder": short, "overdue": False, "face_up": True}
                event.matched = True; event.handler_name = "library_tome_acquired"
                break

    if not event.matched and short and "Overdue" in rest:
        for tome in LIBRARY_TOMES:
            if tome in rest:
                # Initialize the tome entry if missing — overdue can be logged
                # before an explicit "acquired" event (first-Doom auto-tracking).
                if tome not in state.library_tomes:
                    state.library_tomes[tome] = {"holder": short, "overdue": False, "face_up": True}
                if "is now" in rest:
                    state.library_tomes[tome]["overdue"] = True
                elif "no longer" in rest:
                    state.library_tomes[tome]["overdue"] = False
                event.matched = True; event.handler_name = "library_tome_overdue"
                break

    if not event.matched and short and "Silence Token" in rest:
        if not hasattr(state, 'silence_tokens'):
            state.silence_tokens = {}
        if "received" in rest:
            state.silence_tokens[short] = state.silence_tokens.get(short, 0) + 1
            event.matched = True; event.handler_name = "silence_token_received"
        elif "discarded" in rest:
            state.silence_tokens[short] = max(0, state.silence_tokens.get(short, 0) - 1)
            event.matched = True; event.handler_name = "silence_token_discarded"
        elif "spent" in rest:
            state.silence_tokens[short] = max(0, state.silence_tokens.get(short, 0) - 1)
            event.matched = True; event.handler_name = "silence_token_spent"

    if not event.matched and "Silence Token" in rest and "was discarded" in rest:
        # Generic discard (barrier payment)
        event.matched = True; event.handler_name = "silence_token_discarded"

    # ── CUSTODIAN: unit moved to region (faction unit, not the Custodian piece) ──
    # Log format (plain): "<Faction> <UnitName> moved to <Region> (Custodian)"
    # Example:            "Firstborn Desiccated moved to Oubliette (Custodian)"
    # Distinct from "<Faction> moved Custodian to <Region>" (handled below as
    # library_unit_move): this is a faction unit being relocated by the Custodian
    # mechanic, typically to Oubliette as part of agony resolution.
    if not event.matched and short and "(Custodian)" in rest and " moved to " in rest:
        m = re.match(r"^([\w' -]+?)\s+moved to\s+(.+?)\s*\(Custodian\)\s*$", rest)
        if m:
            unit_name = m.group(1).strip()
            dst_region = region_key(m.group(2).strip())
            # Per CW rules, the Custodian relocates units from ITS current region.
            # Prefer that as source so we don't accidentally pull an instance from
            # another region (causing downstream battle-defender mismatches).
            custodian_region = state.library_units.get("custodian")
            moved = False
            if custodian_region:
                src_reg = state.regions.get(custodian_region)
                if src_reg and src_reg.has_unit(short, unit_name):
                    state.move_unit(short, unit_name, custodian_region, dst_region)
                    moved = True
            if not moved:
                # Fallback: any source != dst, then pool
                state.relocate_unit(short, unit_name, dst_region)
            event.matched = True; event.handler_name = "custodian_relocate_unit"

    if not event.matched and short and ("Custodian" in rest or "Librarian" in rest):
        if "moved" in rest.lower() or "stays in" in rest.lower():
            # Track custodian/librarian region
            unit_type = "custodian" if "Custodian" in rest else "librarian"
            clean_rest = strip_html(rest)
            # Remove trailing parenthetical like "(+1 to Agony roll)" or "(Custodian)"
            clean_rest = re.sub(r'\s*\([^)]*\)\s*$', '', clean_rest)
            m_move = re.search(r"to (.+?)$", clean_rest)
            m_stay = re.search(r"stays in (.+?)$", clean_rest)
            reg_name = None
            is_stay = False
            if m_move: reg_name = m_move.group(1).strip()
            elif m_stay:
                reg_name = m_stay.group(1).strip()
                is_stay = True
            if reg_name:
                state.library_units[unit_type] = region_key(reg_name)
            event.matched = True
            # Stays-in is a deliberate no-op; tag separately so the audit ignores it
            event.handler_name = "library_unit_stays" if is_stay else "library_unit_move"
        elif "spent" in rest.lower():
            # "spent a Silence Token to activate the Custodian/Librarian" — decrement token
            if not hasattr(state, 'silence_tokens'):
                state.silence_tokens = {}
            state.silence_tokens[short] = max(0, state.silence_tokens.get(short, 0) - 1)
            event.matched = True; event.handler_name = "library_unit_activate"
        elif "activate" in rest.lower():
            event.matched = True; event.handler_name = "library_unit_action"

    if not event.matched and short and "Agony" in rest:
        event.matched = True; event.handler_name = "agony_action"

    if not event.matched and short and "flip" in rest.lower() and "face-up" in rest:
        for tome in LIBRARY_TOMES:
            if tome in rest:
                if hasattr(state, 'library_tomes') and tome in state.library_tomes:
                    state.library_tomes[tome]["face_up"] = True
                event.matched = True; event.handler_name = "library_tome_flipped_up"
                break

    if not event.matched and short and "blocked from controlling" in rest:
        event.matched = True; event.handler_name = "library_gate_blocked"

    if not event.matched and short and "Battle was blocked by" in rest:
        event.matched = True; event.handler_name = "barrier_battle_blocked"

    # Library auto-placed gates at first Doom Phase (no faction owner — neutral
    # gates that mark a tome's special-collection region as having a gate).
    if not event.matched and "Gate placed in" in plain and "first Doom Phase" in plain:
        m_gp = re.search(r"Gate placed in <span class='(?:region|sea)'>([\w' -]+)</span>", raw_line)
        if m_gp:
            rk = region_key(m_gp.group(1).strip())
            reg = state.regions.get(rk)
            if reg:
                reg.gate.exists = True
                reg.gate.owner = ""  # neutral
                state.gate_locations.add(rk)
        event.matched = True; event.handler_name = "library_gate_placed"

    # ── DAEMON SULTAN (DS) ─────────────────────────────────────────────
    # DS-specific log strings emitted by FactionDS.scala. The replay engine
    # tracks azathoth_track, the Azathoth combat die, Chaos Gate placements,
    # and Avatar awakenings so DS state can be reconstructed from logs.

    if not event.matched and short == "DS":
        # Awaken Avatar Thesis sets the azathoth_track value (0..8) used by
        # combat strength for both Thesis and Antithesis.
        m = re.match(r"^awakened Avatar Thesis in (.+?) setting Azathoth track to (-?\d+)$", rest)
        if m:
            reg = region_key(m.group(1).strip()); track = int(m.group(2))
            state.place_unit("DS", "Avatar Thesis", reg)
            fs = state.factions.get("DS")
            if fs is not None:
                fs.custom["azathoth_track"] = track
            event.matched = True; event.handler_name = "ds_awaken_avatar_thesis"

        if not event.matched:
            m = re.match(r"^awakened Avatar Antithesis in (.+?)$", rest)
            if m:
                reg = region_key(m.group(1).strip())
                state.place_unit("DS", "Avatar Antithesis", reg)
                event.matched = True; event.handler_name = "ds_awaken_avatar_antithesis"

        if not event.matched:
            m = re.match(r"^awakened Avatar Synthesis in (.+?)$", rest)
            if m:
                reg = region_key(m.group(1).strip())
                state.place_unit("DS", "Avatar Synthesis", reg)
                event.matched = True; event.handler_name = "ds_awaken_avatar_synthesis"

        # Azathoth combat die rolled. Two log shapes:
        #   "Avatar Synthesis rolled the Azathoth die [N] — combat strength [S]"
        #   "rolled the Azathoth die [N]"
        if not event.matched and "Azathoth die" in rest:
            m = re.search(r"Azathoth die \[(\d+)\]", rest)
            if m:
                roll = int(m.group(1))
                fs = state.factions.get("DS")
                if fs is not None:
                    fs.custom["azathoth_die"] = roll
                event.matched = True; event.handler_name = "ds_azathoth_die_rolled"

        # Azathoth Synthesis bidding — power/doom transfer to Azathoth.
        if not event.matched and "to Azathoth" in rest:
            event.matched = True; event.handler_name = "ds_azathoth_bid"

        if not event.matched and rest in ("refused to negotiate", "offered nothing to Azathoth"):
            event.matched = True; event.handler_name = "ds_azathoth_refuse_or_nothing"

        # Psychosis: places an Acolyte (typically into Oubliette or chaos region).
        if not event.matched:
            m = re.match(r"^used Psychosis placing an Acolyte in (.+?)$", rest)
            if m:
                reg = region_key(m.group(1).strip())
                state.place_unit("DS", "Acolyte", reg)
                event.matched = True; event.handler_name = "ds_psychosis"

        # Chaos Gate placement — DS faction-card / battle effect.
        if not event.matched:
            m = re.match(r"^placed Chaos Gate in (.+?)$", rest)
            if m:
                reg = region_key(m.group(1).strip())
                state.place_unit("DS", "Chaos Gate", reg)
                fs = state.factions.get("DS")
                if fs is not None:
                    if reg not in fs.custom.get("chaos_gates", []):
                        fs.custom.setdefault("chaos_gates", []).append(reg)
                event.matched = True; event.handler_name = "ds_place_chaos_gate"

        # Animate Matter — relocates a Chaos Gate.
        if not event.matched:
            m = re.match(r"^used Animate Matter moving Chaos Gate from (.+?) to (.+?)$", rest)
            if m:
                src = region_key(m.group(1).strip()); dst = region_key(m.group(2).strip())
                fs = state.factions.get("DS")
                if fs is not None:
                    cg = fs.custom.get("chaos_gates", [])
                    if src in cg:
                        cg.remove(src)
                    if dst not in cg:
                        cg.append(dst)
                    fs.custom["chaos_gates"] = cg
                # Also move the Chaos Gate unit between regions
                if src in state.regions and dst in state.regions:
                    state.regions[src].remove_unit("DS", "Chaos Gate", 1)
                    state.regions[dst].add_unit("DS", "Chaos Gate", 1)
                event.matched = True; event.handler_name = "ds_animate_matter"

        # Consummation: unflip a spellbook or a cursed tome.
        if not event.matched and "used Consummation" in rest and "to unflip" in rest:
            event.matched = True; event.handler_name = "ds_consummation"

        # Undirected Energy: power gain from N factions in region.
        # v5 (2026-05-13): apply the power gain. Log format:
        # "DS used Undirected Energy gaining N Power from M factions in Region"
        if not event.matched and "used Undirected Energy" in rest:
            m = re.search(r"gaining (\d+) Power", rest)
            if m:
                ds_fs = state.factions.get("DS")
                if ds_fs is not None:
                    ds_fs.power += int(m.group(1))
            event.matched = True; event.handler_name = "ds_undirected_energy"

        # Fiendish Growth (DS battle effect).
        if not event.matched and "used Fiendish Growth" in rest:
            event.matched = True; event.handler_name = "ds_fiendish_growth"

        # Traitors: converts Chaos Gate into a unit gain for another faction.
        # v5 (2026-05-13): convert chaos gate to normal gate in the affected
        # region (removes from DS chaos_gates list, sets RegionState.gate to
        # a normal gate). The recipient's acolyte placement is on a follow-up
        # "<Faction> gained Acolyte ... from Traitors!" line — see below.
        # Note: log uses "Traitors!" (with bang).
        if not event.matched and ("used Traitors converting Chaos Gate" in rest or
                                  "used Traitors! converting Chaos Gate" in rest):
            m = re.search(r"converting Chaos Gate in <span class='(?:region|sea)'>([\w' -]+)</span>", raw_line)
            if m:
                reg = region_key(m.group(1).strip())
                ds_fs = state.factions.get("DS")
                if ds_fs is not None:
                    cg = ds_fs.custom.get("chaos_gates", [])
                    if reg in cg: cg.remove(reg)
                    ds_fs.custom["chaos_gates"] = cg
                r = state.regions.get(reg)
                if r:
                    # Chaos Gate becomes a regular gate; owner is the recipient
                    # (set on the follow-up "gained Acolyte" line where the
                    # recipient places their Acolyte).
                    r.gate.exists = True
                    if not r.gate.owner:
                        r.gate.owner = ""
                    state.gate_locations.add(reg)
            event.matched = True; event.handler_name = "ds_traitors"

        # Cosmic Ruler — sacrifice another Avatar/iGOO to save a killed Avatar.
        # Format: "used Cosmic Ruler eliminating <sacrificed> to save <saved>".
        # Both args are UnitFigure descriptors (uclass.styled), e.g. "Y'Golonac".
        if not event.matched and "used Cosmic Ruler eliminating" in rest:
            event.matched = True; event.handler_name = "ds_cosmic_ruler_sacrifice"

        # Power/Doom Offer SBR ("offers each faction their choice of 1 Power or 1 Doom").
        if not event.matched and "offers each faction their choice of" in rest:
            event.matched = True; event.handler_name = "ds_power_doom_offer_announce"

        # Chaos Gate becoming a normal gate (Gather Power phase reconciliation).
        if not event.matched and "Chaos Gate in" in rest and "became a normal gate" in rest:
            m = re.match(r"^Chaos Gate in (.+?) became a normal gate$", rest)
            if m:
                reg = region_key(m.group(1).strip())
                fs = state.factions.get("DS")
                if fs is not None:
                    cg = fs.custom.get("chaos_gates", [])
                    if reg in cg:
                        cg.remove(reg)
                    fs.custom["chaos_gates"] = cg
            event.matched = True; event.handler_name = "ds_chaos_gate_normalized"

        # DS setup line.
        if not event.matched and "starts with all Acolytes in the pool" in rest:
            event.matched = True; event.handler_name = "ds_setup"

        # Azathoth Synthesis auction housekeeping lines (not direct state mutations).
        if not event.matched and "Halved to" in rest and "player game" in rest:
            event.matched = True; event.handler_name = "ds_azathoth_target_halved"

        if not event.matched and "Other factions must collectively offer" in rest:
            event.matched = True; event.handler_name = "ds_azathoth_announce"

    # ── TS gaps: Hecatomb / Grasping Dead / Glaaki awakening / Tomes ────
    if not event.matched and short == "TS":
        if "performed Hecatomb ritual" in rest:
            event.matched = True; event.handler_name = "ts_hecatomb_ritual"
        elif "Hecatomb: using" in rest and "Death's Head toward Ritual" in rest:
            # v5 (2026-05-13): decrement Death's Head by the consumed amount.
            m_dh = re.search(r"using\s+(\d+)\s+Death", rest)
            if m_dh:
                consumed = int(m_dh.group(1))
                state.deaths_head = max(0, state.deaths_head - consumed)
                ts_fs = state.factions.get("TS")
                if ts_fs is not None:
                    ts_fs.custom["deaths_head"] = state.deaths_head
            event.matched = True; event.handler_name = "ts_hecatomb_apply"
        elif "Hecatomb: remaining" in rest and "discarded" in rest:
            # v5: leftover Death's Head discarded after Hecatomb ritual — drop to 0
            # (the "remaining N" is the surplus that wasn't applied to the track).
            m_dh = re.search(r"remaining\s+(\d+)\s+Death", rest)
            if m_dh:
                state.deaths_head = max(0, state.deaths_head - int(m_dh.group(1)))
                ts_fs = state.factions.get("TS")
                if ts_fs is not None:
                    ts_fs.custom["deaths_head"] = state.deaths_head
            event.matched = True; event.handler_name = "ts_hecatomb_discard"
        elif "spent 2 Death's Head for Grasping Dead" in rest:
            event.matched = True; event.handler_name = "ts_grasping_dead_activate"
        elif "Grasping Dead: battle with" in rest:
            event.matched = True; event.handler_name = "ts_grasping_dead_battle"
        elif "awakened Gla'aki" in rest or "awakened Glaaki" in rest:
            # Match a region and update Glaaki placement
            m = re.search(r"awakened Gla.aki in (.+?) for", rest)
            if m:
                reg = region_key(m.group(1).strip())
                state.place_unit("TS", "Gla'aki", reg)
            event.matched = True; event.handler_name = "ts_awaken_glaaki"
        elif "Undulate: carried" in rest:
            event.matched = True; event.handler_name = "ts_undulate_carry"

    # ── iGOO ability events (Abhoth Filth spawn, Daoloth gate moves, etc.) ──
    # These are emitted by Faction.styled neutral-prefixed text — they don't have
    # a `short` faction code matching a player faction, but they appear in the
    # log as the iGOO acting. Handle the common ones so they don't fall through
    # as "unhandled_faction_event".

    if not event.matched and "Abhoth placed Filth in" in rest:
        # Abhoth distributes Filth units to factions; handled as a generic
        # placement event downstream. Tag here to satisfy the event log.
        event.matched = True; event.handler_name = "abhoth_placed_filth"

    if not event.matched and re.match(r"^Cthulhu Wars HRF", rest):
        event.matched = True; event.handler_name = "version_banner"

    if not event.matched and "Dimensional Shambler deployed to" in rest:
        # DS / SL faction-card Shambler deploy log — independent of who deployed.
        event.matched = True; event.handler_name = "shambler_deploy"

    # ── [2026-05-24] MNU neutral-unit ability events ─────────────────────
    # The MNU build adds 14 new monsters/terrors + 10 new IGOOs. Each ability
    # logs an "nt"-styled line when it fires. The replay parser needs to
    # recognize these so they don't surface as "issues" in the issue tracker.
    # All handlers are informational; state mutations are handled by other
    # rules. We just mark the event with a unique handler_name.
    if not event.matched:
        if "Frenzy" in rest and "summoned" in rest:
            event.matched = True; event.handler_name = "mnu_frenzy"
        elif "Riding the Shantak" in rest:
            event.matched = True; event.handler_name = "mnu_riding_the_shantak"
        elif "Sapping" in rest and "drained" in rest:
            event.matched = True; event.handler_name = "mnu_sapping"
        elif "Vicious" in rest and "added" in rest and "Kill" in rest:
            event.matched = True; event.handler_name = "mnu_vicious"
        elif "Grottos" in rest:
            event.matched = True; event.handler_name = "mnu_grottos"
        elif "Possession" in rest:
            event.matched = True; event.handler_name = "mnu_possession"
        elif "Velvet Fan" in rest:
            event.matched = True; event.handler_name = "mnu_velvet_fan"
        elif "Mummify" in rest or "no longer mummified" in rest or "auto-mummified" in rest:
            event.matched = True; event.handler_name = "mnu_mummify"
        elif "Execration of Mu" in rest or "ExecrationOfMu" in rest:
            event.matched = True; event.handler_name = "mnu_execration_of_mu"
        elif "Prime Cause" in rest:
            event.matched = True; event.handler_name = "mnu_prime_cause"
        elif "Dust to Dust" in rest:
            event.matched = True; event.handler_name = "mnu_dust_to_dust"
        elif "Planetary Destruction" in rest:
            event.matched = True; event.handler_name = "mnu_planetary_destruction"
        elif "Hebephrenia" in rest:
            event.matched = True; event.handler_name = "mnu_hebephrenia"
        elif "Angles of Time" in rest:
            event.matched = True; event.handler_name = "mnu_angles_of_time"
        elif "Cronophage" in rest:
            event.matched = True; event.handler_name = "mnu_cronophage"
        elif "Familiar" in rest and ("returned to" in rest or "Brown Jenkin" in rest):
            event.matched = True; event.handler_name = "mnu_familiar"
        elif "Loathsome Titter" in rest:
            event.matched = True; event.handler_name = "mnu_loathsome_titter"
        elif "Moonbeast" in rest or "Moonbeasts" in rest:
            event.matched = True; event.handler_name = "mnu_moonbeast"
        elif "Laughingstock" in rest:
            # [2026-05-24] Laughingstock multi-step. Lines like
            # "Laughingstock: moved Giant Blind Albino Penguins to battle area" /
            # "Laughingstock: Penguins transferred to <side> for battle" /
            # "Laughingstock: Penguins returned to <orig>" — actually move the
            # unit. Lines like dice/strength adjustments are announcement-only.
            if "moved" in rest and "to battle area" in rest:
                pen = "Giant Blind Albino Penguins"
                if "Albino Penguins" in rest and pen not in rest:
                    pen = "Albino Penguins"
                if state.battle.region:
                    # Find penguins for any faction (Laughingstock owner is also
                    # the line's `short`; penguins were placed when LC was taken)
                    for fc in state.factions:
                        if state.relocate_unit(fc, pen, state.battle.region):
                            break
            elif "transferred to" in rest and "for battle" in rest:
                # Penguin temporarily fights for opposite side — no map move
                pass
            elif "returned to" in rest:
                # Penguin returned to original owner — no map move, just owner
                # bookkeeping (not tracked separately in state)
                pass
            event.matched = True; event.handler_name = "mnu_laughingstock"
        elif "Mind Parasite" in rest or "mind parasited" in rest or "(Mind Parasite)" in rest:
            event.matched = True; event.handler_name = "mnu_mind_parasite"
        elif "Fecund" in rest:
            event.matched = True; event.handler_name = "mnu_fecund"
        elif "Servitor of the Outer Gods" in rest or "Servitors in pool" in rest:
            event.matched = True; event.handler_name = "mnu_servitor"
        elif "blocked by" in rest and "Elder Thing" in rest:
            event.matched = True; event.handler_name = "mnu_elder_thing_mind_control"
        elif rest.startswith("doom from gate in") and "blocked by" in rest and "Filth" in rest:
            # Abhoth Filth suppression: faction's gate didn't yield doom this turn.
            # Doom math is already correct (the parent "got N Doom" line was
            # decremented at engine time). Just tag so it doesn't surface as unhandled.
            event.matched = True; event.handler_name = "abhoth_filth_blocked_doom"
        elif "Place Spinneret" in rest or "web token" in rest:
            event.matched = True; event.handler_name = "mnu_place_spinneret"
        elif "Bloodthirst" in rest:
            event.matched = True; event.handler_name = "mnu_bloodthirst"
        elif "Cosmic Web" in rest:
            event.matched = True; event.handler_name = "mnu_cosmic_web"
        elif "Tomb Herd" in rest and "their pool" in rest:
            event.matched = True; event.handler_name = "mnu_tomb_herd"
        elif "Green Decay" in rest:
            event.matched = True; event.handler_name = "mnu_green_decay"
        elif "Disaster Looms" in rest:
            event.matched = True; event.handler_name = "mnu_disaster_looms"
        elif "Innsmouth Look" in rest or "TheInnsmouthLook" in rest:
            event.matched = True; event.handler_name = "mnu_innsmouth_look"
        elif "Zygote" in rest or "TheZygote" in rest:
            event.matched = True; event.handler_name = "mnu_zygote"
        elif "Tsunami" in rest:
            event.matched = True; event.handler_name = "mnu_tsunami"
        elif "Agony Sting" in rest:
            event.matched = True; event.handler_name = "mnu_agony_sting"
        elif "Daemon Sultan" in rest or ("Azathoth" in rest and "glyph" in rest):
            event.matched = True; event.handler_name = "mnu_daemon_sultan"
        elif "Nuclear Chaos" in rest:
            event.matched = True; event.handler_name = "mnu_nuclear_chaos"
        elif "Snakebite" in rest:
            event.matched = True; event.handler_name = "mnu_snakebite"
        elif "Messenger of Yig" in rest or "MessengerOfYig" in rest or "Yig Spellbook Requirement" in rest:
            event.matched = True; event.handler_name = "mnu_messenger_of_yig"
        elif "Firestorm" in rest:
            event.matched = True; event.handler_name = "mnu_firestorm"
        elif "Cthugha" in rest:
            # [2026-05-24] "<GOO> replaced by Cthugha" → remove the replaced
            # GOO from the map (state change). Other Cthugha lines (awaken,
            # combat-match) are announcement-only.
            m_repl = re.match(r"^([\w' -]+) replaced by", plain)
            if m_repl and "Cthugha" in plain:
                replaced_goo = m_repl.group(1).strip()
                # Look for "<Faction> <GOO> replaced by Cthugha" pattern
                fac_m = re.search(r"<span class='(\w+) inline-block'>", raw_line)
                if fac_m:
                    fc = fac_m.group(1).upper()
                    if fc in state.factions:
                        state.remove_unit_anywhere(fc, replaced_goo)
            event.matched = True; event.handler_name = "mnu_cthugha"
        elif "Bokrug" in rest or "Ghosts of Ib" in rest or "Doom that Came to Sarnath" in rest or "DoomThatCameToSarnath" in rest:
            event.matched = True; event.handler_name = "mnu_bokrug"
        elif "Shadow Pharaoh" in rest or ("Pharaoh" in rest and "CC" in rest):
            event.matched = True; event.handler_name = "mnu_shadow_pharaoh"
        elif "awakened" in rest and ("Mother Hydra" in rest or "Father Dagon" in rest
                                      or "Bloated Woman" in rest or "Atlach-Nacha" in rest
                                      or "Bokrug" in rest or "Gla'aki" in rest or "Yig" in rest
                                      or "Ghatanothoa" in rest or "Azathoth" in rest):
            event.matched = True; event.handler_name = "mnu_igoo_awakened"

    # ── Non-faction-prefixed informational lines ───────────────────────────
    # These don't have a faction prefix and were previously unmatched, cluttering
    # the audit overlay. None mutate state.
    if not event.matched and re.match(r"^Agony Die rolled \d+", plain):
        event.matched = True; event.handler_name = "agony_die_roll"
    if not event.matched and plain.startswith("ROUNDTRIP MISMATCH"):
        # SimRunner debug instrumentation, not a real game log line.
        event.matched = True; event.handler_name = "sim_debug_marker"

    # ── Specific handlers for common phrases that would otherwise fall to ──
    # the unhandled_faction_event catchall and noisy up the audit.
    # Each either mutates state (real handler) or is marked informational.

    # Doom transfer: "X supplied Y with N Doom" — subtract from X, add to Y.
    # `rest` is plain text (HTML stripped) so the recipient name appears as
    # the full faction string (e.g., "Black Goat").
    if not event.matched and short and "supplied" in rest and "Doom" in rest:
        m_dt = re.match(r"^supplied (.+?) with (\d+) Doom$", rest)
        if m_dt:
            recipient_full = m_dt.group(1).strip()
            amount = int(m_dt.group(2))
            recipient = FACTION_NAMES.get(recipient_full)
            fs_from = state.factions.get(short)
            if fs_from:
                fs_from.doom = max(0, fs_from.doom - amount)
            if recipient:
                state.ensure_faction(recipient)
                state.factions[recipient].doom += amount
            event.matched = True; event.handler_name = "doom_transfer"

    # Yr and the Nhhngr (tome): "X used Yr and the Nhhngr and gained N Power"
    if not event.matched and short and "used" in rest and "Yr and the Nhhngr" in rest and "gained" in rest and "Power" in rest:
        m_yr = re.search(r"gained (\d+) Power", rest)
        if m_yr:
            fs = state.factions.get(short)
            if fs:
                fs.power += int(m_yr.group(1))
            event.matched = True; event.handler_name = "tome_yr_gain_power"

    # Yr and the Nhhngr (tome): "X used Yr and the Nhhngr to place <Unit> in <Region>"
    if not event.matched and short and "used" in rest and "Yr and the Nhhngr" in rest and "to place" in rest:
        m_yp = re.match(r"^used .*Yr and the Nhhngr.* to place (.+?) in (.+?)$", rest)
        if m_yp:
            unit = m_yp.group(1).strip()
            reg = region_key(m_yp.group(2).strip())
            state.place_unit(short, unit, reg)
            event.matched = True; event.handler_name = "tome_yr_place_unit"

    # Guardian under the Lake (tome): "X used Guardian under the Lake to move
    # <Target> units from <Src> to <Dst>" — moves all target-faction units
    # from src to dst. Plain-text variant.
    if not event.matched and short and "used" in rest and "Guardian under the Lake" in rest and "to move" in rest:
        m_gu = re.match(r"^used .*Guardian under the Lake.* to move (.+?) units from (.+?) to (.+?)$", rest)
        if m_gu:
            target_full = m_gu.group(1).strip()
            src = region_key(m_gu.group(2).strip())
            dst = region_key(m_gu.group(3).strip())
            target = FACTION_NAMES.get(target_full)
            src_reg = state.regions.get(src)
            dst_reg = state.regions.get(dst)
            if target and src_reg and dst_reg:
                # Move ALL units of target faction from src to dst
                units_to_move = []
                for u in list(src_reg.faction_units(target)):
                    if u.quantity > 0:
                        units_to_move.append((u.name, u.quantity))
                for uname, qty in units_to_move:
                    for _ in range(qty):
                        if src_reg.remove_unit(target, uname):
                            dst_reg.add_unit(target, uname)
            event.matched = True; event.handler_name = "tome_guardian_move"

    # Larvae of the Outer Gods (tome): "X used Larvae of the Outer Gods, gained
    # an Elder Sign using Larvae of the Outer Gods" (success) — ES gain handled
    # by a separate gained-ES handler. The failure path "no opponent has more
    # Power — no ES gained" is informational.
    if not event.matched and short and "used" in rest and "Larvae of the Outer Gods" in rest:
        event.matched = True; event.handler_name = "tome_larvae_used"

    # "X eliminated N Cultists" — announcement; specific unit kills logged
    # separately on follow-up lines.
    if not event.matched and short and re.match(r"^eliminated \d+ Cultist", rest):
        event.matched = True; event.handler_name = "eliminated_cultists_announce"

    # SL "was sleeping" — Sleeper's pass-turn during sleep. No state mutation;
    # SL wakes when the appropriate condition is logged separately.
    if not event.matched and short == "SL" and rest == "was sleeping":
        event.matched = True; event.handler_name = "sl_sleeping"

    # Negotiation outcomes (battle-time offers/refusals — purely informational).
    if not event.matched and short and ("refused to negotiate" in rest or
                                        "offered no Cultists" in rest or
                                        "offered no power" in rest or
                                        "offered no Power" in rest or
                                        re.match(r"^offered to lose \d+", rest)):
        event.matched = True; event.handler_name = "battle_negotiation"

    # Vengeance kill/pain assignments — informational header before the
    # specific kill/pain lines.
    if not event.matched and short and "assigned" in rest and "with Vengeance" in rest:
        event.matched = True; event.handler_name = "vengeance_assignment"

    # IP cancel — state already reverted via FBInfernalPactCancelAction in the
    # game engine; the log line is informational.
    if not event.matched and short and "Cancelled" in rest and "Infernal Pact" in rest:
        event.matched = True; event.handler_name = "ip_cancelled"

    # v5 (2026-05-13): Azathoth auction + PowerDoomOffer choice — these fire
    # for non-DS factions too, so they must live OUTSIDE the DS-only block.
    # "<X> offered N Power and M Doom to Azathoth" — pre-outcome announcement
    #    (informational; the sacrifice line applies the deduction)
    # "<X> sacrificed N Power and/or M Doom to Azathoth" — actual deduction
    if not event.matched and short and "to Azathoth" in rest and "offered" in rest:
        event.matched = True; event.handler_name = "azathoth_offer"
    if not event.matched and short and "to Azathoth" in rest and "sacrificed" in rest:
        m_p = re.search(r"sacrificed.*?(\d+)\s+Power", rest)
        m_d = re.search(r"(\d+)\s+Doom\s+to Azathoth", rest)
        fs_az = state.factions.get(short)
        if fs_az is not None:
            if m_p: fs_az.power = max(0, fs_az.power - int(m_p.group(1)))
            if m_d: fs_az.doom = max(0, fs_az.doom - int(m_d.group(1)))
        event.matched = True; event.handler_name = "azathoth_sacrifice"

    # "<X> chose N Power from PowerDoomOffer" / "...N Doom from PowerDoomOffer"
    # — apply gain on the active faction.
    if not event.matched and short and "from PowerDoomOffer" in rest:
        m = re.search(r"chose (\d+) (Power|Doom) from PowerDoomOffer", rest)
        if m:
            amount = int(m.group(1))
            resource = m.group(2)
            fs_off = state.factions.get(short)
            if fs_off is not None:
                if resource == "Power":
                    fs_off.power += amount
                else:
                    fs_off.doom += amount
        event.matched = True; event.handler_name = "ds_power_doom_offer_choice"

    # v5 (2026-05-13): GC Dreams — "Great Cthulhu sent dreams to <Faction> in <Region>".
    # Per game rules: eliminate one enemy cultist on the gate in that region,
    # then GC places an Acolyte from pool there.
    if not event.matched and short == "GC" and "sent dreams to" in rest:
        m = re.search(r"sent dreams to <span[^>]*>([\w ]+)</span> in <span class='(?:region|sea)'>([\w' -]+)</span>", raw_line)
        if m:
            target_full = m.group(1).strip()
            target = FACTION_NAMES.get(target_full)
            reg = region_key(m.group(2).strip())
            r = state.regions.get(reg)
            if r and target:
                for unit_class in ("Acolyte", "High Priest"):
                    if r.has_unit(target, unit_class):
                        r.remove_unit(target, unit_class)
                        break
            state.place_unit("GC", "Acolyte", reg)
        event.matched = True; event.handler_name = "gc_dreams"

    # v5 (2026-05-13): Augury / Carnage / Eternal / Traitors-acolyte handlers.

    # Augury stored kills (FB): "Augury: stored N Kill(s) (M total)"
    if not event.matched and short == "FB" and "Augury:" in rest and "stored" in rest:
        m = re.search(r"\((\d+)\s+total\)", rest)
        if m:
            total_kills = int(m.group(1))
            fb_fs = state.factions.get("FB")
            if fb_fs is not None:
                fb_fs.custom["augury_kills"] = total_kills
        event.matched = True; event.handler_name = "augury_stored"

    # Augury used (writhe or battle): "Augury: replaced N Miss(es) with N Kill(s)"
    # or "...with Kills in battle". Either way deducts N from augury_kills.
    if not event.matched and short == "FB" and "Augury:" in rest and "replaced" in rest:
        m = re.search(r"replaced (\d+)\s+Miss", rest)
        if m:
            n = int(m.group(1))
            fb_fs = state.factions.get("FB")
            if fb_fs is not None:
                cur = fb_fs.custom.get("augury_kills", 0) or 0
                fb_fs.custom["augury_kills"] = max(0, cur - n)
        event.matched = True; event.handler_name = "augury_used"

    # Carnage paid 1 Power for 1 ES.
    if not event.matched and short == "FB" and "Carnage:" in rest and "paid" in rest:
        fb_fs = state.factions.get("FB")
        if fb_fs is not None:
            fb_fs.power = max(0, fb_fs.power - 1)
            fb_fs.elder_signs_hidden += 1
        event.matched = True; event.handler_name = "carnage_paid"

    # Carnage flipped <SB> facedown for 1 ES.
    if not event.matched and short == "FB" and "Carnage:" in rest and "flipped" in rest and "facedown" in rest:
        fb_fs = state.factions.get("FB")
        if fb_fs is not None:
            fb_fs.elder_signs_hidden += 1
            # Flip the named SB face-down on FB's spellbook list
            m_sb = re.search(r"flipped\s+([\w' -]+?)\s+facedown", rest)
            if m_sb:
                sb_name = m_sb.group(1).strip()
                fb_fs.flip_spellbook(sb_name, False)
        event.matched = True; event.handler_name = "carnage_flipped"

    # WW Eternal pay: "Faction payed 1 Power for Eternal to cancel <Kill|Pain>
    # on <unit>". Power -= 1; the kill/pain was prevented in the engine so no
    # state-revert needed here (the unit's status is preserved going forward).
    if not event.matched and short and "payed" in rest and "for" in rest and "Eternal" in rest:
        m = re.search(r"payed\s+(\d+)\s+Power", rest)
        if m:
            fs_e = state.factions.get(short)
            if fs_e is not None:
                fs_e.power = max(0, fs_e.power - int(m.group(1)))
        event.matched = True; event.handler_name = "eternal_pay"

    # "<Faction> gained <Unit> in <Region> from Traitors!" — place the unit.
    if not event.matched and short and "from" in rest and "Traitors" in rest and "gained" in rest:
        m = re.match(r"^gained\s+<span[^>]*>([\w' -]+)</span>\s+in\s+<span[^>]*>([\w' -]+)</span>\s+from", raw_line.split(">", 2)[2] if raw_line.count(">") >= 2 else rest)
        if not m:
            # Fallback to plain-text match
            m = re.match(r"^gained\s+([\w' -]+?)\s+in\s+(.+?)\s+from\s+Traitors", rest)
        if m:
            unit = m.group(1).strip()
            reg = region_key(m.group(2).strip())
            state.place_unit(short, unit, reg)
            # Also assign gate ownership in the converted region
            r = state.regions.get(reg)
            if r:
                r.gate.exists = True
                r.gate.owner = short
                state.gate_locations.add(reg)
                fs_g = state.factions.get(short)
                if fs_g is not None:
                    fs_g.gates.add(reg)
        event.matched = True; event.handler_name = "traitors_acolyte_gained"

    # Catch any remaining faction-prefixed events as matched (logged but no state change)
    if not event.matched and short:
        event.matched = True; event.handler_name = "unhandled_faction_event"

    # Check state change
    fp_after = state.summary_fingerprint()
    event.state_changed = (fp_before != fp_after)

    return event
