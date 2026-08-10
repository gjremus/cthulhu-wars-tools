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
"""
import sys, json, re

def block(reason):
    sys.stderr.write("BLOCKED BY DOCX GUARD: " + reason + "\n")
    sys.stderr.write("Tickers may only change a .docx via hb-doc-edit.py/"
                     "fbe-doc-edit.py replace-text. No delete/move/trash/overwrite.\n")
    sys.exit(2)

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # If we can't parse input, fail OPEN would be unsafe; but blocking all
        # tools would wedge the ticker. Only Bash is hooked, so allow-through
        # here would still be caught by the specific patterns below on retry.
        sys.exit(0)

    tool = payload.get("tool_name") or payload.get("tool") or ""
    if tool != "Bash":
        sys.exit(0)

    ti = payload.get("tool_input") or payload.get("input") or {}
    cmd = ti.get("command", "")
    if not cmd:
        sys.exit(0)

    low = cmd.lower()
    # A PRIMARY document reference ends AT the extension: ".docx" / ".xlsx"
    # followed by end-of-string, whitespace, a quote, a paren, or a redirect —
    # NOT by another char. This deliberately does NOT match a backup file such
    # as "Foo.docx.20260810-095658.bak" (there ".docx" is followed by "."), so
    # the ticker may freely trash/delete its OWN backups while every op against
    # a live .docx/.xlsx is still blocked. (Rule: never move/delete/trash a MAIN
    # doc; only backups.)
    PRIMARY_DOCX_RE = re.compile(r'\.docx(?![.\w])')
    PRIMARY_XLSX_RE = re.compile(r'\.xlsx(?![.\w])')
    mentions_docx = bool(PRIMARY_DOCX_RE.search(low))
    mentions_xlsx = bool(PRIMARY_XLSX_RE.search(low))

    # The one sanctioned pattern: our surgical editors. Allow them through.
    sanctioned = ("hb-doc-edit.py" in cmd) or ("fbe-doc-edit.py" in cmd)
    # The one sanctioned path for the master spreadsheet.
    sanctioned_xlsx = "task-move.py" in cmd

    # pandoc producing docx output is banned regardless of an explicit filename
    # (it strips embedded fonts and destroys these files).
    if "pandoc" in low and not sanctioned:
        if ((("-o" in low or "--output" in low) and ".docx" in low)
                or re.search(r'-t\s+docx', low)
                or "--to=docx" in low or "--to docx" in low):
            block("attempt to WRITE a .docx with pandoc (strips fonts, destroys file).")

    # 1) Any destructive verb anywhere near a .docx => block.
    if mentions_docx:
        # rm / unlink
        if re.search(r'\b(rm|unlink|trash|rmtrash)\b', low):
            block("attempt to delete a .docx (rm/unlink/trash).")
        # mv / rename a docx (moving to Trash or elsewhere)
        if re.search(r'\bmv\b', low):
            block("attempt to move/rename a .docx (mv).")
        # trash via Finder/osascript/AppleScript "delete"
        if "osascript" in low and "delete" in low:
            block("attempt to trash a .docx via AppleScript.")
        # explicit ~/.Trash target
        if ".trash" in low:
            block("attempt to send a .docx to the Trash.")
        # pandoc writing a docx (-o something.docx, or -t docx)
        if "pandoc" in low and (re.search(r'-o\s+\S*\.docx', low) or "-t docx" in low or "--to=docx" in low):
            if not sanctioned:
                block("attempt to WRITE a .docx with pandoc (strips fonts, destroys file).")
        # cp OVER an existing docx (cp source dest.docx) — allow cp to a NEW backup name only if not overwriting is unknowable here, so block cp-to-docx outright unless sanctioned
        if re.search(r'\bcp\b', low) and re.search(r'\.docx\b', low):
            if not sanctioned:
                block("attempt to cp onto/over a .docx.")
        # shell redirection into a docx ( > file.docx )
        if re.search(r'>\s*\S*\.docx', low):
            block("attempt to overwrite a .docx via shell redirection.")

    # 2) python/python3 that imports docx libs or opens Document() — block
    #    (covers inline -c and here-doc styles) regardless of .docx mention.
    if re.search(r'\bpython3?\b', low):
        if ("import docx" in low or "from docx" in low or "docx.document(" in low
                or "load_workbook" in low or "import openpyxl" in low
                or "import xlsxwriter" in low):
            if not sanctioned:
                block("attempt to open/write an Office file via python docx/openpyxl.")

        # GAP CLOSED (2026-08-05): a script can clobber a .docx WITHOUT importing
        # docx/openpyxl — just `open(path, "w"/"a"/"wb")` or
        # `zipfile.ZipFile(path, "w"/"a")` on the raw file (this is exactly how a
        # docx is a zip, so it's the real destruction path). Block any python that
        # mentions a .docx AND opens it for writing/appending, or zips to it.
        # The sanctioned surgical editors are exempt (checked above via `sanctioned`).
        if mentions_docx and not sanctioned:
            # Normalise away backslashes/quotes so shell-escaped forms like
            # open(\"x.docx\",\"w\") match the same as open("x.docx","w").
            norm = low.replace("\\", "").replace('"', '').replace("'", "")
            # open( ... .docx ... , <mode with w/a/x/+> ) — any write/append/truncate mode
            if re.search(r'open\s*\([^)]*\.docx[^)]*,\s*[rwax+b]*[wax+][rwax+b]*\s*\)', norm):
                block("attempt to open a .docx for writing/appending in python (clobbers the file).")
            # zipfile.ZipFile( ... .docx ... , <w/a> ) — writing the docx zip directly
            if re.search(r'zipfile\s*\([^)]*\.docx[^)]*,\s*[wa]', norm):
                block("attempt to write a .docx zip directly in python (clobbers the file).")
            # shutil copy/move, os remove/rename/replace, pathlib unlink/rename/write onto a .docx
            if re.search(r'(shutil\.(copy\w*|move)|os\.(remove|unlink|rename|replace)|\.(unlink|write_bytes|write_text)\s*\()', norm) and ".docx" in norm:
                block("attempt to remove/rename/overwrite a .docx via python (shutil/os/pathlib).")

    # ---- MASTER SPREADSHEET (.xlsx) GUARD -------------------------------
    # The master tasks spreadsheet may ONLY be touched via task-move.py.
    # Anything else that could delete/move/overwrite it, or open it with a
    # spreadsheet library outside task-move.py, is blocked.
    if mentions_xlsx and not sanctioned_xlsx:
        # rm / unlink / trash
        if re.search(r'\b(rm|unlink|trash|rmtrash)\b', low):
            block("attempt to delete a .xlsx (rm/unlink/trash).")
        # mv / rename
        if re.search(r'\bmv\b', low):
            block("attempt to move/rename a .xlsx (mv).")
        # cp over an xlsx
        if re.search(r'\bcp\b', low):
            block("attempt to cp onto/over a .xlsx.")
        # AppleScript trash
        if "osascript" in low and "delete" in low:
            block("attempt to trash a .xlsx via AppleScript.")
        # explicit Trash target
        if ".trash" in low:
            block("attempt to send a .xlsx to the Trash.")
        # shell redirection into an xlsx
        if re.search(r'>\s*\S*\.xlsx', low):
            block("attempt to overwrite a .xlsx via shell redirection.")

    # python touching spreadsheet libs, outside task-move.py, is blocked
    # regardless of an explicit .xlsx filename (the libs ARE the write path).
    if re.search(r'\bpython3?\b', low) and not sanctioned_xlsx:
        if ("load_workbook" in low or "import openpyxl" in low
                or "from openpyxl" in low or "import xlsxwriter" in low
                or "import pandas" in low or "import xlrd" in low
                or "read_excel" in low or "to_excel" in low):
            block("attempt to open/write the master spreadsheet via python "
                  "(openpyxl/pandas/xlrd/xlsxwriter). Use task-move.py only.")
        # raw open()/zipfile write onto an .xlsx (a .xlsx is a zip, same as docx)
        if mentions_xlsx:
            norm = low.replace("\\", "").replace('"', '').replace("'", "")
            if re.search(r'open\s*\([^)]*\.xlsx[^)]*,\s*[rwax+b]*[wax+][rwax+b]*\s*\)', norm):
                block("attempt to open a .xlsx for writing/appending in python (clobbers the file).")
            if re.search(r'zipfile\s*\([^)]*\.xlsx[^)]*,\s*[wa]', norm):
                block("attempt to write a .xlsx zip directly in python (clobbers the file).")
            if re.search(r'(shutil\.(copy\w*|move)|os\.(remove|unlink|rename|replace)|\.(unlink|write_bytes|write_text)\s*\()', norm) and ".xlsx" in norm:
                block("attempt to remove/rename/overwrite a .xlsx via python (shutil/os/pathlib).")

    # 3) safe-docx-write.sh is permanently banned (full-file replacement).
    if "safe-docx-write.sh" in low:
        block("safe-docx-write.sh is banned (full-file replacement destroys docs).")

    sys.exit(0)

if __name__ == "__main__":
    main()
