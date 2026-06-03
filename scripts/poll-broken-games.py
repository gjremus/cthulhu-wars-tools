#!/usr/bin/env python3
"""
Poll the admin /games endpoint, find broken/errored games, infer build from log,
filter to Library/MNU (skip TT/BB — other Claude handles those), and emit a JSON
candidate list to stdout for the ticker to pick up + analyze.

Phase A of the proactive-diagnosis pipeline (2026-06-03). The ticker calls this
each tick. The actual root-cause analysis + fix proposal happens in the ticker
prompt — this script just identifies WHICH games to look at and what their
basic state is.

Usage:
  poll-broken-games.py
    → prints JSON: { "candidates": [{game_id, build, has_fix_response, log_url, admin_url}, ...] }

Filtering:
  - only games with broken=1 OR errored (per the admin.html isErrored heuristic)
  - skip games that already have a fix-response (don't spam the field every tick)
  - skip games whose log mentions TchoTcho or Bubastis factions (those are TT/BB,
    other Claude's responsibility)

Build inference:
  - log contains "TchoTcho" or "Tcho-Tcho" → build="tt", SKIP
  - log contains "Bubastis" → build="bb", SKIP
  - log contains "Tombstalker" / "Firstborn" / "Daemon Sultan" → build="mnu" (those
    are post-Library factions present in MNU but not Library)
  - else → build="library"
"""

import json
import os
import sys
import urllib.request
import urllib.parse

SERVER = os.environ.get("CWO_SERVER", "https://cwo.freeddns.org")
# Order: $CWO_ADMIN_TOKEN_FILE, then this Mac's known path, then other Mac's
# expected path (sibling layout). Other Claude on a different machine sets
# CWO_ADMIN_TOKEN_FILE to wherever they store the token.
TOKEN_PATH = os.environ.get(
    "CWO_ADMIN_TOKEN_FILE",
    next((
        p for p in [
            "/Users/gremus/My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/Server Deployment/owner-admin-token.txt",
            os.path.expanduser("~/My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/Server Deployment/owner-admin-token.txt"),
            os.path.expanduser("~/cwo-admin-token.txt"),
        ] if os.path.exists(p)
    ), "")
)
# Other Claude (on a different machine handling TT/BB) inverts the build filter:
# instead of skipping tt/bb, it processes them and skips library/mnu. Set the
# CWO_RL_BUILDS env var to "tt,bb" to flip the filter. Default: this Mac's
# Library/MNU scope.
ALLOWED_BUILDS = set((os.environ.get("CWO_RL_BUILDS") or "library,mnu").split(","))

# Build identity is encoded in log[0] (the first log line — version header
# written by each frontend at game creation, e.g. "Cthulhu Wars HRF
# library-at-celaeno-v4" or "Cthulhu Wars HRF more-neutral-units-v2").
# The server's own redirect logic at CthulhuWarsOnline.scala:232-247 reads
# this same line; we follow that convention. When the server-side migration
# adds a Games.build column (recipe posted to other Claude 2026-06-03), this
# can swap to a direct column read.
VERSION_HEADER_MARKERS = {
    "library-at-celaeno": "library",
    "more-neutral-units": "mnu",
    "tcho-tcho": "tt",
    "bubastis": "bb",
}


def _get(path, timeout=15):
    url = f"{SERVER}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def load_token():
    with open(TOKEN_PATH) as f:
        return f.read().strip()


def parse_games_tsv(text):
    """Return list of dicts mirroring admin.html populateGames()."""
    games = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if not parts or not parts[0].strip():
            continue
        # Old server responses pad with 0/empty; indexing is stable.
        try:
            games.append(
                dict(
                    id=parts[0],
                    name=parts[1] if len(parts) > 1 else "",
                    secret=parts[2] if len(parts) > 2 else "",
                    last_write_ms=int(parts[3] or "0") if len(parts) > 3 else 0,
                    broken=(parts[4] if len(parts) > 4 else "0").strip() == "1",
                    completed=(parts[5] if len(parts) > 5 else "0").strip() == "1",
                    is_bot=(parts[6] if len(parts) > 6 else "0").strip() == "1",
                    player_count=int(parts[7] or "0") if len(parts) > 7 else 0,
                    bot_count=int(parts[8] or "0") if len(parts) > 8 else 0,
                    has_fix_response=(parts[9] if len(parts) > 9 else "0").strip() == "1",
                    # parts[10] is overloaded for back-compat: the post-2026-06-03
                    # server emits the per-game build name (a string like "library")
                    # there, while a hypothetical pre-change server would have put
                    # startMs (a number). Sniff: if numeric, treat as startMs; else
                    # treat as a build hint we can use to skip the log[0] inference.
                    # (Patch contributed by BB Claude 2026-06-03 22:18 after the
                    # original code's int(parts[10] or "0") raised ValueError on
                    # every row of the new schema and silently skipped all games.)
                    start_ms=int(parts[10]) if len(parts) > 10 and (parts[10] or "").strip().lstrip("-").isdigit() else 0,
                    build_hint=((parts[10] or "").strip().lower() if len(parts) > 10 and not (parts[10] or "").strip().lstrip("-").isdigit() else ""),
                )
            )
        except (ValueError, IndexError):
            continue
    return games


def is_errored_heuristic(g, log_text=""):
    """Mirror admin.html isErrored(): flagged broken, or log shows a stack trace."""
    if g["broken"]:
        return True
    # Simple log-based heuristic; admin.html has a richer one, but for filtering
    # candidates here the basic check is enough.
    return "Exception" in log_text or "at scala." in log_text or "ERROR" in log_text


def infer_build(log_text):
    """Read log[0] (first log line / version header) and return the build name.

    Returns:
      'library' | 'mnu' | 'tt' | 'bb' on clean match
      'ambiguous' if log[0] is missing, malformed, or matches multiple markers
        (skip these in the caller rather than guess)
    """
    if not log_text:
        return "ambiguous"
    # The first row of the TSV log is the version header. Take the first
    # newline-delimited line and look for our markers.
    first = log_text.split("\n", 1)[0] if "\n" in log_text else log_text
    first_lower = first.lower()
    matches = [build for marker, build in VERSION_HEADER_MARKERS.items() if marker in first_lower]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return "ambiguous"
    # No marker hit — could be a brand-new build we don't know, or a corrupted
    # log. Skip rather than guess.
    return "ambiguous"


def main():
    token = load_token()
    games_text = _get(f"/admin/{token}/games")
    games = parse_games_tsv(games_text)

    candidates = []
    skipped_tt_bb = 0
    skipped_has_fix = 0
    skipped_completed = 0

    for g in games:
        if g["is_bot"]:
            continue
        if g["completed"] and not g["broken"]:
            skipped_completed += 1
            continue
        if g["has_fix_response"]:
            # already analyzed; skip unless the user clicks Discuss/Dismiss to
            # clear it. Phase B will add per-game force-reanalyze.
            skipped_has_fix += 1
            continue

        # Fetch log to do the errored check + build inference. Light cost since
        # most games aren't broken.
        try:
            log = _get(f"/admin/{token}/log/{g['id']}")
        except Exception as e:
            # If log fetch fails, surface as a candidate with the error so the
            # ticker knows about it.
            log = f"(log fetch failed: {e})"

        # Not errored AND not broken? skip.
        if not is_errored_heuristic(g, log):
            continue

        # Prefer the server's build column when present (set by the server's
        # log[0] inference at TSV emit time — see /admin/$TOK/games handler);
        # fall back to local log[0] parsing when not (legacy or non-matching).
        hint = g.get("build_hint", "")
        if hint in {"library", "mnu", "tt", "bb"}:
            build = hint
        else:
            build = infer_build(log)
        if build not in ALLOWED_BUILDS and build != "ambiguous":
            skipped_tt_bb += 1
            continue
        if build == "ambiguous":
            # Defensive: log[0] missing/malformed/multi-match. Skip rather than
            # guess. Surface separately so ticker can flag for manual review.
            candidates.append(
                dict(
                    game_id=g["id"],
                    game_name=g["name"],
                    build="ambiguous",
                    broken=g["broken"],
                    completed=g["completed"],
                    player_count=g["player_count"],
                    bot_count=g["bot_count"],
                    last_write_ms=g["last_write_ms"],
                    log_url=f"{SERVER}/admin/{token}/log/{g['id']}",
                    admin_url=f"{SERVER}/admin.html#game={g['id']}",
                    log_snippet=log[:500],  # first 500 chars so we can eyeball log[0]
                    needs_manual_review=True,
                )
            )
            continue

        candidates.append(
            dict(
                game_id=g["id"],
                game_name=g["name"],
                build=build,
                broken=g["broken"],
                completed=g["completed"],
                player_count=g["player_count"],
                bot_count=g["bot_count"],
                last_write_ms=g["last_write_ms"],
                log_url=f"{SERVER}/admin/{token}/log/{g['id']}",
                admin_url=f"{SERVER}/admin.html#game={g['id']}",
                log_snippet=log[-2000:] if len(log) > 2000 else log,  # last 2KB
            )
        )

    print(json.dumps(
        dict(
            total_games=len(games),
            allowed_builds=sorted(ALLOWED_BUILDS),
            skipped_other_builds=skipped_tt_bb,
            skipped_has_fix=skipped_has_fix,
            skipped_completed=skipped_completed,
            candidates=candidates,
        ),
        indent=2,
    ))


if __name__ == "__main__":
    main()
