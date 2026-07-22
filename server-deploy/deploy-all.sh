#!/bin/bash
# Deploy all 5 game builds in order: Library -> MNU -> TT -> BB -> HB
# Stops on first failure.
#
# Usage:
#   ./deploy-all.sh              # deploy all (main.js + index.html only)
#   ./deploy-all.sh --build      # force sbt fullLinkJS on each before deploying
#   ./deploy-all.sh --assets     # also resync webp + fonts on each (slow)
#
# Flags are passed through to each individual deploy script.

set -euo pipefail

export JAVA_HOME="/Users/gremus/.local/jdk/zulu21.50.19-ca-jdk21.0.11-macosx_aarch64/Contents/Home"
export PATH="$JAVA_HOME/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

BUILDS=(
    "Library:deploy-library-to-vm.sh"
    "MNU:deploy-mnu-to-vm.sh"
    "TT:deploy-tt-to-vm.sh"
    "BB:deploy-bb-to-vm.sh"
    "HB:deploy-hb-to-vm.sh"
)

echo "========================================"
echo " Deploy ALL builds"
echo " Order: Library -> MNU -> TT -> BB -> HB"
echo "========================================"
echo

FAILED=0
for entry in "${BUILDS[@]}"; do
    NAME="${entry%%:*}"
    SCRIPT="${entry##*:}"
    echo "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
    echo " Deploying: $NAME"
    echo "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
    if "$SCRIPT_DIR/$SCRIPT" "$@"; then
        echo "  ✓ $NAME deployed successfully."
        echo
    else
        echo "  ✗ $NAME FAILED. Stopping."
        FAILED=1
        break
    fi
done

if [ "$FAILED" -eq 0 ]; then
    echo "========================================"
    echo " All 5 builds deployed successfully."
    echo "========================================"
else
    exit 1
fi
