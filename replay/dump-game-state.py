#!/usr/bin/env python3
"""Dump full game state after every action to XML for analysis.

Usage: python3 dump-game-state.py <trace-file.txt> <output.xml>

Each <action> element contains:
  - round: game round (1-6+)
  - phase: placement, action, gather_power, player_order, doom
  - action_num: sequential within phase (resets each phase)
  - faction: faction taking action
  - text: game log text
  - state: full game state snapshot AFTER the action
"""

import sys, os, re
from xml.etree.ElementTree import Element, SubElement, tostring, indent

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from game_state import FullGameState, FACTION_ROSTER
from event_handlers import process_line, strip_html, FACTION_NAMES

if len(sys.argv) < 3:
    print("Usage: python3 dump-game-state.py <trace-file.txt> <output.xml>")
    sys.exit(1)

trace_path = sys.argv[1]
output_path = sys.argv[2]

# Read trace file — extract HTML log lines
with open(trace_path) as f:
    content = f.read()

html_lines = re.findall(r"<div class='p'>(.*?)</div>", content)
if not html_lines:
    html_lines = [f"<div class='p'>{l.strip()}</div>" for l in content.split('\n') if l.strip()]

# Phase detection — determines the phase attribute on each <action> element.
# Phase transitions are detected from log text BEFORE processing the line,
# so the phase reflects the context in which the action occurred.
TURN_PATTERN = re.compile(r'^Turn (\d+)$')
POWER_GATHER = re.compile(r'^POWER GATHER$')
PLAY_ORDER = re.compile(r'^Play order (.+)$')
DOOM_PHASE = re.compile(r'^Ritual cost is (\d+)')
PLACEMENT_DONE = re.compile(r'^Placement .*(done|complete)', re.I)

state = FullGameState()
root = Element("game")

current_round = 0
current_phase = "setup"
action_num = 0
total_actions = 0

for i, raw_line in enumerate(html_lines):
    plain = strip_html(raw_line)

    # Detect phase transitions BEFORE processing
    m = TURN_PATTERN.match(plain)
    if m:
        current_round = int(m.group(1))
        current_phase = "action"
        action_num = 0

    if POWER_GATHER.match(plain):
        current_phase = "gather_power"
        action_num = 0

    m = PLAY_ORDER.match(plain)
    if m:
        current_phase = "player_order"
        action_num = 0

    m = DOOM_PHASE.match(plain)
    if m:
        current_phase = "doom"
        action_num = 0

    # Process line through event handlers
    event = process_line(state, raw_line, i)

    # Skip debug/separator lines
    if event.handler_name in ("debug_line", "separator"):
        continue

    # Skip truly empty/uninteresting lines
    if not plain.strip() or plain.startswith(".........."):
        continue

    action_num += 1
    total_actions += 1

    # Build XML element
    action_el = SubElement(root, "action")
    action_el.set("n", str(total_actions))
    action_el.set("round", str(current_round))
    action_el.set("phase", current_phase)
    action_el.set("phase_action", str(action_num))
    action_el.set("faction", event.faction or "")
    action_el.set("handler", event.handler_name or "unmatched")
    action_el.set("matched", str(event.matched).lower())

    text_el = SubElement(action_el, "text")
    text_el.text = plain

    # Dump state snapshot
    state_el = SubElement(action_el, "state")

    # Ritual cost
    SubElement(state_el, "ritual_cost").text = str(state.ritual_cost)

    # Each faction
    for code in state.faction_order:
        fs = state.factions[code]
        f_el = SubElement(state_el, "faction")
        f_el.set("code", code)
        f_el.set("name", fs.name)
        f_el.set("power", str(fs.power))
        f_el.set("doom", str(fs.doom))
        f_el.set("es", str(fs.elder_signs_hidden))
        f_el.set("gates", str(len(fs.gates)))
        f_el.set("gate_regions", ",".join(sorted(fs.gates)))

        # Spellbooks
        sbs = ",".join(s.name for s in fs.spellbooks)
        if sbs:
            f_el.set("spellbooks", sbs)

        # Pool
        pool_parts = []
        for uname, qty in sorted(fs.pool.items()):
            if qty > 0:
                pool_parts.append(f"{qty}x{uname}")
        if pool_parts:
            f_el.set("pool", ",".join(pool_parts))

        # Captured
        if fs.captured:
            cap_parts = []
            for c in fs.captured:
                cap_parts.append(f"{c.get('qty',1)}x{c.get('unit','?')}")
            f_el.set("captured", ",".join(cap_parts))

    # Regions with units or gates
    regions_el = SubElement(state_el, "regions")
    for rkey in sorted(state.regions.keys()):
        reg = state.regions[rkey]
        has_units = any(reg.units.get(fc) for fc in state.faction_order)
        has_gate = reg.gate.exists
        has_buildings = bool(reg.buildings)

        if not (has_units or has_gate or has_buildings):
            continue

        r_el = SubElement(regions_el, "region")
        r_el.set("name", reg.display_name)
        r_el.set("key", rkey)
        if reg.is_ocean:
            r_el.set("ocean", "true")

        if has_gate:
            g_el = SubElement(r_el, "gate")
            g_el.set("owner", reg.gate.owner or "abandoned")

        for bld in reg.buildings:
            b_el = SubElement(r_el, "building")
            b_el.set("type", bld.type)
            b_el.set("faction", bld.faction)

        for fc in state.faction_order:
            for u in reg.faction_units(fc):
                if u.quantity > 0:
                    u_el = SubElement(r_el, "unit")
                    u_el.set("faction", fc)
                    u_el.set("name", u.name)
                    u_el.set("category", u.category)
                    u_el.set("qty", str(u.quantity))

# Write XML
indent(root, space="  ")
xml_bytes = tostring(root, encoding="unicode", xml_declaration=False)
xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes

with open(output_path, 'w') as f:
    f.write(xml_str)

print(f"Wrote {total_actions} actions to {output_path}")
print(f"Factions: {', '.join(state.faction_order)}")
print(f"Rounds: {current_round}")
