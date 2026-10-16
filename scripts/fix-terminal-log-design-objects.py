#!/usr/bin/env python3
"""
Audit and fix designObject fields for designer terminal log entries.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

# Read admin token
token_file = Path.home() / ".cw-admin-token"
ADMIN_TOKEN = token_file.read_text().strip()

BASE_URL = "https://cwo.freeddns.org/designer/api/admin"

def fetch_terminal_log():
    """Fetch all terminal log entries."""
    url = f"{BASE_URL}/{ADMIN_TOKEN}/terminal-log"
    result = subprocess.run(
        ["curl", "-s", url],
        capture_output=True,
        text=True,
        check=True
    )
    return json.loads(result.stdout)["entries"]

def update_entry(entry_id, design_object):
    """Update a terminal log entry's designObject field."""
    url = f"{BASE_URL}/{ADMIN_TOKEN}/terminal-log/{entry_id}"
    data = json.dumps({"designObject": design_object})
    result = subprocess.run(
        ["curl", "-s", "-X", "POST", "-H", "Content-Type: application/json", "-d", data, url],
        capture_output=True,
        text=True,
        check=True
    )
    return json.loads(result.stdout)

def extract_design_from_prompt(prompt, user):
    """
    Extract the design object name from the prompt text.
    Returns the faction/map/unit name if found.
    """
    # Known faction names (including base factions)
    factions = [
        "Fleshmason",
        "Permeation",
        "Xyrious Storm",
        "Tribulation",
        "Colour Out of Space",
        "Fungi from Yuggoth",
        "Primal",
        "Deities of Tribulation",
        "Scroll Test Faction",
        "Cat from Mercury",
        "Faceless Blight",
        "Newborns",
        "Agony",
        "Great Cthulhu",
        "Crawling Chaos",
        "Black Goat",
        "Yellow Sign"
    ]

    # Known map names
    maps = ["Yuggoth"]

    # User-specific patterns (scrolltest_7jyc2n often works on CS)
    if user == "scrolltest_7jyc2n":
        # Check for common CS patterns
        if "CS" in prompt or "tpunhkcjo2c" in prompt:
            return "Colour Out of Space"

    if user == "Zehk":
        # Zehk owns Fleshmason, Permeation, Xyrious Storm
        for faction in ["Fleshmason", "Permeation", "Xyrious Storm"]:
            if faction in prompt or faction.lower() in prompt:
                return faction

    if user == "Daganisoraan":
        # Daganisoraan owns Tribulation
        if "Tribulation" in prompt or "DGT" in prompt or "46lllknws5qi" in prompt:
            return "Tribulation"

    if user == "CavySupreme":
        # CavySupreme owns Colour Out of Space and others
        for name in ["Colour Out of Space", "Cat from Mercury", "Yuggoth"]:
            if name in prompt or name.lower().replace(" ", "") in prompt.lower().replace(" ", ""):
                return name

    # Check for faction mentions in prompt
    for faction in factions:
        if faction in prompt:
            return faction
        # Try case-insensitive match without spaces
        if faction.lower().replace(" ", "") in prompt.lower().replace(" ", ""):
            return faction

    # Check for map mentions
    for map_name in maps:
        if map_name in prompt:
            return map_name

    # Check for faction codes (FM, PRM, DGT, CS, etc)
    faction_code_map = {
        "FM": "Fleshmason",
        "PRM": "Permeation",
        "DGT": "Tribulation",
        "CS": "Colour Out of Space",
        "ST3": "Scroll Test Faction"
    }

    for code, faction in faction_code_map.items():
        if f'"{code}"' in prompt or f"({code})" in prompt or f" {code} " in prompt:
            return faction

    # Check for specific unit/entity names that might indicate a design
    if "Acolyte" in prompt or "Meteorite" in prompt:
        return "Colour Out of Space"

    return None

def main():
    print("Fetching terminal log entries...")
    entries = fetch_terminal_log()

    print(f"Total entries: {len(entries)}")

    # Find designer entries (user != "admin")
    designer_entries = [e for e in entries if e.get("user") != "admin"]
    print(f"Designer entries: {len(designer_entries)}")

    # Find entries with missing/empty designObject
    missing = []
    for entry in designer_entries:
        design_obj = entry.get("designObject", "")
        # Check if empty or just the user name (which is wrong)
        if not design_obj or design_obj == entry.get("user"):
            missing.append(entry)

    print(f"Entries with missing/empty designObject: {len(missing)}")

    if not missing:
        print("✓ All designer entries have designObject populated!")
        return

    # Try to fix each one
    fixed = 0
    could_not_determine = []

    for entry in missing:
        entry_id = entry["id"]
        user = entry.get("user", "")
        prompt = entry.get("prompt", "")

        # Try to extract design name
        design_name = extract_design_from_prompt(prompt, user)

        if design_name:
            print(f"\nEntry {entry_id} (user: {user})")
            print(f"  Detected design: {design_name}")
            print(f"  Prompt preview: {prompt[:100]}...")

            try:
                update_entry(entry_id, design_name)
                print(f"  ✓ Updated")
                fixed += 1
            except Exception as e:
                print(f"  ✗ Failed to update: {e}")
        else:
            could_not_determine.append({
                "id": entry_id,
                "user": user,
                "prompt": prompt[:200]
            })

    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Total designer entries: {len(designer_entries)}")
    print(f"  Entries missing designObject: {len(missing)}")
    print(f"  Successfully fixed: {fixed}")
    print(f"  Could not determine: {len(could_not_determine)}")

    if could_not_determine:
        print(f"\nEntries I couldn't determine design for:")
        for item in could_not_determine:
            print(f"\n  ID: {item['id']}")
            print(f"  User: {item['user']}")
            print(f"  Prompt: {item['prompt']}...")

if __name__ == "__main__":
    main()
