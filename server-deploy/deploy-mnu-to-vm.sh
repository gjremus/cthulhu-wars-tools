#!/bin/bash
# Deploy More Neutral Units (MNU) beta build to the live VM at cwo.freeddns.org/mnu/.
#
# Pattern (lifted from the earlier ad-hoc commands recorded during the first MNU push):
#   - Rebuild main.js (sbt fullLinkJS) in this MNU workspace.
#   - scp main.js → /opt/cwo/mnu/target/scala-2.13/cthulhu-wars-solo-hrf-opt/main.js
#   - scp index.html → /opt/cwo/mnu/index.html, with the script-tag cache tag bumped.
#   - Optional: --assets to also resync webp + fonts (slow; only when bitmaps/fonts changed).
#
# The VM hosts BOTH builds:
#   /opt/cwo/solo/   ← Library at Celaeno (served at https://cwo.freeddns.org/)
#   /opt/cwo/mnu/    ← MNU                (served at https://cwo.freeddns.org/mnu/)
#
# Usage:
#   ./deploy-mnu-to-vm.sh             # main.js + index.html only (fast)
#   ./deploy-mnu-to-vm.sh --assets    # also resync webp + fonts (slow, ~50MB)
#   ./deploy-mnu-to-vm.sh --build     # force `sbt fullLinkJS` before deploying
#
# Server JAR is shared with the Library build and is deployed by the Library
# server-deploy script, not by this one.

set -euo pipefail

MNU_ROOT="/Users/gremus/claude-projects/cthulhu-wars More Neutral Units"
SSH_KEY="/Users/gremus/My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/Server Deployment/oracle_cw_ed25519"
HOST="oracle-cw-server@35.255.125.91"
REMOTE_ROOT="/opt/cwo/mnu"

DO_BUILD=false
DO_ASSETS=false
for arg in "$@"; do
    case "$arg" in
        --build)  DO_BUILD=true ;;
        --assets) DO_ASSETS=true ;;
        -h|--help) sed -n '1,40p' "$0"; exit 0 ;;
        *) echo "unknown arg: $arg"; exit 2 ;;
    esac
done

if [ ! -f "$SSH_KEY" ]; then
    echo "ERROR: ssh key not found at: $SSH_KEY"
    exit 1
fi

MAIN_JS="$MNU_ROOT/solo/target/scala-2.13/cthulhu-wars-solo-hrf-opt/main.js"
if $DO_BUILD || [ ! -f "$MAIN_JS" ]; then
    echo "==> [build] sbt fullLinkJS (MNU) ..."
    (cd "$MNU_ROOT/solo" && sbt fullLinkJS 2>&1 | tail -3)
fi
if [ ! -f "$MAIN_JS" ]; then
    echo "ERROR: $MAIN_JS still missing after build."
    exit 1
fi

CACHE_TAG="$(date +%Y%m%d-%H%M%S)"
echo "==> [stage] cache tag = $CACHE_TAG"

# Stage a patched index.html in /tmp: same patches the Library publish-pages.sh
# applies (### SERVER URL substitution + main.js path rewrite + cache-tag bump).
TMP_INDEX="$(mktemp -t mnu-index.XXXXXX).html"
cp "$MNU_ROOT/solo/index.html" "$TMP_INDEX"
sed -i '' \
    -e 's|###SERVER-URL###|https://cwo.freeddns.org/mnu/|g' \
    -e 's|./target/scala-2.13/cthulhu-wars-solo-hrf-opt/main.js|./target/scala-2.13/cthulhu-wars-solo-hrf-opt/main.js|g' \
    -e "s|main\\.js?v=[A-Za-z0-9-]*|main.js?v=$CACHE_TAG|g" \
    "$TMP_INDEX"

echo "==> [upload] main.js → $REMOTE_ROOT/target/scala-2.13/.../main.js"
scp -i "$SSH_KEY" -C "$MAIN_JS" \
    "$HOST:$REMOTE_ROOT/target/scala-2.13/cthulhu-wars-solo-hrf-opt/main.js" 2>&1 | tail -1

echo "==> [upload] index.html → $REMOTE_ROOT/index.html"
scp -i "$SSH_KEY" -C "$TMP_INDEX" "$HOST:$REMOTE_ROOT/index.html" 2>&1 | tail -1
rm -f "$TMP_INDEX"

if $DO_ASSETS; then
    echo "==> [upload] webp + fonts (tar pipe) ..."
    (cd "$MNU_ROOT/solo" && tar -czf - webp fonts \
        | ssh -i "$SSH_KEY" -C "$HOST" "cd $REMOTE_ROOT && tar -xzf -" 2>&1 | tail -3)
fi

echo "==> [verify] HEAD /mnu/"
curl -s -o /dev/null -w "  HTTP %{http_code}  size_bytes=%{size_download}\n" "https://cwo.freeddns.org/mnu/"

echo
echo "Done.  Live: https://cwo.freeddns.org/mnu/   (cache tag $CACHE_TAG)"
echo "Allow ~1 min for browsers with warm caches to refetch main.js."
