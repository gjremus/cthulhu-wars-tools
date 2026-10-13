#!/usr/bin/env python3
"""
FBE Current Tasks ticker writer — updates the most recent summary bullet
"""
import sys
from docx import Document

if len(sys.argv) != 4:
    print("Usage: fbe_tick_writer.py <docx_path> <old_text> <new_text>", file=sys.stderr)
    sys.exit(2)

docx_path = sys.argv[1]
old_text = sys.argv[2]
new_text = sys.argv[3]

doc = Document(docx_path)

# Find and replace the text in paragraphs
replaced = False
for para in doc.paragraphs:
    if old_text in para.text:
        # Replace by clearing runs and adding new text with original formatting
        para.text = para.text.replace(old_text, new_text)
        replaced = True
        break

if not replaced:
    print(f"WARNING: Could not find text to replace: {old_text[:50]}...", file=sys.stderr)
    sys.exit(1)

doc.save(docx_path)
print(f"Updated tick summary in {docx_path}")
