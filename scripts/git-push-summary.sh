#!/bin/bash
# Commit + push with a plain change summary. Use this for EVERY source commit
# (game builds, tools, designer) so git history says what changed and why.
#
# Usage:
#   git-push-summary.sh <repo-dir> "<title>" "<summary>" <file>...   # commit only these files
#   git-push-summary.sh <repo-dir> "<title>" "<summary>" -u          # all tracked changes
#
# Options (before <repo-dir>):
#   --model sonnet|haiku|opus   who did the work (sets the Co-Authored-By line; default sonnet)
#   --no-push                   commit only
#
# The commit message is: title, blank line, summary, blank line, a list of the
# changed files with +/- line counts, then the Co-Authored-By line.
# Prints branch, short commit hash and the file list. Never prints the remote URL.

set -euo pipefail

MODEL=sonnet
DO_PUSH=true
while [ $# -gt 0 ]; do
    case "$1" in
        --model)   MODEL="$2"; shift 2 ;;
        --no-push) DO_PUSH=false; shift ;;
        -h|--help) sed -n '1,16p' "$0"; exit 0 ;;
        *) break ;;
    esac
done

if [ $# -lt 4 ]; then sed -n '1,16p' "$0"; exit 2; fi
REPO="$1"; TITLE="$2"; SUMMARY="$3"; shift 3

case "$MODEL" in
    sonnet) COAUTHOR="Claude Sonnet 5 <noreply@anthropic.com>" ;;
    haiku)  COAUTHOR="Claude Haiku 4.5 <noreply@anthropic.com>" ;;
    opus)   COAUTHOR="Claude Opus 5.5 <noreply@anthropic.com>" ;;
    *) echo "ERROR: --model must be sonnet, haiku or opus"; exit 2 ;;
esac

[ -n "$TITLE" ]   || { echo "ERROR: title is empty"; exit 2; }
[ -n "$SUMMARY" ] || { echo "ERROR: summary is empty - say what changed and why"; exit 2; }

cd "$REPO"
git rev-parse --git-dir >/dev/null 2>&1 || { echo "ERROR: $REPO is not a git repo"; exit 1; }

if [ "$1" = "-u" ]; then
    git add -u
else
    git add -- "$@"
fi

if git diff --cached --quiet; then
    echo "Nothing staged to commit (files unchanged?)."; exit 1
fi

FILES=$(git diff --cached --numstat | awk '{printf "  %s (+%s -%s)\n", $3, $1, $2}')
MSG_FILE=$(mktemp -t gps-msg)
{
    echo "$TITLE"
    echo
    echo "$SUMMARY" | fold -s -w 72
    echo
    echo "Changed files:"
    echo "$FILES"
    echo
    echo "Co-Authored-By: $COAUTHOR"
} > "$MSG_FILE"

git commit -q -F "$MSG_FILE"
rm -f "$MSG_FILE"

BRANCH=$(git rev-parse --abbrev-ref HEAD)
HASH=$(git rev-parse --short HEAD)
echo "==> committed $HASH on $BRANCH: $TITLE"
echo "$FILES"

if $DO_PUSH; then
    # Hide the remote address in any output.
    if ! git push 2>&1 | sed -E -e '/^To /d' -e 's#(https?://|git@|ssh://)[^ ]+#<remote>#g' | tail -3; then
        echo "ERROR: git push failed"; exit 1
    fi
    echo "==> pushed $HASH"
fi
