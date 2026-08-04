#!/bin/bash
# Deploy Bubastis (BB) build to the live VM at https://cwo.freeddns.org/BB/
#
# Thin wrapper — all deploy logic lives in deploy-common.sh, which is IDENTICAL
# for every build. The only per-build differences are the four config values
# below (workspace path, server path, public URL, lock key). Any behavioural
# difference between builds would be a bug.
#
# Usage:
#   ./deploy-bb-to-vm.sh            # bump version, build, deploy, verify
#   ./deploy-bb-to-vm.sh --assets   # also resync webp + fonts (slow)
#   ./deploy-bb-to-vm.sh --no-bump  # deploy without bumping the version

BUILD_KEY="bb"
SOURCE="/Users/gremus/Claude-Projects/cthulhu-wars-Bubastis/solo"
REMOTE_ROOT="/opt/cwo/bb"
SERVER_URL="https://cwo.freeddns.org/BB/"

source "$(cd "$(dirname "$0")" && pwd)/deploy-common.sh"
