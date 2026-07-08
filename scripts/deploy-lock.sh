#!/bin/bash
# Shared deploy lock for CWO builds.
# Used by: telegram bot, Claude Code sessions, tickers.
#
# Usage:
#   source deploy-lock.sh
#   deploy_lock_acquire "library" "claude-code" || exit 1
#   # ... do build/deploy ...
#   deploy_lock_release

DEPLOY_LOCK="/tmp/cwo-deploy.lock"

deploy_lock_acquire() {
    local target="${1:?target required}"
    local source="${2:-unknown}"

    if [ -f "$DEPLOY_LOCK" ]; then
        local age=$(( $(date +%s) - $(stat -f %m "$DEPLOY_LOCK" 2>/dev/null || echo 0) ))
        if [ "$age" -lt 600 ]; then
            echo "ERROR: Deploy lock held (age=${age}s). $(cat "$DEPLOY_LOCK")" >&2
            return 1
        fi
    fi

    echo "{\"target\":\"$target\",\"pid\":$$,\"time\":$(date +%s),\"source\":\"$source\"}" > "$DEPLOY_LOCK"
    return 0
}

deploy_lock_release() {
    rm -f "$DEPLOY_LOCK"
}
