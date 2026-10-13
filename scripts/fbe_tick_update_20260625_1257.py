#!/usr/bin/env python3
"""FBE ticker update — 2026-06-25 ~12:57. Updates the 'nothing happened' summary bullet."""

from docx import Document
import copy

DOCX_PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/HomeBrews/Faceless Blight Current Tasks.docx"

NEW_SUMMARY = (
    "[2026-06-25 ~12:57] Humbly reporting another quiet tick: admin queue is empty, "
    "Homebrew site is healthy (cache 20260625-090552, HTTP 200), worktree is clean, "
    "and no open Faceless Blight tasks remain."
)

OLD_NOTHING_HAPPENED_SNIPPET = "[2026-06-25 ~08:58]"

doc = Document(DOCX_PATH)

found = False
for para in doc.paragraphs:
    if para.text.startswith(OLD_NOTHING_HAPPENED_SNIPPET):
        # Preserve formatting of the first run, update text
        full_text = NEW_SUMMARY
        # Clear existing runs and set the text on the first run
        for i, run in enumerate(para.runs):
            if i == 0:
                run.text = full_text
            else:
                run.text = ""
        found = True
        break

if not found:
    raise RuntimeError(f"Could not find paragraph starting with: {OLD_NOTHING_HAPPENED_SNIPPET!r}")

doc.save(DOCX_PATH)
print(f"Updated summary bullet. Found={found}")
