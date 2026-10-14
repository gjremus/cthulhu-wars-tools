#!/usr/bin/env python3
"""
Verify and fix DGT dual-sided spellbook flags.

This script verifies that DGT's 4 dual-sided spellbooks have the `twoSided=true` flag set:
1. Mayhem <-> Gods' Plague
2. Ruin <-> Gods' Sword
3. Rampage <-> Gods' Scale
4. Despair <-> Gods' Hand

The twoSided flag is critical for:
- Proper UI display in the designer ("Guidance for Claude" section)
- Correct guidance computation for multi-sided spellbooks
- Ensuring Claude understands these are connected spellbook pairs
"""
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

DGT_FID = "46lllknws5qi"

# DGT's 4 dual-sided spellbook pairs
DUAL_SIDED_PAIRS = [
    ("Mayhem", "Gods' Plague"),
    ("Ruin", "Gods' Sword"),
    ("Rampage", "Gods' Scale"),
    ("Despair", "Gods' Hand"),
]


def fetch_faction_from_remote(fid: str, remote_host: str = "cwo") -> Optional[Dict]:
    """Fetch faction design from remote designer server."""
    try:
        result = subprocess.run(
            f"ssh {remote_host} cat /opt/cwo/designer/data/factions/{fid}/faction.json",
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            print(f"Error fetching faction: {result.stderr}")
            return None
    except subprocess.TimeoutExpired:
        print(f"Timeout fetching faction from {remote_host}")
        return None
    except Exception as e:
        print(f"Exception fetching faction: {e}")
        return None


def check_spellbook_flags(faction: Dict) -> tuple[bool, List[str]]:
    """
    Check if all dual-sided spellbooks have twoSided=true.

    Returns: (all_correct, issues)
    """
    sb_rows = faction.get("sb", {}).get("rows", [])
    issues = []
    all_correct = True

    # Map all spellbook names to their rows
    spellbook_map = {}
    for i, row in enumerate(sb_rows):
        name = row.get("name", "").strip()
        if name:
            spellbook_map[name.lower()] = (i, row)

    # Check each dual-sided pair
    for side_a, side_b in DUAL_SIDED_PAIRS:
        side_a_lower = side_a.lower()
        side_b_lower = side_b.lower()

        if side_a_lower not in spellbook_map:
            issues.append(f"Missing spellbook: {side_a}")
            all_correct = False
            continue

        idx_a, row_a = spellbook_map[side_a_lower]
        if not row_a.get("twoSided"):
            issues.append(f"Row {idx_a}: {side_a} missing twoSided=true")
            all_correct = False

        if side_b_lower not in spellbook_map:
            issues.append(f"Missing spellbook: {side_b}")
            all_correct = False
            continue

        idx_b, row_b = spellbook_map[side_b_lower]
        if not row_b.get("twoSided"):
            issues.append(f"Row {idx_b}: {side_b} missing twoSided=true")
            all_correct = False

    return all_correct, issues


def fix_spellbook_flags(faction: Dict) -> bool:
    """Add twoSided=true to dual-sided spellbooks. Returns True if changes made."""
    sb_rows = faction.get("sb", {}).get("rows", [])
    changes_made = False

    # Collect all spellbook names
    spellbook_map = {}
    for i, row in enumerate(sb_rows):
        name = row.get("name", "").strip()
        if name:
            spellbook_map[name.lower()] = (i, row)

    # Add twoSided flag to dual-sided spellbooks
    for side_a, side_b in DUAL_SIDED_PAIRS:
        for side_name in [side_a, side_b]:
            side_lower = side_name.lower()
            if side_lower in spellbook_map:
                idx, row = spellbook_map[side_lower]
                if not row.get("twoSided"):
                    print(f"  Setting twoSided=true for: {side_name}")
                    row["twoSided"] = True
                    changes_made = True
                else:
                    print(f"  Already has twoSided=true: {side_name}")

    return changes_made


def upload_faction_to_remote(faction: Dict, fid: str, remote_host: str = "cwo") -> bool:
    """Upload updated faction to remote designer server."""
    faction_json = json.dumps(faction, indent=2)
    try:
        result = subprocess.run(
            f"""ssh {remote_host} 'cat > /opt/cwo/designer/data/factions/{fid}/faction.json' << 'EOF'
{faction_json}
EOF""",
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print("Faction uploaded successfully")
            return True
        else:
            print(f"Error uploading faction: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"Timeout uploading faction to {remote_host}")
        return False
    except Exception as e:
        print(f"Exception uploading faction: {e}")
        return False


def compute_spellbook_guidance(faction: Dict) -> str:
    """Compute spellbook guidance for Claude (mirrors server logic)."""
    sb = faction.get("sb", {})
    rows = sb.get("rows", [])

    has_multi_sided = any(row.get("twoSided") for row in rows)
    has_multi_power = False
    for row in rows:
        if row.get("dual"):
            has_multi_power = True
            break
        if row.get("twoSided") and row.get("dualB"):
            has_multi_power = True
            break

    if not has_multi_power and not has_multi_sided:
        return ""

    guidance = ""
    if has_multi_power:
        guidance += "MULTI-POWER SPELLBOOKS:\n"
        guidance += "- Spellbooks with multiple powers on 1 side are a single spellbook\n"
        guidance += "- Completing a single SBR can earn you a SB with 2 powers—still ONE spellbook\n"
        guidance += "- Both powers are earned/blocked/copied together\n"
        guidance += "- Max 6 SBR/SB slots on faction card (unless explicitly told otherwise)\n"
        guidance += "- Spellbook overlays must describe BOTH powers\n"
        guidance += "- Moonbeast blocking a 2-power spellbook blocks BOTH powers\n"

    if has_multi_sided:
        if has_multi_power:
            guidance += "\n"
        guidance += "MULTI-SIDED SPELLBOOKS:\n"
        guidance += "- 2 sides with powers = 2 connected spellbooks, not 2 independent ones\n"
        guidance += "- Sides are swapped per that spellbook's rules, not taken independently\n"
        guidance += "- \"Face down\" sides: use Dragon Ascending (one-time) or Daemon Sultans (Doom Phase recharge) as templates\n"
        guidance += "- A 3rd \"face down\" side: use as one-time block OR determine recharge rules (Side A or B)\n"

    return guidance


def main():
    print(f"DGT Spellbook Flag Verification and Fix")
    print(f"Faction ID: {DGT_FID}")
    print(f"=" * 60)
    print()

    print("Fetching DGT faction from remote server...")
    faction = fetch_faction_from_remote(DGT_FID)

    if not faction:
        print("ERROR: Could not fetch faction. Ensure:")
        print("- Remote SSH access to 'cwo' host is configured")
        print("- Designer data is at /opt/cwo/designer/data/factions/{}/faction.json".format(DGT_FID))
        return 1

    print()
    print("Current spellbooks:")
    for i, row in enumerate(faction.get("sb", {}).get("rows", [])):
        name = row.get("name", "").strip()
        if name:
            ts = " [twoSided=true]" if row.get("twoSided") else " [twoSided=false/missing]"
            print(f"  Row {i}: {name}{ts}")
    print()

    # Check current state
    all_correct, issues = check_spellbook_flags(faction)

    if all_correct:
        print("SUCCESS: All dual-sided spellbooks have twoSided=true!")
        print()
    else:
        print("ISSUES FOUND:")
        for issue in issues:
            print(f"  - {issue}")
        print()

        print("Fixing spellbook flags...")
        if fix_spellbook_flags(faction):
            print()
            print("Uploading fixed faction...")
            if not upload_faction_to_remote(faction, DGT_FID):
                return 1
        else:
            print("No changes needed.")

    print()
    print("Computing spellbook guidance...")
    guidance = compute_spellbook_guidance(faction)
    if guidance:
        print("Guidance detected:")
        print("---")
        for line in guidance.split("\n"):
            print(f"  {line}")
        print("---")
    else:
        print("(No multi-power or multi-sided spellbooks detected)")

    print()
    print("DGT faction is ready for build submission.")
    print()
    print("Next steps:")
    print("1. Submit build request from designer interface")
    print("2. Admin queue will pick up the faction")
    print("3. Claude will receive spellbook guidance during build")

    return 0


if __name__ == "__main__":
    exit(main())
