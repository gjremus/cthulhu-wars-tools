#!/bin/bash
# Git commit helper for tickers
# Commits changes in cthulhu-wars-tools with automated message

set -euo pipefail

cd ~/cthulhu-wars-tools

# Check if there are changes
if git diff --quiet && git diff --cached --quiet; then
    echo "No changes to commit"
    exit 0
fi

# Get list of changed files
CHANGED=$(git status --short | head -20)

# Stage all tracked file changes
git add -u

# Create commit message
TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
COMMIT_MSG="Automated commit - $TIMESTAMP

Changed files:
$CHANGED

Committed by ticker automation"

# Commit
git commit -m "$COMMIT_MSG"

echo "Committed changes at $TIMESTAMP"
