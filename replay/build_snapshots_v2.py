"""
Snapshot builder using FullGameState + event handlers.
Drop-in replacement for the legacy build_snapshots() in build-replay.py.

Iterates HTML log lines, runs each through process_line() to mutate game state,
then captures to_snapshot() after every line. Also collects AP boundaries
(from Turn markers), bot decision weights, and unmatched event diagnostics.
"""
import re
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from game_state import FullGameState
from event_handlers import process_line, strip_html, FACTION_NAMES

# Handler names that are matched-by-design but never change game state.
# Excluded from the matched-noop audit so they don't bury the real ones
# (lines that describe a unit/map mutation but didn't apply it).
NOOP_BY_DESIGN = {
    # Pure structural / phase markers
    "debug_line", "separator", "turn_marker", "options_line", "version_line",
    "phase_marker", "doom_phase_marker", "power_gather", "comment", "play_order",
    "display_separator",
    # Placement messages (state recorded elsewhere)
    "started_in",
    # Library informational
    "library_gate_blocked", "barrier_battle_blocked", "agony_action",
    "hastur_heard",  # YS Hastur SBR trigger announcement; awaken state changes elsewhere
    "chose_first_player",  # paired with became_first_player which mutates state.first_player
    "anytime_sb",  # SBR achievement, fulfilled-list update may not be in fingerprint
    # v4 specific-but-informational handlers
    "sl_sleeping", "battle_negotiation", "vengeance_assignment", "ip_cancelled",
    "eliminated_cultists_announce", "tome_larvae_used",
    "shambler_deploy", "abhoth_placed_filth", "version_banner",
    "defended_with",  # battle announcement; kills/pains follow as separate lines
    "rerolled",  # writhe reroll announcement
    "changed_gate_control",  # gate stays with same faction owner; on-gate unit not modeled
    "tome_larvae_used", "library_unit_action", "library_unit_activate",
    "battle_start",  # battle context announcement; state changes happen via subsequent kill/pain/etc
    "writhe_start",  # Writhe dice-roll announcement; relocations follow as separate writhe_relocate lines
    "failed_desecration", "dread_curse_roll",  # roll outcomes, informational
    "writhe_replace",  # mutates state by definition (replace Acolyte→Desiccated); included for safety
    "library_unit_stays",  # Custodian/Librarian "stays in X" — deliberate no-op
    "winner",  # game-end announcement
    "agony_die_roll", "sim_debug_marker",  # roll outcome + sim-side instrumentation
    # v5 (2026-05-13) — pre-final-outcome negotiations & informational announcements
    "negotiation_display",       # "Other factions were to lose X Power", etc.
    "strength_increased",        # "X strength increased to [N]" — display only
    "allowed_summon",            # AN SB "allowed enemy factions to summon their lowest cost..."
    "emissary_survived",         # "Nyarlathotep survived the kill as an Emissary..."
    "ds_azathoth_announce",      # DS Azathoth auction demand announcement
    "ds_azathoth_die_redisplay", # "Avatar Synthesis Azathoth die [N] - strength [N]"
    "ds_power_doom_offer_announce", # DS PowerDoomOffer header
    "ds_fiendish_growth",        # Fiendish Growth header — placed_unit follows
    "ds_consummation",           # "DS used Consummation to unflip Undirected Energy"
    "azathoth_offer",            # "X offered N Power and M Doom to Azathoth" (pre-outcome)
    "wwhibernated",              # WW hibernation announcement
    "writhe_relocate",           # same-src/dst writhe pain (intentional stay-in-place)
    "got_doom",                  # "got 0 Doom" — informational when N==0
    "forfeited_power",           # "passed and forfeited N Power" — N==0 cases when power already at 0
    "became_first_player",       # same faction already tracked as first_player
    "death_march",               # "Death's Head is now N" — same value when already at N
    # Battle / roll announcements — state changes happen in follow-up
    # "X was killed" / "X was eliminated" lines, not in the roll announcement.
    "roll_result", "battle_pain_announce", "attacked_with", "necrophagy",
    "ran_out",  # "<faction> ran out of power" — declarative, no mutation
    "achieved_req",  # SBR achievement announcement — fulfilled-list update may not be in fingerprint
    "ritual_track",  # display of the ritual cost track
    "released",  # captive-cultist release — handled via state.regions update elsewhere if needed
    # [2026-05-24] MNU announcement-style handlers — these tag the line as
    # "an MNU ability fired" but the actual state mutation happens via OTHER
    # lines (placement, removal, etc.) that have their own handlers. Adding
    # to NOOP_BY_DESIGN so they don't surface as "issues".
    "mnu_frenzy",  # "Frenzy: summoned X for free" — actual placement on separate line
    "mnu_riding_the_shantak",  # "carried <cultist>" — the carry IS the move (handled below)
    "mnu_sapping",  # "drained N power/doom" — power change happens via separate logs
    "mnu_vicious",  # "added N Kills" — affects roll, not unit map
    "mnu_grottos",  # Doom phase passive — doom gain handled via "got N Doom" line
    "abhoth_filth_blocked_doom",  # "doom from gate in X blocked by Filth" — engine already excluded that gate from "got N doom"
    "mnu_possession",  # capture announcement (actual capture is separate)
    "mnu_velvet_fan",  # capture announcement
    "mnu_mummify",  # mummify announcement; cultists stay in area
    "mnu_execration_of_mu",  # SB acquisition announcement
    "mnu_prime_cause",  # split into multiple lines; map mutation handled by "removed"/"replaced with" sub-lines
    "mnu_dust_to_dust",  # "permanently removed" — kill handled by battle kill line
    "mnu_planetary_destruction",  # ES/doom award; resource change via separate lines
    "mnu_hebephrenia",  # "gate abandoned" — handled by lost_gate elsewhere
    "mnu_angles_of_time",  # "HoT eliminated" — kill via battle kill line
    "mnu_cronophage",  # teleport announcement; actual move via separate movement line
    "mnu_familiar",  # respawn announcement; place via separate placement line
    "mnu_loathsome_titter",  # power gain announcement; "got N Power" line carries
    "mnu_moonbeast",  # SB block announcement; map state unchanged
    "mnu_mind_parasite",  # affliction/release announcement; unit owner change is conceptual
    "mnu_fecund",  # placement happens via "placed Acolyte in <area>" sub-line
    "mnu_servitor",  # assign + block announcements
    "mnu_elder_thing_mind_control",  # "blocked by Elder Thing" — ability negation, no map change
    "mnu_place_spinneret",  # web token track, not unit map
    "mnu_bloodthirst",  # battle Pain→Kill conversion — affects rolls, not map
    "mnu_cosmic_web",  # web token / game end — handled separately
    "mnu_tomb_herd",  # power gain — "got N Power" carries
    "mnu_green_decay",  # ES instead of power — resource change via separate lines
    "mnu_disaster_looms",  # ES per gate — resource change
    "mnu_innsmouth_look",  # remove acolyte announce; actual removal via separate line
    "mnu_zygote",  # placement on separate sub-lines
    "mnu_tsunami",  # force-move announce; actual moves via separate movement lines
    "mnu_agony_sting",  # force-move announce; same
    "mnu_daemon_sultan",  # combat scaling / glyph track
    "mnu_nuclear_chaos",  # power/ES dist via separate lines
    "mnu_snakebite",  # extra Kill assignment; kill via separate kill line
    "mnu_messenger_of_yig",  # power donate announce
    "mnu_firestorm",  # ES gain on enemy GOO kill — separate
    "mnu_cthugha",  # announcement (replaced GOO handled in dedicated branch)
    "mnu_bokrug",  # Bokrug events — separate placement / elimination lines
    "mnu_shadow_pharaoh",  # acquisition special — separate
    "mnu_igoo_awakened",  # awaken line; unit placement on separate sub-line
    "mnu_sb_acquired",  # "gained X for Y" — SB upgrade tracked elsewhere
    "ip_discount",  # FB Infernal Pact discount — power model handles this elsewhere
}


def build_snapshots_v2(html_lines):
    """Parse HTML log lines using the comprehensive game state.
    Returns (snapshots, display_lines, ap_indices, audit_summary).

    audit_summary is a dict with keys:
      unmatched: {text_prefix -> count} for lines no handler claimed
      matched_noop: {handler_name -> [example_text, ...]} for lines that
        matched a handler but left state.summary_fingerprint() unchanged —
        these are the most useful diagnostic for "the log said X happened
        but the visual doesn't reflect it" bugs.
    """
    state = FullGameState()
    snapshots = []
    display_lines = []
    ap_indices = []
    unmatched_lines = []
    matched_noop_lines = []

    for i, raw_line in enumerate(html_lines):
        plain = strip_html(raw_line)

        # Process through event handler system
        event = process_line(state, raw_line, i)

        # Skip debug/separator lines from display
        if event.handler_name in ("debug_line", "separator"):
            # Collect weights for display
            if event.handler_name == "debug_line":
                pass  # already added to _pending_weights in process_line
            continue

        # Detect AP boundaries — "Turn N" marks the start of each AP
        if event.handler_name == "turn_marker":
            ap_indices.append(len(display_lines))

        # Track unmatched events
        if not event.matched:
            unmatched_lines.append(event)
        # Track matched-but-no-state-change events: a handler claimed the line
        # but state.summary_fingerprint() didn't change. Usually a missing or
        # incomplete handler (e.g., a unit-relocation log line whose handler
        # doesn't actually update unit positions).
        elif (not event.state_changed and
              event.handler_name not in NOOP_BY_DESIGN):
            matched_noop_lines.append(event)

        # Determine faction class for log coloring
        line_faction = None
        for fc in FACTION_NAMES.values():
            if f"class='{fc.lower()}" in raw_line or f'class="{fc.lower()}' in raw_line:
                line_faction = fc.lower()
                break

        # Parse pending weights — BOT/OPT/WHY lines accumulated since last display line.
        # Attach them to this display line so the JS weights panel can show them.
        weights_data = None
        if state._pending_weights:
            chosen = None; options = []; reasons = []
            for w in state._pending_weights:
                m = re.match(r"\[BOT FB @\d+\]\s+(.+?)\s+\((-?\d+)\)", w)
                if m: chosen = {"action": m.group(1).strip(), "score": int(m.group(2))}
                m = re.match(r"\[OPT [^\]]+\]\s+(.+?)\s+=\s+(-?\d+)", w)
                if m: options.append({"action": m.group(1).strip(), "score": int(m.group(2))})
                m = re.match(r"\[WHY\]\s+(-?\d+)\s+=\s+(.+)", w)
                if m: reasons.append({"score": int(m.group(1)), "reason": m.group(2).strip()})
            if chosen or options:
                options.sort(key=lambda x: -x["score"])
                weights_data = {"chosen": chosen, "options": options[:5], "reasons": reasons[:3]}
            state._pending_weights = []

        display_lines.append({
            "text": plain,
            "html": raw_line,
            "faction": line_faction,
            "weights": weights_data
        })
        snapshots.append(state.to_snapshot())

    # Summarize unmatched events
    unmatched_summary = {}
    for evt in unmatched_lines:
        key = evt.plain_text[:40] if evt.plain_text else "(empty)"
        unmatched_summary[key] = unmatched_summary.get(key, 0) + 1

    # Summarize matched-noop events grouped by handler name with example texts
    matched_noop_summary = {}
    for evt in matched_noop_lines:
        h = evt.handler_name or "(no handler)"
        d = matched_noop_summary.setdefault(h, {"count": 0, "examples": []})
        d["count"] += 1
        if len(d["examples"]) < 3:
            d["examples"].append(evt.plain_text[:90])

    # Flat per-line issues list for the in-viewer Issues overlay. One entry
    # per problematic line, in trace order, with kind + handler + plain text.
    issues = []
    for evt in unmatched_lines:
        issues.append({
            "line_index": evt.line_index,
            "kind": "unmatched",
            "handler": None,
            "text": evt.plain_text or "",
        })
    for evt in matched_noop_lines:
        issues.append({
            "line_index": evt.line_index,
            "kind": "matched_noop",
            "handler": evt.handler_name,
            "text": evt.plain_text or "",
        })
    issues.sort(key=lambda e: e["line_index"])

    audit_summary = {
        "unmatched": unmatched_summary,
        "matched_noop": matched_noop_summary,
        "issues": issues,
        "map_id": state.map_id,
    }

    return snapshots, display_lines, ap_indices, audit_summary


if __name__ == "__main__":
    # Quick test: process the latest trace file
    import os
    wl = "/Users/gremus/cthulhu-wars FB/sim/win-logs"
    files = sorted([os.path.join(wl, f) for f in os.listdir(wl) if f.startswith("fb-game-")],
                   key=os.path.getmtime, reverse=True)[:1]
    if not files:
        print("No trace files found")
        sys.exit(1)

    fpath = files[0]
    with open(fpath) as f:
        content = f.read()
    parts = content.split("\n\n", 1)
    if len(parts) < 2:
        print("No HTML section found")
        sys.exit(1)

    html_lines = [l.strip() for l in parts[1].splitlines() if l.strip()]
    print(f"Processing {len(html_lines)} HTML lines from {os.path.basename(fpath)}...")

    snaps, display, ap_idx, unmatched = build_snapshots_v2(html_lines)
    print(f"  {len(snaps)} snapshots, {len(ap_idx)} AP boundaries")
    print(f"  {len(unmatched)} unmatched event types")
    if unmatched:
        print(f"  Top unmatched:")
        for text, count in sorted(unmatched.items(), key=lambda x: -x[1])[:15]:
            print(f"    {count:3d}x {text}")

    # Verify final state
    last = snaps[-1] if snaps else {}
    for fc, fdata in last.get("factions", {}).items():
        print(f"  {fc}: doom={fdata.get('doom',0)} power={fdata.get('power',0)} gates={len(fdata.get('gates',[]))}")
