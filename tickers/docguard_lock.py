"""Shared immutable-flag helper for the sanctioned CW doc editors.

Every LIVE task .docx / .xlsx is protected with the BSD user-immutable flag
(`chflags uchg`). The kernel then refuses ALL delete / overwrite / rename of
that file — from rm, mv, truncate, python, the Write tool, anything — with
EPERM, regardless of the command form. That OS-level lock, not any string
matcher, is what makes a task doc impossible to destroy.

The ONLY code allowed to lift that lock is a sanctioned surgical editor
(hb-doc-edit.py / fbe-doc-edit.py / doc-edit.py / bga-doc-edit.py /
task-move.py), and only for the microseconds of its in-place write. It does so
by calling unlock() immediately before the write and relock() immediately after
(in a finally, so a crash still re-locks). These calls happen INSIDE the .py
process, so the launching Bash command string never contains "chflags" and the
docx-guard hook (which blocks any shell/inline attempt to clear the flag) does
not — and must not — interfere with them.
"""
import os
import stat

# The user-immutable flag. Present on macOS/BSD. On platforms without it these
# helpers degrade to no-ops so the editors still run.
_UF_IMMUTABLE = getattr(stat, "UF_IMMUTABLE", 0x00000002)


def is_locked(path):
    """True if `path` currently carries the user-immutable flag."""
    try:
        return bool(os.stat(path).st_flags & _UF_IMMUTABLE)
    except (OSError, AttributeError):
        return False


def unlock(path):
    """Clear the immutable flag so the file can be written in place.

    Returns True if the file WAS locked (so the caller knows to relock).
    Never raises: a file that cannot be unlocked simply stays as-is and the
    subsequent write will fail loudly on its own.
    """
    try:
        flags = os.stat(path).st_flags
    except (OSError, AttributeError):
        return False
    if not (flags & _UF_IMMUTABLE):
        return False
    try:
        os.chflags(path, flags & ~_UF_IMMUTABLE)
        return True
    except (OSError, AttributeError):
        return False


def relock(path):
    """(Re)apply the immutable flag. Safe to call unconditionally."""
    try:
        flags = os.stat(path).st_flags
        os.chflags(path, flags | _UF_IMMUTABLE)
        return True
    except (OSError, AttributeError):
        return False
