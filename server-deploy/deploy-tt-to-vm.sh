#!/bin/bash
# Deploy TchoTcho/Cats/Yuggoth (TT) build to the live VM at cwo.freeddns.org/TchoTcho/.
#
# Pattern:
#   - Rebuild main.js (sbt fullLinkJS) in this TT workspace.
#   - scp main.js → /opt/cwo/tt/target/scala-2.13/cthulhu-wars-solo-hrf-opt/main.js
#   - Also copy to /opt/cwo/tt/main.js (root-level reference).
#   - scp index.html → /opt/cwo/tt/index.html, with cache tag bumped.
#   - Optional: --assets to also resync webp + fonts (slow; only when bitmaps/fonts changed).
#
# IMPORTANT: NEVER run sbt on the server — it starves the game server of memory.
#
# Usage:
#   ./deploy-tt-to-vm.sh             # main.js + index.html only (fast)
#   ./deploy-tt-to-vm.sh --assets    # also resync webp + fonts (slow)
#   ./deploy-tt-to-vm.sh --build     # force `sbt fullLinkJS` before deploying

set -euo pipefail

SOURCE="/Users/gremus/Claude-Projects/cthulhu-wars-TchoTcho_Cats_Yuggoth/solo"
SSH_KEY="$HOME/.ssh/oracle_cw_ed25519"
SSH_OPTS="-o StrictHostKeyChecking=no"
HOST="oracle-cw-server@35.255.125.91"
REMOTE_ROOT="/opt/cwo/tt"
SERVER_URL="https://cwo.freeddns.org/TchoTcho/"
VERIFY_URL="https://cwo.freeddns.org/TchoTcho/"

DO_BUILD=false
DO_ASSETS=false
for arg in "$@"; do
    case "$arg" in
        --build)  DO_BUILD=true ;;
        --assets) DO_ASSETS=true ;;
        -h|--help) sed -n '1,20p' "$0"; exit 0 ;;
        *) echo "unknown arg: $arg"; exit 2 ;;
    esac
done

if [ ! -f "$SSH_KEY" ]; then
    echo "ERROR: ssh key not found at: $SSH_KEY"
    exit 1
fi

MAIN_JS="$SOURCE/target/scala-2.13/cthulhu-wars-solo-hrf-opt/main.js"
if $DO_BUILD || [ ! -f "$MAIN_JS" ]; then
    echo "==> [build] sbt fullLinkJS (TT) ..."
    (cd "$SOURCE" && sbt fullLinkJS 2>&1 | tail -3)
fi
if [ ! -f "$MAIN_JS" ]; then
    echo "ERROR: $MAIN_JS still missing after build."
    exit 1
fi

CACHE_TAG="$(date +%Y%m%d-%H%M%S)"
echo "==> [stage] cache tag = $CACHE_TAG"

# Stage a patched index.html in /tmp
TMP_INDEX="$(mktemp -t tt-index.XXXXXX).html"
cp "$SOURCE/index.html" "$TMP_INDEX"
sed -i '' \
    -e "s|###SERVER-URL###|${SERVER_URL}|g" \
    -e "s|main\\.js?v=[A-Za-z0-9-]*|main.js?v=$CACHE_TAG|g" \
    "$TMP_INDEX"

echo "==> [upload] main.js → $REMOTE_ROOT/target/scala-2.13/.../main.js"
scp -i "$SSH_KEY" $SSH_OPTS -C "$MAIN_JS" \
    "$HOST:$REMOTE_ROOT/target/scala-2.13/cthulhu-wars-solo-hrf-opt/main.js" 2>&1 | tail -1

echo "==> [upload] main.js → $REMOTE_ROOT/main.js"
scp -i "$SSH_KEY" $SSH_OPTS -C "$MAIN_JS" \
    "$HOST:$REMOTE_ROOT/main.js" 2>&1 | tail -1

echo "==> [upload] index.html → $REMOTE_ROOT/index.html"
scp -i "$SSH_KEY" $SSH_OPTS -C "$TMP_INDEX" "$HOST:$REMOTE_ROOT/index.html" 2>&1 | tail -1
rm -f "$TMP_INDEX"

if $DO_ASSETS; then
    echo "==> [upload] webp + fonts (tar pipe) ..."
    (cd "$SOURCE" && tar -czf - webp fonts \
        | ssh -i "$SSH_KEY" $SSH_OPTS -C "$HOST" "cd $REMOTE_ROOT && tar -xzf -" 2>&1 | tail -3)
fi

echo "==> [verify] HEAD $VERIFY_URL"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$VERIFY_URL")
echo "  HTTP $HTTP_CODE"
if [ "$HTTP_CODE" -lt 200 ] || [ "$HTTP_CODE" -ge 400 ]; then
    echo "ERROR: verification failed (HTTP $HTTP_CODE)"
    exit 1
fi

echo
echo "Done.  Live: $VERIFY_URL   (cache tag $CACHE_TAG)"
echo "Allow ~1 min for browsers with warm caches to refetch main.js."
