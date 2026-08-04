#!/bin/bash
# Deploy Homebrew (HB) build to the live VM at https://cwo.freeddns.org/HB/
#
# Thin wrapper — all deploy logic lives in deploy-common.sh, which is IDENTICAL
# for every build. The only per-build differences are the four config values
# below (workspace path, server path, public URL, lock key). Any behavioural
# difference between builds would be a bug.
#
# Usage:
#   ./deploy-hb-to-vm.sh            # bump version, build, deploy, verify
#   ./deploy-hb-to-vm.sh --assets   # also resync webp + fonts (slow)
#   ./deploy-hb-to-vm.sh --no-bump  # deploy without bumping the version

BUILD_KEY="hb"
SOURCE="/Users/gremus/Claude-Projects/cw-homebrew-wt/solo"
REMOTE_ROOT="/opt/cwo/HB"
SERVER_URL="https://cwo.freeddns.org/HB/"

source "$(cd "$(dirname "$0")" && pwd)/deploy-common.sh"
