#!/bin/zsh
# cw-doclock.sh — manage the OS delete-protection lock on CW task docs.
#
# Every live task .docx/.xlsx carries the BSD user-immutable flag (chflags uchg):
# the kernel then refuses ALL delete/overwrite/rename of it, from any tool or
# command, so the ticker (or a stray script) can NEVER destroy a task doc.
#
# Subcommands:
#   lock-all           lock every live .docx/.xlsx under the CW tree (safe; additive)
#   lock   <file>      lock one file (safe; additive)
#   status             count locked vs unlocked live docs
#   unlock <file>      OWNER ONLY — lift the lock on one file to hand-edit it.
#   unlock-all         OWNER ONLY — lift the lock on every live doc.
#
# UNLOCK is gated on an interactive TTY confirmation. The ticker runs
# non-interactively (stdin = /dev/null, no controlling terminal), so it can
# NEVER satisfy the prompt and therefore can never unlock a doc. Only a human at
# a terminal can. Re-lock afterward with `lock` / `lock-all`.
set -u

CW="/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars"

# Live docs only — skip AppleDouble and every backup/temp form.
is_backup() {
  case "$(basename "$1")" in
    ._*|*.bak|*.bak.*|*backup*|*BACKUP*|*.pre_write_*|*.last_write_hash) return 0;;
  esac
  case "$1" in
    *".backup-"*|*".backup"*|*"_old_master_backups"*) return 0;;
  esac
  return 1
}

live_docs() {
  find "$CW" \( -name "*.docx" -o -name "*.xlsx" \) -not -name "._*" 2>/dev/null
}

confirm_tty() {
  # Refuse unless a human is at a real terminal. The ticker has no /dev/tty.
  if [[ ! -t 0 && ! -e /dev/tty ]]; then
    echo "REFUSED: unlock requires an interactive terminal. (The ticker cannot unlock docs.)" >&2
    exit 3
  fi
  local ans=""
  printf "Type YES to lift delete-protection: " > /dev/tty
  read -r ans < /dev/tty || { echo "REFUSED: no terminal input." >&2; exit 3; }
  [[ "$ans" == "YES" ]] || { echo "Aborted (you did not type YES)." >&2; exit 3; }
}

cmd="${1:-}"
case "$cmd" in
  lock-all)
    n=0
    while IFS= read -r f; do
      is_backup "$f" && continue
      chflags uchg "$f" 2>/dev/null && n=$((n+1))
    done < <(live_docs)
    echo "locked $n live docs (uchg)."
    ;;
  lock)
    f="${2:-}"; [[ -z "$f" ]] && { echo "usage: cw-doclock.sh lock <file>" >&2; exit 1; }
    chflags uchg "$f" && echo "locked: $f"
    ;;
  status)
    locked=0; unlocked=0
    while IFS= read -r f; do
      is_backup "$f" && continue
      if ls -lO "$f" 2>/dev/null | grep -q uchg; then locked=$((locked+1)); else unlocked=$((unlocked+1)); echo "  UNLOCKED: $f"; fi
    done < <(live_docs)
    echo "locked=$locked  unlocked=$unlocked"
    ;;
  unlock)
    f="${2:-}"; [[ -z "$f" ]] && { echo "usage: cw-doclock.sh unlock <file>" >&2; exit 1; }
    confirm_tty
    chflags nouchg "$f" && echo "UNLOCKED (remember to re-lock): $f"
    ;;
  unlock-all)
    confirm_tty
    n=0
    while IFS= read -r f; do
      is_backup "$f" && continue
      chflags nouchg "$f" 2>/dev/null && n=$((n+1))
    done < <(live_docs)
    echo "unlocked $n live docs. RE-LOCK with: cw-doclock.sh lock-all"
    ;;
  *)
    echo "usage: cw-doclock.sh {lock-all|lock <file>|status|unlock <file>|unlock-all}" >&2
    exit 1
    ;;
esac
