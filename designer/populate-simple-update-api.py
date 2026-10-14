#!/usr/bin/env python3
"""
Populate the Simple Update section via the Faction Designer API.

This alternative approach uses the designer's API to add image swap rows
instead of directly modifying faction files. This is useful when you don't
have direct file system access.

Usage:
  python3 populate-simple-update-api.py --server http://localhost:8091 --token YOUR_TOKEN

Example:
  python3 populate-simple-update-api.py --server https://cwo.example.com/designer --token abc123xyz
"""

import json
import sys
import argparse
import base64
from pathlib import Path
from typing import Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


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
    'DGT': [  # Tribulation
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


def api_call(method: str, path: str, server: str, token: str, data: Optional[Dict] = None) -> Dict:
    """Make an API call to the designer server."""
    url = f"{server.rstrip('/')}/api{path}"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}',
    }

    body = json.dumps(data).encode('utf-8') if data else None

    try:
        req = Request(url, data=body, headers=headers, method=method)
        with urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except HTTPError as e:
        error_body = e.read().decode('utf-8')
        try:
            error_json = json.loads(error_body)
            raise Exception(f"HTTP {e.code}: {error_json.get('error', error_body)}")
        except json.JSONDecodeError:
            raise Exception(f"HTTP {e.code}: {error_body}")
    except URLError as e:
        raise Exception(f"Connection error: {e.reason}")


def list_factions(server: str, token: str) -> List[Dict]:
    """List all factions for the authenticated user."""
    result = api_call('GET', '/factions', server, token)
    return result.get('factions', [])


def get_faction_by_acronym(server: str, token: str, acronym: str) -> Optional[Dict]:
    """Find a faction by its acronym."""
    factions = list_factions(server, token)
    for faction in factions:
        if faction.get('acronym') == acronym:
            return faction
    return None


def update_faction_design(server: str, token: str, faction_id: str, filenames: List[str]) -> bool:
    """Add image swap rows to a faction's design."""
    # First, get the full faction data
    faction_result = api_call('GET', f'/factions/{faction_id}', server, token)
    faction = faction_result.get('faction')

    if not faction:
        print(f"  ERROR: Could not load faction")
        return False

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

    if added_count == 0:
        print(f"  No new rows to add (all rows already exist)")
        return False

    # Update the faction design
    try:
        api_call('POST', f'/factions/{faction_id}/design', server, token, {'design': design})
        print(f"  Added {added_count} image swap rows and saved design")
        return True
    except Exception as e:
        print(f"  ERROR: Could not save design: {e}")
        return False


def populate_faction(server: str, token: str, acronym: str) -> bool:
    """Populate Simple Update section for a faction."""
    print(f"\nProcessing {acronym}...")

    # Find faction by acronym
    faction = get_faction_by_acronym(server, token, acronym)
    if not faction:
        print(f"  ERROR: Could not find faction with acronym {acronym}")
        return False

    faction_id = faction.get('id')
    faction_name = faction.get('name')
    print(f"  Found: {faction_name} ({faction_id})")

    # Get list of image filenames to add
    filenames = FACTION_IMAGE_SWAPS.get(acronym, [])
    if not filenames:
        print(f"  ERROR: No image filenames defined for {acronym}")
        return False

    # Update faction design with image swap rows
    return update_faction_design(server, token, faction_id, filenames)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--server',
        default='http://127.0.0.1:8091',
        help='Designer server URL (default: http://127.0.0.1:8091)'
    )
    parser.add_argument(
        '--token',
        required=True,
        help='Admin token for authentication'
    )

    args = parser.parse_args()
    server = args.server.rstrip('/')
    token = args.token

    print(f"Designer Server: {server}")
    print("=" * 60)

    # Test connectivity
    try:
        print("Testing server connection...")
        list_factions(server, token)
        print("Connection successful!")
    except Exception as e:
        print(f"ERROR: Could not connect to server: {e}", file=sys.stderr)
        return 1

    all_success = True
    factions_to_process = ['FM', 'PRM', 'DGT']

    for acronym in factions_to_process:
        try:
            if not populate_faction(server, token, acronym):
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
