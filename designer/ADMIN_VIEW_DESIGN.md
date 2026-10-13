# Admin Read-Only View Design

## TL;DR: Already 90% Complete ✅
**The admin view infrastructure already exists and mostly works.** Admins can open `#/admin/factions/<fid>` and see the exact same form designers see, with all visual feedback (red borders on missing fields, Claude questions, build status).

**Only 1 change required:**
- Hide "Submit Build Request" button in `renderBuildScreen()` when in admin mode

**Optional enhancements:**
- Add owner + faction name to read-only banner
- Add placeholder text for unanswered Claude questions

**Next step:** TEST FIRST by opening an admin view to verify all visual feedback renders correctly. If it does, make only the 1-line change to hide the build button.

---

## Summary
Verify and enhance the existing admin-only read-only view of designer factions that mirrors exactly what designers see during design, including all visual feedback (blocking issues in red, Claude questions, incomplete field indicators).

## Current State
The admin view infrastructure **already exists** and mostly works:
- Route: `#/admin/factions/<fid>` (and `/admin/maps/<mid>`)
- Server endpoint: `GET /admin/<token>/view-faction/<fid>` returns full faction data with `readOnly: true`, `adminView: true`, `claudeQA`, build status
- UI: The `isReadOnly()` system disables all inputs when `currentFaction.readOnly === true`
- Navigation: Admin clicks faction link → opens in same read-only mode designers use

## Problem
The current admin view shows forms but **hides visual feedback** that designers see:
- Missing field indicators (`sx-missing` red borders) may not render
- Build screen status badges (red ✗ for Incomplete) hidden or minimal
- ClaudeQA sections might not display in section views
- No clear way to see "what's blocking the build" at a glance

## Solution: Enhanced Read-Only Rendering

### 1. Architecture (NO changes needed)
**Existing route works:** `#/admin/factions/<fid>` already loads faction with `readOnly: true`.

**Flow:**
1. Admin clicks faction link in dashboard (`#/admin/factions/<fid>`)
2. App calls `loadFaction(fid)` → server returns faction with `readOnly: true`, `adminView: true`
3. App sets `this.state.currentFaction = faction`
4. All existing screens render (Overview, Sections, Build, Versions) with `isReadOnly() === true`
5. Read-only banner appears at top: "You are viewing [Owner]'s [Faction Name] (read only)"

### 2. UI Component Changes

#### A. Section Screens (sections.js)
**File:** `/Users/gremus/Claude-Projects/cthulhu-wars-tools/designer/www/sections.js`

**Current behavior:**
- Renders form fields via `textField()`, `numberField()`, `selectField()`, etc.
- Each field helper checks `ctx.readOnly` and adds `disabled` attribute to inputs
- Missing field indicators (`sx-missing` class) are applied regardless of read-only state

**Required change:**
Ensure `sx-missing` class is ALWAYS applied (even in read-only) when a field is incomplete. The red border (`border: 1px solid #e53935`) must show for admin to see what's blocking.

**Implementation:**
- Audit all field helper functions (`textField`, `numberField`, etc.) in sections.js
- Ensure `sx-missing` class is applied based on field content, not `ctx.readOnly`
- Red border should render on disabled inputs in admin view

**Test:** Open admin view of incomplete faction → see red borders on empty required fields.

---

#### B. Build Screen (app.js)
**File:** `/Users/gremus/Claude-Projects/cthulhu-wars-tools/designer/www/app.js`
**Function:** `renderBuildScreen()` (lines ~2840-2903)

**Current behavior:**
- Shows table of sections with status badges (Complete, Incomplete, etc.)
- "Incomplete" sections get red badge: `<span class="status-badge-red">✗ Incomplete</span>`
- Build button disabled when not ready
- "Missing fields" description section explains what's needed

**Required change:**
In read-only mode:
1. Keep all status badges visible (especially red "Incomplete" badges)
2. Keep "Missing fields" description visible
3. Hide "Submit Build Request" button (admin can't build from this view)
4. Add note: "This is an admin view. To build, the owner must submit from their designer account."

**Implementation:**
```javascript
// In renderBuildScreen(), after table:
if (this.isReadOnly()) {
  const note = document.createElement('p');
  note.style.cssText = 'color: #888; margin-top: 20px; font-style: italic;';
  note.textContent = 'Admin view: owner must submit build request from their account.';
  this.root.appendChild(note);
  // Don't render the "Submit Build Request" button
} else {
  // Existing button rendering code
}
```

**Test:** Open admin view of faction with Incomplete sections → see red badges and missing fields description.

---

#### C. ClaudeQA Sections (sections.js)
**File:** `/Users/gremus/Claude-Projects/cthulhu-wars-tools/designer/www/sections.js`
**Function:** `renderClaudeQA(container, ctx, sectionName)` (lines 264-303)

**Current behavior:**
- Questions box: blue background (`#1e3a8a`), shows Claude's questions
- Answers box: green background (`#065f46`), shows designer's answers (or textarea to type)
- In read-only mode, textarea should be disabled

**Required change:**
In read-only mode, show both boxes as-is but disable the answers textarea. Admin sees:
- What Claude asked (blue box)
- What designer answered (green box, read-only)
- If no answer yet: empty green box with placeholder text "Awaiting designer's answer"

**Implementation:**
In `renderClaudeQA()`:
```javascript
if (ctx.readOnly && !qa.answers) {
  const placeholder = document.createElement('p');
  placeholder.style.cssText = 'color: #888; font-style: italic; padding: 8px;';
  placeholder.textContent = 'Awaiting designer\'s answer';
  answersDiv.appendChild(placeholder);
} else {
  // Existing textarea rendering
  textarea.disabled = ctx.readOnly;
}
```

**Test:** Open admin view of faction with Claude questions → see blue questions box + green answers box (disabled textarea if read-only).

---

#### D. Section Tab Status Indicators (app.js)
**File:** `/Users/gremus/Claude-Projects/cthulhu-wars-tools/designer/www/app.js`
**Function:** `renderFactionOverview()` or where section tabs are rendered

**Current behavior:**
- Section tabs show status: "Complete", "Incomplete", "Claude Question"
- "Claude Question" label is amber (`#fbbf24`)
- Admin view shows status badges with "⚠ Claude Q" indicator

**Required change:**
Ensure all status indicators are visible in admin view. No changes needed if already visible.

**Test:** Open admin view → section tabs show correct status (Complete / Incomplete / Claude Question).

---

### 3. Data Model (NO changes)
The server endpoint `/admin/<token>/view-faction/<fid>` already returns:
```json
{
  "readOnly": true,
  "adminView": true,
  "claudeQA": {"section_key": {"questions": "...", "answers": "..."}},
  "build": {"status": "...", "liveVersion": null, ...},
  "design": { /* full faction design */ },
  "ownerName": "designer_username",
  "builtDesign": { /* built version if exists */ },
  "liveValues": { /* live game values if exists */ }
}
```

No server changes needed.

---

### 4. Styling (sections.js - already complete)
**File:** `/Users/gremus/Claude-Projects/cthulhu-wars-tools/designer/www/sections.js`

**Current state (line 27):**
```css
.sx-missing { border: 2px solid #e53935 !important; }
```

**Status:** ✅ **Already implemented correctly**
- The `!important` rule ensures the red border applies even to disabled inputs
- No changes needed to CSS

**Verify:** Test that disabled fields show red borders in admin view. If not rendering, check browser DevTools to ensure the injected CSS loaded.

---

### 5. Read-Only Banner Enhancement (app.js)
**File:** `/Users/gremus/Claude-Projects/cthulhu-wars-tools/designer/www/app.js`
**Function:** `readOnlyBanner()` (lines ~375-386)

**Current (lines 376-379):**
```javascript
const isAdmin = this.state.adminView;
const bannerText = isAdmin
  ? 'Admin view (read-only): Viewing designer submission. All validation, feedback, and Claude questions visible. Form locked.'
  : 'Shared view (read-only): Form locked for editing.';
```

**Status:** ✅ **Admin banner already exists and is clear**
- Already distinguishes admin view from shared view
- Already mentions validation/feedback/Claude questions are visible

**Optional enhancement:** Add owner + faction name for context:
```javascript
const isAdmin = this.state.adminView;
const faction = this.state.currentFaction;
const ownerName = faction.ownerName || faction.owner;
const factionName = faction.name;

const bannerText = isAdmin
  ? `Admin view (read-only): Viewing ${ownerName}'s faction "${factionName}". All validation, feedback, and Claude questions visible. Form locked.`
  : 'Shared view (read-only): Form locked for editing.';
```

**Decision:** Optional - current banner is functional. Add owner/faction name if desired for extra context.

---

### 6. Implementation Scope

#### Critical Finding: MOST FEATURES ALREADY WORK ✅

The admin view infrastructure is **90% complete**. Red borders, Claude questions, status badges, and build feedback already render in read-only mode. Only minor enhancements needed:

#### Files to Change (MINIMAL):

**REQUIRED changes:**
1. **`/Users/gremus/Claude-Projects/cthulhu-wars-tools/designer/www/app.js`**
   - Line ~2840: `renderBuildScreen()` - hide build button in read-only, add admin note

**OPTIONAL enhancements:**
2. **`/Users/gremus/Claude-Projects/cthulhu-wars-tools/designer/www/sections.js`**
   - Line ~264: `renderClaudeQA()` - add placeholder text for unanswered questions in read-only
   
3. **`/Users/gremus/Claude-Projects/cthulhu-wars-tools/designer/www/app.js`**
   - Line ~375: `readOnlyBanner()` - add owner + faction name to banner text

#### Files to Test:
**TEST FIRST before making changes:** Open `#/admin/factions/<fid>` and verify:
- ✓ Red borders (`sx-missing`) visible on empty required fields in disabled inputs?
- ✓ Claude questions (blue box) and answers (green box) visible in section screens?
- ✓ Build screen shows red "✗ Incomplete" badges and missing fields description?
- ✓ Section tabs show status (Complete / Incomplete / Claude Question)?

**If all tests pass:** Only change needed is hiding the build button in `renderBuildScreen()`.

**If tests fail:** Add the optional enhancements.

---

### 7. Testing Checklist

**Scenario 1: Incomplete Faction**
1. Admin opens `#/admin/factions/<fid>` for faction with empty required fields
2. ✓ Read-only banner shows owner + faction name
3. ✓ Section tabs show "Incomplete" in red/amber
4. ✓ Section screens show red borders (`sx-missing`) on empty required fields
5. ✓ Build screen shows red "✗ Incomplete" badges
6. ✓ Build screen shows "Missing fields" description

**Scenario 2: Faction with Claude Questions**
1. Admin opens faction where Claude has asked questions
2. ✓ Section tabs show "Claude Question" in amber
3. ✓ Section screen shows blue questions box
4. ✓ Section screen shows green answers box (disabled textarea or placeholder if unanswered)

**Scenario 3: Built Faction**
1. Admin opens built faction
2. ✓ Build screen shows "Built" status with green checkmark
3. ✓ All sections show "Complete" status
4. ✓ No red borders on fields

---

## Implementation Steps for Haiku

### Step 1: TEST FIRST (DO NOT SKIP)
**Before writing any code**, verify what already works:

1. SSH to server: `ssh cwo`
2. Open browser to `https://cwo.im/designer/`
3. Log in as admin (use admin token from terminal log or stored session)
4. Navigate to `#/admin/users` (admin dashboard)
5. Click on a faction link → opens `#/admin/factions/<fid>`
6. **Verify these work:**
   - ✓ Read-only banner appears at top mentioning admin view
   - ✓ Red borders (`sx-missing`) visible on empty required fields (inputs are disabled but show red)
   - ✓ Navigate to Build screen → see table with red "✗ Incomplete" badges
   - ✓ Navigate to section with Claude questions → see blue questions box + green answers box
   - ✓ All form fields are disabled (can't type)

7. **Note what DOESN'T work:**
   - Build button still visible? (should be hidden in admin view)
   - Red borders NOT showing on disabled fields? (CSS issue)
   - Claude questions NOT visible? (rendering issue)

### Step 2: Fix Only What's Broken
Based on Step 1 findings, make ONLY the necessary changes:

**If red borders work, Claude questions work, and only build button needs hiding:**
```javascript
// File: /Users/gremus/Claude-Projects/cthulhu-wars-tools/designer/www/app.js
// Function: renderBuildScreen() (line ~2840)
// After the status table, before the "Submit Build Request" section:

if (this.isReadOnly()) {
  const note = document.createElement('p');
  note.style.cssText = 'color: #888; margin-top: 20px; font-style: italic;';
  note.textContent = 'Admin view: The owner must submit the build request from their designer account.';
  this.root.appendChild(note);
  // Skip rendering the "Submit Build Request" button
} else {
  // Existing button rendering code...
}
```

**If Claude questions need placeholder for unanswered:**
```javascript
// File: /Users/gremus/Claude-Projects/cthulhu-wars-tools/designer/www/sections.js
// Function: renderClaudeQA() (line ~280, in the answers section)

if (ctx.readOnly && !qa.answers) {
  const placeholder = h('p', {style: 'color: #888; font-style: italic; padding: 8px;'}, 
    'Awaiting designer\'s answer');
  answersDiv.appendChild(placeholder);
} else {
  // Existing textarea rendering...
}
```

**If banner needs owner/faction name:**
```javascript
// File: /Users/gremus/Claude-Projects/cthulhu-wars-tools/designer/www/app.js
// Function: readOnlyBanner() (line ~375)

const isAdmin = this.state.adminView;
const faction = this.state.currentFaction;
const ownerName = faction.ownerName || faction.owner;
const factionName = faction.name;

const bannerText = isAdmin
  ? `Admin view (read-only): Viewing ${ownerName}'s faction "${factionName}". All validation, feedback, and Claude questions visible. Form locked.`
  : 'Shared view (read-only): Form locked for editing.';
```

### Step 3: Deploy
```bash
cd /Users/gremus/Claude-Projects/cthulhu-wars-tools/designer
./deploy/deploy-designer-to-vm.sh
```

### Step 4: Verify Fix
1. Hard refresh browser (Cmd+Shift+R to clear cache)
2. Navigate to same test faction
3. Verify the change worked
4. Test with multiple faction states: incomplete, with Claude questions, built

---

## Non-Goals (out of scope)
- ❌ Admin editing factions from this view (use separate admin patch endpoint)
- ❌ Admin submitting build requests from this view (owners must submit)
- ❌ New admin-only fields or data not visible to designers
- ❌ Filtering/searching factions in admin view (use existing dashboard)

This design keeps the admin view as a **pure mirror** of what designers see, with identical visual feedback.
