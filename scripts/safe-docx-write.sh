#!/bin/bash
# Safe DOCX writer with 5-minute mtime lockout and backup management
# Usage: safe-docx-write.sh <source-file> <target-docx>
# Exit codes: 0=success, 1=lockout/error

set -e

SOURCE="$1"
TARGET="$2"

if [ -z "$SOURCE" ] || [ -z "$TARGET" ]; then
    echo "Usage: safe-docx-write.sh <source-file> <target-docx>" >&2
    exit 1
fi

if [ ! -f "$SOURCE" ]; then
    echo "Error: Source file '$SOURCE' does not exist" >&2
    exit 1
fi

# Check 5-minute lockout
if [ -f "$TARGET" ]; then
    NOW=$(date +%s)
    MTIME=$(stat -f "%m" "$TARGET" 2>/dev/null || stat -c "%Y" "$TARGET" 2>/dev/null)
    AGE=$((NOW - MTIME))

    if [ $AGE -lt 300 ]; then
        echo "LOCKOUT: Document modified $AGE seconds ago (need 300+)" >&2
        exit 1
    fi
fi

# Wait 5 seconds (pre-watch)
sleep 5

# Create backup with ticker timestamp
if [ -f "$TARGET" ]; then
    BACKUP="${TARGET}.bak.ticker_$(date +%s)"
    cp "$TARGET" "$BACKUP"
    echo "Backup created: $BACKUP"

    # Manage backup count - keep only 2 most recent ticker backups
    BACKUP_DIR=$(dirname "$TARGET")
    BACKUP_BASE=$(basename "$TARGET")
    ls -t "$BACKUP_DIR" | grep "^${BACKUP_BASE}.bak.ticker_" | tail -n +3 | while read old; do
        mv "$BACKUP_DIR/$old" ~/.Trash/
        echo "Moved old backup to Trash: $old"
    done
fi

# Perform the write
cp "$SOURCE" "$TARGET"
echo "Write successful: $TARGET"

# Wait 5 seconds (post-watch)
sleep 5

exit 0
