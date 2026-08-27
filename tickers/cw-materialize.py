#!/usr/bin/env python3
"""Force Google Drive File Stream to download 'dataless' placeholder files.

WHY THIS EXISTS
---------------
Google Drive on macOS keeps files as `compressed,dataless` placeholders and only
downloads the real bytes on demand. The trigger is reading the WHOLE file to EOF.
A small peek (pandoc's buffered header read, zipfile's central-directory seek, a
`read(2)`) does NOT kick off the fetch -- Drive hands back an empty/stub buffer or
raises EDEADLK ("resource deadlock avoided" / "resource busy"). Verified live on
2026-08-26: `read(2)` returned b'' on a dataless .docx while a full `open().read()`
pulled all 8.3 MB and flipped the file to materialized, after which pandoc read it
fine. The tickers had been logging a bogus multi-hour "Drive outage" that was
really just this never-triggered download.

Reading the whole file is NOT corruption and does NOT modify the file. Run this on
any Drive path (or several) BEFORE reading it with pandoc / zipfile / openpyxl.

USAGE
-----
    cw-materialize.py "<path>" ["<path2>" ...]

Exit 0 if every path materialized to non-empty bytes (zip files also PK-verified).
Exit 1 if any path could not be materialized after the retry budget (real Drive
mount problem, not a per-file issue).
"""
import os
import sys
import time

TRIES = 18
DELAY = 8


def materialize(path, tries=TRIES, delay=DELAY):
    """Force a full read to trigger Drive's on-demand download. Returns True once
    the file reads to EOF with a plausible payload; False if it never downloads."""
    is_zip = path.lower().endswith((".docx", ".xlsx", ".pptx", ".zip"))
    for i in range(tries):
        try:
            with open(path, "rb") as fh:
                data = fh.read()  # full read is what forces the fetch
            if data and (not is_zip or data[:2] == b"PK"):
                return True
            # empty / non-zip stub => still dataless; re-stat to nudge and retry
            try:
                os.stat(path)
            except OSError:
                pass
        except OSError as e:
            # EDEADLK / resource busy mid-fetch -- transient, keep polling
            print(f"  materialize {os.path.basename(path)} "
                  f"attempt {i + 1}/{tries}: {e}", file=sys.stderr)
        time.sleep(delay)
    return False


def main(argv):
    if len(argv) < 2:
        print("usage: cw-materialize.py <path> [<path> ...]", file=sys.stderr)
        return 2
    ok = True
    for path in argv[1:]:
        if materialize(path):
            print(f"OK: {path}")
        else:
            print(f"FAILED to materialize (Drive mount issue, not corruption): "
                  f"{path}", file=sys.stderr)
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
