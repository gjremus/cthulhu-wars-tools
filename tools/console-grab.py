#!/usr/bin/env python3
"""
console-grab.py — load a Cthulhu Wars Online game in a headless browser, capture
console errors / page errors / 404s, and write the result back into the game's
admin annotation (Notes), flagging the game broken if there are uncaught errors.

SERVER-CODE-FREE: this reuses existing admin endpoints only. Nothing here touches
server.jar or the server source.

Endpoints used (all under  https://<HOST>/admin/<TOKEN>/...):
  GET  roles/<gameId>        -> TSV "name\\tsecret" per line. "#" = spectator,
                                "$" = master. We prefer the spectator secret.
  GET  annotation/<gameId>   -> "0|1\\tnotes"  (broken flag + free-text notes)
  POST annotation/<gameId>   -> body "0|1\\tnotes" (replaces the row)
  GET  games                 -> TSV id,name,masterSecret,lastWriteMs,broken,
                                completed,isBot,humans,bots  (used by --sweep)

Play URL is built from the build tag:
  mnu                 -> https://<HOST>/mnu/play/<secret>
  hb / HB             -> https://<HOST>/HB/play/<secret>
  library / solo / "" -> https://<HOST>/play/<secret>
  (tt / bb pass through to /<TchoTcho|BB>/play/<secret> best-effort)

Usage:
  console-grab.py --game 454 --build mnu
  console-grab.py --sweep            # all active (non-bot, not-completed) games
  console-grab.py --game 454 --build mnu --dry-run   # don't write annotation
"""

import argparse
import datetime
import re
import sys
import time
import urllib.request
import urllib.error

HOST = "https://cwo.freeddns.org"
TOKEN_FILE = ("/Users/gremus/Library/CloudStorage/"
              "GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/"
              "Cthulhu Wars/Library at Celaeno/Server Deployment/"
              "owner-admin-token.txt")

# How long to let the replay run before snapshotting console output.
REPLAY_WAIT_MS = 18000
PAGE_LOAD_TIMEOUT_MS = 60000
# Notes column is capped at 4000 chars server-side; keep our entry well under.
MAX_NOTE_ENTRY = 1200
MAX_NOTES_TOTAL = 3800

# Console lines worth surfacing (case-insensitive substring match).
ERROR_KEYWORDS = ["unknown class", "uncaught", "error", "exception",
                  "failed to load", "404"]


TOKEN_CACHE = "/Users/gremus/.cw-admin-token"

def read_token():
    # Google Drive intermittently dehydrates the token file (empty read). Prefer
    # the Drive copy when it's readable (and refresh the off-Drive cache); fall
    # back to the cache when Drive has evicted it so this never blanks out.
    tok = ""
    try:
        with open(TOKEN_FILE) as f:
            tok = f.read().strip()
    except OSError:
        tok = ""
    if tok:
        try:
            with open(TOKEN_CACHE, "w") as c:
                c.write(tok + "\n")
        except OSError:
            pass
        return tok
    try:
        with open(TOKEN_CACHE) as c:
            return c.read().strip()
    except OSError:
        return ""


def admin_url(token, path):
    return f"{HOST}/admin/{token}/{path}"


def http_get(url, timeout=30):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def http_post_text(url, body, timeout=30):
    data = body.encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "text/plain; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def build_to_path(build):
    """Map an admin build tag to the URL path prefix (no leading/trailing slash
    other than what's returned). Returns '' for the root/library build."""
    b = (build or "").strip().lower()
    if b in ("mnu",):
        return "mnu"
    if b in ("hb", "homebrew"):
        return "HB"
    if b in ("tt", "tchotcho"):
        return "TchoTcho"
    if b in ("bb",):
        return "BB"
    # library / solo / unknown / empty all serve from root.
    return ""


def play_url(build, secret):
    prefix = build_to_path(build)
    if prefix:
        return f"{HOST}/{prefix}/play/{secret}"
    return f"{HOST}/play/{secret}"


def pick_secret(token, game_id):
    """Fetch roles for the game, return a secret to play with.
    Prefer the spectator entry ('#'); else any non-master faction; else master."""
    status, body = http_get(admin_url(token, f"roles/{game_id}"))
    if status != 200:
        raise RuntimeError(f"roles/{game_id} returned HTTP {status}")
    spectator = None
    faction = None
    master = None
    for line in body.splitlines():
        if "\t" not in line:
            continue
        name, secret = line.split("\t", 1)
        name = name.strip()
        secret = secret.strip()
        if not secret:
            continue
        if name == "#":
            spectator = secret
        elif name == "$":
            master = secret
        elif faction is None:
            faction = secret
    chosen = spectator or faction or master
    if not chosen:
        raise RuntimeError(f"roles/{game_id}: no usable secret found")
    kind = "spectator" if chosen == spectator else (
        "faction" if chosen == faction else "master")
    return chosen, kind


def capture_console(url, wait_ms=REPLAY_WAIT_MS):
    """Load url headless, collect console messages + page errors. Returns a dict
    with keys: page_errors (list[str]), console_errors (list[str], de-duped),
    body (str snippet), load_error (str|None)."""
    from playwright.sync_api import sync_playwright

    console_msgs = []
    page_errors = []
    body = ""
    load_error = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.on("console", lambda m: console_msgs.append(f"[{m.type}] {m.text}"))
            page.on("pageerror", lambda e: page_errors.append(str(e)))
            try:
                page.goto(url, wait_until="load", timeout=PAGE_LOAD_TIMEOUT_MS)
            except Exception as e:  # noqa: BLE001
                load_error = f"goto failed: {e}"
            page.wait_for_timeout(wait_ms)
            try:
                body = page.evaluate("document.body.innerText")
                body = body.strip().replace("\n", " | ")[:300]
            except Exception:  # noqa: BLE001
                body = ""
        finally:
            browser.close()

    # De-dup console lines, keep only error-ish ones, preserve order.
    seen = set()
    console_errors = []
    for m in console_msgs:
        low = m.lower()
        if any(k in low for k in ERROR_KEYWORDS):
            if m not in seen:
                seen.add(m)
                console_errors.append(m)
    # De-dup page errors too.
    seen_pe = set()
    deduped_pe = []
    for e in page_errors:
        if e not in seen_pe:
            seen_pe.add(e)
            deduped_pe.append(e)

    return {
        "page_errors": deduped_pe,
        "console_errors": console_errors,
        "body": body,
        "load_error": load_error,
    }


def summarize(result):
    """Produce a one-entry human summary string for the Notes column, plus a
    boolean 'has_uncaught' for the broken flag."""
    pe = result["page_errors"]
    ce = result["console_errors"]
    has_uncaught = bool(pe) or result["load_error"] is not None

    parts = []
    if result["load_error"]:
        parts.append(f"LOAD-ERROR: {result['load_error']}")
    if pe:
        parts.append("UNCAUGHT PAGE ERRORS:")
        parts.extend("  - " + e for e in pe)
    if ce:
        parts.append("CONSOLE errors/404s:")
        parts.extend("  - " + m for m in ce)
    if not pe and not ce and not result["load_error"]:
        parts.append("clean — no uncaught errors, no console errors/404s.")
    summary = "\n".join(parts)
    if len(summary) > MAX_NOTE_ENTRY:
        summary = summary[:MAX_NOTE_ENTRY - 3] + "..."
    return summary, has_uncaught


def write_annotation(token, game_id, entry, set_broken, dry_run=False):
    """Append the timestamped CONSOLE entry to the game's notes, preserving
    existing notes. If set_broken, raise the broken flag; otherwise preserve the
    existing broken flag (never auto-clear it)."""
    status, body = http_get(admin_url(token, f"annotation/{game_id}"))
    if status != 200:
        raise RuntimeError(f"GET annotation/{game_id} returned HTTP {status}")
    tab = body.find("\t")
    if tab >= 0:
        cur_broken = body[:tab].strip() == "1"
        cur_notes = body[tab + 1:]
    else:
        cur_broken = body.strip() == "1"
        cur_notes = ""

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    new_entry = f"CONSOLE {ts}: {entry}"
    # Append below existing notes, newest at bottom (matches free-text edits).
    if cur_notes.strip():
        merged = cur_notes.rstrip("\n") + "\n\n" + new_entry
    else:
        merged = new_entry
    if len(merged) > MAX_NOTES_TOTAL:
        merged = merged[-MAX_NOTES_TOTAL:]

    new_broken = cur_broken or set_broken
    payload = ("1" if new_broken else "0") + "\t" + merged

    if dry_run:
        print(f"[dry-run] would POST annotation/{game_id} "
              f"(broken={'1' if new_broken else '0'}):")
        print(new_entry)
        return True, new_broken

    status, _ = http_post_text(admin_url(token, f"annotation/{game_id}"), payload)
    ok = status in (200, 202)
    return ok, new_broken


def grab_one(token, game_id, build, dry_run=False):
    """Run a console-grab for a single game. Returns a result dict. Wrapped so a
    single failure during a sweep doesn't kill the whole run."""
    out = {"game_id": game_id, "build": build, "ok": False, "broken": None,
           "secret_kind": None, "summary": None, "error": None, "url": None}
    try:
        secret, kind = pick_secret(token, game_id)
        out["secret_kind"] = kind
        url = play_url(build, secret)
        out["url"] = url
        print(f"[game {game_id}] build={build} secret={kind} url={url}")
        result = capture_console(url)
        summary, has_uncaught = summarize(result)
        out["summary"] = summary
        print(f"[game {game_id}] body: {result['body']!r}")
        print(f"[game {game_id}] summary:\n{summary}")
        wrote, new_broken = write_annotation(
            token, game_id, summary.replace("\n", " | "),
            set_broken=has_uncaught, dry_run=dry_run)
        out["ok"] = wrote
        out["broken"] = new_broken
        status_word = "OK" if wrote else "FAILED"
        print(f"[game {game_id}] annotation write: {status_word} "
              f"(broken={'1' if new_broken else '0'})")
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)
        print(f"[game {game_id}] ERROR: {e}", file=sys.stderr)
    return out


# The games list endpoint (admin "games") is tab-delimited; column index 10 is
# the game's build tag (library|mnu|tt|bb|HB|unknown), the same column the admin
# UI reads as parts[10] (admin.html ~line 1220). The --sweep path uses this real
# per-game build so each game is loaded at its correct play URL. Older server
# responses may omit the column (blank) -> we fall back to "library".
SWEEP_BUILD_DEFAULT = "library"


def normalize_build(raw):
    """Map a games-endpoint build column value to an admin build tag the grab
    path understands. Blank / 'unknown' / 'library' all collapse to the library
    (root) build, matching the prior hardcoded fallback behavior."""
    b = (raw or "").strip()
    if not b or b.lower() in ("unknown", "library"):
        return SWEEP_BUILD_DEFAULT
    return b


def active_games(token):
    """Return list of (id, name, build) for active games: not bot, not completed.

    build is parsed from column index 10 of the tab-delimited games endpoint
    (same column admin.html reads as parts[10]), normalized via normalize_build."""
    status, body = http_get(admin_url(token, "games"))
    if status != 200:
        raise RuntimeError(f"GET games returned HTTP {status}")
    out = []
    for line in body.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        gid = parts[0]
        name = parts[1] if len(parts) > 1 else ""
        completed = (parts[5] if len(parts) > 5 else "0").strip() == "1"
        is_bot = (parts[6] if len(parts) > 6 else "0").strip() == "1"
        build = normalize_build(parts[10] if len(parts) > 10 else "")
        if is_bot or completed:
            continue
        out.append((gid, name, build))
    return out


def main():
    ap = argparse.ArgumentParser(description="Headless console-grab for CWO games.")
    ap.add_argument("--game", type=str, help="game id (single-game mode)")
    ap.add_argument("--build", type=str, default="",
                    help="build tag: mnu|hb|library|solo|tt|bb (single-game mode)")
    ap.add_argument("--sweep", action="store_true",
                    help="run for ALL active (non-bot, not-completed) games")
    ap.add_argument("--dry-run", action="store_true",
                    help="capture + print but do NOT write the annotation")
    args = ap.parse_args()

    token = read_token()
    if not token:
        print("FATAL: empty admin token", file=sys.stderr)
        return 2

    if args.sweep:
        games = active_games(token)
        print(f"[sweep] {len(games)} active games")
        n_ok = n_fail = 0
        for gid, name, build in games:
            r = grab_one(token, gid, build, dry_run=args.dry_run)
            if r["ok"]:
                n_ok += 1
            else:
                n_fail += 1
            # Be gentle: small gap between games.
            time.sleep(1)
        print(f"[sweep] done: {n_ok} ok, {n_fail} failed")
        return 0 if n_fail == 0 else 1

    if not args.game:
        ap.error("either --game <id> --build <build> or --sweep is required")
    r = grab_one(token, args.game, args.build, dry_run=args.dry_run)
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
