#!/bin/bash
# Deploy More Neutral Units (MNU) build to the live VM at https://cwo.freeddns.org/mnu/
#
# Thin wrapper — all deploy logic lives in deploy-common.sh, which is IDENTICAL
# for every build. The only per-build differences are the four config values
# below (workspace path, server path, public URL, lock key). Any behavioural
# difference between builds would be a bug.
#
# Usage:
#   ./deploy-mnu-to-vm.sh            # bump version, build, deploy, verify
#   ./deploy-mnu-to-vm.sh --assets   # also resync webp + fonts (slow)
#   ./deploy-mnu-to-vm.sh --no-bump  # deploy without bumping the version

BUILD_KEY="mnu"
SOURCE="/Users/gremus/Claude-Projects/cw-mnu-wt/solo"
REMOTE_ROOT="/opt/cwo/mnu"
SERVER_URL="https://cwo.freeddns.org/mnu/"

source "$(cd "$(dirname "$0")" && pwd)/deploy-common.sh"
