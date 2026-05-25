#!/usr/bin/env python3
"""Analyze Tactic 03: Balance units across 3 gates.
When FB has 3 gates, power > 4, and units imbalanced > 1 discrepancy,
writhe to balance toward ideal: 1 ghato/rev + 2 desc + 2 cult per gate.

Uses XML state dumps for deterministic analysis."""

import os, sys, re, glob, time, subprocess, tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DUMP_SCRIPT = os.path.join(SCRIPT_DIR, "dump-game-state.py")

if len(sys.argv) < 2:
    print("Usage: python3 analyze-tactic03.py <win-logs-dir>")
    sys.exit(1)

log_dir = sys.argv[1]
files = sorted(glob.glob(os.path.join(log_dir, "fb-*.txt")))
print(f"Found {len(files)} game logs")

total = 0
never_had_3gates = 0
had_3gates = 0
had_3gates_power_gt4 = 0
writhed_to_balance = 0
didnt_writhe = 0
imbalanced_at_3gates = 0
balanced_at_3gates = 0
# Track unit distribution quality
ideal_score_before = []
ideal_score_after = []

def gate_ideal_score(state_el):
    """Score how close FB's 3-gate unit distribution is to ideal.
    Ideal per gate: 1 defender (ghato/rev) + 2 desc + 2 cult = 5 units.
    Returns (score, details) where score=0 is perfect."""
    factions = state_el.findall('faction')
    fb = None
    for f in factions:
        if f.get('code') == 'FB':
            fb = f
            break
    if fb is None:
        return (99, "no FB")

    gate_regions = fb.get('gate_regions', '')
    if not gate_regions:
        return (99, "no gates")
    gates = gate_regions.split(',')
    if len(gates) < 3:
        return (99, f"only {len(gates)} gates")

    regions = state_el.find('regions')
    total_deficit = 0
    details = []
    for greg in gates:
        # Find region
        reg_el = None
        for r in regions:
            if r.get('key') == greg:
                reg_el = r
                break
        if reg_el is None:
            details.append(f"{greg}: not found")
            total_deficit += 5
            continue

        # Count FB units at this gate
        cults = 0; descs = 0; defenders = 0
        for u in reg_el.findall('unit'):
            if u.get('faction') != 'FB':
                continue
            name = u.get('name', '')
            qty = int(u.get('qty', 0))
            cat = u.get('category', '')
            if name in ('Ghatanothoa', 'Revenant of K\'Naa', 'Revenant'):
                defenders += qty
            elif name == 'Desiccated':
                descs += qty
            elif cat == 'cultist':
                cults += qty

        # Deficit from ideal (1 defender, 2 desc, 2 cult)
        def_deficit = max(0, 1 - defenders)
        desc_deficit = max(0, 2 - descs)
        cult_deficit = max(0, 2 - cults)
        gate_deficit = def_deficit + desc_deficit + cult_deficit
        total_deficit += gate_deficit
        details.append(f"{greg}: {defenders}def/{descs}d/{cults}c (deficit {gate_deficit})")

    return (total_deficit, "; ".join(details))

errors = 0
for fpath in files:
    total += 1
    xml_path = os.path.join(tempfile.gettempdir(), f"cw-t03-{os.path.basename(fpath)}.xml")
    try:
        result = subprocess.run(
            ["python3", DUMP_SCRIPT, fpath, xml_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            errors += 1; continue
    except:
        errors += 1; continue

    try:
        tree = ET.parse(xml_path)
    except:
        errors += 1; os.unlink(xml_path); continue
    root = tree.getroot()

    # Find first moment FB has 3 gates with power > 4
    found_3gate_moment = False
    for action in root:
        state = action.find('state')
        for f in state.findall('faction'):
            if f.get('code') == 'FB':
                gates = int(f.get('gates'))
                power = int(f.get('power'))
                if gates >= 3 and power > 4:
                    found_3gate_moment = True
                    had_3gates_power_gt4 += 1

                    # Check unit distribution
                    score, details = gate_ideal_score(state)
                    ideal_score_before.append(score)
                    if score > 3:  # more than 1 discrepancy per gate
                        imbalanced_at_3gates += 1
                    else:
                        balanced_at_3gates += 1

                    # Check: does FB writhe next?
                    action_n = int(action.get('n'))
                    next_fb_action = None
                    for a2 in root:
                        n2 = int(a2.get('n'))
                        if n2 <= action_n:
                            continue
                        text = a2.find('text').text or ''
                        faction = a2.get('faction', '')
                        if faction != 'FB':
                            continue
                        if 'ran out of power' in text or 'had no power' in text:
                            next_fb_action = 'no_power'
                            break
                        if 'POWER GATHER' in text:
                            next_fb_action = 'turn_ended'
                            break
                        if 'used Writhe' in text:
                            next_fb_action = 'writhe'
                            # Check state after this writhe sequence
                            # Find next non-writhe FB action
                            for a3 in root:
                                n3 = int(a3.get('n'))
                                if n3 <= n2 + 1:
                                    continue
                                t3 = a3.find('text').text or ''
                                f3 = a3.get('faction', '')
                                if f3 == 'FB' and 'Writhe' not in t3:
                                    score_after, _ = gate_ideal_score(a3.find('state'))
                                    ideal_score_after.append(score_after)
                                    break
                            break
                        if any(x in text for x in ['recruited', 'summoned', 'built a gate',
                                                     'captured', 'moved', 'attacked', 'battled',
                                                     'Call of the Faithful']):
                            next_fb_action = text.split()[1] if len(text.split()) > 1 else 'other'
                            break

                    if next_fb_action == 'writhe':
                        writhed_to_balance += 1
                    else:
                        didnt_writhe += 1
                    break
        if found_3gate_moment:
            break
        # Also track if FB ever had 3 gates
        for f in state.findall('faction'):
            if f.get('code') == 'FB' and int(f.get('gates')) >= 3:
                had_3gates += 1
                break

    os.unlink(xml_path)

# Only count had_3gates for games that never triggered the power>4 check
games_with_3gates = had_3gates_power_gt4

avg_before = sum(ideal_score_before) / len(ideal_score_before) if ideal_score_before else 0
avg_after = sum(ideal_score_after) / len(ideal_score_after) if ideal_score_after else 0

print(f"""
Decision Tree: Tactic 03 — Balance Units Across 3 Gates
{'='*60}

{total} games (errors: {errors})
├── Never had 3 gates with power > 4: {total - had_3gates_power_gt4 - errors}
└── Had 3 gates + power > 4: {had_3gates_power_gt4}
    ├── Already balanced (deficit ≤ 3): {balanced_at_3gates}
    └── Imbalanced (deficit > 3): {imbalanced_at_3gates}
        ├── Writhed to balance: {writhed_to_balance}
        └── Didn't writhe: {didnt_writhe}

Unit distribution quality (0 = perfect ideal):
  Before writhe: avg deficit {avg_before:.1f}
  After writhe:  avg deficit {avg_after:.1f}
  Improvement:   {avg_before - avg_after:+.1f}

Target: 95% of imbalanced cases should writhe to balance.
Current: {writhed_to_balance}/{imbalanced_at_3gates} = {writhed_to_balance*100//max(imbalanced_at_3gates,1)}% (of imbalanced)
Overall: {writhed_to_balance}/{had_3gates_power_gt4} = {writhed_to_balance*100//max(had_3gates_power_gt4,1)}% (of all 3-gate moments)
""")
