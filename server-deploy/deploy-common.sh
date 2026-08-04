#!/bin/bash
# Shared deploy body for all Cthulhu Wars Online builds.
#
# A per-build wrapper (deploy-hb-to-vm.sh, deploy-bb-to-vm.sh, ...) sets these
# variables and then sources this file. The ONLY differences between builds are
# these config values — the deploy LOGIC is identical for every build:
#
#   BUILD_KEY    short lock/label key, e.g. "hb"
#   SOURCE       absolute path to the build's solo/ workspace
#   REMOTE_ROOT  server path, e.g. /opt/cwo/HB
#   SERVER_URL   public URL, e.g. https://cwo.freeddns.org/HB/
#
# Behaviour (same for every build):
#   1. Bump the numeric suffix of `version :=` in solo/common.sbt (so EVERY
#      deploy ships a new, visible version number).
#   2. Commit the version bump and git push.
#   3. ALWAYS rebuild main.js (sbt fullLinkJS) so the new version is compiled in.
#   4. scp main.js (both paths) + index.html; every scp failure is fatal.
#   5. Hash-verify: served main.js must byte-match the local build, else abort.
#   6. HEAD-verify the public URL returns 2xx/3xx.
#
# IMPORTANT: NEVER run sbt on the server — it starves the game server of memory.
#
# Flags (accepted by every wrapper):
#   --assets    also resync webp + fonts (slow; only when bitmaps/fonts changed)
#   --no-bump   skip the version bump (rare; e.g. re-deploying an identical build)
#   -h|--help   print the wrapper header

set -euo pipefail

export JAVA_HOME="/Users/gremus/.local/jdk/zulu21.50.19-ca-jdk21.0.11-macosx_aarch64/Contents/Home"
export PATH="$JAVA_HOME/bin:$PATH"
export SBT_OPTS="${SBT_OPTS:--Xmx6G -Xss8m}"

: "${BUILD_KEY:?BUILD_KEY must be set by the wrapper}"
: "${SOURCE:?SOURCE must be set by the wrapper}"
: "${REMOTE_ROOT:?REMOTE_ROOT must be set by the wrapper}"
: "${SERVER_URL:?SERVER_URL must be set by the wrapper}"

SSH_KEY="$HOME/.ssh/oracle_cw_ed25519"
SSH_OPTS="-o ConnectTimeout=15 -o StrictHostKeyChecking=no"
HOST="oracle-cw-server@35.255.125.91"
VERIFY_URL="$SERVER_URL"
COMMON_SBT="$SOURCE/common.sbt"

DO_ASSETS=false
DO_BUMP=true
for arg in "$@"; do
    case "$arg" in
        --assets)  DO_ASSETS=true ;;
        --no-bump) DO_BUMP=false ;;
        --build)   ;;   # accepted for backward-compat; we ALWAYS build now
        -h|--help) sed -n '1,40p' "$0"; exit 0 ;;
        *) echo "unknown arg: $arg"; exit 2 ;;
    esac
done

if [ ! -f "$SSH_KEY" ]; then
    echo "ERROR: ssh key not found at: $SSH_KEY"; exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../scripts/deploy-lock.sh"
deploy_lock_acquire "$BUILD_KEY" "deploy-$BUILD_KEY" || exit 1
trap deploy_lock_release EXIT

# ── 1. Version bump ──────────────────────────────────────────────────────────
# Bump the LAST numeric group of the version string in common.sbt. Works for
# every build's format: "Homebrew v 2.31" -> 2.32, "bubastis-v2.4.41" -> 2.4.42,
# "library-at-celaeno-v5.8" -> 5.9, etc.
if $DO_BUMP; then
    if [ ! -f "$COMMON_SBT" ]; then
        echo "ERROR: $COMMON_SBT not found — cannot bump version."; exit 1
    fi
    OLD_VER=$(grep -E '^version :=' "$COMMON_SBT" | head -1 | sed -E 's/^version := "(.*)".*/\1/')
    if [ -z "$OLD_VER" ]; then
        echo "ERROR: could not read version from $COMMON_SBT."; exit 1
    fi
    # Split trailing integer (the last run of digits) and increment it.
    NEW_VER=$(echo "$OLD_VER" | perl -pe 's/(\d+)(\D*)$/($1+1).$2/e')
    if [ "$NEW_VER" = "$OLD_VER" ]; then
        echo "ERROR: version bump produced no change ('$OLD_VER') — aborting."; exit 1
    fi
    echo "==> [version] $OLD_VER -> $NEW_VER"
    sed -i '' -E "s|^version := \".*\"|version := \"$NEW_VER\"|" "$COMMON_SBT"
    (cd "$SOURCE" && git add common.sbt && git commit -q -m "$BUILD_KEY: bump version to $NEW_VER (deploy)" || true)
fi

echo "==> [git push] pushing source to remote..."
(cd "$SOURCE" && git push 2>&1 | tail -3)

# ── 2. Always rebuild so the new version is compiled into main.js ────────────
MAIN_JS="$SOURCE/target/scala-2.13/cthulhu-wars-solo-hrf-opt/main.js"
echo "==> [build] sbt fullLinkJS ($BUILD_KEY) ..."
(cd "$SOURCE" && sbt -J-Xmx6G fullLinkJS 2>&1 | tail -5)
if [ ! -f "$MAIN_JS" ]; then
    echo "ERROR: $MAIN_JS missing after build."; exit 1
fi

CACHE_TAG="$(date +%Y%m%d-%H%M%S)"
echo "==> [stage] cache tag = $CACHE_TAG"

TMP_INDEX="$(mktemp -t ${BUILD_KEY}-index.XXXXXX).html"
cp "$SOURCE/index.html" "$TMP_INDEX"
sed -i '' \
    -e "s|###SERVER-URL###|${SERVER_URL}|g" \
    -e "s|main\\.js?v=[A-Za-z0-9-]*|main.js?v=$CACHE_TAG|g" \
    "$TMP_INDEX"

# ── 3. Upload (every scp failure is fatal) ───────────────────────────────────
echo "==> [upload] main.js → $REMOTE_ROOT/target/scala-2.13/.../main.js"
scp -i "$SSH_KEY" $SSH_OPTS -C "$MAIN_JS" \
    "$HOST:$REMOTE_ROOT/target/scala-2.13/cthulhu-wars-solo-hrf-opt/main.js" \
    || { echo "ERROR: scp of main.js (target path) failed"; exit 1; }

echo "==> [upload] main.js → $REMOTE_ROOT/main.js"
scp -i "$SSH_KEY" $SSH_OPTS -C "$MAIN_JS" \
    "$HOST:$REMOTE_ROOT/main.js" \
    || { echo "ERROR: scp of main.js (root path) failed"; exit 1; }

echo "==> [upload] index.html → $REMOTE_ROOT/index.html"
scp -i "$SSH_KEY" $SSH_OPTS -C "$TMP_INDEX" "$HOST:$REMOTE_ROOT/index.html" \
    || { echo "ERROR: scp of index.html failed"; exit 1; }
rm -f "$TMP_INDEX"

echo "==> [upload] cache-bust.txt → $REMOTE_ROOT/cache-bust.txt"
ssh -i "$SSH_KEY" $SSH_OPTS "$HOST" "echo '$CACHE_TAG' > $REMOTE_ROOT/cache-bust.txt"

if $DO_ASSETS; then
    echo "==> [upload] webp + fonts (tar pipe) ..."
    (cd "$SOURCE" && tar -czf - webp fonts \
        | ssh -i "$SSH_KEY" $SSH_OPTS -C "$HOST" "cd $REMOTE_ROOT && tar -xzf -") \
        || { echo "ERROR: asset tar-pipe failed"; exit 1; }
fi

# ── 4. Hash-verify: served main.js must byte-match the local build ───────────
echo "==> [verify] main.js hash (local build == served file)"
LOCAL_SHA=$(shasum "$MAIN_JS" | cut -d' ' -f1)
REMOTE_SHA=$(ssh -i "$SSH_KEY" $SSH_OPTS "$HOST" "sha1sum $REMOTE_ROOT/main.js 2>/dev/null | cut -d' ' -f1")
echo "  local=$LOCAL_SHA"
echo "  served=$REMOTE_SHA"
if [ -z "$REMOTE_SHA" ]; then
    echo "ERROR: could not read served main.js hash — deploy NOT verified."; exit 1
fi
if [ "$LOCAL_SHA" != "$REMOTE_SHA" ]; then
    echo "ERROR: served main.js does NOT match local build (scp likely failed silently)."
    echo "       The website is serving a DIFFERENT build than you just compiled. ABORTING."
    exit 1
fi
echo "  MATCH — served build verified."

# ── 5. HEAD-verify the public URL ────────────────────────────────────────────
echo "==> [verify] HEAD $VERIFY_URL"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$VERIFY_URL")
echo "  HTTP $HTTP_CODE"
if [ "$HTTP_CODE" -lt 200 ] || [ "$HTTP_CODE" -ge 400 ]; then
    echo "ERROR: verification failed (HTTP $HTTP_CODE)"; exit 1
fi

echo
echo "Done.  Live: $VERIFY_URL   (cache tag $CACHE_TAG)"
echo "Allow ~1 min for browsers with warm caches to refetch main.js."
