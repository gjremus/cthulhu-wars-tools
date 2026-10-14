# Populate Simple Update for FM, PRM, DGT Factions

## Quick Summary

This folder contains two scripts to populate the **Simple Update** section with image swap rows for three new factions: Fleshmason (FM), Permeation (PRM), and Tribulation (DGT).

After running these scripts, designers will see pre-populated image swap rows in the designer UI under **Faction → Simple Update → Quick Image Swap** section.

## Files

- **`populate-simple-update.py`** - File-system based approach (direct data modification)
- **`populate-simple-update-api.py`** - API-based approach (works remotely via HTTP)
- **`POPULATE_SIMPLE_UPDATE_GUIDE.md`** - Detailed guide with troubleshooting

## Quick Start

### Option A: Direct File Modification (SSH Access Required)

If you have SSH access to the production server:

```bash
# Copy script to server
scp populate-simple-update.py cwo-admin@design-vm.example.com:/tmp/

# SSH into server and run
ssh cwo-admin@design-vm.example.com
cd /opt/cwo/designer
python3 /tmp/populate-simple-update.py

# Or if not in default location
python3 populate-simple-update.py --data-dir /opt/cwo/designer/data
```

### Option B: API-Based Approach (No Direct Access Required)

If you don't have SSH access but have an admin token:

```bash
python3 populate-simple-update-api.py \
  --server https://cwo.freeddns.org/designer \
  --token YOUR_ADMIN_TOKEN
```

## What Gets Added

For each faction (FM, PRM, DGT), the following image swap rows are added:

- Glyph (symbol)
- Card (faction card image)
- Spellbooks (spellbook reference)
- Acolyte (cultist image)
- High Priest (if applicable)
- Custom units (specific to each faction)

Example rows:
- `fm-glyph.webp` → empty, ready for image upload
- `fm-card.webp` → empty, ready for image upload
- `fm-bone-sculptor.webp` → empty, ready for image upload
- etc.

## Verification

After running the script:

1. Log into the Faction Designer with admin token
2. Open faction: FM, PRM, or DGT
3. Click **Build** (if needed)
4. Click **Simple Update**
5. Scroll to **Quick Image Swap** section
6. Verify all expected rows appear with empty filenames

## Next Steps

Once rows are populated, designers can:

1. **Add Image**: Click "Upload" to select a replacement image file
2. **Deploy**: Click "Deploy" to push the swap to the live build
3. **Verify**: Check that the image appears in the game

## Troubleshooting

### "Could not find faction with acronym FM"
- Verify faction exists: Log into designer, check FM/PRM/DGT are present
- Check acronyms are exactly: `FM`, `PRM`, `DGT` (case-sensitive)

### "Could not connect to server"  
- Verify server URL: Should be `https://cwo.freeddns.org/designer` or local IP
- Check admin token: Verify token is valid and hasn't expired
- Network access: Confirm you can reach the server

### "Permission denied" when running with file approach
- Verify user has write permissions: `ls -la /opt/cwo/designer/data/factions`
- Check script is executable: `chmod +x populate-simple-update.py`
- Run as correct user: `sudo -u cwo-user python3 populate-simple-update.py`

## Technical Details

### File-based Script
- Directly modifies `faction.json` files
- Requires file system access
- More efficient for bulk operations
- Changes are immediate

### API-based Script
- Uses designer HTTP API
- Works over network
- Requires authentication token
- Better for remote/CI automation

## Related Documentation

- [QUICKSTART_IMAGE_SWAPS.md](QUICKSTART_IMAGE_SWAPS.md) - Image swap UI walkthrough
- [IMAGE_SWAPS.md](IMAGE_SWAPS.md) - Technical details
- [POPULATE_SIMPLE_UPDATE_GUIDE.md](POPULATE_SIMPLE_UPDATE_GUIDE.md) - Detailed guide

## Support

For issues:

1. Check troubleshooting section above
2. Verify faction exists and has acronym set correctly
3. Ensure data directory path is correct
4. Check file permissions in data directory
5. Review server logs: `/var/log/designer-server.log`

## Code Review

The scripts follow these principles:

- **Idempotent**: Safe to run multiple times
- **Atomic**: Uses atomic writes to prevent corruption
- **Validated**: Checks for existing rows before adding
- **Logged**: Clear output shows what was added
- **Error-handling**: Graceful failure with helpful messages
