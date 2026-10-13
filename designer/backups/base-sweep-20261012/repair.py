#!/usr/bin/env python3
"""
Repair base factions: restore v1 originals, verify structured data is correct.
"""
import json
import sys
from pathlib import Path

ORIG_DIR = Path(__file__).parent / "orig"

def load_json(path):
    with open(path) as f:
        return json.load(f)

def compare_and_build_patch(fid, acronym, v1_path, current_path):
    """Compare v1 vs current, build patch ops to restore v1 content."""
    v1_design = load_json(v1_path)
    current_design = load_json(current_path)["design"]

    # For CC, the current version is completely wrong - it's not even CC data!
    # We should just restore v1 as-is.
    # Build a replaceSection op for each major section

    ops = []

    # Restore all sections from v1
    for section in ["meta", "card", "sbImages", "sbImagesB", "ae", "ufa", "setup", "units", "sbr", "sb", "region", "tokens", "custom", "menus"]:
        if section in v1_design:
            ops.append({
                "op": "replaceSection",
                "path": section,
                "value": v1_design[section]
            })

    return ops

def main():
    factions = [
        ("w53yakj7wmjg", "CC", "CC-v1.json", "CC-current.json"),
        ("0ciymclfvfr", "BG", "BG-v1.json", "BG-current.json"),
        ("obgfby7d2yh0", "YS", "YS-v1.json", "YS-current.json"),
    ]

    for fid, acronym, v1_file, current_file in factions:
        print(f"=== {acronym} ({fid}) ===")
        v1_path = ORIG_DIR / v1_file
        current_path = ORIG_DIR / current_file

        ops = compare_and_build_patch(fid, acronym, v1_path, current_path)

        # Write ops to file
        ops_file = ORIG_DIR.parent / f"{acronym}-repair-ops.json"
        with open(ops_file, 'w') as f:
            json.dump({"ops": ops}, f, indent=2)

        print(f"  Generated {len(ops)} patch ops -> {ops_file}")
        print()

if __name__ == "__main__":
    main()
