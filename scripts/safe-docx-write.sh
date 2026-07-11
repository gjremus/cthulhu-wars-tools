#!/usr/bin/env bash
# safe-docx-write.sh — Guarded write for .docx files
# Usage: safe-docx-write.sh "/path/to/file.docx" "python3 /path/to/writer.py"

set -euo pipefail

TARGET="${1:-}"
WRITE_CMD="${2:-}"
LOCKOUT_SECONDS=300
WATCH_SECONDS=5

# ── Argument validation ────────────────────────────────────────────────────────
if [[ -z "$TARGET" || -z "$WRITE_CMD" ]]; then
    echo "Usage: safe-docx-write.sh <target.docx> <write-command>" >&2
    exit 2
fi

# ── Helper: get mtime as epoch seconds (macOS + Linux compatible) ──────────────
mtime_epoch() {
    local f="$1"
    if [[ "$(uname)" == "Darwin" ]]; then
        stat -f "%m" "$f"
    else
        stat -c "%Y" "$f"
    fi
}

# ── Step 1: 5-minute mtime lockout ────────────────────────────────────────────
if [[ -f "$TARGET" ]]; then
    FILE_MTIME=$(mtime_epoch "$TARGET")
    NOW=$(date +%s)
    AGE=$(( NOW - FILE_MTIME ))
    if (( AGE < LOCKOUT_SECONDS )); then
        echo "LOCKED: file modified ${AGE} seconds ago (lockout is ${LOCKOUT_SECONDS}s)"
        exit 1
    fi
fi

# ── Step 1b: Content hash check (catches Google Drive sync delays) ────────────
# After OUR last write, we save a hash. If the current hash doesn't match,
# someone else changed the file — abort even if mtime looks old.
HASH_FILE="${TARGET}.last_write_hash"
if [[ -f "$TARGET" && -f "$HASH_FILE" ]]; then
    SAVED_HASH=$(cat "$HASH_FILE" 2>/dev/null)
    CURRENT_HASH=$(shasum -a 256 "$TARGET" 2>/dev/null | awk '{print $1}')
    if [[ -n "$SAVED_HASH" && -n "$CURRENT_HASH" && "$SAVED_HASH" != "$CURRENT_HASH" ]]; then
        echo "LOCKED: file content changed since our last write (Google Drive sync detected)"
        echo "  Saved hash:   ${SAVED_HASH:0:16}..."
        echo "  Current hash: ${CURRENT_HASH:0:16}..."
        exit 1
    fi
fi

# ── Step 2: 5-second pre-write watch ──────────────────────────────────────────
if [[ -f "$TARGET" ]]; then
    MTIME_BEFORE=$(mtime_epoch "$TARGET")
    echo "Pre-write watch: waiting ${WATCH_SECONDS}s …"
    sleep "$WATCH_SECONDS"
    MTIME_AFTER_WATCH=$(mtime_epoch "$TARGET")
    if [[ "$MTIME_AFTER_WATCH" != "$MTIME_BEFORE" ]]; then
        echo "ABORTED: file changed during pre-watch"
        exit 1
    fi
    MTIME_PRE="$MTIME_BEFORE"
else
    echo "Pre-write watch: target does not exist yet, skipping mtime check."
    sleep "$WATCH_SECONDS"
    MTIME_PRE=0
fi

# ── Step 2b: Acquire lockfile (prevents concurrent writers) ───────────────────
LOCKFILE="${TARGET}.write_lock"
if ! mkdir "$LOCKFILE" 2>/dev/null; then
    echo "LOCKED: another writer holds the lock (${LOCKFILE})"
    exit 1
fi
trap 'rmdir "$LOCKFILE" 2>/dev/null' EXIT

# ── Step 3: Raw-bytes backup ───────────────────────────────────────────────────
if [[ -f "$TARGET" ]]; then
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP="/tmp/safe-docx-backup-${TIMESTAMP}.docx"
    cp -- "$TARGET" "$BACKUP"
    echo "Backup: ${BACKUP}"
fi

# ── Step 3b: Final mtime re-check (closes TOCTOU gap) ────────────────────────
if [[ -f "$TARGET" ]]; then
    MTIME_FINAL=$(mtime_epoch "$TARGET")
    if [[ "$MTIME_FINAL" != "$MTIME_PRE" ]]; then
        echo "ABORTED: file changed between pre-watch and write (TOCTOU catch)"
        exit 1
    fi
fi

# ── Step 4: Run the write operation ───────────────────────────────────────────
echo "Running write command: ${WRITE_CMD}"
eval "$WRITE_CMD"

# ── Step 5: 5-second post-write watch ─────────────────────────────────────────
echo "Post-write watch: waiting ${WATCH_SECONDS}s …"
sleep "$WATCH_SECONDS"

if [[ ! -f "$TARGET" ]]; then
    echo "ERROR: target file does not exist after write" >&2
    exit 1
fi

MTIME_POST=$(mtime_epoch "$TARGET")
if [[ "$MTIME_POST" == "$MTIME_PRE" ]]; then
    echo "WARNING: file mtime did not change — write may not have occurred" >&2
    exit 1
fi

# ── Step 6: Save content hash for next write's comparison ─────────────────────
NEW_HASH=$(shasum -a 256 "$TARGET" 2>/dev/null | awk '{print $1}')
if [[ -n "$NEW_HASH" ]]; then
    echo "$NEW_HASH" > "$HASH_FILE"
fi

# ── Done ───────────────────────────────────────────────────────────────────────
echo "SAFE_WRITE: OK"
