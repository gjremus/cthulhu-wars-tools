#!/usr/bin/env python3
"""Move tasks between sheets in master current tasks.xlsx.

The ticker MUST use this script for ALL xlsx writes. It is FORBIDDEN
from writing its own openpyxl code.

TWO-SHEET MODEL:
  "Open Tasks" — all active work (status: O = open, / = in progress)
  "Completed Tasks" — archive of finished work (status: X)

The ticker marks O → / in place. The OWNER marks / → X.
The ticker's ONLY movement job: when it sees X in Open Tasks, move to Completed.

Usage:
  task-move.py start <row_number>
      Mark a task as in-progress IN PLACE (sets column A to /, sets started timestamp).
      The row stays in "Open Tasks". Does NOT move it anywhere.

  task-move.py complete <row_number>
      Move an X-marked row from "Open Tasks" → "Completed Tasks".
      The ticker calls this ONLY after the OWNER has marked column A as X.
      Sets completed timestamp. Copies all columns.

  task-move.py reopen <row_number>
      Reset a / task back to O in "Open Tasks" (if ticker can't finish it this tick).

  task-move.py append <sheet> <row_number> <comment_text>
      SAFE DEFAULT for tick notes. Appends comment_text to whatever is already in
      column C, so history can NEVER be lost by accident. Idempotent: re-running
      with the same tail text does nothing. USE THIS for every routine tick note.
      Sheet must be one of: open, completed, summary

  task-move.py comment <sheet> <row_number> <comment_text>
      OVERWRITES all of column C with comment_text. Use ONLY to deliberately
      correct/replace a cell — never for routine notes (it destroys history).
      Sheet must be one of: open, completed, summary

  task-move.py read
      Dump all sheets (except Rules) in a readable format.

Row numbers are 1-indexed as shown in the spreadsheet (row 1 = header).

SAFETY:
  - Enforces 5-minute mtime lockout (aborts if doc modified within 5 min by someone else)
  - Creates backup before every write
  - NEVER touches column B (task description) — only reads it
  - NEVER touches the Rules sheet
  - Verifies source row exists before moving
"""
import sys, os, time, shutil
import docguard_lock  # unlock()/relock() the OS immutable flag around our write

XLSX = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/master current tasks.xlsx"
BACKUP_DIR = os.path.expanduser("~/.cw-xlsx-backups")
OUR_WRITE_MARKER = os.path.join(BACKUP_DIR, ".last-ticker-write")
LOCKOUT_SECONDS = 300

SHEET_OPEN = "Open Tasks"
SHEET_DONE = "Completed Tasks"
SHEET_SUMMARY = "Recent Summary"

def check_lockout():
    try:
        mtime = os.path.getmtime(XLSX)
    except OSError:
        return
    age = time.time() - mtime
    if age >= LOCKOUT_SECONDS:
        return
    try:
        with open(OUR_WRITE_MARKER, 'r') as f:
            our_last = float(f.read().strip())
        if abs(mtime - our_last) < 10:
            return
    except (OSError, ValueError):
        pass
    print(f"LOCKOUT: xlsx modified {int(age)}s ago (need {LOCKOUT_SECONDS}s). Aborting.", file=sys.stderr)
    sys.exit(2)

def mark_our_write():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with open(OUR_WRITE_MARKER, 'w') as f:
        f.write(str(time.time()))

# Exit code 3 == Google Drive is actively syncing this file right now (distinct
# from LOCKOUT==2, "a human edited it recently"). The caller treats code 3 as:
# wait 5 min and retry; keep retrying; after ~1h record a note + alert but NEVER
# delete/move/copy the file. Writing during a live Drive sync makes Drive's
# conflict resolver spawn "(1)"/"(2)" copies and move the open working copy to
# the Trash; this guard declines to write during that window.
#   NOTE: exit code 3 was previously used by save_wb's grow-guard. That guard
#   now exits 6 (see save_wb) so code 3 unambiguously means "Drive busy".
DRIVE_BUSY = 3

def check_drive_sync():
    try:
        s1 = os.stat(XLSX)
    except OSError:
        return
    time.sleep(1.5)
    try:
        s2 = os.stat(XLSX)
    except OSError:
        print("DRIVE BUSY: file vanished while checking for Drive sync; will retry.", file=sys.stderr)
        sys.exit(DRIVE_BUSY)
    if (s1.st_size, int(s1.st_mtime)) != (s2.st_size, int(s2.st_mtime)):
        print("DRIVE BUSY: Google Drive is actively syncing this file "
              "(size/mtime changing). Not writing into a live sync; will retry.", file=sys.stderr)
        sys.exit(DRIVE_BUSY)

def backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(BACKUP_DIR, f"master-tasks-{stamp}.xlsx")
    try:
        shutil.copy2(XLSX, dst)
        docguard_lock.unlock(dst)  # keep our own backups mutable/prunable
    except OSError as e:
        print(f"WARNING: backup failed: {e}", file=sys.stderr)
        return
    # Prune surplus backups (keep 3 newest) by deleting IN PLACE inside our own
    # private BACKUP_DIR. Never move to ~/.Trash: these copies are named like the
    # live tasks file, so trashing them looks exactly like the real file vanished,
    # and it bypasses the docx/xlsx guard hook. Only ever remove files that
    # physically live inside BACKUP_DIR.
    backups = sorted(
        [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.endswith('.xlsx')],
        key=os.path.getmtime, reverse=True
    )
    real_backup_dir = os.path.realpath(BACKUP_DIR)
    for old in backups[3:]:
        if os.path.realpath(os.path.dirname(old)) != real_backup_dir:
            continue
        try:
            os.remove(old)
        except OSError:
            pass

def _materialize_or_die(path, tries=30, delay=8):
    """Google Drive File Stream sometimes serves this file as a non-materialized
    ('dataless') placeholder. The ONLY thing that triggers Drive's on-demand
    download is reading the WHOLE file to EOF -- a small peek (e.g. read(2))
    returns an empty/stub buffer and NEVER kicks off the fetch, so the old
    peek-then-poll loop could spin forever on a file that a plain full read
    materializes instantly (verified 2026-08-26: read(2) -> b'' while a full
    open().read() pulled all bytes and flipped the file to materialized). So we
    force a full read every attempt and only accept a complete PK zip. This is
    NOT corruption: the file is fine once Drive materializes it. Only if Drive
    never downloads it do we exit(1) with a clear 'mount issue' message."""
    for i in range(tries):
        try:
            with open(path, 'rb') as fh:
                data = fh.read()  # full read is what forces the on-demand fetch
            if len(data) >= 4 and data[:2] == b'PK':
                return
            # empty/short buffer => still a dataless stub; re-stat and retry
            try:
                os.stat(path)
            except OSError:
                pass
        except OSError as e:
            # EDEADLK / 'resource deadlock avoided' / 'resource busy' mid-fetch
            print(f"materialize attempt {i+1}/{tries}: {e}", file=sys.stderr)
        time.sleep(delay)
    print(f"FAILED: master xlsx stayed dataless (not a zip) after {tries} "
          f"materialize attempts over ~{tries*delay}s — Google Drive did not "
          "download it. This is a Drive mount issue, not file corruption.",
          file=sys.stderr)
    sys.exit(1)

def load_wb():
    import openpyxl
    _materialize_or_die(XLSX)
    for attempt in range(3):
        try:
            return openpyxl.load_workbook(XLSX)
        except Exception as e:
            if attempt < 2:
                _materialize_or_die(XLSX)  # re-nudge Drive before each retry
                time.sleep(5)
            else:
                print(f"FAILED to load xlsx after 3 attempts: {e}", file=sys.stderr)
                sys.exit(1)

def save_wb(wb):
    check_lockout()
    check_drive_sync()
    backup()
    check_lockout()
    # Guard: count rows in Open Tasks BEFORE saving. If it grew beyond what
    # we expect (header + data rows we read), refuse to save — something tried
    # to insert rows. The complete command DELETES a row (net -1), start/comment
    # don't change row count (net 0). Growing is NEVER valid.
    ws_open = wb[SHEET_OPEN]
    new_count = sum(1 for r in range(1, ws_open.max_row + 1) if ws_open.cell(row=r, column=2).value)
    marker_file = os.path.join(BACKUP_DIR, ".open-task-count")
    try:
        with open(marker_file, 'r') as f:
            prev_count = int(f.read().strip())
        if new_count > prev_count:
            # exit 6 (integrity guard), NOT 3 — code 3 is reserved for Drive-busy.
            print(f"FATAL: Open Tasks grew from {prev_count} to {new_count} rows. REFUSING TO SAVE. Something tried to insert rows.", file=sys.stderr)
            sys.exit(6)
    except (OSError, ValueError):
        pass
    # Final Drive-sync check in the narrowest window right before the write, then
    # capture the file identity. openpyxl writes directly to XLSX (it does not
    # os.replace), so the inode — and therefore the Drive file ID and sharing —
    # is preserved. If the inode changes across the save, Drive swapped the file
    # underneath us (conflicted copy); treat as Drive-busy and retry.
    check_drive_sync()
    try:
        pre_ino = os.stat(XLSX).st_ino
    except OSError:
        pre_ino = None
    # XLSX is OS-locked (uchg); lift only for the save, always restore.
    _was_locked = docguard_lock.unlock(XLSX)
    try:
        wb.save(XLSX)
    finally:
        if _was_locked:
            docguard_lock.relock(XLSX)
    if pre_ino is not None:
        try:
            post_ino = os.stat(XLSX).st_ino
        except OSError:
            post_ino = None
        if post_ino is not None and post_ino != pre_ino:
            print("DRIVE BUSY: file identity (inode) changed during save — Drive "
                  "may have swapped/conflicted the file; will retry. A backup was "
                  "made before the write.", file=sys.stderr)
            sys.exit(DRIVE_BUSY)
    mark_our_write()
    # Update the row count marker after successful save
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with open(marker_file, 'w') as f:
        f.write(str(new_count))

def get_row_data(ws, row):
    """Read columns A-H from a row. Returns dict."""
    return {
        'status': ws.cell(row=row, column=1).value or '',
        'task': ws.cell(row=row, column=2).value or '',
        'comment': ws.cell(row=row, column=3).value or '',
        'started': ws.cell(row=row, column=4).value or '',
        'completed': ws.cell(row=row, column=5).value or '',
        'priority': ws.cell(row=row, column=6).value or '',
        'build': ws.cell(row=row, column=7).value or '',
        'game': ws.cell(row=row, column=8).value or '',
    }


def cmd_start(row_num):
    """Mark a task as in-progress in Open Tasks (no move). O → /"""
    wb = load_wb()
    ws = wb[SHEET_OPEN]

    data = get_row_data(ws, row_num)
    if not data['task']:
        print(f"ERROR: Row {row_num} in '{SHEET_OPEN}' is empty (no task text in column B).", file=sys.stderr)
        sys.exit(1)

    stamp = time.strftime("%Y-%m-%d %H:%M")
    ws.cell(row=row_num, column=1, value='/')
    ws.cell(row=row_num, column=4, value=stamp)

    save_wb(wb)
    print(f"Done. Marked in-progress: {data['task'][:80]}... Started: {stamp}")

def cmd_complete(row_num):
    """Move an X-marked task from Open Tasks → Completed Tasks."""
    wb = load_wb()
    src = wb[SHEET_OPEN]
    dst = wb[SHEET_DONE]

    data = get_row_data(src, row_num)
    if not data['task']:
        print(f"ERROR: Row {row_num} in '{SHEET_OPEN}' is empty (no task text in column B).", file=sys.stderr)
        sys.exit(1)

    status = str(data['status']).strip().upper()
    if status != 'X':
        print(f"ERROR: Row {row_num} status is '{data['status']}', not 'X'. Only move X tasks to Completed.", file=sys.stderr)
        sys.exit(1)

    print(f"Moving to Completed: {data['task'][:80]}...")

    stamp = time.strftime("%Y-%m-%d %H:%M")

    # Insert at row 2 (right after header), shifting all existing rows down
    dst.insert_rows(2)
    dst.cell(row=2, column=1, value='X')
    dst.cell(row=2, column=2, value=data['task'])
    dst.cell(row=2, column=3, value=data['comment'])
    dst.cell(row=2, column=4, value=data['started'])
    dst.cell(row=2, column=5, value=stamp)
    dst.cell(row=2, column=6, value=data['priority'])
    dst.cell(row=2, column=7, value=data['build'])
    dst.cell(row=2, column=8, value=data['game'])

    src.delete_rows(row_num)

    save_wb(wb)
    print(f"Done. Moved to '{SHEET_DONE}' row 2 (top). Completed: {stamp}")

def cmd_reopen(row_num):
    """Reset a / task back to O in Open Tasks."""
    wb = load_wb()
    ws = wb[SHEET_OPEN]

    data = get_row_data(ws, row_num)
    if not data['task']:
        print(f"ERROR: Row {row_num} in '{SHEET_OPEN}' is empty.", file=sys.stderr)
        sys.exit(1)

    ws.cell(row=row_num, column=1, value='O')
    ws.cell(row=row_num, column=4, value='')

    save_wb(wb)
    print(f"Done. Reset to open: {data['task'][:80]}...")

def cmd_comment(sheet_key, row_num, text):
    """Write a comment to column C."""
    sheet_map = {'open': SHEET_OPEN, 'completed': SHEET_DONE, 'summary': SHEET_SUMMARY}
    if sheet_key not in sheet_map:
        print(f"ERROR: sheet must be one of: open, completed, summary. Got: {sheet_key}", file=sys.stderr)
        sys.exit(1)

    wb = load_wb()
    ws = wb[sheet_map[sheet_key]]

    if sheet_key == 'summary':
        from datetime import datetime
        ws.cell(row=row_num, column=1, value=text)
        ws.cell(row=row_num, column=2, value=datetime.now().strftime("%Y-%m-%d %H:%M CDT"))
        save_wb(wb)
        print(f"Done. Updated summary row {row_num}: {text[:60]}...")
        return

    task = ws.cell(row=row_num, column=2).value
    if not task:
        print(f"ERROR: Row {row_num} in '{sheet_map[sheet_key]}' is empty.", file=sys.stderr)
        sys.exit(1)

    ws.cell(row=row_num, column=3, value=text)
    save_wb(wb)
    print(f"Done. Updated comment on row {row_num}: {text[:60]}...")

def cmd_append(sheet_key, row_num, text):
    """APPEND text to column C without ever destroying what is already there.

    This is the SAFE default for the ticker's per-pass notes. The old 'comment'
    command overwrites the whole cell, so any tick that passed only its new note
    (instead of old+new concatenated) silently wiped the row's entire history —
    the recurring 'my previous edit overwrote and lost this row's record' bug.
    Appending here makes that class of data loss impossible.

    Idempotent: if the exact new text is already the tail of the cell (a resumed
    or re-run tick), it is NOT appended again, so retries can't duplicate notes.
    """
    sheet_map = {'open': SHEET_OPEN, 'completed': SHEET_DONE, 'summary': SHEET_SUMMARY}
    if sheet_key not in sheet_map:
        print(f"ERROR: sheet must be one of: open, completed, summary. Got: {sheet_key}", file=sys.stderr)
        sys.exit(1)

    wb = load_wb()
    ws = wb[sheet_map[sheet_key]]

    task = ws.cell(row=row_num, column=2).value
    if not task:
        print(f"ERROR: Row {row_num} in '{sheet_map[sheet_key]}' is empty.", file=sys.stderr)
        sys.exit(1)

    existing = ws.cell(row=row_num, column=3).value or ''
    new_text = text.strip()
    if not new_text:
        print("ERROR: refusing to append empty text.", file=sys.stderr)
        sys.exit(1)

    if existing.rstrip().endswith(new_text):
        print(f"No change — that note is already the latest on row {row_num} (idempotent skip).")
        return

    combined = (existing.rstrip() + ' ' + new_text) if existing.strip() else new_text
    ws.cell(row=row_num, column=3, value=combined)
    save_wb(wb)
    print(f"Done. Appended to row {row_num} (cell now {len(combined)} chars): ...{new_text[:60]}")

def cmd_add_task(task_description):
    """DISABLED — tickers are forbidden from adding tasks. Only the owner adds tasks."""
    print("ERROR: The 'add' command is disabled. Tickers CANNOT add new tasks.")
    print("Only the owner creates tasks. If you found a bug, write it in column C as INPUT NEEDED.")
    sys.exit(1)

def cmd_read():
    """Dump all task sheets in readable format."""
    wb = load_wb()
    for sheet_name in [SHEET_OPEN, SHEET_DONE]:
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        print(f"\n=== {sheet_name} ===")
        for row in range(1, ws.max_row + 1):
            vals = []
            for col in range(1, 9):
                v = ws.cell(row=row, column=col).value
                vals.append(str(v) if v else '')
            if any(vals):
                print(f"  Row {row}: {' | '.join(vals)}")
    if "Recent Summary" in wb.sheetnames:
        ws = wb["Recent Summary"]
        print(f"\n=== Recent Summary ===")
        for row in range(1, ws.max_row + 1):
            v = ws.cell(row=row, column=1).value
            if v:
                print(f"  Row {row}: {v}")
    # Record the Open Tasks row count as baseline for the grow-guard
    if SHEET_OPEN in wb.sheetnames:
        ws = wb[SHEET_OPEN]
        count = sum(1 for r in range(1, ws.max_row + 1) if ws.cell(row=r, column=2).value)
        os.makedirs(BACKUP_DIR, exist_ok=True)
        marker_file = os.path.join(BACKUP_DIR, ".open-task-count")
        with open(marker_file, 'w') as f:
            f.write(str(count))

def cmd_read_rules():
    """Read-only dump of the Rules sheet."""
    wb = load_wb()
    if "Rules" not in wb.sheetnames:
        print("No 'Rules' sheet found.")
        return
    ws = wb["Rules"]
    print("\n=== Rules ===")
    for row in ws.iter_rows(values_only=True):
        print("  " + " | ".join(str(v) if v else '' for v in row))

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == 'start' and len(sys.argv) == 3:
        cmd_start(int(sys.argv[2]))
    elif cmd == 'complete' and len(sys.argv) == 3:
        cmd_complete(int(sys.argv[2]))
    elif cmd == 'reopen' and len(sys.argv) == 3:
        cmd_reopen(int(sys.argv[2]))
    elif cmd == 'comment' and len(sys.argv) == 5:
        cmd_comment(sys.argv[2], int(sys.argv[3]), sys.argv[4])
    elif cmd == 'append' and len(sys.argv) == 5:
        cmd_append(sys.argv[2], int(sys.argv[3]), sys.argv[4])
    elif cmd == 'add' and len(sys.argv) == 3:
        cmd_add_task(sys.argv[2])
    elif cmd == 'read':
        cmd_read()
    elif cmd == 'read-rules':
        cmd_read_rules()
    else:
        print(__doc__)
        sys.exit(1)
