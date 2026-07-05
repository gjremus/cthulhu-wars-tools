#!/usr/bin/env python3
"""Surgical docx editor for BGA current tasks doc.
Uses pandoc markdown as intermediary — does line-level edits only.

Usage:
  bga-doc-edit.py move-to-completed "search text unique to the bullet"
  bga-doc-edit.py remove "search text unique to the bullet"
  bga-doc-edit.py add-open "- \\[\\] new task text here"
  bga-doc-edit.py add-completed "- [x] completed task text"
  bga-doc-edit.py mark-done "search text" "replacement text for the [x] version"
  bga-doc-edit.py add-summary "- summary text"
  bga-doc-edit.py insert-after "search text" "new text"
  bga-doc-edit.py replace-bullet "search text" "new text"

The search text should be enough of the bullet to uniquely identify it.
Multi-line bullets (indented continuation) are handled as a group.
"""
import subprocess, sys, os

DOC = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/BGA/BGA current tasks.docx"
PANDOC = "/Users/gremus/.local/bin/pandoc"

def read_doc():
    result = subprocess.run([PANDOC, DOC, "-t", "markdown"], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"pandoc read failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout

def write_doc(md):
    result = subprocess.run(
        [PANDOC, "-f", "markdown", "-t", "docx", "-o", DOC, "--reference-doc", DOC],
        input=md, capture_output=True, text=True
    )
    if result.returncode != 0:
        result = subprocess.run(
            [PANDOC, "-f", "markdown", "-t", "docx", "-o", DOC],
            input=md, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"pandoc write failed: {result.stderr}", file=sys.stderr)
            sys.exit(1)

def find_paragraph(lines, search):
    search_lower = search.lower()
    for i, line in enumerate(lines):
        if search_lower in line.lower() and not line.startswith('- '):
            start = i
            end = start + 1
            while end < len(lines):
                l = lines[end]
                if l.strip() == '' or l.startswith('- ') or l.strip() in ('Open', 'In Progress', 'Completed'):
                    break
                if not l.startswith(' ') and not l.startswith('\t'):
                    break
                end += 1
            return start, end
    return None, None

def find_bullet(lines, search):
    search_lower = search.lower()
    for i, line in enumerate(lines):
        if search_lower in line.lower():
            start = i
            while start > 0 and not lines[start].startswith('- '):
                start -= 1
            if not lines[start].startswith('- '):
                continue
            end = start + 1
            while end < len(lines):
                l = lines[end]
                if l.startswith('- '):
                    break
                if l.strip() == '' and end + 1 < len(lines) and (lines[end+1].startswith('- ') or lines[end+1].strip() in ('Open', 'In Progress', 'Completed') or not lines[end+1].startswith(' ')):
                    break
                if l.strip() in ('Open', 'In Progress', 'Completed'):
                    break
                end += 1
            return start, end
    return None, None

def find_section_end(lines, section_name):
    in_section = False
    sections = ('Open', 'In Progress', 'Completed')
    for i, line in enumerate(lines):
        if line.strip() == section_name:
            in_section = True
            continue
        if in_section and line.strip() in sections:
            j = i - 1
            while j > 0 and lines[j].strip() == '':
                j -= 1
            return j + 1
    if in_section:
        return len(lines)
    return None

def cmd_remove(search):
    md = read_doc()
    lines = md.split('\n')
    start, end = find_bullet(lines, search)
    if start is None:
        start, end = find_paragraph(lines, search)
    if start is None:
        print(f"Could not find bullet containing: {search}", file=sys.stderr)
        sys.exit(1)
    removed = '\n'.join(lines[start:end])
    print(f"Removing: {removed[:100]}...")
    del lines[start:end]
    cleaned = []
    prev_blank = False
    for line in lines:
        if line.strip() == '':
            if prev_blank:
                continue
            prev_blank = True
        else:
            prev_blank = False
        cleaned.append(line)
    write_doc('\n'.join(cleaned))
    print("Done.")

def cmd_move_to_completed(search):
    md = read_doc()
    lines = md.split('\n')
    start, end = find_bullet(lines, search)
    if start is None:
        print(f"Could not find bullet containing: {search}", file=sys.stderr)
        sys.exit(1)
    bullet_lines = lines[start:end]
    print(f"Moving to Completed: {bullet_lines[0][:80]}...")
    del lines[start:end]
    for i, line in enumerate(lines):
        if line.strip() == 'Completed':
            insert_at = i + 1
            if insert_at < len(lines) and lines[insert_at].strip() == '':
                insert_at += 1
            for j, bl in enumerate(bullet_lines):
                lines.insert(insert_at + j, bl)
            lines.insert(insert_at + len(bullet_lines), '')
            break
    write_doc('\n'.join(lines))
    print("Done.")

def cmd_mark_done(search, replacement_text=None):
    md = read_doc()
    lines = md.split('\n')
    start, end = find_bullet(lines, search)
    if start is None:
        print(f"Could not find bullet containing: {search}", file=sys.stderr)
        sys.exit(1)
    old_bullet = lines[start:end]
    print(f"Marking done: {old_bullet[0][:80]}...")
    del lines[start:end]
    if replacement_text:
        new_bullet = replacement_text.split('\n')
    else:
        first = old_bullet[0]
        first = first.replace('\\[\\]', '[x]').replace('\\[/\\]', '[x]').replace('[/]', '[x]').replace('[ ]', '[x]')
        new_bullet = [first] + old_bullet[1:]
    for i, line in enumerate(lines):
        if line.strip() == 'Completed':
            insert_at = i + 1
            if insert_at < len(lines) and lines[insert_at].strip() == '':
                insert_at += 1
            for j, bl in enumerate(new_bullet):
                lines.insert(insert_at + j, bl)
            lines.insert(insert_at + len(new_bullet), '')
            break
    write_doc('\n'.join(lines))
    print("Done.")

def cmd_add_open(text):
    md = read_doc()
    lines = md.split('\n')
    for i, line in enumerate(lines):
        if line.strip() in ('\\[\\].', '- \\[\\].'):
            lines.insert(i, '')
            lines.insert(i, text)
            break
    else:
        for i, line in enumerate(lines):
            if line.strip() == 'In Progress':
                lines.insert(i, '')
                lines.insert(i, text)
                break
    write_doc('\n'.join(lines))
    print("Done.")

def cmd_add_completed(text):
    md = read_doc()
    lines = md.split('\n')
    for i, line in enumerate(lines):
        if line.strip() == 'Completed':
            insert_at = i + 1
            if insert_at < len(lines) and lines[insert_at].strip() == '':
                insert_at += 1
            lines.insert(insert_at, '')
            lines.insert(insert_at, text)
            break
    write_doc('\n'.join(lines))
    print("Done.")

def cmd_add_summary(text):
    md = read_doc()
    lines = md.split('\n')
    for i, line in enumerate(lines):
        if 'Bulleted summary' in line and 'newest' in line:
            insert_at = i + 1
            if insert_at < len(lines) and lines[insert_at].strip() == '':
                insert_at += 1
            lines.insert(insert_at, '')
            lines.insert(insert_at, text)
            break
    write_doc('\n'.join(lines))
    print("Done.")

def cmd_insert_after(search, text):
    md = read_doc()
    lines = md.split('\n')
    search_lower = search.lower()
    for i, line in enumerate(lines):
        if search_lower in line.lower():
            lines.insert(i + 1, '')
            lines.insert(i + 2, text)
            write_doc('\n'.join(lines))
            print(f"Inserted after line {i}: {line[:60]}...")
            return
    print(f"Could not find line containing: {search}", file=sys.stderr)
    sys.exit(1)

def cmd_replace_bullet(search, new_text):
    md = read_doc()
    lines = md.split('\n')
    start, end = find_bullet(lines, search)
    if start is None:
        print(f"Could not find bullet containing: {search}", file=sys.stderr)
        sys.exit(1)
    old = '\n'.join(lines[start:end])
    print(f"Replacing: {old[:80]}...")
    new_lines = new_text.split('\n')
    lines[start:end] = new_lines
    write_doc('\n'.join(lines))
    print("Done.")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == 'remove':
        cmd_remove(sys.argv[2])
    elif cmd == 'move-to-completed':
        cmd_move_to_completed(sys.argv[2])
    elif cmd == 'mark-done':
        replacement = sys.argv[3] if len(sys.argv) > 3 else None
        cmd_mark_done(sys.argv[2], replacement)
    elif cmd == 'add-open':
        cmd_add_open(sys.argv[2])
    elif cmd == 'add-completed':
        cmd_add_completed(sys.argv[2])
    elif cmd == 'add-summary':
        cmd_add_summary(sys.argv[2])
    elif cmd == 'insert-after':
        if len(sys.argv) < 4:
            print("insert-after requires search and text arguments", file=sys.stderr)
            sys.exit(1)
        cmd_insert_after(sys.argv[2], sys.argv[3])
    elif cmd == 'replace-bullet':
        if len(sys.argv) < 4:
            print("replace-bullet requires search and replacement arguments", file=sys.stderr)
            sys.exit(1)
        cmd_replace_bullet(sys.argv[2], sys.argv[3])
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
