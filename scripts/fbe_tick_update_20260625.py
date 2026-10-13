#!/usr/bin/env python3
"""FBE tick update 2026-06-25 ~02:53
- Inserts new tick summary (newest-at-top) after the 'Bulleted summary' heading
- Moves the oldest existing summary bullet (para[38], the 13:12 one) to Summary History
"""

import docx
import copy
import sys

DOCX_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/HomeBrews/Faceless Blight Current Tasks.docx"

NEW_SUMMARY = (
    "[2026-06-25 ~02:53] Humble correction and apologies: the prior three tick summaries "
    "were wrong — both the Ice Age Power tax on free Animated Rush moves and the Gate-control "
    "labels on every unit menu WERE built and deployed live on 2026-06-24 ~21:58 "
    "(Homebrew v2.10, cache tag 20260624-215835, HTTP 200). "
    "Admin queue is empty, site healthy at 200, and no open Faceless Blight tasks remain this tick."
)

def find_para_containing(doc, text_fragment):
    """Return index of first paragraph containing text_fragment."""
    for i, p in enumerate(doc.paragraphs):
        if text_fragment in p.text:
            return i
    return None

def clone_paragraph_after(doc, source_idx, insert_after_idx):
    """Copy paragraph at source_idx and insert it after insert_after_idx."""
    source_para = doc.paragraphs[source_idx]
    ref_para = doc.paragraphs[insert_after_idx]
    # Insert new paragraph node after ref_para
    new_para = copy.deepcopy(source_para._element)
    ref_para._element.addnext(new_para)

def insert_new_paragraph_after(doc, insert_after_idx, text, style_name=None):
    """Insert a fresh paragraph after insert_after_idx with given text."""
    ref_para = doc.paragraphs[insert_after_idx]
    # Use the same style as the reference paragraph if not specified
    if style_name is None:
        style_name = ref_para.style.name
    # Create new paragraph via docx XML manipulation
    from docx.oxml.ns import qn
    from lxml import etree
    import copy as cp
    # Deepcopy the source para element to preserve formatting
    new_elem = cp.deepcopy(ref_para._element)
    # Clear all runs from the copy
    for r in new_elem.findall(qn('w:r')):
        new_elem.remove(r)
    # Create a run with our text
    r_elem = etree.SubElement(new_elem, qn('w:r'))
    # Copy run properties from first run of source if available
    src_runs = ref_para._element.findall(qn('w:r'))
    if src_runs:
        rpr = src_runs[0].find(qn('w:rPr'))
        if rpr is not None:
            r_elem.insert(0, cp.deepcopy(rpr))
    t_elem = etree.SubElement(r_elem, qn('w:t'))
    t_elem.text = text
    t_elem.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    ref_para._element.addnext(new_elem)

def remove_paragraph(doc, idx):
    """Remove paragraph at index idx from the document."""
    para = doc.paragraphs[idx]
    para._element.getparent().remove(para._element)

def main():
    doc = docx.Document(DOCX_PATH)
    paras = doc.paragraphs

    # Print current para indices for verification
    for i, p in enumerate(paras):
        if p.text.strip():
            print(f"{i:4d}: {p.text[:100]}")

    # Find key anchors
    bulleted_summary_idx = find_para_containing(doc, "Bulleted summary (newest at top)")
    summary_history_idx = find_para_containing(doc, "Summary History (older tick lines")

    if bulleted_summary_idx is None:
        print("ERROR: Could not find 'Bulleted summary' heading", file=sys.stderr)
        sys.exit(1)
    if summary_history_idx is None:
        print("ERROR: Could not find 'Summary History' heading", file=sys.stderr)
        sys.exit(1)

    print(f"\nBulleted summary heading at para {bulleted_summary_idx}")
    print(f"Summary History heading at para {summary_history_idx}")

    # The 3 current tick summaries are at bulleted_summary_idx+1, +2, +3
    # (newest = +1 = ~21:57, middle = +2 = ~13:27, oldest = +3 = ~13:12)
    oldest_summary_idx = bulleted_summary_idx + 3

    print(f"\nOldest summary (to move) at para {oldest_summary_idx}:")
    print(f"  '{doc.paragraphs[oldest_summary_idx].text[:120]}'")

    # Verify this is the ~13:12 tick
    if "13:12" not in doc.paragraphs[oldest_summary_idx].text:
        print(f"WARNING: Para {oldest_summary_idx} does not contain '13:12' as expected. Text:", file=sys.stderr)
        print(f"  '{doc.paragraphs[oldest_summary_idx].text[:200]}'", file=sys.stderr)
        # Still proceed but log warning

    # Step 1: Clone the oldest summary paragraph and insert it after Summary History heading
    # (summary_history_idx may shift after we insert at the top, so do the bottom operation first)
    print(f"\nStep 1: Cloning oldest summary to position after Summary History heading (idx {summary_history_idx})")
    clone_paragraph_after(doc, oldest_summary_idx, summary_history_idx)

    # Step 2: Remove the original oldest summary (it's now at bulleted_summary_idx+3)
    # Recalculate indices since we inserted a paragraph
    # After inserting after summary_history_idx, the oldest_summary is still at bulleted_summary_idx+3
    # (the insert was BELOW it in the doc), so index hasn't changed
    print(f"\nStep 2: Removing oldest summary from original position (idx {oldest_summary_idx})")
    remove_paragraph(doc, oldest_summary_idx)

    # Step 3: Insert new tick summary after bulleted_summary_idx
    print(f"\nStep 3: Inserting new tick summary after bulleted_summary heading (idx {bulleted_summary_idx})")
    insert_new_paragraph_after(doc, bulleted_summary_idx, NEW_SUMMARY)

    # Save
    doc.save(DOCX_PATH)
    print(f"\nSaved. Verifying paragraph count...")

    # Quick verify
    doc2 = docx.Document(DOCX_PATH)
    print(f"Total paragraphs after: {len(doc2.paragraphs)}")
    bs_idx2 = find_para_containing(doc2, "Bulleted summary (newest at top)")
    sh_idx2 = find_para_containing(doc2, "Summary History (older tick lines")
    if bs_idx2 is not None and sh_idx2 is not None:
        print(f"\nBulleted summary section (paras {bs_idx2} to {bs_idx2+4}):")
        for i in range(bs_idx2, min(bs_idx2+5, len(doc2.paragraphs))):
            print(f"  {i}: {doc2.paragraphs[i].text[:120]}")
        print(f"\nSummary History section (paras {sh_idx2} to {sh_idx2+3}):")
        for i in range(sh_idx2, min(sh_idx2+4, len(doc2.paragraphs))):
            print(f"  {i}: {doc2.paragraphs[i].text[:120]}")

    print("\nDone.")

if __name__ == "__main__":
    main()
