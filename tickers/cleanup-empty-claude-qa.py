#!/usr/bin/env python3
"""
Clean up empty claudeQA questions fields (whitespace-only strings) across all factions, units, and maps.
Makes the UI consistent - either blank or has real questions.
"""

import json
import sys
import time
from pathlib import Path

def clean_entity(entity_file: Path, entity_type: str):
    """Clean up empty claudeQA fields in an entity"""
    try:
        entity = json.loads(entity_file.read_text())
    except:
        return False

    claudeQA = entity.get('claudeQA', {})
    if not claudeQA:
        return False

    changed = False
    for section, data in list(claudeQA.items()):
        if not data or not isinstance(data, dict):
            continue

        # Clean empty questions (whitespace only)
        if 'questions' in data:
            original = data['questions']
            if original and not original.strip():
                data['questions'] = ''
                changed = True

        # Clean empty answers (whitespace only)
        if 'answers' in data:
            original = data['answers']
            if original and not original.strip():
                data['answers'] = ''
                changed = True

    if changed:
        entity['updated'] = int(time.time())

        # Atomic write
        tmp = entity_file.with_suffix('.tmp')
        tmp.write_text(json.dumps(entity, indent=2))
        tmp.replace(entity_file)

        name = entity.get('name', entity_file.parent.name)
        print(f"Cleaned {entity_type}: {name}")
        return True

    return False

def main():
    # Determine data directory
    if len(sys.argv) > 1:
        data_dir = Path(sys.argv[1])
    else:
        # Default to server data dir
        data_dir = Path('/opt/cwo/designer/data')

    if not data_dir.exists():
        print(f"Error: {data_dir} does not exist")
        sys.exit(1)

    cleaned = 0

    # Clean factions
    factions_dir = data_dir / 'factions'
    if factions_dir.exists():
        for faction_dir in factions_dir.iterdir():
            if not faction_dir.is_dir():
                continue
            faction_file = faction_dir / 'faction.json'
            if faction_file.exists():
                if clean_entity(faction_file, 'faction'):
                    cleaned += 1

    # Clean units
    units_dir = data_dir / 'units'
    if units_dir.exists():
        for unit_dir in units_dir.iterdir():
            if not unit_dir.is_dir():
                continue
            unit_file = unit_dir / 'unit.json'
            if unit_file.exists():
                if clean_entity(unit_file, 'unit'):
                    cleaned += 1

    # Clean maps
    maps_dir = data_dir / 'maps'
    if maps_dir.exists():
        for map_dir in maps_dir.iterdir():
            if not map_dir.is_dir():
                continue
            map_file = map_dir / 'map.json'
            if map_file.exists():
                if clean_entity(map_file, 'map'):
                    cleaned += 1

    print(f"Total cleaned: {cleaned}")

if __name__ == '__main__':
    main()
