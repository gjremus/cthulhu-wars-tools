#!/usr/bin/env python3
"""Move tasks between sheets in master current tasks.xlsx.

The ticker MUST use these scripts for ALL task movements. It is FORBIDDEN
from writing its own openpyxl code to move rows between sheets.

Usage:
  task-move.py start <row_number>
      Move row from "Open Tasks" → "In Progress Tasks". Sets started timestamp.
      Copies: task(B), priority(F), build(G), game(H). Sets status to [/].

  task-move.py complete <row_number>
      OWNER ONLY. The ticker is FORBIDDEN from calling this command.
      Move row from "In Progress Tasks" → "Completed Tasks". Sets completed timestamp.
      Copies: task(B), claude comment(C), priority(F), build(G), game(H). Sets status to [x].

  task-move.py reopen <row_number>
      Move row from "In Progress Tasks" → "Open Tasks". Resets status to [].
      Copies: task(B), priority(F), build(G), game(H). Clears started timestamp.

  task-move.py comment <sheet> <row_number> <comment_text>
      Write comment text into column C of the given row on the given sheet.
      Sheet must be one of: open, inprogress, completed

  task-move.py read
      Dump all sheets (except Rules) in a readable format. For the ticker to read state.

Row numbers are 1-indexed as shown in the spreadsheet (row 1 = header).

SAFETY:
  - Enforces 5-minute mtime lockout (aborts if doc modified within 5 min by someone else)
  - Creates backup before every write
  - NEVER touches column B (task description) — only reads it
  - NEVER touches the Rules sheet
  - Verifies source row exists before moving
"""
import sys, os, time, shutil

XLSX = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/master current tasks.xlsx"
BACKUP_DIR = os.path.expanduser("~/.cw-xlsx-backups")
OUR_WRITE_MARKER = os.path.join(BACKUP_DIR, ".last-ticker-write")
LOCKOUT_SECONDS = 300

SHEET_OPEN = "Open Tasks"
SHEET_INPROG = "In Progress Tasks"
SHEET_DONE = "Completed Tasks"

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

def backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(BACKUP_DIR, f"master-tasks-{stamp}.xlsx")
    try:
        shutil.copy2(XLSX, dst)
    except OSError as e:
        print(f"WARNING: backup failed: {e}", file=sys.stderr)
        return
    backups = sorted(
        [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.endswith('.xlsx')],
        key=os.path.getmtime, reverse=True
    )
    trash = os.path.expanduser("~/.Trash")
    for old in backups[3:]:
        try:
            shutil.move(old, os.path.join(trash, os.path.basename(old)))
        except OSError:
            pass

def load_wb():
    import openpyxl
    for attempt in range(3):
        try:
            return openpyxl.load_workbook(XLSX)
        except Exception as e:
            if attempt < 2:
                time.sleep(5)
            else:
                print(f"FAILED to load xlsx after 3 attempts: {e}", file=sys.stderr)
                sys.exit(1)

def save_wb(wb):
    check_lockout()
    backup()
    check_lockout()
    wb.save(XLSX)
    mark_our_write()

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

def find_next_empty_row(ws):
    """Find the first empty row (where column B is empty)."""
    for row in range(2, ws.max_row + 2):
        if not ws.cell(row=row, column=2).value:
            return row
    return ws.max_row + 1

def cmd_start(row_num):
    """Move from Open Tasks → In Progress Tasks."""
    wb = load_wb()
    src = wb[SHEET_OPEN]
    dst = wb[SHEET_INPROG]

    data = get_row_data(src, row_num)
    if not data['task']:
        print(f"ERROR: Row {row_num} in '{SHEET_OPEN}' is empty (no task text in column B).", file=sys.stderr)
        sys.exit(1)

    print(f"Moving to In Progress: {data['task'][:80]}...")

    dest_row = find_next_empty_row(dst)
    stamp = time.strftime("%Y-%m-%d %H:%M")

    dst.cell(row=dest_row, column=1, value='[/]')
    dst.cell(row=dest_row, column=2, value=data['task'])
    dst.cell(row=dest_row, column=3, value=data['comment'])
    dst.cell(row=dest_row, column=4, value=stamp)
    dst.cell(row=dest_row, column=6, value=data['priority'])
    dst.cell(row=dest_row, column=7, value=data['build'])
    dst.cell(row=dest_row, column=8, value=data['game'])

    src.delete_rows(row_num)

    save_wb(wb)
    print(f"Done. Moved to '{SHEET_INPROG}' row {dest_row}. Started: {stamp}")

def cmd_complete(row_num):
    """Move from In Progress Tasks → Completed Tasks."""
    wb = load_wb()
    src = wb[SHEET_INPROG]
    dst = wb[SHEET_DONE]

    data = get_row_data(src, row_num)
    if not data['task']:
        print(f"ERROR: Row {row_num} in '{SHEET_INPROG}' is empty (no task text in column B).", file=sys.stderr)
        sys.exit(1)

    print(f"Moving to Completed: {data['task'][:80]}...")

    dest_row = find_next_empty_row(dst)
    stamp = time.strftime("%Y-%m-%d %H:%M")

    dst.cell(row=dest_row, column=1, value='[x]')
    dst.cell(row=dest_row, column=2, value=data['task'])
    dst.cell(row=dest_row, column=3, value=data['comment'])
    dst.cell(row=dest_row, column=4, value=data['started'])
    dst.cell(row=dest_row, column=5, value=stamp)
    dst.cell(row=dest_row, column=6, value=data['priority'])
    dst.cell(row=dest_row, column=7, value=data['build'])
    dst.cell(row=dest_row, column=8, value=data['game'])

    src.delete_rows(row_num)

    save_wb(wb)
    print(f"Done. Moved to '{SHEET_DONE}' row {dest_row}. Completed: {stamp}")

def cmd_reopen(row_num):
    """Move from In Progress Tasks → Open Tasks."""
    wb = load_wb()
    src = wb[SHEET_INPROG]
    dst = wb[SHEET_OPEN]

    data = get_row_data(src, row_num)
    if not data['task']:
        print(f"ERROR: Row {row_num} in '{SHEET_INPROG}' is empty (no task text in column B).", file=sys.stderr)
        sys.exit(1)

    print(f"Moving back to Open: {data['task'][:80]}...")

    dest_row = find_next_empty_row(dst)

    dst.cell(row=dest_row, column=1, value='[]')
    dst.cell(row=dest_row, column=2, value=data['task'])
    dst.cell(row=dest_row, column=3, value=data['comment'])
    dst.cell(row=dest_row, column=6, value=data['priority'])
    dst.cell(row=dest_row, column=7, value=data['build'])
    dst.cell(row=dest_row, column=8, value=data['game'])

    src.delete_rows(row_num)

    save_wb(wb)
    print(f"Done. Moved to '{SHEET_OPEN}' row {dest_row}.")

def cmd_comment(sheet_key, row_num, text):
    """Write a comment to column C."""
    sheet_map = {'open': SHEET_OPEN, 'inprogress': SHEET_INPROG, 'completed': SHEET_DONE}
    if sheet_key not in sheet_map:
        print(f"ERROR: sheet must be one of: open, inprogress, completed. Got: {sheet_key}", file=sys.stderr)
        sys.exit(1)

    wb = load_wb()
    ws = wb[sheet_map[sheet_key]]

    task = ws.cell(row=row_num, column=2).value
    if not task:
        print(f"ERROR: Row {row_num} in '{sheet_map[sheet_key]}' is empty.", file=sys.stderr)
        sys.exit(1)

    ws.cell(row=row_num, column=3, value=text)
    save_wb(wb)
    print(f"Done. Updated comment on row {row_num}: {text[:60]}...")

def cmd_read():
    """Dump all task sheets in readable format."""
    wb = load_wb()
    for sheet_name in [SHEET_OPEN, SHEET_INPROG, SHEET_DONE]:
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
    elif cmd == 'read':
        cmd_read()
    else:
        print(__doc__)
        sys.exit(1)
