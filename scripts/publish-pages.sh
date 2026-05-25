#!/bin/bash
# Publish the solo build to the fork's gh-pages branch.
# Bumps the script-tag cache-busting query string so browsers re-fetch main.js.
# Usage: ./scripts/publish-pages.sh

set -euo pipefail

LIB_ROOT="/Users/gremus/claude-projects/cthulhu-wars Library at Celaeno"

# Read GitHub PAT from a file outside the repo so the script can be committed
# safely. Generate a fine-grained PAT at github.com/settings/tokens, save it to
# the path below as a single line (no trailing newline), and chmod 600 the file.
PAT_FILE="${HOME}/.config/cwo/github-pat"
if [[ ! -r "$PAT_FILE" ]]; then
    echo "ERROR: GitHub PAT file not found at $PAT_FILE" >&2
    echo "  Create it with the steps in the script comments above." >&2
    exit 1
fi
GH_PAT="$(cat "$PAT_FILE")"
FORK_URL="https://${GH_PAT}@github.com/gjremus/cthulhu-wars.git"

TMP_DIR="/tmp/cw-pages-publish"
CACHE_TAG="$(date +%Y%m%d-%H%M%S)"

echo "==> [1/5] Rebuilding main.js (sbt fullLinkJS) ..."
cd "$LIB_ROOT/solo"
sbt fullLinkJS 2>&1 | tail -3

echo "==> [2/5] Cloning gh-pages branch into $TMP_DIR ..."
rm -rf "$TMP_DIR"
git clone --quiet --branch gh-pages "$FORK_URL" "$TMP_DIR" 2>&1 | tail -1

echo "==> [3/5] Copying fresh assets + bumping cache tag to $CACHE_TAG ..."
cp "$LIB_ROOT/solo/index.html"  "$TMP_DIR/index.html"
cp "$LIB_ROOT/solo/target/scala-2.13/cthulhu-wars-solo-hrf-opt/main.js" "$TMP_DIR/main.js"
rm -rf "$TMP_DIR/webp" "$TMP_DIR/fonts"
cp -R "$LIB_ROOT/solo/webp"  "$TMP_DIR/webp"
cp -R "$LIB_ROOT/solo/fonts" "$TMP_DIR/fonts"

# Patch index.html for the online-enabled build:
#   - Substitute the akka-http backend URL for ###SERVER-URL### (CORS-enabled there).
#   - Leave data-online="true" from source (multiplayer enabled).
#   - Rewrite the script src to ./main.js with a fresh cache-busting tag.
sed -i '' \
  -e 's|###SERVER-URL###|https://cwo.freeddns.org/|g' \
  -e 's|./target/scala-2.13/cthulhu-wars-solo-hrf-opt/main.js|./main.js|g' \
  -e "s|main\\.js?v=[A-Za-z0-9-]*|main.js?v=$CACHE_TAG|g" \
  "$TMP_DIR/index.html"

touch "$TMP_DIR/.nojekyll"

echo "==> [4/5] Committing + force-pushing gh-pages (single-commit branch) ..."
cd "$TMP_DIR"
# Squash to one commit so the branch doesn't bloat over time
git checkout --orphan staging
git -c user.email=gjremus@gmail.com -c user.name="George Remus" add -A
git -c user.email=gjremus@gmail.com -c user.name="George Remus" commit -q -m "Pages build $CACHE_TAG"
git branch -D gh-pages
git branch -m gh-pages
git push -f origin gh-pages 2>&1 | tail -3

echo "==> [5/5] Cleanup."
rm -rf "$TMP_DIR"

echo
echo "Done.  Live URL: https://gjremus.github.io/cthulhu-wars/"
echo "Cache tag: $CACHE_TAG"
echo "Allow 1-2 min for GitHub Pages to redeploy."
