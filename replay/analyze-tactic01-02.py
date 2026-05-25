#!/usr/bin/env python3
"""Analyze Tactic 01+02 using deterministic XML game state dumps.

Usage: python3 analyze-tactic01-02.py <win-logs-dir> [--dump-xml]

Processes each game log:
1. Dumps game state to XML via dump-game-state.py
2. Finds first post-awaken Ghato writhe in next AP
3. Queries exact gate/unit state at writhe time
4. Builds decision tree with accurate data
"""

import os, sys, re, glob, time, subprocess, tempfile
import xml.etree.ElementTree as ET

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DUMP_SCRIPT = os.path.join(SCRIPT_DIR, "dump-game-state.py")

if len(sys.argv) < 2:
    print("Usage: python3 analyze-tactic01-02.py <win-logs-dir>")
    sys.exit(1)

log_dir = sys.argv[1]
dump_xml = "--dump-xml" in sys.argv

# Find recent game logs
cutoff = time.time() - 86400
files = sorted(
    [f for f in glob.glob(os.path.join(log_dir, "fb-*.txt"))
     if os.path.getmtime(f) > cutoff],
    key=os.path.getmtime
)
print(f"Found {len(files)} recent game logs")

# Counters
total = 0
excluded = 0
ghato_not_writhed = 0
writhed = 0
to_enemy_gate = 0
to_enemy_gate_no_goo = 0
to_enemy_gate_with_goo = 0
to_empty_land = 0
to_own_gate = 0
to_abandoned = 0
to_other = 0

# After arrival at enemy gate (no GOO)
from collections import defaultdict
next_actions = defaultdict(int)
gate_gained_count = 0

# Empty land breakdown
empty_viable_nogoo = 0
empty_all_goo = 0
empty_no_enemy_gates = 0

errors = 0

for fpath in files:
    total += 1

    # Generate XML dump
    xml_path = os.path.join(tempfile.gettempdir(), f"cw-state-{os.path.basename(fpath)}.xml")
    try:
        result = subprocess.run(
            ["python3", DUMP_SCRIPT, fpath, xml_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            errors += 1
            continue
    except Exception as e:
        errors += 1
        continue

    try:
        tree = ET.parse(xml_path)
    except ET.ParseError:
        errors += 1
        continue
    root = tree.getroot()

    # Find Ghato awaken — this anchors the analysis; games without awakening are excluded
    awaken_n = None
    awaken_round = None
    for action in root:
        text = action.find('text').text or ''
        if 'awakened Ghatanothoa' in text and 'Firstborn' in text:
            awaken_n = int(action.get('n'))
            awaken_round = int(action.get('round'))
            break

    if awaken_n is None:
        excluded += 1
        os.unlink(xml_path)
        continue

    # Find first Writhe with Ghato relocation in a LATER round than awaken.
    # This is the key tactic: where does the bot send Ghato on its first post-awaken writhe?
    ghato_dest_key = None
    ghato_dest_name = None
    writhe_n = None
    writhe_state = None

    for action in root:
        n = int(action.get('n'))
        rnd = int(action.get('round'))
        if n <= awaken_n:
            continue
        # Must be in a later round than awaken
        if rnd <= awaken_round:
            continue

        text = action.find('text').text or ''
        if 'Writhe: relocated' in text and 'Ghatanothoa' in text:
            m = re.search(r'relocated Ghatanothoa from .+ to (.+)', text)
            if m:
                ghato_dest_name = m.group(1).strip()
                ghato_dest_key = ghato_dest_name.replace(" ", "")
                writhe_n = n
                writhe_state = action.find('state')
                break

    if ghato_dest_key is None:
        ghato_not_writhed += 1
        os.unlink(xml_path)
        continue

    writhed += 1

    # Query state at writhe moment
    regions = writhe_state.find('regions')

    # Find destination region
    dest_reg = None
    for reg in regions:
        if reg.get('key') == ghato_dest_key:
            dest_reg = reg
            break

    if dest_reg is None:
        to_other += 1
        os.unlink(xml_path)
        continue

    # Check gate at destination
    dest_gate = dest_reg.find('gate')
    dest_has_gate = dest_gate is not None
    dest_gate_owner = dest_gate.get('owner') if dest_gate is not None else None

    # Check for GOO at destination (excluding FB's own GOO which just arrived)
    dest_enemy_goo = False
    for unit in dest_reg.findall('unit'):
        if unit.get('category') == 'GOO' and unit.get('faction') != 'FB':
            dest_enemy_goo = True

    # Classify destination — the ideal tactic is enemy gate without GOO protection
    if dest_has_gate and dest_gate_owner and dest_gate_owner != 'FB' and dest_gate_owner != 'abandoned':
        if dest_enemy_goo:
            to_enemy_gate_with_goo += 1
            to_enemy_gate += 1
        else:
            to_enemy_gate_no_goo += 1
            to_enemy_gate += 1
    elif dest_has_gate and dest_gate_owner == 'FB':
        to_own_gate += 1
        os.unlink(xml_path)
        continue
    elif dest_has_gate and dest_gate_owner == 'abandoned':
        to_abandoned += 1
        os.unlink(xml_path)
        continue
    else:
        to_empty_land += 1

        # Check: were there enemy gates without GOO available?
        any_enemy_gate_no_goo = False
        any_enemy_gate = False
        for reg in regions:
            gate = reg.find('gate')
            if gate is None:
                continue
            gowner = gate.get('owner')
            if not gowner or gowner == 'FB' or gowner == 'abandoned':
                continue
            any_enemy_gate = True
            # Check GOO at this gate
            has_goo = False
            for unit in reg.findall('unit'):
                if unit.get('category') == 'GOO' and unit.get('faction') != 'FB':
                    has_goo = True
            if not has_goo:
                any_enemy_gate_no_goo = True

        if any_enemy_gate_no_goo:
            empty_viable_nogoo += 1
        elif any_enemy_gate:
            empty_all_goo += 1
        else:
            empty_no_enemy_gates += 1

        os.unlink(xml_path)
        continue

    # Ghato arrived at enemy gate — find next FB action
    fb_next = None
    fb_gained_gate = False
    for action in root:
        n = int(action.get('n'))
        if n <= writhe_n:
            continue
        text = action.find('text').text or ''
        faction = action.get('faction', '')

        # Check for power gather (AP boundary)
        if 'POWER GATHER' in text:
            fb_next = 'turn_ended'
            break

        # Only FB actions
        if faction != 'FB':
            continue

        if 'ran out of power' in text or 'had no power' in text:
            fb_next = 'no_power'
            break
        elif 'captured' in text.lower() and 'Firstborn' in text:
            fb_next = 'capture'
            break
        elif 'Call of the Faithful' in text:
            fb_next = 'cof'
            break
        elif 'recruited' in text:
            fb_next = 'recruit'
            break
        elif re.search(r'attacked|battled', text) and 'Firstborn' in text:
            fb_next = 'battle'
            break
        elif 'used Writhe' in text:
            # Check if kill or move
            kill_n = n
            is_kill = False
            for a2 in root:
                n2 = int(a2.get('n'))
                if n2 <= kill_n:
                    continue
                if n2 > kill_n + 20:
                    break
                t2 = a2.find('text').text or ''
                if 'eliminated' in t2 and 'Firstborn' in t2:
                    is_kill = True
                    break
                if 'replaced' in t2 and 'Firstborn' in t2:
                    is_kill = True
                    break
                if 'used Writhe' in t2:
                    break
            fb_next = 'writhe-kill' if is_kill else 'writhe-move'
            break
        elif 'summoned' in text:
            fb_next = 'summon'
            break
        elif 'built a gate' in text:
            fb_next = 'build_gate'
            break

    if fb_next is None:
        fb_next = 'unknown'

    # Check if FB gained gate
    for action in root:
        n = int(action.get('n'))
        if n <= writhe_n:
            continue
        if n > writhe_n + 100:
            break
        text = action.find('text').text or ''
        if 'gained control of the gate' in text and 'Firstborn' in text and ghato_dest_name in text:
            fb_gained_gate = True
            break

    next_actions[fb_next] += 1
    if fb_gained_gate:
        gate_gained_count += 1

    if not dump_xml:
        os.unlink(xml_path)

# Print results
print(f"""
Decision Tree: Tactic 01+02 ({total} games, XML state analysis)
{'='*60}

{total} games
├── Excluded (no Ghato awaken): {excluded}
├── XML errors: {errors}
└── Included: {total - excluded - errors}
    ├── Ghato not writhed in next AP: {ghato_not_writhed}
    └── Ghato writhed: {writhed}
        ├── To enemy gate (no GOO): {to_enemy_gate_no_goo} ({to_enemy_gate_no_goo*100//max(writhed,1)}%) ✓
        ├── To enemy gate (with GOO): {to_enemy_gate_with_goo}
        ├── To empty land: {to_empty_land} ({to_empty_land*100//max(writhed,1)}%)
        │   ├── Viable gates exist (no GOO): {empty_viable_nogoo} ← SCORING BUG
        │   ├── All gates have GOO: {empty_all_goo} ← structural
        │   └── No enemy gates: {empty_no_enemy_gates}
        ├── To own gate: {to_own_gate}
        └── To abandoned/other: {to_abandoned + to_other}
""")

if to_enemy_gate > 0:
    print(f"After Ghato arrives at enemy gate ({to_enemy_gate} cases):")
    print(f"{'─'*50}")
    for action, count in sorted(next_actions.items(), key=lambda x: -x[1]):
        pct = count * 100 // to_enemy_gate
        correct = '✓' if action in ('capture', 'cof', 'recruit', 'battle', 'writhe-kill') else ''
        print(f"  {action:20s} {count:3d} ({pct:2d}%) {correct}")

    correct_total = sum(next_actions.get(a, 0) for a in ('capture', 'cof', 'recruit', 'battle', 'writhe-kill'))
    print(f"\nCorrect response: {correct_total}/{to_enemy_gate} = {correct_total*100//to_enemy_gate}%")
    print(f"Gate gained: {gate_gained_count}")
