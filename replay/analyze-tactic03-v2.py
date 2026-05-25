#!/usr/bin/env python3
"""Tactic 03 compliance: Balance units across 3 gates.
Checks game state before/after writhe for:
1. All 3 gates have units
2. Ghato/rev spread (not both on same gate)
3. No gate abandoned
4. Unit disparity decreases
5. Exception: no pains = structural (not failure)
"""

import os, sys, re, glob, subprocess, tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DUMP_SCRIPT = os.path.join(SCRIPT_DIR, "dump-game-state.py")

if len(sys.argv) < 2:
    print("Usage: python3 analyze-tactic03-v2.py <win-logs-dir>")
    sys.exit(1)

log_dir = sys.argv[1]
files = sorted(glob.glob(os.path.join(log_dir, "fb-*.txt")))
print(f"Found {len(files)} game logs")

total = 0; errors = 0
never_3gates = 0
had_3gates = 0
compliant = 0; non_compliant = 0; structural = 0
failures = defaultdict(int)

for fpath in files:
    total += 1
    xml_path = os.path.join(tempfile.gettempdir(), f"cw-t03v2-{os.path.basename(fpath)}.xml")
    try:
        r = subprocess.run(["python3", DUMP_SCRIPT, fpath, xml_path],
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0: errors += 1; continue
    except: errors += 1; continue
    try: tree = ET.parse(xml_path)
    except: errors += 1; os.unlink(xml_path); continue
    root = tree.getroot()
    actions = list(root)

    # Find first moment FB has 3 gates with power > 4 in action phase
    checked = False
    for idx, action in enumerate(actions):
        if checked: break
        phase = action.get('phase', '')
        if phase != 'action': continue

        state = action.find('state')
        fb = None
        for f in state.findall('faction'):
            if f.get('code') == 'FB': fb = f; break
        if fb is None: continue

        gates_str = fb.get('gate_regions', '')
        if not gates_str: continue
        gates = gates_str.split(',')
        power = int(fb.get('power'))

        if len(gates) < 3 or power <= 4: continue
        had_3gates += 1
        checked = True

        # Get unit distribution at each gate BEFORE writhe
        regions = state.find('regions')
        def get_gate_info(gate_list, reg_el):
            info = {}
            for greg in gate_list:
                for r2 in reg_el:
                    if r2.get('key') == greg:
                        units = {'cult': 0, 'desc': 0, 'ghato': False, 'rev': False, 'total': 0}
                        for u in r2.findall('unit'):
                            if u.get('faction') != 'FB': continue
                            qty = int(u.get('qty', 0))
                            name = u.get('name', '')
                            if name == 'Ghatanothoa' and qty > 0: units['ghato'] = True
                            elif name in ("Revenant of K'Naa", "Revenant") and qty > 0: units['rev'] = True
                            elif name == 'Desiccated': units['desc'] += qty
                            elif u.get('category') == 'cultist': units['cult'] += qty
                            units['total'] += qty
                        info[greg] = units
                        break
            return info

        before = get_gate_info(gates, regions)
        before_disparity = max(g['total'] for g in before.values()) - min(g['total'] for g in before.values()) if before else 0

        # Find next FB writhe
        action_n = int(action.get('n'))
        writhe_found = False
        writhe_had_pains = False

        for a2 in actions[idx+1:]:
            text = a2.find('text').text or ''
            fc = a2.get('faction', '')
            if 'POWER GATHER' in text: break
            if fc != 'FB': continue
            if 'ran out of power' in text: break

            if 'used Writhe' in text:
                writhe_found = True
                # Check for pains in the writhe
                for a3 in actions[actions.index(a2)+1:]:
                    t3 = a3.find('text').text or ''
                    if 'POWER GATHER' in t3 or ('used Writhe' in t3 and a3 != a2): break
                    if 'relocated' in t3 and 'Firstborn' in t3:
                        writhe_had_pains = True
                    if 'Firstborn' in t3 and 'Writhe' not in t3 and a3.get('faction') == 'FB':
                        # First non-writhe FB action = state after writhe
                        after_state = a3.find('state')
                        after_fb = None
                        for f2 in after_state.findall('faction'):
                            if f2.get('code') == 'FB': after_fb = f2; break
                        if after_fb:
                            after_gates_str = after_fb.get('gate_regions', '')
                            after_gates = after_gates_str.split(',') if after_gates_str else []
                            after_regions = after_state.find('regions')
                            after_info = get_gate_info(after_gates, after_regions)

                            # Check compliance criteria
                            fail_reasons = []

                            # 1. All gates have units
                            for greg, info in after_info.items():
                                if info['total'] == 0:
                                    fail_reasons.append(f'gate_empty:{greg}')

                            # 2. Ghato/rev spread (not both on same gate)
                            ghato_gate = None; rev_gates = []
                            for greg, info in after_info.items():
                                if info['ghato']: ghato_gate = greg
                                if info['rev']: rev_gates.append(greg)
                            if ghato_gate and ghato_gate in rev_gates and len(after_gates) >= 3:
                                # Ghato and rev on same gate while 3+ gates
                                other_gates_undefended = [g for g in after_gates if g != ghato_gate and g not in rev_gates and not after_info.get(g, {}).get('ghato', False)]
                                if other_gates_undefended:
                                    fail_reasons.append('ghato_rev_same_gate')

                            # 3. Gate abandoned (was in before, not in after)
                            for greg in gates:
                                if greg not in after_gates:
                                    fail_reasons.append(f'gate_abandoned:{greg}')

                            # 4. Disparity should decrease or stay same
                            if after_info:
                                after_disparity = max(g['total'] for g in after_info.values()) - min(g['total'] for g in after_info.values())
                                if after_disparity > before_disparity:
                                    fail_reasons.append(f'disparity_increased:{before_disparity}->{after_disparity}')

                            if fail_reasons:
                                non_compliant += 1
                                for fr in fail_reasons:
                                    failures[fr.split(':')[0]] += 1
                            else:
                                compliant += 1
                        break
                break

            # Non-writhe FB action
            if any(x in text for x in ['recruited', 'summoned', 'built', 'captured', 'moved',
                                        'Call of the Faithful', 'attacked', 'battled']):
                non_compliant += 1
                failures['didnt_writhe'] += 1
                break

        if not writhe_found and not checked:
            if writhe_had_pains:
                non_compliant += 1
                failures['no_writhe_with_pains'] += 1
            else:
                structural += 1

    os.unlink(xml_path)

total_eligible = compliant + non_compliant + structural
print(f"""
Tactic 03 Compliance: Balance Units Across 3 Gates
{'='*55}

{total} games ({errors} errors)
├── Never had 3 gates + power > 4: {total - had_3gates - errors}
└── Had 3 gates + power > 4: {had_3gates}
    ├── Compliant: {compliant} ({compliant*100//max(had_3gates,1)}%)
    ├── Non-compliant: {non_compliant} ({non_compliant*100//max(had_3gates,1)}%)
    └── Structural (no pains): {structural}

Failure breakdown:
""")
for reason, count in sorted(failures.items(), key=lambda x: -x[1]):
    print(f"  {reason:30s} {count}")

print(f"\nAdherence: {compliant}/{had_3gates} = {compliant*100//max(had_3gates,1)}% (target: 95%)")
