#!/bin/bash
# Deploy the MAIN build to the live VM at the BASE URL https://cwo.freeddns.org/
#
# "Main" is the former "BB"/Bubastis build — the most-advanced non-Homebrew
# build. The base URL (/) serves /opt/cwo/library (via the `solo` symlink), so
# deploying Main means writing that directory and verifying the base URL.
#
# This supersedes deploy-bb-to-vm.sh (legacy /BB/ path, kept lights-on only for
# in-flight games) and deploy-library-to-vm.sh (pointed at the stale celaeno
# checkout — do NOT use it; its SOURCE is wrong and would clobber the base).
#
# Thin wrapper — all deploy logic lives in deploy-common.sh.
#
# Usage:
#   ./deploy-main-to-vm.sh            # bump version, build, deploy, verify
#   ./deploy-main-to-vm.sh --assets   # also resync webp + fonts (slow)
#   ./deploy-main-to-vm.sh --no-bump  # deploy without bumping the version

BUILD_KEY="main"
SOURCE="/Users/gremus/Claude-Projects/cthulhu-wars-Main/solo"
REMOTE_ROOT="/opt/cwo/library"
SERVER_URL="https://cwo.freeddns.org/"

source "$(cd "$(dirname "$0")" && pwd)/deploy-common.sh"
