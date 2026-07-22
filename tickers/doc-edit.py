#!/usr/bin/env python3
"""Surgical docx editor for master tasks doc.
Uses pandoc markdown as intermediary — does line-level edits only.

Usage:
  doc-edit.py move-to-completed "search text unique to the bullet"
  doc-edit.py remove "search text unique to the bullet"
  doc-edit.py add-open "- \\[\\] new task text here"
  doc-edit.py add-completed "- [x] completed task text"
  doc-edit.py mark-done "search text" "replacement text for the [x] version"

The search text should be enough of the bullet to uniquely identify it.
Multi-line bullets (indented continuation) are handled as a group.
"""
import subprocess, sys, os

DOC = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx"
PANDOC = "/Users/gremus/.local/bin/pandoc"
LOCKOUT_SECONDS = 300  # 5 minutes
BACKUP_DIR = os.path.expanduser("~/.cw-doc-backups")
OUR_WRITE_MARKER = os.path.expanduser("~/.cw-doc-backups/.last-ticker-write")

def mark_our_write():
    """Record that WE just wrote the doc, so our own mtime doesn't trigger lockout."""
    os.makedirs(os.path.dirname(OUR_WRITE_MARKER), exist_ok=True)
    with open(OUR_WRITE_MARKER, 'w') as f:
        import time
        f.write(str(time.time()))

def check_lockout():
    """Enforce 5-minute mtime lockout. Abort if doc was modified recently by someone other than us."""
    import time
    try:
        mtime = os.path.getmtime(DOC)
    except OSError:
        return
    age = time.time() - mtime
    if age >= LOCKOUT_SECONDS:
        return
    # Check if the recent modification was our own write
    try:
        with open(OUR_WRITE_MARKER, 'r') as f:
            our_last = float(f.read().strip())
        # If doc mtime is within 10 seconds of our last write marker, it's ours
        if abs(mtime - our_last) < 10:
            return
    except (OSError, ValueError):
        pass
    print(f"LOCKOUT: doc modified {int(age)}s ago (need {LOCKOUT_SECONDS}s). ABORTING write to protect user edits.", file=sys.stderr)
    sys.exit(2)

def backup_before_write():
    """Create a backup of the current doc BEFORE any write operation."""
    import shutil, time
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"master-tasks-{timestamp}.docx")
    try:
        shutil.copy2(DOC, backup_path)
    except OSError as e:
        print(f"WARNING: backup failed: {e}", file=sys.stderr)
        return
    # Keep only 2 most recent backups, move others to Trash
    backups = sorted(
        [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.endswith('.docx')],
        key=os.path.getmtime, reverse=True
    )
    trash = os.path.expanduser("~/.Trash")
    for old in backups[2:]:
        try:
            shutil.move(old, os.path.join(trash, os.path.basename(old)))
        except OSError:
            pass

_read_hash = None

def read_doc():
    global _read_hash
    import hashlib
    result = subprocess.run([PANDOC, DOC, "-t", "markdown"], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"pandoc read failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    try:
        with open(DOC, 'rb') as f:
            _read_hash = hashlib.sha256(f.read()).hexdigest()
    except OSError:
        _read_hash = None
    return result.stdout

def verify_no_external_changes():
    """Abort if the doc content changed since we read it (race condition protection)."""
    import hashlib
    global _read_hash
    if _read_hash is None:
        return
    try:
        with open(DOC, 'rb') as f:
            current_hash = hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return
    if current_hash != _read_hash:
        print("ABORT: doc content changed between read and write — someone edited it while we were working. NOT writing.", file=sys.stderr)
        sys.exit(3)

def write_doc(md):
    check_lockout()
    verify_no_external_changes()
    backup_before_write()
    check_lockout()
    verify_no_external_changes()
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
    mark_our_write()

def find_paragraph(lines, search):
    """Find a bare paragraph (non-bullet) containing search text. Returns (start_idx, end_idx)."""
    search_lower = search.lower()
    for i, line in enumerate(lines):
        if search_lower in line.lower() and not line.startswith('- '):
            start = i
            # Walk forward to end of paragraph (blank line or section header)
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
    """Find a bullet containing search text. Returns (start_idx, end_idx) of the full bullet including continuations."""
    search_lower = search.lower()
    for i, line in enumerate(lines):
        if search_lower in line.lower():
            start = i
            # Walk backwards to find the bullet start (in case search matched a continuation line)
            while start > 0 and not lines[start].startswith('- '):
                start -= 1
            if not lines[start].startswith('- '):
                continue
            # Walk forward to find the end of this bullet (next bullet, blank line before non-continuation, or section header)
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
    """Find the line index just before the next section after section_name."""
    in_section = False
    sections = ('Open', 'In Progress', 'Completed')
    for i, line in enumerate(lines):
        if line.strip() == section_name:
            in_section = True
            continue
        if in_section and line.strip() in sections:
            # Return the line before this section header (skip trailing blanks)
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
    # Remove consecutive blank lines
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
    # Find Completed section and insert at the top
    for i, line in enumerate(lines):
        if line.strip() == 'Completed':
            # Insert after "Completed" header and the blank line following it
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
    # Remove from current location
    del lines[start:end]
    # Build completed version
    if replacement_text:
        new_bullet = replacement_text.split('\n')
    else:
        # Auto-mark: change \[\] or [/] to [x]
        first = old_bullet[0]
        first = first.replace('\\[\\]', '[x]').replace('\\[/\\]', '[x]').replace('[/]', '[x]').replace('[ ]', '[x]')
        new_bullet = [first] + old_bullet[1:]
    # Find Completed section and insert at top
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
    # Find the empty \[\]. bullet at the end of Open and insert before it
    for i, line in enumerate(lines):
        if line.strip() in ('\\[\\].', '- \\[\\].'):
            lines.insert(i, '')
            lines.insert(i, text)
            break
    else:
        # No empty bullet found, insert before In Progress
        for i, line in enumerate(lines):
            if line.strip() == 'In Progress':
                lines.insert(i, '')
                lines.insert(i, text)
                break
    write_doc('\n'.join(lines))
    print("Done.")

def cmd_add_in_progress(text):
    md = read_doc()
    lines = md.split('\n')
    for i, line in enumerate(lines):
        if line.strip() == 'In Progress':
            insert_at = i + 1
            if insert_at < len(lines) and lines[insert_at].strip() == '':
                insert_at += 1
            lines.insert(insert_at, '')
            lines.insert(insert_at, text)
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
    """Add a summary bullet at the top of the Bulleted summary section."""
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
    """Insert text on the line after the first line containing search."""
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
    """Replace a bullet's content (found by search) with new text."""
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

def cmd_remove_paragraph(search):
    """Remove a bare paragraph (non-bullet) containing search text."""
    md = read_doc()
    lines = md.split('\n')
    start, end = find_paragraph(lines, search)
    if start is None:
        print(f"Could not find bare paragraph containing: {search}", file=sys.stderr)
        sys.exit(1)
    removed = '\n'.join(lines[start:end])
    print(f"Removing paragraph: {removed[:100]}...")
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

def cmd_remove_exact_line(exact_text):
    """Remove the first line whose stripped content matches exact_text exactly."""
    md = read_doc()
    lines = md.split('\n')
    for i, line in enumerate(lines):
        if line.strip() == exact_text:
            print(f"Removing exact line {i}: {line}")
            del lines[i]
            # Clean up double blank
            if i < len(lines) and i > 0 and lines[i-1].strip() == '' and lines[i].strip() == '':
                del lines[i]
            write_doc('\n'.join(lines))
            print("Done.")
            return
    print(f"Could not find exact line: {exact_text}", file=sys.stderr)
    sys.exit(1)

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
    elif cmd == 'add-in-progress':
        cmd_add_in_progress(sys.argv[2])
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
    elif cmd == 'remove-paragraph':
        cmd_remove_paragraph(sys.argv[2])
    elif cmd == 'remove-exact-line':
        cmd_remove_exact_line(sys.argv[2])
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
