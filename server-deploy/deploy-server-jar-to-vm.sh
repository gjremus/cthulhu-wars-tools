#!/bin/bash
# Deploy CthulhuWarsOnline (akka-http backend) server.jar to the live VM.
# Runs as systemd unit cwo.service. Restart triggers a brief 502 window
# (~3s) while the JVM boots.
#
# Usage:
#   ./deploy-server-jar-to-vm.sh            # build + scp + restart
#   ./deploy-server-jar-to-vm.sh --no-build # skip sbt assembly (use existing jar)
#
# Pattern lifted from the 2026-06-03 14:25 manual deploy that should have been
# scripted earlier.

set -euo pipefail

export JAVA_HOME="/Users/gremus/.local/jdk/zulu21.50.19-ca-jdk21.0.11-macosx_aarch64/Contents/Home"
export PATH="$JAVA_HOME/bin:$PATH"

REPO_ROOT="/Users/gremus/cthulhu-wars-tools"
ONLINE_DIR="$REPO_ROOT/online"
JAR_PATH="$ONLINE_DIR/target/scala-2.13/Cthulhu Wars Online-assembly-8.0.jar"
SSH_KEY="$HOME/.ssh/oracle_cw_ed25519"
HOST="oracle-cw-server@35.255.125.91"
REMOTE_PATH="/opt/cwo/server/server.jar"

DO_BUILD=true
for arg in "$@"; do
    case "$arg" in
        --no-build) DO_BUILD=false ;;
        -h|--help) sed -n '1,15p' "$0"; exit 0 ;;
        *) echo "unknown arg: $arg"; exit 2 ;;
    esac
done

if [ ! -f "$SSH_KEY" ]; then
    echo "ERROR: ssh key not found at: $SSH_KEY"
    exit 1
fi

if $DO_BUILD; then
    echo "==> [build] sbt assembly in $ONLINE_DIR ..."
    (cd "$ONLINE_DIR" && sbt assembly 2>&1 | tail -5)
fi

if [ ! -f "$JAR_PATH" ]; then
    echo "ERROR: $JAR_PATH missing. Did sbt assembly fail?"
    exit 1
fi

STAMP="$(date +%Y%m%d-%H%M%S)"

echo "==> [backup] $REMOTE_PATH → server.jar.bak-$STAMP"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$HOST" \
    "cp $REMOTE_PATH ${REMOTE_PATH}.bak-$STAMP" 2>&1 | tail -3

echo "==> [upload] $JAR_PATH → $REMOTE_PATH"
scp -i "$SSH_KEY" -o StrictHostKeyChecking=no -C "$JAR_PATH" "$HOST:$REMOTE_PATH" 2>&1 | tail -3

echo "==> [restart] cwo.service"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$HOST" \
    'sudo systemctl restart cwo.service' 2>&1 | tail -3

echo "==> [poll] wait for akka-http to come up"
for i in 1 2 3 4 5 6 7 8; do
    sleep 3
    CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://cwo.freeddns.org/admin.html" || echo 000)
    echo "  attempt $i (after $((i*3))s):  HTTP $CODE"
    [ "$CODE" = "200" ] && break
done

echo
echo "Done.  Service status:"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$HOST" 'systemctl is-active cwo.service' 2>&1
