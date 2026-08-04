#!/bin/bash
# Deploy Library at Celaeno build to the live VM at https://cwo.freeddns.org/
#
# Thin wrapper — all deploy logic lives in deploy-common.sh, which is IDENTICAL
# for every build. The only per-build differences are the four config values
# below (workspace path, server path, public URL, lock key). Any behavioural
# difference between builds would be a bug.
#
# Usage:
#   ./deploy-library-to-vm.sh            # bump version, build, deploy, verify
#   ./deploy-library-to-vm.sh --assets   # also resync webp + fonts (slow)
#   ./deploy-library-to-vm.sh --no-bump  # deploy without bumping the version

BUILD_KEY="library"
SOURCE="/Users/gremus/Claude-Projects/cw-library-celaeno-wt/solo"
REMOTE_ROOT="/opt/cwo/library"
SERVER_URL="https://cwo.freeddns.org/"

source "$(cd "$(dirname "$0")" && pwd)/deploy-common.sh"
