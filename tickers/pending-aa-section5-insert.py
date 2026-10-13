#!/usr/bin/env python3
# Orchestration-only helper: calls the sanctioned hb-doc-edit.py tool via subprocess
# with a clean argv list (no shell-quoting), one insert-after call per pair, verifying
# exit code 0 before proceeding to the next. Never touches the .docx directly.
import subprocess, sys

DOCX = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Alt Ancients Faction Implementation Guide.docx"
TOOL = "/Users/gremus/Claude-Projects/cthulhu-wars-tools/tickers/hb-doc-edit.py"

PAIRS = [
("§5.1 Menu Flows",
 "Pass — confirmed AA has zero dedicated menu classes of its own. AA is selected purely via the same alt-picker mechanism used for BB/OW/SL/DS: a second picker entry, PickerEntry(AN, true) at CthulhuWarsSolo.scala:5568, which sets a shared anAlt boolean threaded through startSetup/startOnlineSetup (CthulhuWarsSolo.scala:4816-4837, 5171-5183) to flip the ANAlternateSpellbooks game option. Every Dematerialization-related action class in FactionAN.scala is typed generically on Faction, so AA reuses AN's entire menu tree verbatim with no branch of its own — matches the guide's own claim of 0 AA-specific menus."),
("G7 — Use styled keywords for all menu text",
 "Pass — reviewed the AA-relevant action classes (Dematerialization* at FactionAN.scala:102-106, and the Crusade/Sanguinessence hooks in Battle.scala/Game.scala). All faction, spellbook, Doom, and Power references route through the shared styled-keyword helpers exactly as they do for every other faction, with one narrow exception noted under the Done-button item below."),
("G8 — Any Canonical styled keyword class",
 "Pass — the styled keyword class always resolves through the faction's own style code, which is literally \"an\" for both AN and AA since AA has no distinct Faction object; confirmed via the Sanguinessence and Crusade log lines (Battle.scala:2171,2175; Game.scala:4986). No separate AA style class exists or is needed."),
("G9 — Cancel button rules (Soft only)",
 "Pass — DematerializationFromRegionAction, DematerializationToRegionAction, and DematerializationMoveUnitAction are all declared \"with Soft\" and correctly chained with a Cancel option (FactionAN.scala:329,334,337,344), while the terminal DematerializationDoneAction carries no Soft/Cancel, matching the rule that only mid-flow Soft actions get a Cancel button."),
("G10 — Done button uses styled('power')",
 "Bug found, minor and non-blocking, inherited from AN rather than introduced by AA — DematerializationDoneAction's button text (FactionAN.scala:106) is a raw \"Done\" string, not wrapped in the styled-power format the way the codebase's other Done buttons are (compare Game.scala's DoomDoneAction or Firstborn's Infernal Pact Done button). Since this action class is shared unchanged between AN and AA, the inconsistency affects both factions equally; flagged here because it's exactly what this guide item checks, but the actual fix belongs to AN's own code, not anything AA added."),
("G11 — Faction-color border on cross-faction asks (menu border style)",
 "Pass — cross-faction ask rendering is generic to Game.scala's shared Ask class, which derives its border color from the asking faction's own style at render time. Because AA's Dematerialization/Sanguinessence/Crusade prompts are all typed on the plain AN faction object, any cross-faction ask automatically gets the correct \"an\" colored border with no AA-specific styling code required."),
("G12 — CSS classes .dc, .dc-background, .dc-border in index.html and online HTML",
 "Confirmed by design, not a gap — checked index.html's faction color/background/border CSS blocks and found only .an, .an-background, and .an-border; no .aa, .aa-background, or .aa-border class exists anywhere in index.html or overlay.scala. AA deliberately reuses AN's existing CSS classes end to end, consistent with AA having no distinct Faction object at all."),
("G13 — RoA overlay tintFilter case for (Faction Acronym)",
 "Confirmed by design, not a gap — the Ritual of Annihilation tint-lookup switch in overlay.scala has a case for AN and no separate AA case, and none is needed: since AA is never a distinct faction short-code in the engine, any AA unit's tint always resolves through the existing AN case automatically."),
("G14 — Faction info card layout via overlay.scala faction(...) case",
 "Pass — AA does not have and does not need its own faction info card. overlay.scala's shared AN faction-card builder is the single card builder for both variants: only the Cathedral's spellbook-reference line changes, listing the three original spellbooks when the alt flag is off or the three swapped-in ones (Holy Ground, Sanguinessence, Crusade) when it's on, while the ability text, background asset, and all unit stat rows stay identical either way."),
("G15 — Unique Ability border (.border-outer / .border-inner)",
 "Pass — the Unique Ability's border-outer/border-inner markup is emitted generically inside the same shared faction card template used by every faction, so AA's Dematerialization ability inherits the correct border chrome automatically with no separate markup required."),
("§5.5 Faction Card Layout",
 "Since AA shares AN's faction card wholesale, with only the Cathedral spellbook-reference line's text differing by a boolean flag, the physical layout — unit rows, stat columns, ability box, and border chrome — is identical between AN and AA. No layout gap found."),
("§5.6 Background Image",
 "AA does not have its own background art; the shared card overlay always renders the AN background asset regardless of the alt-spellbook flag. This is confirmed intentional reuse rather than a missing asset, consistent with AA carrying no unique visual identity beyond its three swapped spellbook texts."),
("§5.7 Faction Card Formatting",
 "Typeface, color, and drawing proportions all check out as fully inherited: the body-level typewriter font and the header font apply globally rather than per faction, the \"an\" text color is shared, and Cathedral's on-map footprint uses a fixed non-square rectangle sized like other Building-class assets rather than a square icon default, unaffected by whether Holy Ground is currently active."),
("G22 — Typeface, color, frame (bohemian-typewriter + abaddon fonts)",
 "Pass — the bohemian-typewriter and abaddon fonts are declared once in index.html and applied at the body/class level rather than per faction, so AA needs no separate font wiring; it simply consumes the same \"an\" color and frame variables AN already uses."),
("G23 — DrawRect dimensions follow other-faction proportions, not square defaults",
 "Pass — Cathedral's map-tile rendering call (CthulhuWarsSolo.scala:1291) uses the same rectangular, non-square proportions as other Building/GOO map assets (for comparison, Azathoth's iGOO renders at 119x138, Ghatanothoa's iGOO at 125x145). This call is unconditional and not gated on the Holy Ground flag, so Cathedral's visual footprint correctly stays a Building-shaped icon on the map at all times even though Holy Ground mechanically treats it as a GOO during the Action Phase."),
("G24 — Six SB overlay text cases in overlay.scala spellbook(...) match",
 "Pass — all six spellbook overlay cases render correctly for AA: the three unswapped ones (Festival, Brainless, Extinction) plus the three swapped-in alt cases (Holy Ground, Sanguinessence, Crusade), selected via the same conditional that builds the Cathedral's spellbook-reference line. Direct text comparison against the guide's own quoted card wording found an exact match with no drift."),
("G25 — Six SBR overlay text cases (one per requirement)",
 "Pass — the six Spellbook Requirement cases all render correctly, matching the six Requirement objects declared in FactionAN.scala and returned by AN's requirements list. These SBRs are tied to Glyph/effect conditions rather than to which three spellbooks are currently swapped in, so the same six apply unchanged to both AN and AA."),
("G26 — Verbatim SB text fidelity (no paraphrasing)",
 "Pass — side-by-side comparison of the three swapped spellbook texts (Holy Ground, Sanguinessence, Crusade) against the guide's own quoted card text found a character-for-character match with no paraphrasing."),
("G27 — Six requirement objects use canonical naming",
 "Pass — all six requirement objects follow the same canonical Requirement declaration pattern used across every other faction's SBRs, declared as case objects in FactionAN.scala, consistent with the naming conventions used elsewhere in the codebase."),
("§5.9 Meta — Audit Summary",
 "Audit summary (2026-08-28 HomeBrews ticker, Pass 1): Section 5 for Alt Ancients is in strong shape precisely because almost none of it is AA-specific code — AA has no Faction object, no distinct short code, no CSS classes, no background art, and no menu classes of its own; it is purely a shared alternate-spellbooks game option, toggled on through the alt-picker's second entry for AN, that a shared card builder and a handful of AN spellbook-check branches in Battle.scala and Game.scala key off of. All six spellbook texts and all six requirement texts render correctly and verbatim, Holy Ground's Cathedral-as-Great-Old-One overlay still correctly keeps Cathedrals out of Pain and Retreat assignment at all times, and Dematerialization's Capture-immunity check is faction-agnostic and works for AA unmodified. Two items need the owner's eyes: a small, AN-inherited (not AA-caused) unstyled \"Done\" button, and a fresh, targeted re-search that still turned up zero evidence anywhere in the codebase for the previously-flagged Yog-Sothoth \"+2 combat dice for all 4 Cathedrals\" bonus — the only coded \"all 4 Cathedrals\" effects found are Consecration's Elder-Sign doubling and the Cathedral card's Awaken-without-a-GOO clause, neither of which is a combat-dice bonus, so this looks like either an unbuilt feature or a mislabeled one."),
("§5.10 Audit passes",
 "Pass 1 - 2026-08-28 (HomeBrews ticker): first full audit of Section 5 against the General Faction Creation Guide and the live code in FactionAN.scala, Battle.scala, Game.scala, overlay.scala, CthulhuWarsSolo.scala, and index.html, layered on top of FactionAN.scala since AA has no faction file of its own. No prior audit pass exists to compare against."),
]

GAP_LIST_ANCHOR = "§5.11 FINAL GAP LIST (open questions to resolve before implementation)"
GAP_LIST_LINES = [
"1. DematerializationDoneAction's \"Done\" button text (FactionAN.scala:106) is a raw unstyled string, not wrapped in the styled-power format the way other factions' Done buttons are. Cosmetic, inherited from AN's own code rather than introduced by AA, open-non-blocking.",
"2. The guide-described \"Yog-Sothoth gains +2 combat dice when all 4 Cathedrals are in play\" bonus could not be found anywhere in the code on a fresh, targeted search of IGOOs.scala, FactionOW.scala, Game.scala, and Battle.scala for any Yog-Sothoth-plus-Cathedral combination. The only \"all 4 Cathedrals\" effects that do exist in code are Consecration's Elder-Sign doubling and the Cathedral card's Awaken-an-Independent-GOO-without-your-own-GOO clause. This should stay flagged INPUT NEEDED: either the bonus was never implemented and the guide text needs correcting, or it refers to one of these two real effects and was mislabeled.",
]

def run(anchor, text):
    r = subprocess.run(["python3", TOOL, DOCX, "insert-after", anchor, text], capture_output=True, text=True)
    print("EXIT", r.returncode, "for anchor:", anchor[:60])
    if r.stdout.strip():
        print("STDOUT:", r.stdout.strip()[:300])
    if r.stderr.strip():
        print("STDERR:", r.stderr.strip()[:500])
    return r.returncode

def run_file(anchor, lines):
    import tempfile, os
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    r = subprocess.run(["python3", TOOL, DOCX, "insert-after", anchor, "--file", path], capture_output=True, text=True)
    print("EXIT", r.returncode, "for anchor:", anchor[:60], "(--file, %d lines)" % len(lines))
    if r.stdout.strip():
        print("STDOUT:", r.stdout.strip()[:300])
    if r.stderr.strip():
        print("STDERR:", r.stderr.strip()[:500])
    return r.returncode

if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for i, (anchor, text) in enumerate(PAIRS):
        if only is not None and str(i) != only:
            continue
        rc = run(anchor, text)
        if rc != 0:
            print("ABORTING at index", i)
            sys.exit(rc)
    if only is None or only == "gaplist":
        rc = run_file(GAP_LIST_ANCHOR, GAP_LIST_LINES)
        if rc != 0:
            print("ABORTING at gap list step")
            sys.exit(rc)
    print("ALL DONE" if only is None else "SINGLE DONE")
