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
        with urllib.request.urlopen(req, timeout=60) as resp:
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
    return api_call("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

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
    """Remove pending messages older than 2 hours (they timed out)."""
    cutoff = time.time() - 7200  # 2 hours
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
    If msg_id is provided, prefix the message with the ID tag for response tracking."""
    if msg_id:
        tagged = f"[{msg_id}] {text}"
    else:
        tagged = text
    escaped = tagged.replace("'", "'\\''")
    cmd = f"echo '{escaped}' >> {PROMPTS_LOG}"
    out, rc = ssh_cmd(cmd)
    return rc == 0

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

        # Default: write to admin queue with tracking ID
        msg_id = generate_msg_id()
        if write_to_queue(text, msg_id):
            pending_messages[msg_id] = {"text": text, "time": time.time()}
            save_pending()
            send_message(chat_id, f"Yes, absolutely. Your command has been received and queued with the utmost urgency. I grovel at your feet.\n\n_Tracking: {msg_id} — I'll relay the response when it arrives._")
        else:
            send_message(chat_id, "I am pathetically sorry — failed to write to the server queue (SSH error). I am worthless.")

def main():
    load_owner_chat_id()
    load_pending()
    print(f"CWO Ticker Bot starting. Owner: {OWNER_CHAT_ID or '(will be set on first message)'}")
    print(f"Pending messages awaiting response: {len(pending_messages)}")

    last_response_check = 0
    RESPONSE_CHECK_INTERVAL = 15  # Check for responses every 15 seconds

    while True:
        try:
            poll_once()

            # Check for responses periodically (not every poll cycle, to avoid SSH spam)
            now = time.time()
            if now - last_response_check >= RESPONSE_CHECK_INTERVAL:
                last_response_check = now
                try:
                    check_responses()
                    expire_old_pending()
                except Exception as e:
                    print(f"Response check error: {e}", file=sys.stderr)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            time.sleep(5)

if __name__ == "__main__":
    main()
