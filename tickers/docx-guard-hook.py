#!/usr/bin/env python3
"""PreToolUse guard hook for the Cthulhu Wars tickers.

Claude Code invokes this before every Bash tool call, passing the tool input as
JSON on stdin. This hook PHYSICALLY BLOCKS any command that could delete, move,
trash, rename, or overwrite a .docx file, or that would use pandoc/python to
write a .docx. It is the last line of defense independent of what the model's
prompt says or decides.

Exit code 0  => allow the command.
Exit code 2  => BLOCK the command (Claude Code treats nonzero PreToolUse as a
                deny and surfaces stderr to the model).

Only the sanctioned surgical editor (hb-doc-edit.py / fbe-doc-edit.py) may
change a .docx, and even those are matched explicitly so nothing else can.

--- 2026-08-18 false-positive fix ---
The destructive-verb detection used to match the *word* rm/unlink/trash/mv/cp
ANYWHERE in the command string. That wrongly blocked:
  * sanctioned hb-doc-edit.py reads/writes of files whose NAME contains the word
    "TRASH" (or a "DO NOT DELETE OR MOVE TO TRASH" safety suffix),
  * sanctioned writes whose REPLACEMENT TEXT merely mentioned trash/delete,
  * plain `ls`/`echo`/append commands that referenced a .docx filename and
    happened to contain one of those words in unrelated text.
It now (a) exempts the sanctioned editors from the delete/move checks (they
physically cannot delete — they only surgically replace text), and (b) only
treats rm/unlink/trash/rmtrash/mv/cp/osascript as destructive when they are the
actual COMMAND being run (first token of a shell segment), not a substring of a
quoted filename or free text. All the hard protections (chflags, redirect onto a
doc, python docx/openpyxl writes, pandoc-to-docx) are unchanged.
"""
import sys, json, re

def block(reason):
    sys.stderr.write("BLOCKED BY DOCX GUARD: " + reason + "\n")
    sys.stderr.write("Tickers may only change a .docx via hb-doc-edit.py/"
                     "fbe-doc-edit.py replace-text. No delete/move/trash/overwrite.\n")
    sys.exit(2)

# Split a shell command into segments on separators, and return the set of
# COMMAND names actually being invoked (first real token of each segment, with
# any leading `sudo`, `command`, `env`, or FOO=bar assignments stripped, and the
# path basename taken). This lets us tell `rm foo.docx` (command rm) apart from
# `echo "do not move to trash" > note.txt` or a filename that contains "trash".
def command_names(cmd):
    names = set()
    # separators: ; | & && || newline, and $( ) `...` command substitution starts
    segments = re.split(r'\|\||&&|[;\n|&]|\$\(|`', cmd)
    for seg in segments:
        toks = seg.strip().split()
        i = 0
        # strip leading env-assignments and simple wrappers
        while i < len(toks) and (re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', toks[i])
                                 or toks[i] in ("sudo", "command", "env", "nice",
                                                "nohup", "time", "exec", "\\")):
            i += 1
        if i < len(toks):
            base = toks[i].split('/')[-1].lower()
            names.add(base)
    return names

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool = payload.get("tool_name") or payload.get("tool") or ""
    ti = payload.get("tool_input") or payload.get("input") or {}

    # ---- NON-Bash file tools (Write/Edit/MultiEdit/NotebookEdit) ------------
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        p = (ti.get("file_path") or ti.get("path") or ti.get("notebook_path")
             or "").lower()
        if re.search(r'\.docx(?![.\w])', p) or re.search(r'\.xlsx(?![.\w])', p):
            block(f"attempt to write a .docx/.xlsx via the {tool} tool "
                  "(corrupts the zip / destroys the doc). Use the surgical editor.")
        sys.exit(0)

    if tool != "Bash":
        sys.exit(0)

    cmd = ti.get("command", "")
    if not cmd:
        sys.exit(0)

    low = cmd.lower()
    PRIMARY_DOCX_RE = re.compile(r'\.docx(?![.\w])')
    PRIMARY_XLSX_RE = re.compile(r'\.xlsx(?![.\w])')
    mentions_docx = bool(PRIMARY_DOCX_RE.search(low))
    mentions_xlsx = bool(PRIMARY_XLSX_RE.search(low))

    # The one sanctioned pattern: our surgical editors. Allow them through.
    sanctioned = ("hb-doc-edit.py" in cmd) or ("fbe-doc-edit.py" in cmd)
    # The one sanctioned path for the master spreadsheet.
    sanctioned_xlsx = "task-move.py" in cmd

    # Command verbs actually being invoked in this command line.
    verbs = command_names(cmd)
    DELETE_VERBS = {"rm", "unlink", "trash", "rmtrash", "trash-put", "gio"}
    MOVE_VERBS = {"mv"}
    COPY_VERBS = {"cp"}

    # ---- IMMUTABLE-LOCK PROTECTION (unconditional) --------------------------
    if (mentions_docx or mentions_xlsx) and re.search(r'\bchflags\b', low):
        block("attempt to change filesystem flags on a .docx/.xlsx "
              "(would strip the delete-protection lock). Owner: use cw-doclock.sh.")

    # pandoc producing docx output is banned regardless of an explicit filename.
    if "pandoc" in low and not sanctioned:
        if ((("-o" in low or "--output" in low) and ".docx" in low)
                or re.search(r'-t\s+docx', low)
                or "--to=docx" in low or "--to docx" in low):
            block("attempt to WRITE a .docx with pandoc (strips fonts, destroys file).")

    # 1) A destructive COMMAND acting where a .docx is referenced => block.
    #    Gated by `not sanctioned`: hb-doc-edit.py/fbe-doc-edit.py cannot delete.
    if mentions_docx and not sanctioned:
        if verbs & DELETE_VERBS:
            block("attempt to delete a .docx (rm/unlink/trash) — destructive command.")
        if verbs & MOVE_VERBS:
            block("attempt to move/rename a .docx (mv).")
        if verbs & COPY_VERBS:
            block("attempt to cp onto/over a .docx.")
        # trash via Finder/osascript "delete"
        if "osascript" in verbs and "delete" in low:
            block("attempt to trash a .docx via AppleScript.")
        # shell redirection into a docx ( > file.docx ) — unambiguous overwrite.
        # Allow spaces inside a (possibly quoted) path — the real doc names all
        # contain spaces, e.g. "HomeBrews Current Tasks.docx"; a \S* target match
        # stops at the first space and misses them. Match up to a command separator.
        if re.search(r'>>?\s*["\']?[^|;&\n]*\.docx', low):
            block("attempt to overwrite a .docx via shell redirection.")
        # pandoc writing a docx (redundant safety, kept for clarity)
        if "pandoc" in verbs and (re.search(r'-o\s+\S*\.docx', low) or "-t docx" in low or "--to=docx" in low):
            block("attempt to WRITE a .docx with pandoc (strips fonts, destroys file).")

    # 2) python/python3 that imports docx libs or opens Document() — block.
    if re.search(r'\bpython3?\b', low):
        if ("import docx" in low or "from docx" in low or "docx.document(" in low
                or "load_workbook" in low or "import openpyxl" in low
                or "import xlsxwriter" in low):
            if not sanctioned:
                block("attempt to open/write an Office file via python docx/openpyxl.")

        if mentions_docx and not sanctioned:
            norm = low.replace("\\", "").replace('"', '').replace("'", "")
            if re.search(r'open\s*\([^)]*\.docx[^)]*,\s*[rwax+b]*[wax+][rwax+b]*\s*\)', norm):
                block("attempt to open a .docx for writing/appending in python (clobbers the file).")
            if re.search(r'zipfile\s*\([^)]*\.docx[^)]*,\s*[wa]', norm):
                block("attempt to write a .docx zip directly in python (clobbers the file).")
            if re.search(r'(shutil\.(copy\w*|move)|os\.(remove|unlink|rename|replace|chflags|chmod)|\.(unlink|write_bytes|write_text)\s*\()', norm) and ".docx" in norm:
                block("attempt to remove/rename/overwrite/unlock a .docx via python (shutil/os/pathlib).")

    # ---- MASTER SPREADSHEET (.xlsx) GUARD -----------------------------------
    if mentions_xlsx and not sanctioned_xlsx:
        if verbs & DELETE_VERBS:
            block("attempt to delete a .xlsx (rm/unlink/trash) — destructive command.")
        if verbs & MOVE_VERBS:
            block("attempt to move/rename a .xlsx (mv).")
        if verbs & COPY_VERBS:
            block("attempt to cp onto/over a .xlsx.")
        if "osascript" in verbs and "delete" in low:
            block("attempt to trash a .xlsx via AppleScript.")
        if re.search(r'>>?\s*["\']?[^|;&\n]*\.xlsx', low):
            block("attempt to overwrite a .xlsx via shell redirection.")

    if re.search(r'\bpython3?\b', low) and not sanctioned_xlsx:
        if ("load_workbook" in low or "import openpyxl" in low
                or "from openpyxl" in low or "import xlsxwriter" in low
                or "import pandas" in low or "import xlrd" in low
                or "read_excel" in low or "to_excel" in low):
            block("attempt to open/write the master spreadsheet via python "
                  "(openpyxl/pandas/xlrd/xlsxwriter). Use task-move.py only.")
        if mentions_xlsx:
            norm = low.replace("\\", "").replace('"', '').replace("'", "")
            if re.search(r'open\s*\([^)]*\.xlsx[^)]*,\s*[rwax+b]*[wax+][rwax+b]*\s*\)', norm):
                block("attempt to open a .xlsx for writing/appending in python (clobbers the file).")
            if re.search(r'zipfile\s*\([^)]*\.xlsx[^)]*,\s*[wa]', norm):
                block("attempt to write a .xlsx zip directly in python (clobbers the file).")
            if re.search(r'(shutil\.(copy\w*|move)|os\.(remove|unlink|rename|replace|chflags|chmod)|\.(unlink|write_bytes|write_text)\s*\()', norm) and ".xlsx" in norm:
                block("attempt to remove/rename/overwrite/unlock a .xlsx via python (shutil/os/pathlib).")

    # 3) safe-docx-write.sh is permanently banned (full-file replacement).
    if "safe-docx-write.sh" in low:
        block("safe-docx-write.sh is banned (full-file replacement destroys docs).")

    sys.exit(0)

if __name__ == "__main__":
    main()
