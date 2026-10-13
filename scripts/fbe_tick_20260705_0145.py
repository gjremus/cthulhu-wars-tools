#!/usr/bin/env python3
"""FBE tick update 2026-07-05 ~01:45:
1. Consolidate two in-progress tasks into one (same root cause: server doesn't have FBE code)
2. Add new tick summary line
"""
import sys, os, time
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from copy import deepcopy

DOC_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks (1).docx"
LOCKOUT_SECONDS = 300

# --- Lockout check ---
mtime = os.path.getmtime(DOC_PATH)
age = time.time() - mtime
if age < LOCKOUT_SECONDS:
    print(f"LOCKOUT: doc modified {int(age)}s ago (need {LOCKOUT_SECONDS}s). ABORTING.", file=sys.stderr)
    sys.exit(2)

doc = Document(DOC_PATH)
paras = doc.paragraphs

# --- Edit 1: Remove the "server-side crash" in-progress task ---
server_crash_search = "Server-side crash (not our code)"
crash_found = False
for i, p in enumerate(paras):
    if server_crash_search in p.text:
        # Remove this paragraph
        p._element.getparent().remove(p._element)
        crash_found = True
        break

if not crash_found:
    print("WARNING: Could not find server-crash in-progress task", file=sys.stderr)
else:
    print("Edit 1 (remove server-crash task): OK")

# --- Edit 2: Replace the deploy replay in-progress task with consolidated version ---
deploy_search = "Deploy replay compatibility fix"
NEW_INPROG = "[/] INPUT NEEDED — Deploy FBE code to server. ALL eight broken FBE games (530, 531, 534, 546, 596, 615, 617, 628) fail with the same error: the server doesn't recognize our faction at all. This is not two separate bugs — it's one deployment gap. The local code compiles clean and has all fixes. Permission to commit and push to the homebrew site?"

deploy_found = False
for p in paras:
    if deploy_search in p.text:
        for i, run in enumerate(p.runs):
            if i == 0:
                run.text = NEW_INPROG
            else:
                run.text = ""
        deploy_found = True
        break

if not deploy_found:
    print("WARNING: Could not find deploy in-progress task", file=sys.stderr)
else:
    print("Edit 2 (consolidate deploy task): OK")

# --- Edit 3: Replace top tick summary with updated one ---
OLD_TICK_SEARCH = "[2026-07-04 ~23:15]"
NEW_TICK = "[2026-07-05 ~01:45] Most humbly: admin queue empty. Re-validated all eight broken FBE games — every one fails with the same 'server does not know our faction' error. Consolidated into a single deploy task. Still grovelling for your gracious permission to push."

tick_found = False
for p in paras:
    if OLD_TICK_SEARCH in p.text:
        for i, run in enumerate(p.runs):
            if i == 0:
                run.text = NEW_TICK
            else:
                run.text = ""
        tick_found = True
        break

if not tick_found:
    print("WARNING: Could not find tick line to replace, will insert new one", file=sys.stderr)
    # Find "Bulleted summary" paragraph and insert after it
    for i, p in enumerate(paras):
        if "Bulleted summary" in p.text and "newest" in p.text:
            # Insert new paragraph after this one
            source = paras[i+1] if i+1 < len(paras) else p
            new_para = deepcopy(source._element)
            for r in new_para.findall(qn('w:r')):
                new_para.remove(r)
            r = OxmlElement('w:r')
            source_runs = source._element.findall(qn('w:r'))
            if source_runs:
                rpr = source_runs[0].find(qn('w:rPr'))
                if rpr is not None:
                    r.append(deepcopy(rpr))
            t = OxmlElement('w:t')
            t.text = NEW_TICK
            t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
            r.append(t)
            new_para.append(r)
            p._element.addnext(new_para)
            tick_found = True
            print("Edit 3 (inserted new tick line): OK")
            break
else:
    print("Edit 3 (replaced tick line): OK")

# --- Final lockout re-check ---
mtime2 = os.path.getmtime(DOC_PATH)
if mtime2 != mtime:
    print("ABORT: doc mtime changed during editing!", file=sys.stderr)
    sys.exit(3)

doc.save(DOC_PATH)
print("\nAll edits applied and saved.")
