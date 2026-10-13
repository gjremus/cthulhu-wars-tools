#!/usr/bin/env python3
"""
FBE Tick update — 2026-06-25 ~15:35
1. Replace [2026-06-25 ~14:10] nothing-happened summary bullet with the new tick summary.
2. Move oldest summary bullet [2026-06-25 ~02:53] to Summary History.
3. Change [/] In-Progress task to [x] and move it to Completed section.
"""
import docx
import copy
import sys

PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks.docx"

NEW_SUMMARY = (
    "[2026-06-25 ~15:35] Humble apologies for the wait — the Distributed Death fix and real faction logo "
    "(commit 812b0c7) are confirmed live: server build verified at 3,978,745 bytes. "
    "Admin queue drained: 8 old FBE test games from before the current fixes flagged, no new code bugs."
)

COMPLETED_TEXT = (
    "[x] Distributed Death unit-choice + excess-Pain fix + real faction logo — CONFIRMED LIVE "
    "2026-06-25 ~15:19 (commit 812b0c7, HB v2.12, server build verified). "
    "Saved units are now immune to follow-up pain in the same battle; player now picks which unit(s) to save. "
    "Real fbe-glyph shown in faction picker, confirmation screen, and on the map. "
    "Documented in HB Rollback Guide Fix HB-F."
)

doc = docx.Document(PATH)

# ── Print paragraph map for verification ─────────────────────────────────────
def reindex():
    result = {}
    for i, p in enumerate(doc.paragraphs):
        t = p.text.strip()
        if t == "Bulleted summary (newest at top)": result['summary'] = i
        elif t == "Open": result['open'] = i
        elif t == "In Progress": result['ip_header'] = i
        elif t == "Completed": result['completed'] = i
        elif t == "Summary History (older tick lines, archived per the brevity rule)": result['history'] = i
        elif t.startswith("[/] Distributed Death fix"): result['ip_task'] = i
    return result

idx = reindex()
print("Initial index:", idx)

# Verify the doc structure
assert 'summary' in idx, "Missing Bulleted summary header"
assert 'open' in idx, "Missing Open header"
assert 'ip_header' in idx, "Missing In Progress header"
assert 'completed' in idx, "Missing Completed header"
assert 'history' in idx, "Missing Summary History header"
assert 'ip_task' in idx, "Missing [/] In-Progress task"

# ── Find the summary bullets between 'summary' and 'open' ────────────────────
sb = [(i, doc.paragraphs[i]) for i in range(idx['summary']+1, idx['open'])
      if doc.paragraphs[i].text.strip()]
print(f"Summary bullets ({len(sb)}):")
for i, p in sb:
    print(f"  [{i}]: {p.text[:80]}")

# Rule 33: keep ≤3 summary bullets. Current: 3 (14:12, 14:10, 02:53).
# Per rule 34: one nothing-happened bullet exists — REPLACE it (don't move to history).
# The ~14:10 bullet is the nothing-happened one.
# The ~02:53 is the oldest substantive — move to history.
# Then we'll have: [new tick, 14:12] = 2 bullets.

# Find nothing-happened bullet (14:10)
nothing_idx = None
for i, p in sb:
    if "quiet tick" in p.text or "nothing happened" in p.text.lower():
        nothing_idx = i
        break
print(f"Nothing-happened bullet at para {nothing_idx}")

# Find oldest substantive (02:53)
oldest_idx = None
for i, p in reversed(sb):
    if i != nothing_idx:
        oldest_idx = i
        break
print(f"Oldest substantive bullet at para {oldest_idx}")

# ── Step 1: Replace nothing-happened bullet with new summary ─────────────────
if nothing_idx is not None:
    p = doc.paragraphs[nothing_idx]
    # Clear runs and set new text
    for r in p.runs:
        r.text = ""
    if p.runs:
        p.runs[0].text = NEW_SUMMARY
    else:
        p.add_run(NEW_SUMMARY)
    print(f"Step 1: replaced nothing-happened bullet at {nothing_idx}")
else:
    # No nothing-happened bullet found: insert new summary after header
    from lxml import etree
    from docx.oxml.ns import qn
    anchor = doc.paragraphs[idx['summary']]
    # Copy style from first summary bullet
    if sb:
        new_el = copy.deepcopy(doc.paragraphs[sb[0][0]]._element)
        for child in list(new_el):
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag in ('r', 'hyperlink', 'ins'):
                new_el.remove(child)
        r = etree.SubElement(new_el, qn('w:r'))
        t = etree.SubElement(r, qn('w:t'))
        t.text = NEW_SUMMARY
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        anchor._p.addnext(new_el)
    print("Step 1: inserted new summary bullet after header (no nothing-happened bullet existed)")

# ── Step 2: Move oldest substantive bullet to Summary History ─────────────────
if oldest_idx is not None:
    old_text = doc.paragraphs[oldest_idx].text
    # Save element, remove from current position
    old_el = copy.deepcopy(doc.paragraphs[oldest_idx]._element)
    doc.paragraphs[oldest_idx]._element.getparent().remove(doc.paragraphs[oldest_idx]._element)
    # Re-find history index
    hist_i = None
    for i, p in enumerate(doc.paragraphs):
        if "Summary History" in p.text:
            hist_i = i
            break
    doc.paragraphs[hist_i]._element.addnext(old_el)
    print(f"Step 2: moved oldest bullet to Summary History. Text: {old_text[:80]}")
else:
    print("Step 2: no oldest bullet to move")

# ── Step 3: Update [/] task → [x] with new text ───────────────────────────────
idx = reindex()
print("After steps 1-2, index:", idx)

ip_para = doc.paragraphs[idx['ip_task']]
# Clear runs
for r in ip_para.runs:
    r.text = ""
if ip_para.runs:
    ip_para.runs[0].text = COMPLETED_TEXT
else:
    ip_para.add_run(COMPLETED_TEXT)
print(f"Step 3: updated [/] task text to [x]. First 80 chars: {ip_para.text[:80]}")

# ── Step 4: Move [x] task from In-Progress to Completed ──────────────────────
idx = reindex()
# Find the now-[x] task (it starts with "[x] Distributed Death unit-choice")
task_final_idx = None
for i, p in enumerate(doc.paragraphs):
    if p.text.strip().startswith("[x] Distributed Death unit-choice"):
        task_final_idx = i
        break
completed_final_idx = idx.get('completed')
print(f"Moving [x] task from {task_final_idx} to after Completed header at {completed_final_idx}")

if task_final_idx is not None and completed_final_idx is not None:
    task_el = copy.deepcopy(doc.paragraphs[task_final_idx]._element)
    doc.paragraphs[task_final_idx]._element.getparent().remove(
        doc.paragraphs[task_final_idx]._element)
    # Re-find completed after removal
    comp_final2 = None
    for i, p in enumerate(doc.paragraphs):
        if p.text.strip() == "Completed":
            comp_final2 = i
            break
    doc.paragraphs[comp_final2]._element.addnext(task_el)
    print(f"Step 4: moved [x] task to Completed section")

# ── Final verification ─────────────────────────────────────────────────────────
idx2 = reindex()
sb2 = [(i, doc.paragraphs[i]) for i in range(idx2['summary']+1, idx2['open'])
       if doc.paragraphs[i].text.strip()]
print(f"\nFinal summary bullets ({len(sb2)}):")
for i, p in sb2:
    print(f"  [{i}]: {p.text[:80]}")

# Check [/] is gone from In-Progress section
ip_remaining = [(i, doc.paragraphs[i]) for i in range(idx2['ip_header']+1, idx2['completed'])
                if doc.paragraphs[i].text.strip()]
print(f"\nIn-Progress remaining tasks ({len(ip_remaining)}):")
for i, p in ip_remaining:
    print(f"  [{i}]: {p.text[:80]}")

# Check [x] is in Completed section
comp_hist_range = idx2.get('history', len(doc.paragraphs))
completed_tasks = [(i, doc.paragraphs[i]) for i in range(idx2['completed']+1, comp_hist_range)
                   if doc.paragraphs[i].text.strip().startswith("[x]")]
print(f"\nCompleted [x] tasks (first 3):")
for i, p in completed_tasks[:3]:
    print(f"  [{i}]: {p.text[:80]}")

doc.save(PATH)
print("\nSaved OK.")
