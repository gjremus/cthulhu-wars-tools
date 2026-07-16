#!/bin/bash
# Deploy Library at Celaeno build to the live VM at cwo.freeddns.org/.
#
# VM tree: /opt/cwo/solo/ (index.html, webp/, fonts/, target/)
#
# Usage:
#   ./deploy-library-to-vm.sh             # main.js + index.html only (fast)
#   ./deploy-library-to-vm.sh --assets    # also resync webp + fonts
#   ./deploy-library-to-vm.sh --build     # force `sbt fullLinkJS` before deploying

set -euo pipefail

LIB_ROOT="/Users/gremus/Claude-Projects/cthulhu-wars-mnu"
LIB_BRANCH="library-at-celaeno"
SSH_KEY="/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Maps/Library at Celaeno/Server Deployment/oracle_cw_ed25519"
HOST="oracle-cw-server@35.255.125.91"
REMOTE_ROOT="/opt/cwo/library"
export JAVA_HOME="/Users/gremus/.local/jdk/zulu21.50.19-ca-jdk21.0.11-macosx_aarch64/Contents/Home"
export PATH="$JAVA_HOME/bin:$PATH"

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

# Ensure we're on the library branch
CURRENT_BRANCH="$(cd "$LIB_ROOT" && git branch --show-current)"
if [ "$CURRENT_BRANCH" != "$LIB_BRANCH" ]; then
    echo "ERROR: expected branch $LIB_BRANCH but on $CURRENT_BRANCH"
    echo "  Run: cd $LIB_ROOT && git checkout $LIB_BRANCH"
    exit 1
fi

MAIN_JS="$LIB_ROOT/solo/target/scala-2.13/cthulhu-wars-solo-hrf-opt/main.js"
if $DO_BUILD || [ ! -f "$MAIN_JS" ]; then
    echo "==> [build] sbt fullLinkJS (Library) ..."
    (cd "$LIB_ROOT/solo" && sbt fullLinkJS 2>&1 | tail -3)
fi
if [ ! -f "$MAIN_JS" ]; then
    echo "ERROR: $MAIN_JS still missing after build."
    exit 1
fi

CACHE_TAG="$(date +%Y%m%d-%H%M%S)"
echo "==> [stage] cache tag = $CACHE_TAG"

TMP_INDEX="$(mktemp -t lib-index.XXXXXX).html"
cp "$LIB_ROOT/solo/index.html" "$TMP_INDEX"
sed -i '' \
    -e 's|###SERVER-URL###|https://cwo.freeddns.org/|g' \
    -e "s|main\\.js?v=[A-Za-z0-9-]*|main.js?v=$CACHE_TAG|g" \
    "$TMP_INDEX"

echo "==> [upload] main.js → $REMOTE_ROOT/target/scala-2.13/.../main.js"
scp -i "$SSH_KEY" -C "$MAIN_JS" \
    "$HOST:$REMOTE_ROOT/target/scala-2.13/cthulhu-wars-solo-hrf-opt/main.js" 2>&1 | tail -1

echo "==> [upload] index.html → $REMOTE_ROOT/index.html"
scp -i "$SSH_KEY" -C "$TMP_INDEX" "$HOST:$REMOTE_ROOT/index.html" 2>&1 | tail -1
rm -f "$TMP_INDEX"

echo "==> [write] cache-bust.txt → $REMOTE_ROOT/cache-bust.txt"
ssh -i "$SSH_KEY" "$HOST" "echo '$CACHE_TAG' > $REMOTE_ROOT/cache-bust.txt"

if $DO_ASSETS; then
    echo "==> [upload] webp + fonts (tar pipe) ..."
    (cd "$LIB_ROOT/solo" && tar -czf - webp fonts \
        | ssh -i "$SSH_KEY" -C "$HOST" "cd $REMOTE_ROOT && tar -xzf -" 2>&1 | tail -3)
fi

echo "==> [verify] HEAD /"
curl -s -o /dev/null -w "  HTTP %{http_code}  size_bytes=%{size_download}\n" "https://cwo.freeddns.org/"

echo
echo "Done.  Live: https://cwo.freeddns.org/   (cache tag $CACHE_TAG)"
