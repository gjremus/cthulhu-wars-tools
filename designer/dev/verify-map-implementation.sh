#!/bin/bash
# Verify Map Designer implementation is complete

echo "=== Map Designer Implementation Verification ==="
echo

REPO="/Users/gremus/Claude-Projects/cthulhu-wars-tools/designer"
cd "$REPO" || exit 1

errors=0
warnings=0

check_file() {
    local file="$1"
    local desc="$2"
    if [ -f "$file" ]; then
        echo "✓ $desc: $file"
    else
        echo "✗ MISSING: $desc: $file"
        ((errors++))
    fi
}

check_keyword() {
    local file="$1"
    local keyword="$2"
    local desc="$3"
    if [ ! -f "$file" ]; then
        return
    fi
    if grep -q "$keyword" "$file" 2>/dev/null; then
        echo "  ✓ Contains: $desc"
    else
        echo "  ⚠ Missing: $desc"
        ((warnings++))
    fi
}

echo "## Core Files"
check_file "server/designer_server.py" "Backend server"
check_file "www/app.js" "Frontend app"
check_file "www/sections.js" "Section renderers"
check_file "www/rules.js" "Rules engine"

echo
echo "## Backend Checks"
check_keyword "server/designer_server.py" "def.*maps_dir" "maps_dir() function"
check_keyword "server/designer_server.py" "def.*load_map" "load_map() function"
check_keyword "server/designer_server.py" "def.*new_map_design" "new_map_design() function"
check_keyword "server/designer_server.py" "handle_list_maps" "GET /maps handler"
check_keyword "server/designer_server.py" "handle_create_map" "POST /maps handler"
check_keyword "server/designer_server.py" "handle_patch_map" "PATCH map handler"
check_keyword "server/designer_server.py" "'/designer/api/maps'" "Maps API routes"

echo
echo "## Frontend Checks"
check_keyword "www/app.js" "loadMapList" "loadMapList() method"
check_keyword "www/app.js" "createMap" "createMap() method"
check_keyword "www/app.js" "renderMapMainDesign" "renderMapMainDesign() method"
check_keyword "www/app.js" "'#/map/" "Map routes"

check_keyword "www/sections.js" "renderMapImages" "renderMapImages() function"
check_keyword "www/sections.js" "renderMapBitmaps" "renderMapBitmaps() function"
check_keyword "www/sections.js" "renderMapAdjacency" "renderMapAdjacency() function"
check_keyword "www/sections.js" "renderMapUnits" "renderMapUnits() function"

check_keyword "www/rules.js" "MAP_SECTIONS" "MAP_SECTIONS array"
check_keyword "www/rules.js" "newMapDesign" "newMapDesign() function"
check_keyword "www/rules.js" "mapBuildReady" "mapBuildReady() function"

echo
echo "## Test Files"
check_file "server/test_designer_server.py" "Existing server tests"
check_file "server/test_map_features.py" "Map feature tests"
check_file "dev/test-map-browser.sh" "Browser tests"

echo
echo "## Assets"
check_file "www/glyphs/gc-glyph.webp" "Great Cthulhu glyph"
check_file "www/glyphs/cc-glyph.webp" "Crawling Chaos glyph"
check_file "www/glyphs/bg-glyph.webp" "Black Goat glyph"
check_file "www/glyphs/ys-glyph.webp" "Yellow Sign glyph"
check_file "www/glyphs/dragon.png" "Dragon glyph"
check_file "www/glyphs/thorns.png" "Thorns glyph"
check_file "www/glyphs/chevron.png" "Chevron glyph"

echo
echo "## Admin CLI"
check_file "/Users/gremus/Claude-Projects/cthulhu-wars-tools/tickers/designer-admin.py" "Admin CLI"
check_keyword "/Users/gremus/Claude-Projects/cthulhu-wars-tools/tickers/designer-admin.py" "map <mid>" "map command"
check_keyword "/Users/gremus/Claude-Projects/cthulhu-wars-tools/tickers/designer-admin.py" "map-patch" "map-patch command"
check_keyword "/Users/gremus/Claude-Projects/cthulhu-wars-tools/tickers/designer-admin.py" "map-build-status" "map-build-status command"

echo
echo "## Documentation"
check_file "SPEC.md" "Technical spec"
check_keyword "SPEC.md" "maps/<mid>/map.json" "Map storage documented"
check_keyword "SPEC.md" "Map design" "Map design schema"
check_keyword "SPEC.md" "/designer/api/maps" "Maps API documented"

echo
echo "=== Summary ==="
echo "Errors:   $errors"
echo "Warnings: $warnings"
echo

if [ $errors -eq 0 ]; then
    echo "✓ All required files present"
    if [ $warnings -eq 0 ]; then
        echo "✓ All checks passed"
        echo
        echo "Next steps:"
        echo "1. Run server tests: cd server && python3 -m unittest -v test_designer_server test_map_features"
        echo "2. Start local servers and run browser tests: dev/test-map-browser.sh"
        exit 0
    else
        echo "⚠ Some warnings detected - review implementation"
        exit 1
    fi
else
    echo "✗ Missing required files - implementation incomplete"
    exit 1
fi
