# Populating Simple Update Sections for FM, PRM, and DGT

This guide explains how to populate the "Simple Update" section with image swap rows for the three new factions: Fleshmason (FM), Permeation (PRM), and Tribulation (DGT).

## Overview

The **Simple Update** feature in the Faction Designer allows quick image swaps without rebuilding. To enable designers to use this feature, we need to pre-populate the image swap rows in each faction's design file.

This script automates that process by adding all required image swap rows to the faction design JSON files.

## What Gets Added

For each faction, the following image swap rows are added:

### FM (Fleshmason)
- `fm-glyph.webp` - faction symbol
- `fm-card.webp` - faction card
- `fm-spellbooks.webp` - spellbook reference
- `fm-acolyte.webp` - cultist image
- `fm-high-priest.webp` - high priest image
- `fm-bone-sculptor.webp` - custom unit
- `fm-muscle-stitcher.webp` - custom unit
- `fm-body-architect.webp` - custom unit
- `fm-screaming-wall.webp` - custom unit

### PRM (Permeation)
- `prm-glyph.webp` - faction symbol
- `prm-card.webp` - faction card
- `prm-spellbooks.webp` - spellbook reference
- `prm-acolyte.webp` - cultist image
- `prm-astral-egg.webp` - custom unit
- `prm-celestial-fledgling.webp` - custom unit
- `prm-ycgnagnnisssz.webp` - custom unit

### DGT (Tribulation)
- `dgt-glyph.webp` - faction symbol
- `dgt-card.webp` - faction card
- `dgt-spellbooks.webp` - spellbook reference
- `dgt-acolyte.webp` - cultist image
- `dgt-conquest.webp` - custom unit
- `dgt-pestilence.webp` - custom unit
- `dgt-war.webp` - custom unit
- `dgt-famine.webp` - custom unit
- `dgt-death.webp` - custom unit

## How to Use

### Option 1: Run Locally (with remote data access)

If you have SSH access to the production server:

```bash
# Option A: Run directly on the server
ssh cwo-admin@design-vm.example.com
cd /opt/cwo/designer
python3 populate-simple-update.py

# Option B: Copy script to server, run it, then copy results back
scp populate-simple-update.py cwo-admin@design-vm.example.com:/opt/cwo/designer/
ssh cwo-admin@design-vm.example.com "cd /opt/cwo/designer && python3 populate-simple-update.py"
```

### Option 2: Specify Custom Data Directory

If the data is stored in a non-standard location:

```bash
python3 populate-simple-update.py --data-dir /path/to/custom/data
```

### Option 3: Local Development/Testing

For local testing with development data:

```bash
# Create local dev data structure (optional)
mkdir -p dev/data/factions

# Run script against local data
python3 populate-simple-update.py --data-dir ./dev/data
```

## Script Output

When successful, the script will output:

```
Using data directory: /opt/cwo/designer/data
============================================================

Processing FM...
  Found faction ID: f_abc123def
  Added 9 image swap rows
  Saved updated faction data

Processing PRM...
  Found faction ID: f_xyz789pqr
  Added 7 image swap rows
  Saved updated faction data

Processing DGT...
  Found faction ID: f_tuv456ghi
  Added 9 image swap rows
  Saved updated faction data

============================================================
SUCCESS: All factions updated
```

## Verification

After running the script:

1. Log into the Faction Designer (admin console with token)
2. Navigate to each faction: FM, PRM, DGT
3. Click **Build** (if not already built)
4. Click **Simple Update**
5. Scroll to **Quick Image Swap** section
6. Verify that all expected rows are present with empty filenames
7. Designers can now upload images and deploy swaps

## What the Script Does

1. **Finds each faction** by acronym (FM, PRM, DGT) in the data directory
2. **Loads the faction design file** (`faction.json`)
3. **Initializes imageSwaps structure** if not present:
   ```json
   {
     "design": {
       "imageSwaps": {
         "rows": []
       }
     }
   }
   ```
4. **Adds image swap rows** for each filename:
   ```json
   {
     "filename": "fm-glyph.webp",
     "imageId": null
   }
   ```
5. **Saves the updated faction file** atomically

## Idempotency

The script is idempotent:
- If run multiple times, it won't duplicate rows
- Existing rows with the same filename are skipped
- Safe to run without worry of data corruption

## Troubleshooting

### "Could not find faction with acronym FM"

**Problem**: The faction doesn't exist in the data directory.

**Solution**:
1. Verify the faction has been created in the designer
2. Check that acronyms are exactly: FM, PRM, DGT (case-sensitive)
3. Verify data directory is correct with: `ls -la /opt/cwo/designer/data/factions`

### "Could not load faction file"

**Problem**: The faction.json file is corrupted or missing.

**Solution**:
1. Check file permissions: `ls -la /opt/cwo/designer/data/factions/<faction-id>/faction.json`
2. Verify JSON is valid: `python3 -m json.tool faction.json`
3. Restore from backup if necessary

### Script not finding data directory

**Problem**: `/opt/cwo/designer/data` doesn't exist.

**Solution**:
1. Find the correct data directory: `grep "data_dir" /etc/systemd/system/designer.service`
2. Run with correct path: `python3 populate-simple-update.py --data-dir /actual/path`
3. Or check server startup logs for the configured path

## Integration with Deployment

After running this script, the image swap rows will be available in the Simple Update section. When designers deploy image swaps:

1. Rows will be populated with images through the UI
2. Each deploy creates an entry in the request log
3. During `deploy-homebrew-to-vm.sh --assets`, the `apply-image-swaps.py` script will copy swapped images to the build

## File Location

The script is located at:
```
/Users/gremus/Claude-Projects/cthulhu-wars-tools/designer/populate-simple-update.py
```

Or on the production server:
```
/opt/cwo/designer/populate-simple-update.py
```

## Related Files

- **UI Handler**: `designer/www/app.js` (renderSimpleUpdateImageSwaps)
- **Server API**: `designer/server/designer_server.py` (handle_image_swap_push)
- **Deploy Helper**: `designer/server/apply-image-swaps.py`
- **Quickstart Guide**: `designer/QUICKSTART_IMAGE_SWAPS.md`
