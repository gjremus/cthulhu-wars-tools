#!/usr/bin/env python3
"""
CLI admin tool for the Faction Designer
Usage:
  designer-admin.py stability <faction_id> <alpha|beta|stable>
"""
import json
import sys
from pathlib import Path

DATA_DIR = Path("/opt/cwo/designer/data")
LOCAL_DATA_DIR = Path(__file__).parent.parent / "dev" / "data"

def load_json(path):
    if not path.exists():
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def atomic_write(path, data):
    tmp = path.parent / f"{path.name}.tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
    import os
    os.replace(tmp, path)

def set_stability(fid, stability):
    valid_values = ['alpha', 'beta', 'stable']
    if stability not in valid_values:
        print(f"Error: stability must be one of: {', '.join(valid_values)}")
        return 1

    # Try production data dir first, then local dev
    data_dir = DATA_DIR if DATA_DIR.exists() else LOCAL_DATA_DIR
    faction_file = data_dir / "factions" / fid / "faction.json"

    if not faction_file.exists():
        print(f"Error: faction {fid} not found")
        return 1

    faction = load_json(faction_file)
    if not faction:
        print(f"Error: could not load faction {fid}")
        return 1

    old_stability = faction.get("stability", "(none)")
    faction["stability"] = stability

    import time
    faction["updated"] = int(time.time())

    atomic_write(faction_file, faction)

    acronym = faction.get("acronym", "???")
    print(f"Set {acronym} ({fid}) stability: {old_stability} → {stability}")
    return 0

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    command = sys.argv[1]

    if command == "stability":
        if len(sys.argv) != 4:
            print("Usage: designer-admin.py stability <faction_id> <alpha|beta|stable>")
            return 1
        return set_stability(sys.argv[2], sys.argv[3])
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        return 1

if __name__ == "__main__":
    sys.exit(main())
