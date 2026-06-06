#!/bin/bash
# Deploy the Homebrew (Defilers Court) build to the live VM at cwo.freeddns.org/HB/.
#
# Mirrors deploy-mnu-to-vm.sh, with paths swapped to the Homebrew worktree
# and /opt/cwo/HB/ on the VM.
#
# Usage:
#   ./deploy-homebrew-to-vm.sh             # main.js + index.html only (fast)
#   ./deploy-homebrew-to-vm.sh --assets    # also resync webp + fonts (slow)
#   ./deploy-homebrew-to-vm.sh --build     # force `sbt fullLinkJS` before deploying

set -euo pipefail

HB_ROOT="/Users/gremus/claude-projects/cthulhu-wars Homebrew"
SSH_KEY="/Users/gremus/My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/Server Deployment/oracle_cw_ed25519"
HOST="oracle-cw-server@35.255.125.91"
REMOTE_ROOT="/opt/cwo/HB"

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

MAIN_JS="$HB_ROOT/solo/target/scala-2.13/cthulhu-wars-solo-hrf-opt/main.js"
if $DO_BUILD || [ ! -f "$MAIN_JS" ]; then
    echo "==> [build] sbt fullLinkJS (Homebrew) ..."
    (cd "$HB_ROOT/solo" && sbt fullLinkJS 2>&1 | tail -3)
fi
if [ ! -f "$MAIN_JS" ]; then
    echo "ERROR: $MAIN_JS still missing after build."
    exit 1
fi

CACHE_TAG="$(date +%Y%m%d-%H%M%S)"
echo "==> [stage] cache tag = $CACHE_TAG"

TMP_INDEX="$(mktemp -t hb-index.XXXXXX).html"
cp "$HB_ROOT/solo/index.html" "$TMP_INDEX"
sed -i '' \
    -e 's|###SERVER-URL###|https://cwo.freeddns.org/HB/|g' \
    -e 's|./target/scala-2.13/cthulhu-wars-solo-hrf-opt/main.js|./target/scala-2.13/cthulhu-wars-solo-hrf-opt/main.js|g' \
    -e "s|main\\.js?v=[A-Za-z0-9-]*|main.js?v=$CACHE_TAG|g" \
    "$TMP_INDEX"

# Ensure remote directory tree exists
ssh -i "$SSH_KEY" "$HOST" "mkdir -p $REMOTE_ROOT/target/scala-2.13/cthulhu-wars-solo-hrf-opt $REMOTE_ROOT/webp/images $REMOTE_ROOT/webp/info $REMOTE_ROOT/fonts" 2>&1 | tail -3

echo "==> [upload] main.js → $REMOTE_ROOT/target/scala-2.13/.../main.js"
scp -i "$SSH_KEY" -C "$MAIN_JS" \
    "$HOST:$REMOTE_ROOT/target/scala-2.13/cthulhu-wars-solo-hrf-opt/main.js" 2>&1 | tail -1

echo "==> [upload] index.html → $REMOTE_ROOT/index.html"
scp -i "$SSH_KEY" -C "$TMP_INDEX" "$HOST:$REMOTE_ROOT/index.html" 2>&1 | tail -1
rm -f "$TMP_INDEX"

if $DO_ASSETS; then
    echo "==> [upload] webp + fonts (tar pipe) ..."
    (cd "$HB_ROOT/solo" && tar -czf - webp fonts \
        | ssh -i "$SSH_KEY" -C "$HOST" "cd $REMOTE_ROOT && tar -xzf -" 2>&1 | tail -3)
fi

echo "==> [verify] HEAD /HB/"
curl -s -o /dev/null -w "  HTTP %{http_code}  size_bytes=%{size_download}\n" "https://cwo.freeddns.org/HB/"

echo
echo "Done.  Live: https://cwo.freeddns.org/HB/   (cache tag $CACHE_TAG)"
echo "Allow ~1 min for browsers with warm caches to refetch main.js."
