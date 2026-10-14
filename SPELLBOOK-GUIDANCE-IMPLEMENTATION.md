# Spellbook Guidance Implementation — Complete

## Summary

A comprehensive spellbook guidance system has been implemented and deployed for the faction designer system. This system automatically detects multi-power and multi-sided spellbooks and provides Claude with proper context during faction builds.

## What Was Implemented

### 1. **Spellbook Guidance Detection & Computation**

**Location**: `designer/server/designer_server.py` (lines 46-89)

The `compute_spellbook_guidance()` function:
- Detects multi-power spellbooks (when `dual=true` or `dualB=true`)
- Detects multi-sided spellbooks (when `twoSided=true`)
- Generates appropriate guidance text for each type
- Returns empty string if neither type is detected

**Key Flags**:
- `dual=true` — Multiple powers on side A of a spellbook
- `dualB=true` — Multiple powers on side B of a spellbook
- `twoSided=true` — Spellbook has two swappable sides with powers

### 2. **Designer UI Integration**

**Location**: `designer/www/sections.js` (lines 1367-1404)

The frontend renders a "Guidance for Claude" section when applicable:
- Conditionally displayed only when multi-power or multi-sided spellbooks are detected
- Formatted with clear sections for each guidance type
- Styled with distinctive background color (#f9f3e6) for visibility

**UI Display**:
```
┌─────────────────────────────────────────┐
│ Guidance for Claude                     │
├─────────────────────────────────────────┤
│ Multi-Power Spellbooks:                 │
│ • Spellbooks with multiple powers...    │
│ • Completing a single SBR can earn...   │
│ ...                                     │
│                                         │
│ Multi-Sided Spellbooks:                 │
│ • 2 sides with powers = 2 connected...  │
│ ...                                     │
└─────────────────────────────────────────┘
```

### 3. **API Response Integration**

**Location**: `designer/server/designer_server.py` (line 2264)

When Claude requests a faction design via `GET /designer/api/factions/<fid>`, the response includes:

```json
{
  "design": {
    "sb": { ... },
    "spellbookGuidance": "MULTI-SIDED SPELLBOOKS:\n- 2 sides with powers = 2 connected spellbooks..."
  }
}
```

The `spellbookGuidance` field is automatically populated and sent to Claude during build requests.

### 4. **Admin Queue Integration**

**Location**: `tickers/prompt-admin-queue-system.txt` (lines 121-150)

The admin queue system:
- Documents that guidance is automatically computed
- Explains how to detect and flag spellbooks
- Provides specific guidance for DGT's dual-sided structure
- Links to code templates (Dragon Ascending, Daemon Sultans)

### 5. **DGT-Specific Implementation**

**Location**: `verify-dgt-spellbook-flags.py` & `DGT-BUILD-SETUP.md`

Created verification and documentation tools for DGT:
- **Verification script** (`verify-dgt-spellbook-flags.py`):
  - Fetches DGT faction from remote designer
  - Checks all 4 dual-sided spellbooks for `twoSided=true`
  - Auto-fixes missing flags
  - Computes and displays guidance
  - Uploads corrected design

- **Documentation** (`DGT-BUILD-SETUP.md`):
  - Overview of DGT's 4 dual-sided pairs
  - Flag requirements and design structure
  - Explanation of guidance system
  - Step-by-step troubleshooting

## DGT Spellbook Structure

DGT has **14 total spellbook entries** (10 unique + 1 ability):

### Single-Sided (6 spellbooks):
1. The White Rider — Requirement-based trigger
2. The Red Rider — Requirement-based trigger
3. The Black Rider — Requirement-based trigger
4. The Pale Rider — Requirement-based trigger
5. The Martyr's Cry — Action power
6. The Cosmic Chaos — Action power

### Dual-Sided Pairs (4 × 2 = 8 spellbooks):
1. **Mayhem** ↔ **God's Plague**
2. **Ruin** ↔ **God's Sword** (Red Rider +3 combat / +9 with this)
3. **Rampage** ↔ **God's Scale**
4. **Despair** ↔ **God's Hand**

### Unique Ability:
- **Dominion** (always-on)

**Total Slots on Faction Card**: 6 SBR slots = 6 single-sided + 4 dual-sided pairs (4 × 2 = 8 total, but 4 pairs = 4 slots when paired)

## Guidance Claude Receives

When Claude processes a DGT build, it receives:

```
MULTI-SIDED SPELLBOOKS:
- 2 sides with powers = 2 connected spellbooks, not 2 independent ones
- Sides are swapped per that spellbook's rules, not taken independently
- "Face down" sides: use Dragon Ascending (one-time) or Daemon Sultans (Doom Phase recharge) as templates
- A 3rd "face down" side: use as one-time block OR determine recharge rules (Side A or B)
```

This guidance ensures Claude:
1. Treats dual-sided pairs as connected, not independent spellbooks
2. Uses proper code templates for flip mechanics
3. Understands max 6 SBR/SB slot constraint
4. Implements correct recharge logic

## Build Process Flow

```
1. Designer opens DGT faction
   ↓
2. Frontend detects twoSided=true flags
   ↓
3. "Guidance for Claude" section renders
   ↓
4. Designer submits build request
   ↓
5. Admin queue fetches faction via API
   ↓
6. compute_spellbook_guidance() runs
   ↓
7. Claude receives guidance in design JSON
   ↓
8. Claude builds with proper understanding
   ↓
9. Overlays show both sides correctly
   ↓
10. Code uses Dragon Ascending / Daemon Sultans patterns
```

## Files Modified

### Core Implementation
- `designer/server/designer_server.py` — Guidance computation + API response
- `designer/www/sections.js` — UI rendering
- `designer/www/rules.js` — Client-side mirror logic

### Documentation & Tools
- `tickers/prompt-admin-queue-system.txt` — Admin queue documentation
- `verify-dgt-spellbook-flags.py` — Verification script for DGT
- `DGT-BUILD-SETUP.md` — Setup guide for DGT

## Git Commits

1. `f0257db` — Add spellbook guidance to faction designer
2. `2676d06` — Queue DGT rebuild: apply spellbook guidance
3. `8ec0dfd` — Document spellbook guidance integration
4. `ac8e083` — Add DGT verification script and documentation

## How to Use

### For Designers
1. Open faction in designer
2. Check "Guidance for Claude" section when designing dual-sided spellbooks
3. Set `twoSided=true` flag for spellbook pairs
4. Submit build — guidance automatically included

### For DGT Rebuild
```bash
python3 verify-dgt-spellbook-flags.py
```

This script will:
1. Check all DGT dual-sided spellbooks
2. Fix any missing `twoSided=true` flags
3. Compute and display guidance
4. Prepare faction for build

### For Admin Queue
Guidance is automatically included when processing builds:
- Detect `twoSided=true` flags in faction design
- Compute guidance via `compute_spellbook_guidance()`
- Include in build prompt sent to Claude
- Claude implements with proper understanding

## Key Constraints

- **Max 6 SBR/SB slots** on faction card (dual-sided pairs each = 1 slot)
- **Multi-sided = connected**: Both sides must respect the spellbook's swap rules
- **Code templates**: Dragon Ascending (one-time), Daemon Sultans (Doom Phase recharge)
- **Overlays**: Must show both sides clearly
- **Moonbeast blocking**: Blocks all powers on a multi-power spellbook

## Status

✅ **System Complete and Operational**

- Spellbook detection working
- UI rendering complete
- API integration live
- Admin queue ready
- DGT verification tools created
- All changes committed to git
- Ready for production use

## Next Steps

1. Run DGT verification script to confirm flags
2. Submit DGT build request
3. Monitor admin queue for processing
4. Verify overlays and mechanics in game
5. Confirm guidance was properly applied

## References

- **Dragon Ascending**: One-time use power template
- **Daemon Sultans**: Doom Phase recharge template
- **Recriminations**: Neutral swappable spellbook reference
- **Admin Queue**: `/admin/factions/` endpoint
- **Designer API**: `/designer/api/factions/<fid>` endpoint
