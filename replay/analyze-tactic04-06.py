#!/usr/bin/env python3
"""Analyze Tactics 04-06: Power spending at end of AP.
T04: 3-4 power, gate with no ghato/rev → summon rev
T05: 2 power, < 5 cultists → summon cultist; 2 power, > 4 cult, < 5 desc → summon desc
T06: 1 power, < 6 cultists → recruit cultist

Uses XML state dumps."""

import os, sys, re, glob, time, subprocess, tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DUMP_SCRIPT = os.path.join(SCRIPT_DIR, "dump-game-state.py")

if len(sys.argv) < 2:
    print("Usage: python3 analyze-tactic04-06.py <win-logs-dir>")
    sys.exit(1)

log_dir = sys.argv[1]
files = sorted(glob.glob(os.path.join(log_dir, "fb-*.txt")))
print(f"Found {len(files)} game logs")

# Per-tactic counters
t04_eligible = 0; t04_correct = 0; t04_actions = Counter()
t05_eligible = 0; t05_correct = 0; t05_actions = Counter()
t06_eligible = 0; t06_correct = 0; t06_actions = Counter()
errors = 0

for fpath in files:
    xml_path = os.path.join(tempfile.gettempdir(), f"cw-t456-{os.path.basename(fpath)}.xml")
    try:
        result = subprocess.run(["python3", DUMP_SCRIPT, fpath, xml_path],
                                capture_output=True, text=True, timeout=30)
        if result.returncode != 0: errors += 1; continue
    except: errors += 1; continue

    try: tree = ET.parse(xml_path)
    except: errors += 1; os.unlink(xml_path); continue
    root = tree.getroot()

    # Scan all FB actions in action phases
    for action in root:
        phase = action.get('phase', '')
        faction = action.get('faction', '')
        if phase != 'action' or faction != 'FB':
            continue

        text = action.find('text').text or ''
        state = action.find('state')
        fb = None
        for f in state.findall('faction'):
            if f.get('code') == 'FB':
                fb = f; break
        if fb is None:
            continue

        power = int(fb.get('power'))
        gate_regs = fb.get('gate_regions', '')
        gates = gate_regs.split(',') if gate_regs else []
        num_gates = len(gates)

        # Count units on map from regions
        regions = state.find('regions')
        cultists_on_map = 0
        desc_on_map = 0
        undefended_gates = []

        for greg in gates:
            reg_el = None
            for r in regions:
                if r.get('key') == greg:
                    reg_el = r; break
            if reg_el is None:
                continue
            has_ghato = False; has_rev = False
            for u in reg_el.findall('unit'):
                if u.get('faction') != 'FB': continue
                name = u.get('name', '')
                qty = int(u.get('qty', 0))
                if name == 'Ghatanothoa' and qty > 0: has_ghato = True
                if name in ("Revenant of K'Naa", "Revenant") and qty > 0: has_rev = True
            if not has_ghato and not has_rev:
                undefended_gates.append(greg)

        for r in regions:
            for u in r.findall('unit'):
                if u.get('faction') != 'FB': continue
                name = u.get('name', '')
                qty = int(u.get('qty', 0))
                if u.get('category') == 'cultist':
                    cultists_on_map += qty
                if name == 'Desiccated':
                    desc_on_map += qty

        # T04: power 3-4, undefended gate exists → summon rev
        if power in (3, 4) and undefended_gates and num_gates >= 1:
            t04_eligible += 1
            if 'summoned' in text and ("Revenant" in text or "K'Naa" in text):
                t04_correct += 1
                t04_actions['summon_rev'] += 1
            elif 'summoned' in text:
                t04_actions['summon_other'] += 1
            elif 'recruited' in text:
                t04_actions['recruit'] += 1
            elif 'used Writhe' in text:
                t04_actions['writhe'] += 1
            elif 'ran out' in text or 'had no power' in text:
                t04_actions['no_power'] += 1
            else:
                t04_actions['other'] += 1

        # T05: power 2, < 5 cultists → summon cultist; power 2, > 4 cult, < 5 desc → summon desc
        if power == 2 and num_gates >= 1:
            if cultists_on_map < 5:
                t05_eligible += 1
                if 'summoned' in text and 'Acolyte' in text:
                    t05_correct += 1; t05_actions['summon_cult'] += 1
                elif 'summoned' in text:
                    t05_actions['summon_other'] += 1
                elif 'recruited' in text:
                    t05_actions['recruit'] += 1
                else:
                    t05_actions['other'] += 1
            elif cultists_on_map > 4 and desc_on_map < 5:
                t05_eligible += 1
                if 'summoned' in text and 'Desiccated' in text:
                    t05_correct += 1; t05_actions['summon_desc'] += 1
                elif 'summoned' in text:
                    t05_actions['summon_other'] += 1
                else:
                    t05_actions['other'] += 1

        # T06: power 1, < 6 cultists → recruit cultist
        if power == 1 and cultists_on_map < 6 and num_gates >= 1:
            t06_eligible += 1
            if 'recruited' in text and 'Acolyte' in text:
                t06_correct += 1; t06_actions['recruit_cult'] += 1
            elif 'recruited' in text:
                t06_actions['recruit_other'] += 1
            elif 'summoned' in text:
                t06_actions['summon'] += 1
            else:
                t06_actions['other'] += 1

    os.unlink(xml_path)

print(f"""
Tactic 04: Summon Rev at 3-4 Power (undefended gate)
  Eligible: {t04_eligible}, Correct: {t04_correct} ({t04_correct*100//max(t04_eligible,1)}%)
  Actions: {dict(t04_actions)}

Tactic 05: Summon Cultist/Desc at 2 Power
  Eligible: {t05_eligible}, Correct: {t05_correct} ({t05_correct*100//max(t05_eligible,1)}%)
  Actions: {dict(t05_actions)}

Tactic 06: Recruit Cultist at 1 Power
  Eligible: {t06_eligible}, Correct: {t06_correct} ({t06_correct*100//max(t06_eligible,1)}%)
  Actions: {dict(t06_actions)}
""")
