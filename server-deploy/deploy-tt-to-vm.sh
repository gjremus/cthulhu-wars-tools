#!/bin/bash
# Deploy Tcho-Tcho (TT) build to the live VM at https://cwo.freeddns.org/TchoTcho/
#
# Thin wrapper — all deploy logic lives in deploy-common.sh, which is IDENTICAL
# for every build. The only per-build differences are the four config values
# below (workspace path, server path, public URL, lock key). Any behavioural
# difference between builds would be a bug.
#
# Usage:
#   ./deploy-tt-to-vm.sh            # bump version, build, deploy, verify
#   ./deploy-tt-to-vm.sh --assets   # also resync webp + fonts (slow)
#   ./deploy-tt-to-vm.sh --no-bump  # deploy without bumping the version

BUILD_KEY="tt"
SOURCE="/Users/gremus/Claude-Projects/cthulhu-wars-TchoTcho_Cats_Yuggoth/solo"
REMOTE_ROOT="/opt/cwo/tt"
SERVER_URL="https://cwo.freeddns.org/TchoTcho/"

source "$(cd "$(dirname "$0")" && pwd)/deploy-common.sh"
