#!/usr/bin/env python3
"""Append recent fix entries to the BB Deployed Online Rollback Guide."""
import zipfile
import shutil
from copy import deepcopy
from lxml import etree

DOC = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
       "My Drive/Personal/Games/Cthulhu Wars/Factions/Bubastis/"
       "Bubastis Deployed Online Rollback Guide.docx")

ENTRIES = [
    "Fix BB-DoomCont: Doom-phase skip after post-replay spellbook pick (2026-07-09, deployed bubastis-v2.4.37)",
    "Symptom.",
    "After the post-replay spellbook prompt (Fix BB-SBR-CG) fired during the doom phase, the game skipped the remainder of the doom phase and jumped directly to MainAction. Players could not perform doom-phase rituals.",
    "Root cause.",
    "The post-replay spellbook check was hardcoding MainAction(currentFaction) as the continuation after the spellbook pick. When the saved Continue was a doom-phase action (e.g. DoomPhaseAction), the wrong continuation caused the game to skip to the action phase.",
    "Fix.",
    "Extract the original continuation from the saved Continue: val originalNext = cc.get match { case Ask(_, actions) => actions(0).unwrap match { case SpellbookAction(_, _, next) => next; case _ => fallback }; case Then(next : ForcedAction) => next; case _ => fallback }. Uses DoomPhaseAction as fallback when in doom phase.",
    "Anchor.",
    "solo/CthulhuWarsSolo.scala — post-replay spellbook check block (line ~3795). The val originalNext extraction and cc = |(Ask(f).each(bs)(b => SpellbookAction(f, b, originalNext))).",
    "Revert.",
    "Replace the originalNext extraction with the original hardcoded: cc = |(Ask(f).each(bs)(b => SpellbookAction(f, b, MainAction(game.factions(0))))). Rebuild and redeploy.",
    "",
    "Fix BB-NuclearChaos: Azathoth Nuclear Chaos dice rolls not committed as hard (2026-07-10, deployed bubastis-v2.4.38)",
    "Symptom.",
    "Nuclear Chaos dice rolls changed on every page refresh. The game log showed different roll values each time the page loaded, and the outcomes didn't match the displayed rolls.",
    "Root cause.",
    "The original implementation used Force(NuclearChaosRollAction(self, rolls)) with random rolls inside the handler. Force() chains actions internally via internalPerform() WITHOUT recording to the action log. During replay, the rolls were regenerated fresh each time (non-deterministic). Only RollD6 is committed to the log and replayed deterministically.",
    "Fix.",
    "Rewrote Nuclear Chaos to use RollD6 per faction in a sequential chain: NuclearChaosMainAction starts RollD6 for the first faction, which creates NuclearChaosDieAction carrying the roll result plus remaining factions. Each step either chains another RollD6 (if factions remain) or transitions to NuclearChaosRolledAction (all rolls collected). New action classes: NuclearChaosDieAction(self, remaining, rolls, roller, roll) and NuclearChaosRolledAction(self, rolls). Pattern matches HB's correct implementation.",
    "Anchor.",
    "solo/IGOOs.scala — case NuclearChaosMainAction, NuclearChaosDieAction, NuclearChaosRolledAction handlers. Also the case class definitions at top of file.",
    "Revert.",
    "Revert commit 8835c76 (and 6d1f1fd) on branch bubastis. Rebuild and redeploy. WARNING: reverting will re-break Nuclear Chaos rolls for any game that has already recorded RollD6 entries in the new format.",
    "Propagated: MNU (commit 447ea37), TT (commit 26d8563). All three deployed 2026-07-10.",
    "",
    "Fix BB-Overlap: Gate overlap placement bug on Library map (2026-07-09, deployed all 5 builds)",
    "Symptom.",
    "On Library at Celaeno maps, units placed in regions with many occupants could overlap each other significantly, making the board unreadable. Units stacked directly on top of gates.",
    "Root cause.",
    "The previous unit-count-based shrink threshold (regionUniformShrink triggered at N>5 units) was too aggressive for some regions and not responsive enough for others. Units could pass placement without checking whether they visually overlapped existing units.",
    "Fix.",
    "Replaced unit-count shrink with overlap-detection triggered shrink. New function maxUnitOverlapFrac(dd: DrawItem) computes the maximum fraction of overlap between a new unit's bounding rect and any existing unit (excluding Gates). If overlap > 0.30 (30%) after 500 candidate positions tried, triggers regionUniformShrink and replaces all units in the region. Only active on Library maps (board.isLibraryMap guard).",
    "Anchor.",
    "solo/CthulhuWarsSolo.scala — placement loop inside placeUnits(). The maxUnitOverlapFrac() method definition and the overlap check inside the candidate loop. Also the needsShrinkRedo / regionUniformShrink redo block.",
    "Revert.",
    "Revert commit 539c5b4 on branch bubastis. This removes the overlap detection and restores the old unit-count threshold. Rebuild and redeploy all 5 builds.",
    "Propagated: Library (cthulhu-wars-library), MNU, TT, HB — all deployed 2026-07-09.",
    "",
    "Fix BB-CGOptional: Cyclopean Gaze made optional per source (2026-07-10)",
    "Symptom.",
    "Cyclopean Gaze (FB spellbook) auto-fired for every source without giving FB a choice. User requested ability to skip individual CG triggers.",
    "Fix.",
    "Added FBCyclopeanGazeUseAction and FBCyclopeanGazeSkipAction as OptionFactionActions. FBCyclopeanGazePhaseAction now presents a Use/Skip menu instead of auto-dispatching. Bot always picks Use (5000 priority). Skip logs the skip and continues to next source.",
    "Anchor.",
    "solo/FactionFB.scala — case class definitions (FBCyclopeanGazeUseAction, FBCyclopeanGazeSkipAction) and handlers in FBExpansion. solo/BotFB.scala — CG evaluation block.",
    "Revert.",
    "Remove FBCyclopeanGazeUseAction/SkipAction classes, handlers, and bot cases. Restore Force(FBCyclopeanGazeAssignPainAction(...)) in FBCyclopeanGazePhaseAction. Rebuild and redeploy.",
    "Propagated: MNU (committed 27a6b04), TT (committed 2788e29). Not yet deployed standalone (deployed as part of combined dirty-state commit).",
]

# Read the docx, append paragraphs
z = zipfile.ZipFile(DOC, 'r')
tree = etree.parse(z.open('word/document.xml'))
z.close()

ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
body = tree.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}body')

# Find last paragraph to use as style template
all_paras = body.findall('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')
template_p = all_paras[-1]

# Get the sectPr (section properties) which must stay last
sect_pr = body.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sectPr')

for entry_text in ENTRIES:
    new_p = deepcopy(template_p)
    # Clear all runs
    for r in new_p.findall('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r'):
        new_p.remove(r)
    # Add a new run with text
    r_elem = etree.SubElement(new_p, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r')
    t_elem = etree.SubElement(r_elem, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
    t_elem.text = entry_text
    t_elem.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    # Insert before sectPr if it exists, else append
    if sect_pr is not None:
        body.insert(list(body).index(sect_pr), new_p)
    else:
        body.append(new_p)

# Write back
shutil.copy2(DOC, DOC + '.bak.pre_write_' + str(hash(DOC) & 0xFFFFFFFF))

import tempfile, os
with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
    tmp_path = tmp.name

# Copy original zip, replace document.xml
with zipfile.ZipFile(DOC, 'r') as zin:
    with zipfile.ZipFile(tmp_path, 'w') as zout:
        for item in zin.infolist():
            if item.filename == 'word/document.xml':
                zout.writestr(item, etree.tostring(tree, xml_declaration=True, encoding='UTF-8', standalone=True))
            else:
                zout.writestr(item, zin.read(item.filename))

shutil.move(tmp_path, DOC)
print("SUCCESS — 4 new fix entries appended to BB rollback guide")
