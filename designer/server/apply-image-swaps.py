#!/usr/bin/env python3
"""
Apply image swaps from the designer to the homebrew build.
This script is called during deployment to copy swapped images to the build's webp/images folder.

Usage:
  ./apply-image-swaps.py <faction-id> <homebrew-build-path>

Example:
  ./apply-image-swaps.py f_abc123 /Users/gremus/Claude-Projects/cw-homebrew-wt/solo
"""

import sys
import shutil
from pathlib import Path


def apply_image_swaps(faction_id: str, build_path: str) -> bool:
    """Copy image swaps from designer to build. Returns True if any swaps were applied."""
    designer_root = Path(__file__).parent.parent
    data_dir = designer_root / "data"
    faction_dir = data_dir / "factions" / faction_id

    swaps_dir = faction_dir / "imageSwaps"
    if not swaps_dir.exists():
        return False

    build_images_dir = Path(build_path) / "webp" / "images"
    if not build_images_dir.exists():
        print(f"ERROR: Build images directory not found: {build_images_dir}", file=sys.stderr)
        return False

    swapped_count = 0
    for swap_file in swaps_dir.iterdir():
        if not swap_file.is_file():
            continue

        dest = build_images_dir / swap_file.name
        try:
            shutil.copy2(swap_file, dest)
            print(f"Swapped: {swap_file.name}")
            swapped_count += 1
        except Exception as e:
            print(f"ERROR copying {swap_file.name}: {e}", file=sys.stderr)
            return False

    return swapped_count > 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    faction_id = sys.argv[1]
    build_path = sys.argv[2]

    if apply_image_swaps(faction_id, build_path):
        print(f"Image swaps applied for {faction_id}")
        sys.exit(0)
    else:
        print(f"No image swaps found for {faction_id}")
        sys.exit(0)
