#!/usr/bin/env python3
"""
Populate the Simple Update section with image swap rows for FM, PRM, and DGT factions.

This script adds image swap rows to faction design files for quick image swapping.

Usage:
  python3 populate-simple-update.py [--data-dir DATA_DIR]

Examples:
  python3 populate-simple-update.py --data-dir /opt/cwo/designer/data
  python3 populate-simple-update.py --data-dir /path/to/local/data
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
import argparse


# Factions and their image swap rows (acronym -> list of image filenames)
FACTION_IMAGE_SWAPS = {
    'FM': [  # Fleshmason
        'fm-glyph.webp',
        'fm-card.webp',
        'fm-spellbooks.webp',
        'fm-acolyte.webp',
        'fm-high-priest.webp',
        'fm-bone-sculptor.webp',
        'fm-muscle-stitcher.webp',
        'fm-body-architect.webp',
        'fm-screaming-wall.webp',
    ],
    'PRM': [  # Permeation
        'prm-glyph.webp',
        'prm-card.webp',
        'prm-spellbooks.webp',
        'prm-acolyte.webp',
        'prm-astral-egg.webp',
        'prm-celestial-fledgling.webp',
        'prm-ycgnagnnisssz.webp',
    ],
    'DGT': [  # Tribulation (Dread Curse's faction name?)
        'dgt-glyph.webp',
        'dgt-card.webp',
        'dgt-spellbooks.webp',
        'dgt-acolyte.webp',
        'dgt-conquest.webp',
        'dgt-pestilence.webp',
        'dgt-war.webp',
        'dgt-famine.webp',
        'dgt-death.webp',
    ],
}


def load_json(path: Path) -> Dict:
    """Load JSON from file."""
    if not path.exists():
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path: Path, data: Dict):
    """Save JSON to file with atomic write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f"{path.name}.tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
    import os
    os.replace(tmp, path)


def find_faction_id(data_dir: Path, acronym: str) -> Optional[str]:
    """Find faction ID by acronym."""
    factions_dir = data_dir / "factions"
    if not factions_dir.exists():
        return None

    for faction_dir in factions_dir.iterdir():
        if not faction_dir.is_dir():
            continue
        faction_file = faction_dir / "faction.json"
        if not faction_file.exists():
            continue

        faction = load_json(faction_file)
        if faction.get('acronym') == acronym:
            return faction_dir.name

    return None


def add_image_swap_rows(faction: Dict, filenames: List[str]) -> bool:
    """Add image swap rows to faction design."""
    design = faction.get('design', {})

    if 'imageSwaps' not in design:
        design['imageSwaps'] = {'rows': []}

    if 'rows' not in design['imageSwaps']:
        design['imageSwaps']['rows'] = []

    rows = design['imageSwaps']['rows']

    # Add rows for each filename (skip if already exists)
    existing_filenames = {row.get('filename') for row in rows}
    added_count = 0

    for filename in filenames:
        if filename not in existing_filenames:
            rows.append({
                'filename': filename,
                'imageId': None
            })
            added_count += 1

    if added_count > 0:
        faction['design'] = design
        print(f"  Added {added_count} image swap rows")
        return True

    return False


def populate_faction(data_dir: Path, acronym: str) -> bool:
    """Populate Simple Update section for a faction."""
    print(f"\nProcessing {acronym}...")

    # Find faction ID
    faction_id = find_faction_id(data_dir, acronym)
    if not faction_id:
        print(f"  ERROR: Could not find faction with acronym {acronym}")
        return False

    print(f"  Found faction ID: {faction_id}")

    # Load faction data
    faction_file = data_dir / "factions" / faction_id / "faction.json"
    faction = load_json(faction_file)

    if not faction:
        print(f"  ERROR: Could not load faction file: {faction_file}")
        return False

    # Add image swap rows
    filenames = FACTION_IMAGE_SWAPS.get(acronym, [])
    if not filenames:
        print(f"  ERROR: No image filenames defined for {acronym}")
        return False

    if add_image_swap_rows(faction, filenames):
        # Save faction data
        save_json(faction_file, faction)
        print(f"  Saved updated faction data")
        return True
    else:
        print(f"  No new rows added (all rows already exist)")
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--data-dir',
        type=Path,
        default=Path('/opt/cwo/designer/data'),
        help='Path to designer data directory (default: /opt/cwo/designer/data)'
    )

    args = parser.parse_args()
    data_dir = args.data_dir

    if not data_dir.exists():
        print(f"ERROR: Data directory not found: {data_dir}", file=sys.stderr)
        print("Try: python3 populate-simple-update.py --data-dir /path/to/data", file=sys.stderr)
        return 1

    print(f"Using data directory: {data_dir}")
    print("=" * 60)

    all_success = True
    factions_to_process = ['FM', 'PRM', 'DGT']

    for acronym in factions_to_process:
        try:
            if not populate_faction(data_dir, acronym):
                all_success = False
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            all_success = False

    print("\n" + "=" * 60)
    if all_success:
        print("SUCCESS: All factions updated")
        return 0
    else:
        print("PARTIAL: Some factions may not have been updated", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
