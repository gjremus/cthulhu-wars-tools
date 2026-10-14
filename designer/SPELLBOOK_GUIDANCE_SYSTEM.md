# Spellbook Guidance System for Claude

**Status**: ✅ COMPLETE AND OPERATIONAL  
**Last Verified**: 2026-10-14

This document describes the integrated spellbook guidance system that embeds multi-power and multi-sided spellbook instructions into faction designs for Claude to read during builds.

## System Overview

### What It Does

When a faction has multi-power or multi-sided spellbooks:

1. **Designer UI** displays "Guidance for Claude" section to show designers what Claude will see
2. **Backend** computes guidance text based on `dual` and `twoSided` flags
3. **API** transmits guidance to Claude whenever:
   - Faction is fetched for viewing
   - Faction is fetched for building
   - Design is submitted for build/bug-fix/extraction
4. **Admin Queue** includes guidance in build prompt so Claude understands the spellbook mechanics

### How It Works

```
Designer sets flags:          backend detects:         Claude receives:
┌─────────────────┐          ┌──────────────────┐     ┌──────────────────┐
│ dual=true       │──────────│ has_multi_power  │────►│ MULTI-POWER      │
│ (2+ powers      │          │                  │     │ SPELLBOOKS:      │
│  on side A)     │          │ Generates text   │     │ - Single SBR = 1 │
└─────────────────┘          │ for each mode    │     │   SB with 2      │
┌─────────────────┐          │                  │     │   powers         │
│ twoSided=true   │──────────│ has_multi_sided  │────►│ MULTI-SIDED      │
│ (2 swappable    │          │                  │     │ SPELLBOOKS:      │
│  sides with     │          │                  │     │ - 2 sides =      │
│  powers)        │          │                  │     │   2 connected    │
└─────────────────┘          └──────────────────┘     │   SBs not 1+1    │
                                                      └──────────────────┘
```

## Implementation Details

### Designer UI (sections.js:1367-1404)

```javascript
// Checks both multi-power and multi-sided conditions
if (hasMultiPower || hasMultiSided) {
  // Render "Guidance for Claude" box
  // Show Multi-Power guidance if hasMultiPower=true
  // Show Multi-Sided guidance if hasMultiSided=true
}
```

**Visible to**: Designer viewing the faction (read-only info)

### Backend Computation (designer_server.py:46-89)

```python
def compute_spellbook_guidance(design: Dict) -> str:
    # Check flags on all spellbook rows
    has_multi_power = any(row.get('dual') or 
                          (row.get('twoSided') and row.get('dualB')))
    has_multi_sided = any(row.get('twoSided'))
    
    # Build guidance text
    if has_multi_power:
        guidance += "MULTI-POWER SPELLBOOKS:\n..."
    if has_multi_sided:
        guidance += "MULTI-SIDED SPELLBOOKS:\n..."
    
    return guidance
```

**Called by**: 
- `GET /designer/api/factions/<fid>` (get_faction)
- QA data fetch endpoints

### API Transmission (designer_server.py:line ~400)

```python
# In get_faction() handler
if "design" in response:
    response["design"]["spellbookGuidance"] = compute_spellbook_guidance(response["design"])
self.send_json(response)
```

**Result**: Design JSON includes `spellbookGuidance` field

**Transmitted to Claude by**: Admin queue agent when processing build request

## Guidance Content

### Multi-Power Spellbooks (when `dual=true`)

```
MULTI-POWER SPELLBOOKS:
- Spellbooks with multiple powers on 1 side are a single spellbook
- Completing a single SBR can earn you a SB with 2 powers—still ONE spellbook
- Both powers are earned/blocked/copied together
- Max 6 SBR/SB slots on faction card (unless explicitly told otherwise)
- Spellbook overlays must describe BOTH powers
- Moonbeast blocking a 2-power spellbook blocks BOTH powers
```

**When to show**: At least one spellbook row has `dual=true`

### Multi-Sided Spellbooks (when `twoSided=true`)

```
MULTI-SIDED SPELLBOOKS:
- 2 sides with powers = 2 connected spellbooks, not 2 independent ones
- Sides are swapped per that spellbook's rules, not taken independently
- "Face down" sides: use Dragon Ascending (one-time) or Daemon Sultans (Doom Phase recharge) as templates
- A 3rd "face down" side: use as one-time block OR determine recharge rules (Side A or B)
```

**When to show**: At least one spellbook row has `twoSided=true`

## DGT Example (Current Implementation)

**Design ID**: `46lllknws5qi`

### Spellbook Rows

```
1. The White Rider ↔ God's Plague
   - dual=true, twoSided=true
   - Shows both guidance sections

2. The Red Rider ↔ God's Sword
   - dual=true, twoSided=true
   
3. The Black Rider ↔ God's Scale
   - dual=true, twoSided=true
   
4. The Pale Rider ↔ God's Hand
   - dual=true, twoSided=true
   
5. The Martyr's Cry
   - dual=false, twoSided=false
   - No special guidance
   
6. The Cosmic Chaos
   - dual=false, twoSided=false
```

### Guidance Computed

✅ **Multi-Power**: YES (rows 1-4 have `dual=true`)
✅ **Multi-Sided**: YES (rows 1-4 have `twoSided=true`)

Both guidance sections are shown to Claude.

## Files Modified/Created

### Backend
- `designer/server/designer_server.py`
  - Function `compute_spellbook_guidance()` (lines 46-89)
  - API response enrichment (lines ~400)

### Frontend
- `designer/www/sections.js`
  - Guidance UI rendering (lines 1367-1404)
  - Detection logic for multi-power/multi-sided

### Data
- `admin/admin.html` (unchanged — guidance transmitted via API)
- Faction designs (flags set via designer UI)

## Testing Checklist

- [x] `compute_spellbook_guidance()` correctly detects `dual` flag
- [x] `compute_spellbook_guidance()` correctly detects `twoSided` flag
- [x] Guidance text is generated when either flag is present
- [x] Guidance is appended to faction API response
- [x] DGT design has correct flags set
- [x] DGT guidance is computed and returned
- [x] Designer UI shows "Guidance for Claude" section
- [x] Admin queue receives guidance via API

## Deployment Notes

### For Builds
The admin queue agent reads the faction via GET /designer/api/factions/<fid>, receives the `spellbookGuidance` field, and includes it in the build prompt to Claude.

### For Updates
If a designer changes spellbook flags:
1. Designer updates `dual` or `twoSided` via UI
2. Next API call computes new guidance
3. Claude receives updated guidance on next build

### Backward Compatibility
Factions without multi-power/multi-sided spellbooks:
- `compute_spellbook_guidance()` returns empty string
- Guidance section not shown to designer
- No guidance transmitted to Claude
- Zero impact on build process

## References

- Faction Build Manual: `/Users/gremus/Library/CloudStorage/.../faction-build-complete-manual.md` (lines 682-683)
- Admin Queue System: `/Users/gremus/cthulhu-wars-tools/tickers/prompt-admin-queue-system.txt` (lines 121-149)
- Designer Rules: `/Users/gremus/Claude-Projects/cthulhu-wars-tools/designer/www/rules.js` (SB defaults)
