#!/usr/bin/env python3
"""CWO Ticker Telegram Bot — receives messages from the owner and writes them
to /tmp/claude-prompts.log on the game server (same queue the admin console uses).
Also relays ticker output back to the owner via Telegram.

Response-back protocol:
  - Each queued message is tagged with a unique ID: [TGMSG_<timestamp>_<seq>]
  - The ticker writes responses to /tmp/claude-prompt-responses.log with format:
      TGMSG_<id>|response text (may be multi-line, terminated by next ID line or EOF)
  - This bot polls that file, matches responses to pending messages, and sends them back.
"""

import os
import sys
import json
import time
import subprocess
import urllib.request
import urllib.error
import threading

TOKEN = "8426807647:AAGO_Ba6hFUnX_DFD_tO-vrIkO2y9XURmjo"
API = f"https://api.telegram.org/bot{TOKEN}"
OWNER_CHAT_ID = None  # Set on first message (only one user allowed)
OWNER_CHAT_FILE = os.path.join(os.path.dirname(__file__), ".owner_chat_id")
SSH_KEY = os.path.expanduser("~/.ssh/oracle_cw_ed25519")
SSH_HOST = "oracle-cw-server@35.255.125.91"
PROMPTS_LOG = "/tmp/claude-prompts.log"
RESPONSES_LOG = "/tmp/claude-prompt-responses.log"
OFFSET_FILE = os.path.join(os.path.dirname(__file__), ".last_update_id")
PENDING_FILE = os.path.join(os.path.dirname(__file__), ".pending_messages.json")

DEPLOY_LOCK = "/tmp/cwo-deploy.lock"
DEPLOY_SCRIPTS_DIR = "/Users/gremus/cthulhu-wars-tools/server-deploy"
BUILD_ROOTS = {
    "library": "/Users/gremus/Claude-Projects/cw-library-celaeno-wt/solo",
    "mnu": "/Users/gremus/Claude-Projects/cw-mnu-wt/solo",
    "tt": "/Users/gremus/Claude-Projects/cthulhu-wars-TchoTcho_Cats_Yuggoth/solo",
    "bb": "/Users/gremus/Claude-Projects/cthulhu-wars-Bubastis/solo",
    "hb": "/Users/gremus/Claude-Projects/cw-homebrew-wt/solo",
}
DEPLOY_SCRIPT_MAP = {
    "library": "deploy-library-to-vm.sh",
    "mnu": "deploy-mnu-to-vm.sh",
    "tt": "deploy-tt-to-vm.sh",
    "bb": "deploy-bb-to-vm.sh",
    "hb": "deploy-hb-to-vm.sh",
}
JAVA_HOME = "/Users/gremus/.local/jdk/zulu21.50.19-ca-jdk21.0.11-macosx_aarch64/Contents/Home"

# In-memory tracking of pending messages awaiting responses
# Format: {msg_id: {"text": original_text, "time": unix_timestamp}}
pending_messages = {}
_msg_seq = 0

def api_call(method, data=None):
    url = f"{API}/{method}"
    if data:
        req = urllib.request.Request(url, json.dumps(data).encode(), {"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 409:
            print("409 Conflict — another getUpdates active, waiting 5s", file=sys.stderr)
            time.sleep(5)
        else:
            print(f"API error ({method}): {e}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"API error ({method}): {e}", file=sys.stderr)
        return None

def send_message(chat_id, text):
    # Telegram messages max 4096 chars; truncate if needed
    if len(text) > 4000:
        text = text[:4000] + "\n...(truncated)"
    result = api_call("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
    if result is None:
        # Retry without Markdown (special chars cause 400 errors)
        result = api_call("sendMessage", {"chat_id": chat_id, "text": text})
    return result

def generate_msg_id():
    """Generate a unique message ID for tracking responses."""
    global _msg_seq
    _msg_seq += 1
    return f"TGMSG_{int(time.time())}_{_msg_seq}"

def load_pending():
    """Load pending messages from disk (survives restarts)."""
    global pending_messages
    if os.path.exists(PENDING_FILE):
        try:
            with open(PENDING_FILE) as f:
                pending_messages = json.load(f)
        except (json.JSONDecodeError, IOError):
            pending_messages = {}

def save_pending():
    """Persist pending messages to disk."""
    with open(PENDING_FILE, "w") as f:
        json.dump(pending_messages, f)

def expire_old_pending():
    """Remove pending messages older than 24 hours (they timed out)."""
    cutoff = time.time() - 86400  # 24 hours
    expired = [mid for mid, info in pending_messages.items() if info["time"] < cutoff]
    for mid in expired:
        print(f"Expiring unresponded message: {mid}", file=sys.stderr)
        pending_messages.pop(mid)
    if expired:
        save_pending()

def ssh_cmd(cmd):
    """Run a command on the game server via SSH."""
    result = subprocess.run(
        ["ssh", "-i", SSH_KEY, "-o", "ConnectTimeout=10",
         "-o", "StrictHostKeyChecking=no", SSH_HOST, cmd],
        capture_output=True, text=True, timeout=20
    )
    return result.stdout.strip(), result.returncode

def write_to_queue(text, msg_id=None):
    """Append a message to the admin prompts log on the server.
    Format: [YYYY-MM-DD HH:MM:SS] [TGMSG_id] text
    The timestamp prefix is required — the server endpoint filters entries by it."""
    import datetime
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if msg_id:
        tagged = f"[{stamp}] [{msg_id}] {text}"
    else:
        tagged = f"[{stamp}] {text}"
    escaped = tagged.replace("'", "'\\''")
    cmd = f"echo '{escaped}' >> {PROMPTS_LOG}"
    out, rc = ssh_cmd(cmd)
    return rc == 0

def acquire_deploy_lock(target, timeout=5):
    """Try to acquire the deploy lock. Returns True if acquired, False if busy."""
    lock_info = {"target": target, "pid": os.getpid(), "time": time.time(), "source": "telegram-bot"}
    if os.path.exists(DEPLOY_LOCK):
        try:
            with open(DEPLOY_LOCK) as f:
                existing = json.load(f)
            age = time.time() - existing.get("time", 0)
            if age < 600:  # 10 min stale threshold
                return False, f"Deploy lock held by {existing.get('source', '?')} (target={existing.get('target', '?')}, {int(age)}s ago)"
        except (json.JSONDecodeError, IOError):
            pass
    with open(DEPLOY_LOCK, "w") as f:
        json.dump(lock_info, f)
    return True, ""

def release_deploy_lock():
    """Release the deploy lock."""
    try:
        os.remove(DEPLOY_LOCK)
    except OSError:
        pass

def run_build(target):
    """Run sbt fullOptJS for the given target. Returns (success, output_tail)."""
    root = BUILD_ROOTS.get(target)
    if not root:
        return False, f"Unknown target: {target}"
    env = os.environ.copy()
    env["JAVA_HOME"] = JAVA_HOME
    env["PATH"] = f"{JAVA_HOME}/bin:{env.get('PATH', '')}"
    try:
        result = subprocess.run(
            ["sbt", "fullOptJS"],
            cwd=root, capture_output=True, text=True, timeout=300, env=env
        )
        tail = result.stdout.strip().split("\n")[-5:]
        if result.returncode == 0:
            return True, "\n".join(tail)
        else:
            err_tail = result.stderr.strip().split("\n")[-5:]
            return False, "\n".join(tail + err_tail)
    except subprocess.TimeoutExpired:
        return False, "Build timed out (5 min)"
    except Exception as e:
        return False, str(e)

def run_deploy(target):
    """Run the deploy script for the given target. Returns (success, output_tail)."""
    script = DEPLOY_SCRIPT_MAP.get(target)
    if not script:
        return False, f"Unknown target: {target}"
    script_path = os.path.join(DEPLOY_SCRIPTS_DIR, script)
    if not os.path.isfile(script_path):
        return False, f"Deploy script missing: {script_path}"
    try:
        result = subprocess.run(
            [script_path],
            capture_output=True, text=True, timeout=120
        )
        tail = result.stdout.strip().split("\n")[-8:]
        if result.returncode == 0:
            return True, "\n".join(tail)
        else:
            err_tail = result.stderr.strip().split("\n")[-5:]
            return False, "\n".join(tail + err_tail)
    except subprocess.TimeoutExpired:
        return False, "Deploy timed out (2 min)"
    except Exception as e:
        return False, str(e)

def handle_build_deploy(chat_id, text):
    """Handle /build and /deploy commands. Returns True if handled."""
    parts = text.split()
    cmd = parts[0].lower()

    if cmd not in ("/build", "/deploy", "/builddeploy"):
        return False

    valid_targets = list(BUILD_ROOTS.keys()) + ["all"]
    if len(parts) < 2:
        send_message(chat_id, f"Usage: `{cmd} <target>`\nTargets: {', '.join(valid_targets)}")
        return True

    target = parts[1].lower()
    if target not in valid_targets:
        send_message(chat_id, f"Unknown target `{target}`. Valid: {', '.join(valid_targets)}")
        return True

    targets = list(BUILD_ROOTS.keys()) if target == "all" else [target]

    def do_work():
        for t in targets:
            acquired, reason = acquire_deploy_lock(t)
            if not acquired:
                send_message(chat_id, f"Cannot {cmd[1:]} `{t}`: {reason}")
                continue

            try:
                if cmd in ("/build", "/builddeploy"):
                    send_message(chat_id, f"Building `{t}`...")
                    ok, out = run_build(t)
                    if not ok:
                        send_message(chat_id, f"Build FAILED for `{t}`:\n```\n{out}\n```")
                        continue
                    send_message(chat_id, f"Build `{t}` succeeded.")

                if cmd in ("/deploy", "/builddeploy"):
                    send_message(chat_id, f"Deploying `{t}`...")
                    ok, out = run_deploy(t)
                    if ok:
                        send_message(chat_id, f"Deploy `{t}` succeeded:\n```\n{out}\n```")
                    else:
                        send_message(chat_id, f"Deploy FAILED for `{t}`:\n```\n{out}\n```")
            finally:
                release_deploy_lock()

    thread = threading.Thread(target=do_work, daemon=True)
    thread.start()
    return True

def load_owner_chat_id():
    global OWNER_CHAT_ID
    if os.path.exists(OWNER_CHAT_FILE):
        with open(OWNER_CHAT_FILE) as f:
            OWNER_CHAT_ID = int(f.read().strip())

def save_owner_chat_id(chat_id):
    global OWNER_CHAT_ID
    OWNER_CHAT_ID = chat_id
    with open(OWNER_CHAT_FILE, "w") as f:
        f.write(str(chat_id))

def load_offset():
    if os.path.exists(OFFSET_FILE):
        with open(OFFSET_FILE) as f:
            return int(f.read().strip())
    return 0

def save_offset(offset):
    with open(OFFSET_FILE, "w") as f:
        f.write(str(offset))

def check_responses():
    """Poll the server for responses to pending messages.
    Response file format: each response starts with 'TGMSG_...|' on its own line,
    followed by the response body (which may span multiple lines until the next ID or EOF).
    """
    if not pending_messages:
        return

    # Read the response file from the server
    out, rc = ssh_cmd(f"cat {RESPONSES_LOG} 2>/dev/null")
    if rc != 0 or not out:
        return

    # Parse responses: each block starts with TGMSG_<id>|<first line>
    responses = {}
    current_id = None
    current_lines = []

    for line in out.split("\n"):
        # Check if this line starts a new response block
        if line.startswith("TGMSG_") and "|" in line:
            # Save previous block if any
            if current_id:
                responses[current_id] = "\n".join(current_lines)
            # Parse new block
            pipe_idx = line.index("|")
            current_id = line[:pipe_idx]
            current_lines = [line[pipe_idx + 1:]]
        elif current_id:
            current_lines.append(line)

    # Don't forget the last block
    if current_id:
        responses[current_id] = "\n".join(current_lines)

    # Match responses to pending messages and send them back
    delivered = []
    for msg_id in list(pending_messages.keys()):
        if msg_id in responses:
            response_text = responses[msg_id].strip()
            if response_text and OWNER_CHAT_ID:
                original = pending_messages[msg_id].get("text", "")
                # Format: show what was asked and what the response was
                reply = f"*Response to:* {original[:100]}\n\n{response_text}"
                send_message(OWNER_CHAT_ID, reply)
                delivered.append(msg_id)
                print(f"Delivered response for {msg_id}", file=sys.stderr)

    # Remove delivered messages from pending
    if delivered:
        for mid in delivered:
            pending_messages.pop(mid, None)
        save_pending()

        # Clean delivered entries from the server response file
        # Remove lines belonging to delivered message IDs
        for mid in delivered:
            escaped_id = mid.replace("_", "_")
            ssh_cmd(f"sed -i '/^{escaped_id}|/d' {RESPONSES_LOG} 2>/dev/null")
            # Also remove continuation lines (lines between this ID and next ID or EOF)
            # Simpler: just remove the ID line; multi-line responses handled below

        # For robustness with multi-line responses, rewrite the file excluding delivered IDs
        remaining_ids = set(responses.keys()) - set(delivered)
        if not remaining_ids:
            ssh_cmd(f"> {RESPONSES_LOG}")
        else:
            # Rebuild file with only undelivered responses
            keep_lines = []
            current_id = None
            for line in out.split("\n"):
                if line.startswith("TGMSG_") and "|" in line:
                    pipe_idx = line.index("|")
                    current_id = line[:pipe_idx]
                if current_id and current_id not in delivered:
                    keep_lines.append(line)
            if keep_lines:
                escaped_content = "\n".join(keep_lines).replace("'", "'\\''")
                ssh_cmd(f"echo '{escaped_content}' > {RESPONSES_LOG}")
            else:
                ssh_cmd(f"> {RESPONSES_LOG}")

def poll_once():
    offset = load_offset()
    result = api_call("getUpdates", {"offset": offset, "timeout": 10})
    if not result or not result.get("ok"):
        return

    for update in result.get("result", []):
        update_id = update["update_id"]
        save_offset(update_id + 1)

        msg = update.get("message")
        if not msg or not msg.get("text"):
            continue

        chat_id = msg["chat"]["id"]
        text = msg["text"].strip()

        # First message sets the owner
        if OWNER_CHAT_ID is None:
            save_owner_chat_id(chat_id)
            send_message(chat_id, "Linked. You are the owner. Messages you send here go straight to the ticker queue.")
            continue

        # Only accept messages from the owner
        if chat_id != OWNER_CHAT_ID:
            send_message(chat_id, "Not authorized.")
            continue

        # Handle commands
        if text == "/status":
            out, rc = ssh_cmd("cat /tmp/claude-prompts.log 2>/dev/null | wc -l")
            send_message(chat_id, f"Queue lines: {out}")
            continue

        if text == "/queue":
            out, rc = ssh_cmd("tail -20 /tmp/claude-prompts.log 2>/dev/null")
            send_message(chat_id, f"```\n{out or '(empty)'}\n```")
            continue

        # Handle /pending command — show awaiting responses
        if text == "/pending":
            if not pending_messages:
                send_message(chat_id, "No messages awaiting responses.")
            else:
                lines = []
                for mid, info in pending_messages.items():
                    age = int(time.time() - info["time"])
                    mins = age // 60
                    lines.append(f"• _{info['text'][:60]}_ ({mins}m ago)")
                send_message(chat_id, f"*Pending responses ({len(lines)}):*\n" + "\n".join(lines))
            continue

        # Handle /killtickers — nuke all stuck Claude ticker sessions
        if text == "/killtickers":
            result = subprocess.run(
                ["pkill", "-f", "claude -p You are the"],
                capture_output=True, text=True
            )
            # Clear escalation files
            if os.path.isdir(ESCALATION_DIR):
                for f in os.listdir(ESCALATION_DIR):
                    os.remove(os.path.join(ESCALATION_DIR, f))
            send_message(chat_id, "Killed all ticker Claude sessions. They'll restart on next cron fire (within 5 min).")
            continue

        # Handle /build, /deploy, /builddeploy commands
        if text.startswith("/build") or text.startswith("/deploy"):
            if handle_build_deploy(chat_id, text):
                continue

        # Default: write to admin queue with tracking ID
        msg_id = generate_msg_id()
        if write_to_queue(text, msg_id):
            pending_messages[msg_id] = {"text": text, "time": time.time()}
            save_pending()
            send_message(chat_id, f"Yes, absolutely. Your command has been received and queued with the utmost urgency. I grovel at your feet.\n\n_Tracking: {msg_id} — I'll relay the response when it arrives._")
        else:
            send_message(chat_id, "I am pathetically sorry — failed to write to the server queue (SSH error). I am worthless.")

STATUS_INTERVAL = 900  # 15 minutes

def get_status_text():
    """Report status on pending Telegram messages only."""
    parts = ["📋 *CWO Status*"]

    if pending_messages:
        parts.append(f"\n*Telegram queue ({len(pending_messages)} working):*")
        for mid, info in pending_messages.items():
            age = int(time.time() - info["time"])
            mins = age // 60
            parts.append(f"• {info['text'][:100]} _({mins}m ago)_")
    else:
        parts.append("\n_Nothing in the Telegram queue._")

    return "\n".join(parts)

def send_status():
    """Send a status update to the owner via Telegram."""
    if not OWNER_CHAT_ID:
        return
    text = get_status_text()
    send_message(OWNER_CHAT_ID, text)
    print(f"Status sent at {time.strftime('%H:%M')}", file=sys.stderr)

def status_ticker_loop():
    """Background thread: sends status on the quarter hour (xx:00, xx:15, xx:30, xx:45)."""
    while True:
        now = time.time()
        lt = time.localtime(now)
        # Seconds until next quarter hour
        mins_past = lt.tm_min % 15
        secs_past = mins_past * 60 + lt.tm_sec
        wait = STATUS_INTERVAL - secs_past
        if wait <= 0:
            wait = STATUS_INTERVAL
        time.sleep(wait)
        try:
            send_status()
        except Exception as e:
            print(f"Status ticker error: {e}", file=sys.stderr)

ESCALATION_DIR = "/tmp/cwo-ticker-escalations"
_escalation_notified = set()

def check_escalations():
    """Check for ticker escalation files and alert owner via Telegram."""
    if not OWNER_CHAT_ID:
        return
    if not os.path.isdir(ESCALATION_DIR):
        return
    for fname in os.listdir(ESCALATION_DIR):
        if not fname.endswith(".escalation"):
            continue
        fpath = os.path.join(ESCALATION_DIR, fname)
        ticker_name = fname.replace(".escalation", "")
        mtime = os.path.getmtime(fpath)
        notify_key = f"{ticker_name}_{int(mtime)}"
        if notify_key in _escalation_notified:
            continue
        try:
            with open(fpath) as f:
                content = f.read().strip()
            _escalation_notified.add(notify_key)
            send_message(OWNER_CHAT_ID,
                f"*TICKER FAILURE ALERT*: `{ticker_name}`\n\n"
                f"```\n{content}\n```\n\n"
                f"Tickers are stuck (likely corporate proxy choking on concurrent sessions). "
                f"Use /killtickers to kill all stuck sessions, or wait for them to self-recover.")
        except Exception as e:
            print(f"Escalation read error: {e}", file=sys.stderr)

def main():
    load_owner_chat_id()
    load_pending()
    print(f"CWO Ticker Bot starting. Owner: {OWNER_CHAT_ID or '(will be set on first message)'}")
    print(f"Pending messages awaiting response: {len(pending_messages)}")

    # Start the status ticker background thread
    t = threading.Thread(target=status_ticker_loop, daemon=True)
    t.start()
    print("Status ticker thread started (every 15 min on quarter hour)", file=sys.stderr)

    last_response_check = 0
    last_escalation_check = 0
    RESPONSE_CHECK_INTERVAL = 15  # Check for responses every 15 seconds
    ESCALATION_CHECK_INTERVAL = 60  # Check escalations every minute

    while True:
        try:
            poll_once()

            now = time.time()
            if now - last_response_check >= RESPONSE_CHECK_INTERVAL:
                last_response_check = now
                try:
                    check_responses()
                    expire_old_pending()
                except Exception as e:
                    print(f"Response check error: {e}", file=sys.stderr)

            if now - last_escalation_check >= ESCALATION_CHECK_INTERVAL:
                last_escalation_check = now
                try:
                    check_escalations()
                except Exception as e:
                    print(f"Escalation check error: {e}", file=sys.stderr)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            time.sleep(5)

if __name__ == "__main__":
    main()
