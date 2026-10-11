#!/bin/bash
# OLD NAME - kept so old notes still work. Forwards to deploy-hb-to-vm.sh,
# which bumps the version, builds, deploys and verifies (see deploy-common.sh).
exec "$(cd "$(dirname "$0")" && pwd)/deploy-hb-to-vm.sh" "$@"
