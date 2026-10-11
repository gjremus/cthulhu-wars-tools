# Map Design Schema Reference

Quick reference for the map design structure implemented in the Map Designer.

## Complete Map Design Structure

```json
{
  "images": {
    "images": [{"id": "abc123", "label": "Board 1", "imageId": "sha256.webp"}],
    "layout": "single|sideBySide|stacked|grid",
    "gridColumns": 2,
    "order": ["id1", "id2"],
    "notes": "Layout notes",
    "regions": [{
      "id": "reg123",
      "name": "The Laboratory",
      "type": "land|sea",
      "glyphs": ["gc", "dragon", "custom-glyph-id"]
    }],
    "customLogic": ""
  },
  
  "bitmaps": {
    "items": [{
      "id": "bit123",
      "imageId": "sha256.png",
      "colors": {"#ff0000": "reg123", "#00ff00": "reg456"},
      "centroids": {"reg123": [100, 200], "reg456": [300, 400]}
    }],
    "customLogic": ""
  },
  
  "adjacency": {
    "cols": 32,
    "rows": 16,
    "cells": [null, "reg123", "reg123", null, ...],  // cols × rows array
    "specialTypes": [{
      "id": "spec123",
      "name": "Doors",
      "description": "Connect rooms",
      "cost": 1,
      "oneWay": false,
      "pairs": [{"id": "pair1", "from": "reg123", "to": "reg456"}]
    }],
    "customLogic": ""
  },
  
  "units": {
    "wikiUrl": "https://cthulhuwars.fandom.com/wiki/...",
    "rows": [{
      // Neutral unit (no relatedSb field)
      "id": "unit123",
      "type": "Monster|Terror|Great Old One|Elder God",
      "name": "Dimensional Shambler",
      "mapImage": null,
      "mapScale": 1.0,
      "silhouette": "sha256.png",
      "qty": 3,
      "costType": "Fixed|Variable",
      "cost": 3,
      "costCalc": "",
      "combatType": "Fixed Dice|N/A",
      "dice": 2,
      "diceCalc": "",
      "pains": null,
      "kills": null,
      "resultsCalc": "",
      "abilityName": "Dimensional Travel",
      "abilityText": "Can move to any region",
      "spellbook": {
        "enabled": false,
        "requirement": {"text": "", "hasNum": false, "num": null},
        "book": {"name": "", "type": null, "cost": 0, "hasEffect": false, "effect": null, "text": ""}
      }
    }],
    "customLogic": ""
  },
  
  "tokens": {
    "rows": [{
      "id": "tok123",
      "name": "Rift Marker",
      "qty": 6,
      "image": "sha256.png",
      "placement": "On regions with rifts",
      "effects": "Blocks normal movement",
      "hasEffect": true,
      "effect": -1
    }],
    "customLogic": ""
  },
  
  "sb": {
    "multiText": "Requirements for map spellbooks",
    "rows": [{
      "id": "sbr123",
      "text": "Control 3 rift markers",
      "hasNum": true,
      "num": 3
    }],
    "books": [{
      "id": "book123",
      "name": "Master of Rifts",
      "type": "Action|Ongoing|Battle",
      "cost": 4,
      "hasEffect": true,
      "effect": 2,
      "text": "You may spend 1 Power to move any unit through a rift"
    }],
    "customLogic": ""
  },
  
  "glyphs": {
    "rows": [{
      "id": "glyph123",
      "name": "Rift Glyph",
      "image": "sha256.png",
      "description": "Marks locations of dimensional rifts"
    }],
    "customLogic": ""
  },
  
  "abilities": {
    "rows": [{
      "id": "abil123",
      "name": "Unstable Terrain",
      "when": "Setup|Gather Power|Action|Doom|Battle|Ongoing",
      "type": "Action|Ongoing|Battle|Pre-Battle|Post-Battle|Doom|Setup",
      "cost": null,
      "who": "Any faction",
      "text": "At the start of each Action phase, roll 1d6. On a 5+, all rifts move..."
    }],
    "customLogic": ""
  }
}
```

## Section Keys

- `images` - Board images and regions
- `bitmaps` - Placement bitmaps for region mapping
- `adjacency` - Region adjacency grid and special connections
- `units` - Neutral map units
- `tokens` - Map tokens
- `sb` - Map spellbook requirements and books
- `glyphs` - Custom glyphs specific to this map
- `abilities` - Map-specific abilities

## Completeness Rules

### Required for Build
- **images**: ≥1 image, ≥1 region, every region named
- **bitmaps**: every region is placed on some bitmap
- **adjacency**: every region has ≥1 neighbor

### Optional Sections
- tokens, sb, glyphs, abilities - can be empty (N/A)
- special adjacency - optional subsection of adjacency

## Glyph Types

**Base faction glyphs** (checkboxes in region table):
- Great Cthulhu (gc-glyph.webp)
- Crawling Chaos (cc-glyph.webp)
- Black Goat (bg-glyph.webp)
- Yellow Sign (ys-glyph.webp)

**Standard map glyphs**:
- Dragon (dragon.png)
- Thorns (thorns.png)
- Chevron (chevron.png)

**Custom glyphs**: Defined in the `glyphs` section, uploaded by designer

## Version Rules

Maps follow the same version rules as factions:
- Additions stay in current version
- Changes create new version (unless in open session)
- Locked versions: built version or older version after rollback
- Next edit after rollback creates new version

## Requests

- **build**: Execute build for this map
- **extract**: Extract regions from images, or units from wiki
- **bug**: Report bug in built map
