#!/bin/bash
# Browser checks for Map Designer with headless Chrome
# Run after starting local test servers (see task spec section E)

set -e

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DATA_DIR="/tmp/mapqa/data"
CHROME_DATA="/tmp/mapqa/chrome"
SHOTS_DIR="/tmp/mapqa/screenshots"
PORT=8295  # proxy port

echo "=== Map Designer Browser Tests ==="
echo

# Check servers are running
if ! curl -s http://127.0.0.1:8291/designer/api/health > /dev/null 2>&1; then
    echo "ERROR: designer server not running on port 8291"
    echo "Start with: python3 server/designer_server.py --data /tmp/mapqa/data --port 8291 --token-hash-file /tmp/mapqa/th --console-queue /tmp/mapqa/queue.log"
    exit 1
fi

if ! curl -s http://127.0.0.1:$PORT/designer/ > /dev/null 2>&1; then
    echo "ERROR: proxy not running on port $PORT"
    echo "Start with: python3 dev/local-caddy.py --port $PORT --api-port 8291 --data /tmp/mapqa/data"
    exit 1
fi

mkdir -p "$SHOTS_DIR"
rm -f "$SHOTS_DIR"/*.png

# Helper to take screenshot
screenshot() {
    local name="$1"
    local url="$2"
    local wait="${3:-6000}"  # virtual time budget in ms

    echo "📸 Capturing $name..."
    "$CHROME" --headless=new --disable-gpu \
        --user-data-dir="$CHROME_DATA" \
        --window-size=900,1400 \
        --virtual-time-budget=$wait \
        --screenshot="$SHOTS_DIR/$name.png" \
        "$url" 2>/dev/null

    if [ -f "$SHOTS_DIR/$name.png" ]; then
        echo "   ✓ $SHOTS_DIR/$name.png"
    else
        echo "   ✗ FAILED: $name"
        return 1
    fi
}

# Get or create test user token
if [ ! -f /tmp/mapqa/token.txt ]; then
    echo "Creating test user..."
    TOKEN=$(curl -s -X POST http://127.0.0.1:8291/designer/api/register \
        -H "Content-Type: application/json" \
        -d '{"username":"testuser","password":"testpass"}' | \
        python3 -c "import sys, json; print(json.load(sys.stdin)['token'])" 2>/dev/null)
    echo "$TOKEN" > /tmp/mapqa/token.txt
    echo "   Token saved to /tmp/mapqa/token.txt"
else
    TOKEN=$(cat /tmp/mapqa/token.txt)
fi

# Create a test faction for home page
if [ ! -f /tmp/mapqa/fid.txt ]; then
    echo "Creating test faction..."
    FID=$(curl -s -X POST http://127.0.0.1:8291/designer/api/factions \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{"name":"Test Faction","acronym":"TST"}' | \
        python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
    echo "$FID" > /tmp/mapqa/fid.txt
fi

# Create a test unit
if [ ! -f /tmp/mapqa/uid.txt ]; then
    echo "Creating test unit..."
    UID=$(curl -s -X POST http://127.0.0.1:8291/designer/api/units \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{"name":"Test Monster"}' | \
        python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
    echo "$UID" > /tmp/mapqa/uid.txt
fi

# Create a test map
if [ ! -f /tmp/mapqa/mid.txt ]; then
    echo "Creating test map..."
    MID=$(curl -s -X POST http://127.0.0.1:8291/designer/api/maps \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{"name":"Test Map"}' | \
        python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
    echo "$MID" > /tmp/mapqa/mid.txt
else
    MID=$(cat /tmp/mapqa/mid.txt)
fi

echo
echo "Test data:"
echo "  Faction: $(cat /tmp/mapqa/fid.txt)"
echo "  Unit:    $(cat /tmp/mapqa/uid.txt)"
echo "  Map:     $MID"
echo

# Create login shim (temporary, will be deleted after)
cat > www/dev/zz-test-login.html <<'EOF'
<!DOCTYPE html>
<html>
<head><title>Test Login</title></head>
<body>
<script>
const token = new URLSearchParams(window.location.search).get('token');
if (token) {
    localStorage.setItem('cw_designer_token', token);
    window.location.href = '/designer/';
} else {
    document.body.textContent = 'No token provided';
}
</script>
</body>
</html>
EOF

echo "Taking screenshots..."
echo

# 1. Home page with My Maps
screenshot "01-home-my-maps" "http://127.0.0.1:$PORT/designer/dev/zz-test-login.html?token=$TOKEN"

# 2. Map main screen
screenshot "02-map-main" "http://127.0.0.1:$PORT/designer/#/map/$MID"

# 3. Map images section
screenshot "03-map-images" "http://127.0.0.1:$PORT/designer/#/map/$MID/images"

# 4. Map bitmaps section
screenshot "04-map-bitmaps" "http://127.0.0.1:$PORT/designer/#/map/$MID/bitmaps"

# 5. Map adjacency section
screenshot "05-map-adjacency" "http://127.0.0.1:$PORT/designer/#/map/$MID/adjacency"

# 6. Map units section
screenshot "06-map-units" "http://127.0.0.1:$PORT/designer/#/map/$MID/units"

# 7. Map abilities section
screenshot "07-map-abilities" "http://127.0.0.1:$PORT/designer/#/map/$MID/abilities"

# 8. Unit screen (with new meta sections)
UID=$(cat /tmp/mapqa/uid.txt)
screenshot "08-unit-main" "http://127.0.0.1:$PORT/designer/#/unit/$UID"

# 9. Unit build screen
screenshot "09-unit-build" "http://127.0.0.1:$PORT/designer/#/unit/$UID/build"

# 10. Unit versions screen
screenshot "10-unit-versions" "http://127.0.0.1:$PORT/designer/#/unit/$UID/versions"

# Clean up login shim
rm -f www/dev/zz-test-login.html

echo
echo "=== Browser Test Summary ==="
echo "Screenshots saved to: $SHOTS_DIR"
ls -lh "$SHOTS_DIR"/*.png 2>/dev/null | awk '{print $9, $5}'
echo
echo "Review the screenshots and check:"
echo "  - My Maps section appears on home page"
echo "  - Map main screen shows section buttons"
echo "  - Each map section renders correctly"
echo "  - Unit screen has Build, Versions, Bug Report buttons"
echo "  - All tables have visible black borders"
echo "  - No JavaScript errors (check with actual browser if needed)"
echo
echo "To view: open $SHOTS_DIR/*.png"
