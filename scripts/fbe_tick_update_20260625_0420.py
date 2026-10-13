#!/usr/bin/env python3
"""FBE tick update 2026-06-25 ~04:20
Changes:
- Convert 13 lingering READ: markers to ADDRESSED in the Q&A section
- Add new tick summary (newest-at-top), move oldest to Summary History
"""

import docx
import copy
import sys
from lxml import etree
from docx.oxml.ns import qn

DOCX_PATH = ("/Users/gremus/Library/CloudStorage/"
             "GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/"
             "Cthulhu Wars/HomeBrews/Faceless Blight Current Tasks.docx")

NEW_SUMMARY = (
    "[2026-06-25 ~04:20] With humble apologies for the delay in tidying: "
    "drained the admin queue (empty), confirmed the Homebrew site healthy "
    "(cache tag 20260624-215835, HTTP 200), and converted every lingering "
    "creator reply marker to ADDRESSED — all underlying fixes were already "
    "live. No new Faceless Blight issues to act on this tick."
)

# Map: unique fragment to find → full ADDRESSED replacement text
READ_REPLACEMENTS = {
    "Use a similar method to Tombstalker": (
        "ADDRESSED (ticker 2026-06-25): Noted — the Overlord of Death "
        "redesign used the Glaaki-style multi-select monster elimination you "
        "described, then Q4 refined it to the Infernal-Pact discount model "
        "(each monster eliminated = −1 Power cost on next action, undoable). "
        "Deployed as Fix 127; see Q4 below and the completed task above."
    ),
    "Explain for the best pick method works": (
        "ADDRESSED (ticker 2026-06-25): Explanation provided in the "
        "note immediately below."
    ),
    "Best for you is fine for now while other testing": (
        "ADDRESSED (ticker 2026-06-25): Confirmed — automatic "
        "best-for-you die selection (lose weakest dice first, protect "
        "Byagoona's combat dice) stays in place. Player-choice sub-menus "
        "deferred until other testing settles. No code change needed."
    ),
    "Standard prompt is fine, but setup is not using": (
        "ADDRESSED (ticker 2026-06-25): All three issues fixed and "
        "deployed — setup now correctly excludes areas adjacent to any enemy "
        "start area (not just areas lacking a faction glyph); Overlord of "
        "Death redesigned (see Q4); Byagoona Awakening eligibility gated to "
        "areas where monster cost + Power ≥ 10. See completed tasks."
    ),
    "Overlord of Death is consuming a full action to eat one monster": (
        "ADDRESSED (ticker 2026-06-25): Overlord of Death redesigned as "
        "an Infernal-Pact-style multi-select free action — eliminate any of "
        "your monsters to shave 1 Power off your next action's cost per "
        "monster. Undoable. Deployed as Fix 127."
    ),
    "Byagoona Awakening is broken, it is allowing an Awaken": (
        "ADDRESSED (ticker 2026-06-25): Byagoona's Awakening menu now "
        "only appears when at least one area exists where your total monster "
        "recruitment cost plus your current Power reaches 10. Fixed and "
        "deployed."
    ),
    "Animated Rush is not a carry ability, the 2 additional": (
        "ADDRESSED (ticker 2026-06-25): Animated Rush rewritten — the "
        "two bonus units move independently, each from any area to any "
        "adjacent area of its own, not carried along with Byagoona. Fixed "
        "and deployed."
    ),
    "The 'Skip Shapestealing' prompt brings you to the same menu forever": (
        "ADDRESSED (ticker 2026-06-25): Skip Shapestealing now marks the "
        "ability as used so the pre-battle menu advances normally instead "
        "of looping. Fixed and deployed."
    ),
    "All of the prompts are just saying <Unit Type>": (
        "ADDRESSED (ticker 2026-06-25): All unit-choice menus updated to "
        "show unit type, current area, and relevant status (gate control, "
        "cost, etc.). Fixed and deployed."
    ),
    "Occasionally gaining Doom from Self Consuming off of only 2": (
        "ADDRESSED (ticker 2026-06-25): Self Consuming doom threshold "
        "corrected — only your own Monster deaths count toward the 3-Monsters "
        "gate for +1 Doom (any faction's unit deaths still count for the "
        "+1 Power gate at 2+). Fixed and deployed."
    ),
    "Reference game 'Anything versus Color'": (
        "ADDRESSED (ticker 2026-06-25): Reference game reviewed; root "
        "causes identified and fixed (Self Consuming scope, Overlord of "
        "Death action type, Succor phase, Animated Rush carry logic). All "
        "confirmed live."
    ),
    "Succor proc'd outside of the Doom Phase": (
        "ADDRESSED (ticker 2026-06-25): Succor fixed — fires only in the "
        "Doom Phase, returns to the Doom menu after resolving (does not "
        "consume your main action), and has a once-per-Doom-Phase guard. "
        "Fixed and deployed."
    ),
    "Are these changes live yet? I started a new online game": (
        "ADDRESSED (ticker 2026-06-25 — see note below): The 3-dice "
        "Changeling Adherents gap was a genuine remaining bug and is now "
        "fixed and live. Start Area, unit labels, and Byagoona Awakening "
        "were already correct in the current build — your test game loaded "
        "a stale cached page. Self Consuming triggering from a Desecration "
        "is correct per the card. The force-refresh tag has since been "
        "reset so all new games load the current version."
    ),
    "Q4 answered: Overlord of Death": (
        "ADDRESSED (ticker 2026-06-25): Overlord of Death redesigned as "
        "Infernal-Pact-style discount — eliminate monsters (multi-select, "
        "undoable) to reduce your next action's cost by 1 per monster. "
        "Self Consuming fires only after the discounted action resolves. "
        "Deployed as Fix 127."
    ),
}


def find_para_idx(doc, fragment):
    for i, p in enumerate(doc.paragraphs):
        if fragment in p.text:
            return i
    return None


def set_para_text(para, new_text):
    """Replace all runs in a paragraph with a single run containing new_text."""
    # Remove all existing runs
    for r in para._element.findall(qn('w:r')):
        para._element.remove(r)
    # Create a new run with the text
    r_elem = etree.SubElement(para._element, qn('w:r'))
    t_elem = etree.SubElement(r_elem, qn('w:t'))
    t_elem.text = new_text
    t_elem.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')


def insert_para_after(doc, insert_after_idx, text):
    """Insert a fresh paragraph after insert_after_idx, copying style."""
    ref_para = doc.paragraphs[insert_after_idx]
    new_elem = copy.deepcopy(ref_para._element)
    # Clear all runs
    for r in new_elem.findall(qn('w:r')):
        new_elem.remove(r)
    # Add run with text
    r_elem = etree.SubElement(new_elem, qn('w:r'))
    src_runs = ref_para._element.findall(qn('w:r'))
    if src_runs:
        rpr = src_runs[0].find(qn('w:rPr'))
        if rpr is not None:
            r_elem.insert(0, copy.deepcopy(rpr))
    t_elem = etree.SubElement(r_elem, qn('w:t'))
    t_elem.text = text
    t_elem.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    ref_para._element.addnext(new_elem)


def remove_para(doc, idx):
    para = doc.paragraphs[idx]
    para._element.getparent().remove(para._element)


def main():
    doc = docx.Document(DOCX_PATH)

    print(f"Total paragraphs: {len(doc.paragraphs)}")

    # ── Step 1: Convert all READ: markers to ADDRESSED ────────────────────────
    replaced = 0
    for fragment, new_text in READ_REPLACEMENTS.items():
        idx = find_para_idx(doc, fragment)
        if idx is None:
            print(f"WARNING: Could not find fragment: '{fragment[:60]}'",
                  file=sys.stderr)
            continue
        old_text = doc.paragraphs[idx].text
        if not old_text.startswith("READ:") and not old_text.startswith("@@@ "):
            # May already be addressed — check
            if "ADDRESSED" in old_text:
                print(f"  SKIP (already addressed) para {idx}: {old_text[:80]}")
                continue
            print(f"  WARNING: para {idx} doesn't start with READ:, text: "
                  f"{old_text[:80]}", file=sys.stderr)
        print(f"  Replacing para {idx}: '{old_text[:70]}...'")
        set_para_text(doc.paragraphs[idx], new_text)
        replaced += 1

    print(f"\nConverted {replaced} READ: markers to ADDRESSED.")

    # ── Step 2: Add new tick summary & rotate oldest to Summary History ────────
    bulleted_summary_idx = find_para_idx(doc, "Bulleted summary (newest at top)")
    summary_history_idx = find_para_idx(doc, "Summary History (older tick lines")

    if bulleted_summary_idx is None:
        print("ERROR: Could not find 'Bulleted summary' heading", file=sys.stderr)
        sys.exit(1)
    if summary_history_idx is None:
        print("ERROR: Could not find 'Summary History' heading", file=sys.stderr)
        sys.exit(1)

    print(f"\nBulleted summary heading at: {bulleted_summary_idx}")
    print(f"Summary History heading at: {summary_history_idx}")

    # Current 3 summaries are at +1, +2, +3 relative to the heading
    oldest_idx = bulleted_summary_idx + 3
    print(f"Oldest summary (idx {oldest_idx}): '{doc.paragraphs[oldest_idx].text[:80]}'")

    # Clone oldest to just after Summary History heading (do bottom op first
    # so indices above don't shift)
    print(f"Cloning oldest to after Summary History idx {summary_history_idx}")
    insert_para_after(doc, summary_history_idx, doc.paragraphs[oldest_idx].text)

    # Remove original oldest (still at bulleted_summary_idx+3 since insert was below)
    print(f"Removing oldest from idx {oldest_idx}")
    remove_para(doc, oldest_idx)

    # Insert new summary after bulleted_summary heading
    print(f"Inserting new summary after idx {bulleted_summary_idx}")
    insert_para_after(doc, bulleted_summary_idx, NEW_SUMMARY)

    # ── Save ───────────────────────────────────────────────────────────────────
    doc.save(DOCX_PATH)
    print(f"\nSaved to {DOCX_PATH}")

    # ── Verify ────────────────────────────────────────────────────────────────
    doc2 = docx.Document(DOCX_PATH)
    bs2 = find_para_idx(doc2, "Bulleted summary (newest at top)")
    sh2 = find_para_idx(doc2, "Summary History (older tick lines")
    print(f"\nVerification — total paragraphs: {len(doc2.paragraphs)}")
    if bs2 is not None:
        print(f"\nBulleted summary section (paras {bs2}→{bs2+4}):")
        for i in range(bs2, min(bs2 + 5, len(doc2.paragraphs))):
            print(f"  {i}: {doc2.paragraphs[i].text[:100]}")
    if sh2 is not None:
        print(f"\nSummary History (paras {sh2}→{sh2+3}):")
        for i in range(sh2, min(sh2 + 4, len(doc2.paragraphs))):
            print(f"  {i}: {doc2.paragraphs[i].text[:100]}")
    print("\nDone.")


if __name__ == "__main__":
    main()
