# DGT (Tribulation) Build Verification Task

## Overview
The DGT (Dread God Tribulation) faction requires careful setup to ensure its 4 dual-sided spellbooks are properly flagged with `twoSided=true`. This enables the spellbook guidance system to work correctly and provide Claude with proper context during the build process.

## Dual-Sided Spellbooks
DGT has 4 dual-sided spellbook pairs that need the `twoSided=true` flag:

1. **Mayhem** ↔ **Gods' Plague**
2. **Ruin** ↔ **Gods' Sword**
3. **Rampage** ↔ **Gods' Scale**
4. **Despair** ↔ **Gods' Hand**

## Flag Requirements
Each spellbook row in the design must have:
- `twoSided: true` - Indicates this spellbook has alternate sides
- (Optional) `dual: true` - If side A has multiple powers
- (Optional) `dualB: true` - If side B has multiple powers

## Verification Script
Run the verification script to check and fix the flags:

```bash
python3 /Users/gremus/Claude-Projects/cthulhu-wars-tools/verify-dgt-spellbook-flags.py
```

This script will:
1. Fetch DGT faction design from remote designer server
2. Check if all 4 dual-sided spellbooks have `twoSided=true`
3. If missing, automatically add the flags
4. Upload the corrected design
5. Compute and display spellbook guidance for Claude

## Design Structure
The faction design JSON has this structure:

```json
{
  "sb": {
    "twoSided": false,  # Section-level flag (not used for individual spellbooks)
    "rows": [
      {
        "id": "...",
        "name": "Mayhem",
        "nameB": "Gods' Plague",
        "twoSided": true,  # ← THIS FLAG MUST BE SET
        "dual": false,     # Multi-power on side A
        "dualB": false,    # Multi-power on side B
        "type": "...",
        "typeB": "...",
        "cost": 3,
        "costB": 3,
        ...
      }
    ]
  }
}
```

## Spellbook Guidance System
When `twoSided=true` is detected on spellbooks, the designer server:

1. **DETECTION**: Computes `spellbookGuidance` field via `compute_spellbook_guidance()`
2. **UI DISPLAY**: Shows "Guidance for Claude" section in designer when multi-sided detected
3. **CLAUDE RECEIVES**: 
   - Design JSON includes `spellbookGuidance` field
   - Admin queue agent includes guidance in build prompt
   - Claude receives proper context for implementation

## Guidance Content
For DGT with dual-sided spellbooks, Claude receives:

```
MULTI-SIDED SPELLBOOKS:
- 2 sides with powers = 2 connected spellbooks, not 2 independent ones
- Sides are swapped per that spellbook's rules, not taken independently
- "Face down" sides: use Dragon Ascending (one-time) or Daemon Sultans (Doom Phase recharge) as templates
- A 3rd "face down" side: use as one-time block OR determine recharge rules (Side A or B)
```

## Build Queue Status
DGT is currently queued for rebuild at commit 74fbf916 with the message:
```
MAP-BUILD: dgt from commit 74fbf916 (Spellbook guidance application: dual-sided spellbooks marked, guidance embedded for Claude)
```

## Next Steps

1. **Verify Flags** - Run the verification script to ensure all flags are correct
2. **Submit Build** - Build request will be automatically queued when submitted
3. **Track Progress** - Admin queue will process the build request
4. **Confirm Build** - Check game logs and console after deployment to verify spellbooks work correctly

## Technical Details

### API Endpoints
- Fetch: `GET /designer/api/factions/46lllknws5qi`
- Submit Build: `POST /designer/api/factions/46lllknws5qi/request` with `type=build`

### Key Files
- Verification script: `verify-dgt-spellbook-flags.py`
- Designer server: `designer/server/designer_server.py`
- Guidance computation: `compute_spellbook_guidance()` function
- Admin queue: `tickers/prompt-admin-queue-system.txt`

### Important Notes
- The `twoSided` flag is per-spellbook, not per-faction
- Maximum 6 spellbook slots on faction card (including multi-sided pairs)
- Each side of a dual-sided spellbook is ONE spellbook slot
- If a spellbook has both `dual=true` AND `twoSided=true`, it has multi-power on BOTH sides

## Troubleshooting

**Script times out connecting to remote:**
- Check SSH access: `ssh cwo echo "test"`
- Verify designer data path exists on remote
- Try manual fetch: `ssh cwo cat /opt/cwo/designer/data/factions/46lllknws5qi/faction.json`

**Guidance not appearing in designer UI:**
- Ensure at least one row has `twoSided=true`
- Hard refresh browser cache
- Check browser console for errors

**Build not progressing:**
- Check admin queue status at `/admin/requests` endpoint
- Look for build status in faction's `build` field: `status`, `requestedAt`, `builtAt`
- Check game logs for errors during build

## References
- Spellbook guidance implementation: See `compute_spellbook_guidance()` in designer_server.py lines 46-89
- Dragon Ascending template: Reference for one-time use power mechanics
- Daemon Sultans template: Reference for Doom Phase recharge mechanics
