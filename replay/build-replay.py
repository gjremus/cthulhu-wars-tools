#!/usr/bin/env python3
"""Build a self-contained HTML game log viewer from a CW game trace file.

Usage: python3 build-replay.py <trace-file.txt> <output.html> [title]
"""

import sys, re, os, base64, json, html
from collections import defaultdict

# ── CLI ────────────────────────────────────────────────────────────────
if len(sys.argv) < 3:
    print("Usage: python3 build-replay.py <trace-file.txt> <output.html> [title]")
    sys.exit(1)

trace_path = sys.argv[1]
output_path = sys.argv[2]
title = sys.argv[3] if len(sys.argv) > 3 else os.path.basename(trace_path)

IMAGE_DIR_FB = os.path.expanduser("~/cthulhu-wars FB/solo/webp/images")
IMAGE_DIR_LIBRARY = os.path.expanduser("~/cthulhu-wars Library at Celaeno/solo/webp/images")
IMAGE_DIR_MNU = os.path.expanduser("~/cthulhu-wars More Neutral Units/solo/webp/images")
IMAGE_DIR = IMAGE_DIR_FB  # default, updated by detect_map_id

# ── Constants ──────────────────────────────────────────────────────────
FACTION_NAMES = {
    "Firstborn": "FB", "Black Goat": "BG", "Yellow Sign": "YS", "Sleeper": "SL",
    "Windwalker": "WW", "Opener of the Way": "OW", "The Ancients": "AN",
    "Crawling Chaos": "CC", "Great Cthulhu": "GC", "Tombstalker": "TS",
    "Daemon Sultan": "DS",
}
FACTION_FULL = {v: k for k, v in FACTION_NAMES.items()}

REGION_COORDS_EARTH = {
    "ArcticOcean": (933, 77), "Scandinavia": (1135, 165), "Europe": (1110, 255),
    "NorthAsia": (1595, 150), "SouthAsia": (1620, 360), "Arabia": (1455, 460),
    "EastAfrica": (1235, 665), "WestAfrica": (1115, 525),
    "NorthAtlantic": (690, 390), "SouthAtlantic": (855, 665),
    "Antarctica": (970, 815), "SouthPacific": (540, 830),
    "SouthAmerica": (590, 680), "NorthAmerica": (380, 290),
    "NorthPacific": (105, 355), "IndianOcean": (1610, 730), "Australia": (215, 707),
}

# Library at Celaeno — horizontal layout coordinates (Lower LEFT, Upper RIGHT)
# Viewer uses MAP_W=1791 scale, but Library horizontal images are 3582px wide.
# Coordinates are stored at native scale; build-replay scales them to match MAP_W.
_REGION_COORDS_LIBRARY_NATIVE = {
    # Upper floor → x+1791, y unchanged
    "FloatingTower": (2597, 480), "Byakhiary": (2240, 311), "Horrorium": (3423, 312),
    "Fountain": (2599, 746), "YrandtheNhhngr": (2171, 700), "GuardianundertheLake": (3391, 700),
    "Gloomloft": (2645, 1100), "CursedHall": (2591, 1360),
    "BarrierofNaach-Tith": (1949, 1260), "LarvaeoftheOuterGods": (3232, 1430),
    "LakeofHaliOverlook": (2509, 1622), "LakeofHaliBalcony": (2909, 1566),
    # Lower floor → x unchanged, y-1792
    "ChamberofSn'gac": (388, 295), "Oubliette": (907, 421), "BlueHall": (1464, 364),
    "ScorchedChamber": (422, 902), "PorphyrHall": (907, 894), "RedHall": (1578, 588),
    "BlackHall": (1278, 741), "ChamberofApkallu": (387, 1446),
    "Hyperquarium": (904, 1364), "CharnelHall": (1321, 1340), "TheCrawlingOnes": (1559, 1422),
}
# Use native scale — MAP_W/MAP_H in the viewer are set to match (3582x1793)
REGION_COORDS_LIBRARY = _REGION_COORDS_LIBRARY_NATIVE

REGION_COORDS = REGION_COORDS_EARTH

# Map display names for regions (space-separated)
REGION_DISPLAY = {}
for r in REGION_COORDS_EARTH:
    REGION_DISPLAY[r] = re.sub(r'([a-z])([A-Z])', r'\1 \2', r)

# Library region display names (ID → display)
LIBRARY_REGION_DISPLAY = {
    "FloatingTower": "Floating Tower", "Byakhiary": "Byakhiary", "Horrorium": "Horrorium",
    "Fountain": "Fountain", "YrandtheNhhngr": "Yr and the Nhhngr",
    "GuardianundertheLake": "Guardian under the Lake", "Gloomloft": "Gloomloft",
    "CursedHall": "Cursed Hall", "BarrierofNaach-Tith": "Barrier of Naach-Tith",
    "LarvaeoftheOuterGods": "Larvae of the Outer Gods",
    "LakeofHaliOverlook": "Lake of Hali Overlook", "LakeofHaliBalcony": "Lake of Hali Balcony",
    "ChamberofSn'gac": "Chamber of Sn'gac", "Oubliette": "Oubliette", "BlueHall": "Blue Hall",
    "ScorchedChamber": "Scorched Chamber", "PorphyrHall": "Porphyr Hall", "RedHall": "Red Hall",
    "BlackHall": "Black Hall", "ChamberofApkallu": "Chamber of Apkallu",
    "Hyperquarium": "Hyperquarium", "CharnelHall": "Charnel Hall", "TheCrawlingOnes": "The Crawling Ones",
}
REGION_DISPLAY.update(LIBRARY_REGION_DISPLAY)

# Reverse: "North America" -> "NorthAmerica", etc.
REGION_FROM_DISPLAY = {v: k for k, v in REGION_DISPLAY.items()}

# Unit type to image file mapping
UNIT_IMAGE_MAP = {
    # per faction: unit display name -> image filename (without .webp)
    "FB": {"Acolyte": "fb-acolyte", "High Priest": "fb-high-priest", "Desiccated": "fb-desiccated",
           "Revenant": "fb-revenant", "Revenant of K'Naa": "fb-revenant", "Ghatanothoa": "fb-ghatanothoa",
           "Crater": "fb-crater"},
    "GC": {"Acolyte": "gc-acolyte", "High Priest": "gc-high-priest", "Deep One": "gc-deep-one",
           "Shoggoth": "gc-shoggoth", "Starspawn": "gc-starspawn", "Cthulhu": "gc-cthulhu"},
    "SL": {"Acolyte": "sl-acolyte", "High Priest": "sl-high-priest", "Wizard": "sl-wizard",
           "Serpent Man": "sl-serpent-man", "Formless Spawn": "sl-formless-spawn", "Tsathoggua": "sl-tsathoggua"},
    "WW": {"Acolyte": "ww-acolyte", "High Priest": "ww-high-priest", "Wendigo": "ww-wendigo",
           "Gnoph-Keh": "ww-gnoph-keh", "Rhan-Tegoth": "ww-rhan-tegoth", "Rhan Tegoth": "ww-rhan-tegoth",
           "Ithaqua": "ww-ithaqua", "Ice Age": "ww-ice-age"},
    "CC": {"Acolyte": "cc-acolyte", "High Priest": "cc-high-priest", "Nightgaunt": "cc-nightgaunt",
           "Flying Polyp": "cc-flying-polyp", "Hunting Horror": "cc-hunting-horror", "Nyarlathotep": "cc-nyarly"},
    "BG": {"Acolyte": "bg-acolyte", "High Priest": "bg-high-priest", "Ghoul": "bg-ghoul",
           "Fungi": "bg-fungi", "Fungi from Yuggoth": "bg-fungi", "Dark Young": "bg-dark-young",
           "Shub-Niggurath": "bg-shub"},
    "YS": {"Acolyte": "ys-acolyte", "High Priest": "ys-high-priest", "Undead": "ys-undead",
           "Byakhee": "ys-byakhee", "King in Yellow": "ys-king-in-yellow", "Hastur": "ys-hastur"},
    "OW": {"Acolyte": "ow-acolyte", "High Priest": "ow-high-priest", "Mutant": "ow-mutant",
           "Abomination": "ow-abomination", "Spawn of Yog-Sothoth": "ow-spawn-of-yog-sothoth", "Yog-Sothoth": "ow-yog-sothoth"},
    "AN": {"Acolyte": "an-acolyte", "High Priest": "an-high-priest", "Reanimated": "an-reanimated",
           "Un-Man": "an-un-man", "Yothan": "an-yothan", "Cathedral": "an-cathedral"},
    "TS": {"Acolyte": "ts-acolyte", "Tendril": "ts-tendril", "Deep Tendril": "ts-tendril",
           "Tomb Herd": "ts-tomb-herd", "Tomb-Herd": "ts-tomb-herd",
           "Glaaki": "ts-glaaki", "Gla'aki": "ts-glaaki"},
    "DS": {"Acolyte": "ds-acolyte", "High Priest": "ds-high-priest",
           "Avatar Thesis": "ds-avatar-thesis", "Avatar Antithesis": "ds-avatar-antithesis",
           "Avatar Synthesis": "ds-avatar-synthesis",
           "Larva Thesis": "ds-larva-thesis", "Larva Antithesis": "ds-larva-antithesis",
           "Larva Synthesis": "ds-larva-synthesis",
           "Chaos Gate": "ds-chaos-gate"},
    # [2026-05-24] Neutral units (base + MNU). When a faction owns a neutral
    # LC unit (Ghast, Moonbeast, Cthugha awakening, etc.) the engine logs
    # the styled unit name as-is — the replay engine looks up by name first
    # in the faction map, then falls through to "neutral".
    "neutral": {
        # Base neutrals
        "Ghast": "n-ghast", "Gug": "n-gug", "Shantak": "n-shantak",
        "Star Vampire": "n-star-vampire", "Voonith": "n-voonith",
        "Dimensional Shambler": "n-dimensional-shambler",
        "Dimensional Shambler (Hold)": "n-dimensional-shambler",
        "Gnorri": "n-gnorri", "Filth": "n-filth",
        # MNU monsters
        "Moonbeast": "n-moonbeast",
        "Giant Blind Albino Penguins": "n-giant-blind-albino-penguins",
        "Albino Penguins": "n-giant-blind-albino-penguins",
        "Elder Thing": "n-elder-thing",
        "Leng Spider": "n-leng-spider",
        "Satyr": "n-satyr",
        "Insects from Shaggai": "n-insects-from-shaggai",
        "Parasitized Acolyte": "n-insects-from-shaggai",
        "Servitor of the Outer Gods": "n-servitor-of-the-outer-gods",
        # MNU terrors
        "Dhole": "n-dhole",
        "Great Race of Yith": "n-great-race-of-yith",
        "Quachil Uttaus": "n-quachil-uttaus",
        "The Shadow Pharaoh": "n-the-shadow-pharaoh",
        "Hound of Tindalos": "n-hound-of-tindalos",
        "Brown Jenkin": "n-brown-jenkin",
        "Elder Shoggoth": "n-elder-shoggoth",
        # Base IGOOs
        "Byatis": "n-byatis", "Abhoth": "n-abhoth", "Daoloth": "n-daoloth",
        "Nyogtha": "n-nyogtha", "Tulzscha": "n-tulzscha",
        "Y'Golonac": "n-ygolonac", "Ygolonac": "n-ygolonac",
        # MNU IGOOs
        "Azathoth": "n-azathoth", "Cthugha": "n-cthugha",
        "Mother Hydra": "n-mother-hydra", "Yig": "n-yig",
        "Father Dagon": "n-father-dagon",
        # Note: Ghatanothoa as IGOO uses neutral image; FB's owned Ghatanothoa
        # uses fb-ghatanothoa. The lookup tries FB first when faction is FB.
        "The Bloated Woman": "n-the-bloated-woman",
        "Bloated Woman": "n-the-bloated-woman",
        "Atlach-Nacha": "n-atlach-nacha",
        "Bokrug": "n-bokrug",
        "Gla'aki (IGOO)": "n-glaaki-igoo",
    },
}

GOO_TYPES = {
    "Shub-Niggurath", "King in Yellow", "Hastur", "Nyarlathotep", "Cthulhu",
    "Tsathoggua", "Rhan-Tegoth", "Rhan Tegoth", "Ithaqua", "Yog-Sothoth", "Ghatanothoa", "Glaaki", "Gla'aki",
    "Avatar Thesis", "Avatar Antithesis", "Avatar Synthesis",
    # Base IGOOs
    "Byatis", "Abhoth", "Daoloth", "Nyogtha", "Tulzscha", "Y'Golonac", "Ygolonac",
    # MNU IGOOs
    "Azathoth", "Cthugha", "Mother Hydra", "Yig", "Father Dagon",
    "The Bloated Woman", "Bloated Woman", "Atlach-Nacha", "Bokrug", "Gla'aki (IGOO)",
}
CULTIST_TYPES = {"Acolyte", "High Priest"}


def strip_html(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&gt;", ">").replace("&lt;", "<").replace("&nbsp;", " ").replace("&amp;", "&")
    return s.strip()


def region_key(display_name):
    """Convert 'North America' -> 'NorthAmerica'"""
    k = REGION_FROM_DISPLAY.get(display_name)
    if k:
        return k
    # Try removing spaces
    k = display_name.replace(" ", "")
    if k in REGION_COORDS:
        return k
    return display_name


def faction_prefix(line):
    for full, short in FACTION_NAMES.items():
        if line.startswith(full):
            return short, full, line[len(full):].strip()
    return None, None, line


# ── Image embedding ───────────────────────────────────────────────────
_image_cache = {}

def embed_image(filename):
    """Read image file and return base64 data URI. Cached to avoid re-reading.
    v5.2 (2026-05-13): falls back to IMAGE_DIR_LIBRARY (the newer asset set)
    when the file isn't in IMAGE_DIR — the old FB folder doesn't have DS unit
    images, Library at Celaeno's image dir does, and both share filename
    conventions for the common assets."""
    if filename in _image_cache:
        return _image_cache[filename]
    for base in (IMAGE_DIR, IMAGE_DIR_LIBRARY, IMAGE_DIR_MNU):
        path = os.path.join(base, filename)
        if os.path.exists(path):
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode("ascii")
            uri = f"data:image/webp;base64,{data}"
            _image_cache[filename] = uri
            return uri
    _image_cache[filename] = ""
    return ""


def _rtf_escape(s):
    """Escape a string for inclusion in RTF body text."""
    s = s.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    out = []
    for ch in s:
        if ord(ch) > 127:
            out.append(f"\\u{ord(ch)}?")
        else:
            out.append(ch)
    return "".join(out)


def _write_audit_rtf(path, audit, title):
    """Write a human-readable RTF report of the replay-engine audit.

    Two sections:
      (1) Unmatched events: log lines no handler claimed at all.
      (2) Matched-but-no-state-change events: a handler claimed the line but
          state.summary_fingerprint() did not change. These usually indicate
          a missing or incomplete handler (e.g., describes a unit move but
          doesn't update unit positions in state).
    """
    unmatched = audit.get("unmatched", {})
    matched_noop = audit.get("matched_noop", {})
    map_id = audit.get("map_id") or "(unknown)"
    out = []
    out.append(r"{\rtf1\ansi\deff0{\fonttbl{\f0 Helvetica;}{\f1 Courier;}}")
    out.append(r"\fs28\b Replay Engine Audit\b0\par\par")
    out.append(rf"\fs20\b Source:\b0 {_rtf_escape(title)}\par")
    out.append(rf"\b Map (from Options line):\b0 {_rtf_escape(map_id)}\par\par")

    out.append(r"\fs24\b 1. Unmatched events (no handler claimed the line)\b0\par\fs18")
    if unmatched:
        total = sum(unmatched.values())
        out.append(rf"Total: \b {total}\b0 distinct kinds: {len(unmatched)}\par\par")
        for text, count in sorted(unmatched.items(), key=lambda x: -x[1]):
            out.append(rf"\b {count}x\b0  {_rtf_escape(text)}\par")
    else:
        out.append(r"None.\par")
    out.append(r"\par")

    out.append(r"\fs24\b 2. Matched but no state change\b0\par\fs18")
    out.append(r"A handler claimed each line but the state fingerprint didn't change. "
               r"Most likely a missing or incomplete handler. Investigate top entries by count.\par\par")
    if matched_noop:
        total = sum(d["count"] for d in matched_noop.values())
        out.append(rf"Total: \b {total}\b0 across {len(matched_noop)} handlers.\par\par")
        for handler, d in sorted(matched_noop.items(), key=lambda kv: -kv[1]["count"]):
            out.append(rf"\b {d['count']:3d}x  [{_rtf_escape(handler)}]\b0\par")
            for ex in d["examples"]:
                out.append(rf"   e.g. {_rtf_escape(ex)}\par")
            out.append(r"\par")
    else:
        out.append(r"None.\par")

    out.append(r"}")
    with open(path, "w") as f:
        f.write("".join(out))


def detect_map_id(factions_in_game, html_lines=None, action_strings=None):
    """Determine map ID from the Options log line in the game trace.
    The game logs 'MapLibrary35', 'MapEarth35', etc. in the Options line."""
    global IMAGE_DIR, REGION_COORDS
    # Map option string → (image file prefix, is_library)
    MAP_OPTIONS = {
        "MapLibrary33": ("library3", True), "MapLibrary35": ("library35", True),
        "MapLibrary53": ("library53", True), "MapLibrary55": ("library5", True),
        "MapEarth33": ("earth33", False), "MapEarth35": ("earth35", False),
        "MapEarth53": ("earth53", False), "MapEarth55": ("earth55", False),
    }
    if html_lines:
        for line in html_lines[:20]:
            for opt, (img_id, is_lib) in MAP_OPTIONS.items():
                if opt in line:
                    if is_lib:
                        IMAGE_DIR = IMAGE_DIR_LIBRARY
                        REGION_COORDS = REGION_COORDS_LIBRARY
                    return img_id
    # Fallback: check action strings for Library region names
    library_regions = {"FloatingTower", "Horrorium", "Gloomloft", "Fountain", "Oubliette",
                       "YrandtheNhhngr", "GuardianundertheLake", "LarvaeoftheOuterGods",
                       "LakeofHaliOverlook", "ChamberofApkallu", "TheCrawlingOnes", "Byakhiary"}
    if action_strings:
        all_actions = " ".join(action_strings[:50])
        if any(lr in all_actions for lr in library_regions):
            IMAGE_DIR = IMAGE_DIR_LIBRARY
            REGION_COORDS = REGION_COORDS_LIBRARY
            n = len(factions_in_game)
            has_5u = "Byakhiary" in all_actions or "Horrorium" in all_actions
            if n <= 3: return "library3"
            elif n == 5: return "library5"
            elif has_5u: return "library53"
            else: return "library35"
    # Fallback: player count (Earth assumed)
    n = len(factions_in_game)
    if n <= 3: return "earth33"
    elif n == 5: return "earth55"
    else: return "earth35"

_map_id = "earth35"

def collect_needed_images(factions_in_game, html_lines=None, action_strings=None):
    """Collect all images needed for the replay: map, placement bitmap, gate,
    ritual track, and per-faction backgrounds, glyphs, and unit images.
    Returns dict of image_key -> base64 data URI."""
    global _map_id
    _map_id = detect_map_id(factions_in_game, html_lines, action_strings)
    images = {}
    # Map background
    if _map_id.startswith("library"):
        images["map"] = embed_image(f"{_map_id}-h-dark.webp")
        images["place"] = embed_image(f"{_map_id}-h-place.webp")
    else:
        images["map"] = embed_image(f"{_map_id}-dark.webp")
        images["place"] = embed_image(f"{_map_id}-place.webp")
    # Gate
    images["gate"] = embed_image("gate.webp")
    # Ritual tracker
    rt_file = "ritual_track_4p.jpg"
    if _map_id == "earth33":
        rt_file = "ritual_track_3p.jpg"
    elif _map_id == "earth55":
        rt_file = "ritual_track_5p.jpg"
    images["ritual_track"] = embed_image(rt_file) or embed_image("ritual_track_4p.jpg")
    # Library at Celaeno: tome and token images
    if _map_id.startswith("library"):
        for tome_img in ["tome-barrier", "tome-guardian", "tome-larvae", "tome-yr", "library-tome-card"]:
            images[tome_img] = embed_image(f"{tome_img}.webp")
        # Silence token is in icons/ subfolder
        sil_path = os.path.join(os.path.dirname(IMAGE_DIR), "icons", "silence-token.png")
        if os.path.exists(sil_path):
            with open(sil_path, "rb") as f:
                images["silence-token"] = f"data:image/png;base64,{base64.b64encode(f.read()).decode('ascii')}"
        # Custodian/Librarian icons
        for unit_icon in ["custodian", "librarian"]:
            icon_path = os.path.join(os.path.dirname(IMAGE_DIR), "icons", f"{unit_icon}.png")
            if os.path.exists(icon_path):
                with open(icon_path, "rb") as f:
                    images[f"{unit_icon}-icon"] = f"data:image/png;base64,{base64.b64encode(f.read()).decode('ascii')}"

    # Faction backgrounds and units
    for f in factions_in_game:
        bg_file = f"{f.lower()}-background.webp"
        images[f"bg_{f}"] = embed_image(bg_file)
        glyph_file = f"{f.lower()}-glyph.webp"
        images[f"glyph_{f}"] = embed_image(glyph_file)
        if f in UNIT_IMAGE_MAP:
            for utype, img_key in UNIT_IMAGE_MAP[f].items():
                images[f"unit_{f}_{utype}"] = embed_image(f"{img_key}.webp")
    return images


# ── Load trace file ───────────────────────────────────────────────────
def load_trace(path):
    """Split trace file at first blank line: top = Scala action strings,
    bottom = HTML game log lines. Only the HTML lines drive state tracking."""
    with open(path) as f:
        raw = f.read()
    parts = raw.split("\n\n", 1)
    action_strings = [l.strip() for l in parts[0].strip().split("\n") if l.strip()]
    html_lines = []
    if len(parts) > 1:
        html_lines = [l.strip() for l in parts[1].splitlines() if l.strip()]
    return action_strings, html_lines


# ── Legacy state tracking (superseded by game_state.py + build_snapshots_v2) ──
# These classes are no longer used by main() but remain for reference.
class FactionState:
    def __init__(self, code):
        self.code = code
        self.power = 8  # starting power
        self.doom = 0
        self.es = 0
        self.gates = set()
        self.sb_earned = []
        self.sb_facedown = set()
        self.start_region = None
        self.units_by_region = defaultdict(lambda: defaultdict(int))

    def total_gates(self):
        return len(self.gates)

    def unit_summary(self):
        """Return dict of unit_type -> total count on map."""
        totals = defaultdict(int)
        for r, units in self.units_by_region.items():
            for u, n in units.items():
                if n > 0:
                    totals[u] += n
        return dict(totals)

    def clone(self):
        c = FactionState(self.code)
        c.power = self.power
        c.doom = self.doom
        c.es = self.es
        c.gates = set(self.gates)
        c.sb_earned = list(self.sb_earned)
        c.sb_facedown = set(self.sb_facedown)
        c.start_region = self.start_region
        c.units_by_region = defaultdict(lambda: defaultdict(int))
        for r, d in self.units_by_region.items():
            c.units_by_region[r] = defaultdict(int)
            for u, n in d.items():
                if n > 0:
                    c.units_by_region[r][u] = n
        return c

    def to_dict(self):
        units = {}
        for r, d in self.units_by_region.items():
            ru = {}
            for u, n in d.items():
                if n > 0:
                    ru[u] = n
            if ru:
                units[r] = ru
        return {
            "code": self.code,
            "power": self.power,
            "doom": self.doom,
            "es": self.es,
            "gates": sorted(self.gates),
            "sb": self.sb_earned,
            "sbDown": sorted(self.sb_facedown),
            "units": units,
            "startRegion": self.start_region,
        }


class GameState:
    def __init__(self):
        self.factions = {}  # code -> FactionState
        self.faction_order = []  # order they appear
        self.region_gate_owner = {}
        self.gate_locations = set()  # all regions that have/had a gate (never removed)
        self.battle_region = None  # current battle location for kill/retreat tracking
        self.effect_region = None  # current effect target (Dread Curse, Zingaya, etc.)
        self.round_num = 0
        self.ritual_cost = 5  # 4-player starts at 5
        self.ritual_marker = 0  # index into ritual track
        self.ritual_history = []  # list of faction codes that ritualed

    def clone(self):
        c = GameState()
        c.faction_order = list(self.faction_order)
        c.factions = {f: fs.clone() for f, fs in self.factions.items()}
        c.region_gate_owner = dict(self.region_gate_owner)
        c.gate_locations = set(self.gate_locations)
        c.battle_region = self.battle_region
        c.effect_region = self.effect_region
        c.round_num = self.round_num
        c.ritual_cost = self.ritual_cost
        c.ritual_marker = self.ritual_marker
        c.ritual_history = list(self.ritual_history)
        return c

    def to_dict(self):
        return {
            "round": self.round_num,
            "ritualCost": self.ritual_cost,
            "ritualMarker": self.ritual_marker,
            "ritualHistory": self.ritual_history,
            "factions": {f: fs.to_dict() for f, fs in self.factions.items()},
            "gateOwners": self.region_gate_owner,
            "gateLocations": sorted(self.gate_locations),
        }


def build_snapshots(html_lines):
    """Parse HTML log lines and build state snapshots.
    Returns (snapshots, display_lines, ap_indices) where each snapshot is a GameState dict,
    display_lines are cleaned log text with faction class info, and ap_indices mark AP boundaries.
    """
    state = GameState()
    state._pending_weights = []
    snapshots = []
    display_lines = []
    ap_indices = []  # indices where new APs start
    line_factions = []  # faction class for each display line

    for raw_line in html_lines:
        plain = strip_html(raw_line)

        # Collect BOT/OPT/WHY/ALT debug lines for weights display
        if plain.startswith("[BOT") or plain.startswith("[OPT") or plain.startswith("[WHY") or plain.startswith("[ALT"):
            if not hasattr(state, '_pending_weights'):
                state._pending_weights = []
            state._pending_weights.append(plain)
            continue
        # Skip dotted separators
        if plain.startswith(".........."):
            continue
        # Skip TRACE_FACTION lines
        if plain.startswith("TRACE_FACTION"):
            continue
        # Skip Options lines
        if plain.startswith("Options "):
            continue

        # Determine faction class from HTML spans
        line_faction = None
        for fc in FACTION_NAMES.values():
            if f"class='{fc.lower()}" in raw_line or f'class="{fc.lower()}' in raw_line:
                line_faction = fc.lower()
                break

        # Parse the line and update state
        short, full, rest = faction_prefix(plain)

        # Detect round boundaries
        m = re.match(r"^Turn (\d+)$", plain)
        if m:
            state.round_num = int(m.group(1))

        # Play order = new AP
        if plain.startswith("Play order "):
            ap_indices.append(len(display_lines))
            order_names = re.findall(r"([A-Z][a-z]+(?: [A-Z][a-z]+)*)", plain[len("Play order "):])
            state.faction_order = [FACTION_NAMES.get(n, n) for n in order_names]

        if short:
            # Ensure faction exists
            if short not in state.factions:
                state.factions[short] = FactionState(short)
                if short not in state.faction_order:
                    state.faction_order.append(short)

            fs = state.factions[short]

            # Starting region
            m = re.match(r"^started in (.+)$", rest)
            if m:
                reg = region_key(m.group(1).strip())
                fs.start_region = reg
                fs.units_by_region[reg]["Acolyte"] += 6  # 6 starting acolytes
                fs.gates.add(reg)
                state.region_gate_owner[reg] = short
                state.gate_locations.add(reg)
                # Starting power = 8
                fs.power = 8

            # Power gather
            m = re.match(r"^got (\d+) Power", rest)
            if m:
                fs.power = int(m.group(1))

            # Power set
            m = re.match(r"^power increased to (\d+) Power", rest)
            if m:
                fs.power = int(m.group(1))

            # Power recovery
            m = re.match(r"^recovered (\d+) Power", rest)
            if m:
                fs.power += int(m.group(1))

            # Doom gather
            m = re.match(r"^got (\d+) Doom", rest)
            if m:
                fs.doom += int(m.group(1))

            # Doom gain
            m = re.match(r"^gained (\d+) Doom", rest)
            if m:
                fs.doom += int(m.group(1))

            # Out of power
            if rest == "ran out of power" or rest == "had no power":
                fs.power = 0

            # Build gate
            m = re.match(r"^built a gate in (.+)$", rest)
            if m:
                reg = region_key(m.group(1).strip())
                fs.gates.add(reg)
                state.region_gate_owner[reg] = short
                state.gate_locations.add(reg)
                fs.power = max(0, fs.power - 3)

            # Lost gate — gate still physically exists, just unowned
            m = re.match(r"^lost control of the gate in (.+)$", rest)
            if m:
                reg = region_key(m.group(1).strip())
                fs.gates.discard(reg)
                if state.region_gate_owner.get(reg) == short:
                    state.region_gate_owner[reg] = ""

            # Gained gate
            m = re.match(r"^gained control of the gate in (.+)$", rest)
            if m:
                reg = region_key(m.group(1).strip())
                fs.gates.add(reg)
                state.region_gate_owner[reg] = short
                state.gate_locations.add(reg)

            # Move
            m = re.match(r"^moved ([\w' -]+) from (.+?) to (.+?)$", rest)
            if m:
                unit = m.group(1).strip()
                src = region_key(m.group(2).strip())
                dst = region_key(m.group(3).strip())
                if fs.units_by_region[src][unit] > 0:
                    fs.units_by_region[src][unit] -= 1
                fs.units_by_region[dst][unit] += 1

            # Recruit
            m = re.match(r"^recruited ([\w' -]+) in (.+)$", rest)
            if m:
                unit = m.group(1).strip()
                reg = region_key(m.group(2).strip())
                fs.units_by_region[reg][unit] += 1
                fs.power = max(0, fs.power - 1)

            # Summon
            m = re.match(r"^summoned ([\w' -]+) in (.+)$", rest)
            if m:
                unit = m.group(1).strip()
                reg = region_key(m.group(2).strip())
                fs.units_by_region[reg][unit] += 1

            # Awaken (with or without "for X Power" — non-FB factions omit cost)
            m = re.match(r"^awakened ([\w' -]+) in (.+?)(?:\s+for (\d+) Power)?$", rest)
            if m:
                unit = m.group(1).strip()
                reg = region_key(m.group(2).strip())
                cost = int(m.group(3)) if m.group(3) else 0
                # GOOs are unique — remove any existing copy before adding
                if unit in GOO_TYPES:
                    for r in list(fs.units_by_region.keys()):
                        fs.units_by_region[r][unit] = 0
                fs.units_by_region[reg][unit] += 1
                if cost > 0:
                    fs.power = max(0, fs.power - cost)

            # Writhe: Acolyte replaced with Desiccated
            m = re.match(r"^Writhe: Acolyte replaced with Desiccated in (.+)$", rest)
            if m:
                reg = region_key(m.group(1).strip())
                if fs.units_by_region[reg]["Acolyte"] > 0:
                    fs.units_by_region[reg]["Acolyte"] -= 1
                fs.units_by_region[reg]["Desiccated"] += 1

            # Writhe: relocated unit
            m = re.match(r"^Writhe: relocated ([\w' -]+) from (.+?) to (.+?)$", rest)
            if m:
                unit = m.group(1).strip()
                src = region_key(m.group(2).strip())
                dst = region_key(m.group(3).strip())
                if fs.units_by_region[src][unit] > 0:
                    fs.units_by_region[src][unit] -= 1
                fs.units_by_region[dst][unit] += 1

            # Writhe: eliminated
            m = re.match(r"^Writhe: eliminated ([\w' -]+) in (.+)$", rest)
            if m:
                unit = m.group(1).strip()
                reg = region_key(m.group(2).strip())
                if fs.units_by_region[reg][unit] > 0:
                    fs.units_by_region[reg][unit] -= 1

            # Capture
            m = re.match(r"^captured (.+?) in (.+)$", rest)
            if m:
                # short is the captor; we need to figure out victim faction from the HTML
                captured_unit_raw = m.group(1).strip()
                reg = region_key(m.group(2).strip())
                # Try to find victim faction from HTML span class
                cap_match = re.search(r"captured <span class='(\w+)'", raw_line)
                if cap_match:
                    victim_fc = cap_match.group(1).upper()
                    if victim_fc in state.factions:
                        vfs = state.factions[victim_fc]
                        if vfs.units_by_region[reg].get(captured_unit_raw, 0) > 0:
                            vfs.units_by_region[reg][captured_unit_raw] -= 1

            # Ice Age: "started Ice Age in Region"
            m = re.match(r"^started Ice Age in (.+)$", rest)
            if m:
                reg = region_key(m.group(1).strip())
                fs.units_by_region[reg]["Ice Age"] += 1

            # Cathedral: "built a cathedral in Region"
            m = re.match(r"^built a cathedral in (.+)$", rest)
            if m:
                reg = region_key(m.group(1).strip())
                fs.units_by_region[reg]["Cathedral"] += 1

            # Sacrifice: "sacrificed Unit in Region" or "Unit in Region was sacrificed"
            m = re.match(r"^sacrificed ([\w' -]+) in (.+?)(?:\s+for.*)?$", rest)
            if m:
                unit = m.group(1).strip()
                reg = region_key(m.group(2).strip())
                if fs.units_by_region[reg].get(unit, 0) > 0:
                    fs.units_by_region[reg][unit] -= 1

        # "Unit in Region was sacrificed" (no faction prefix — parse from spans)
        if "was sacrificed" in plain and not short:
            sac_match = re.search(r"<span class='(\w+)'>([\w' -]+)</span> in <span class='(?:region|sea)'>([^<]+)</span> was sacrificed", raw_line)
            if sac_match:
                sfc = sac_match.group(1).upper()
                sunit = sac_match.group(2).strip()
                sreg = region_key(sac_match.group(3).strip())
                if sfc in state.factions:
                    sfs = state.factions[sfc]
                    if sfs.units_by_region[sreg].get(sunit, 0) > 0:
                        sfs.units_by_region[sreg][sunit] -= 1

        if short:
            # Spellbook earned
            m = re.match(r"^received (.+)$", rest)
            if m:
                sb_name = m.group(1).strip()
                if sb_name not in fs.sb_earned:
                    fs.sb_earned.append(sb_name)

            # Spellbook facedown
            m = re.match(r"^(.+) flipped facedown$", rest)
            if m:
                sb_name = m.group(1).strip()
                fs.sb_facedown.add(sb_name)

            # Ritual
            m = re.match(r"^performed the ritual for (\d+) Power and gained (\d+) Doom", rest)
            if m:
                cost = int(m.group(1))
                doom = int(m.group(2))
                fs.power = max(0, fs.power - cost)
                fs.doom += doom
                if "Elder Sign" in rest:
                    fs.es += 1
                # Record who ritualed and advance track
                state.ritual_history.append(short)
                RITUAL_TRACK_4P = [5, 6, 7, 7, 8, 8, 9, 10, 999]
                state.ritual_marker = min(state.ritual_marker + 1, len(RITUAL_TRACK_4P) - 1)
                state.ritual_cost = RITUAL_TRACK_4P[state.ritual_marker]

            # Elder sign reveal
            m = re.match(r"^revealed .+ for (\d+) Doom$", rest)
            if m:
                fs.doom += int(m.group(1))

            # Promotion (MFO): "promoted Mutant in Region to Abomination"
            m = re.match(r"^promoted ([\w' -]+) in (.+?) to ([\w' -]+)$", rest)
            if m:
                old_unit = m.group(1).strip()
                reg = region_key(m.group(2).strip())
                new_unit = m.group(3).strip()
                if fs.units_by_region[reg].get(old_unit, 0) > 0:
                    fs.units_by_region[reg][old_unit] -= 1
                fs.units_by_region[reg][new_unit] += 1

            # Devil's Mark: gate destruction + crater
            m = re.match(r"^Gate in (.+?) destroyed by Crater$", rest)
            if m:
                reg = region_key(m.group(1).strip())
                fs.gates.discard(reg)
                if state.region_gate_owner.get(reg) == short:
                    del state.region_gate_owner[reg]
                state.gate_locations.discard(reg)
                # Place crater on map (visible building)
                fs.units_by_region[reg]["Crater"] += 1

            # Cursed Slumber: "moved gate from Region to Cursed Slumber"
            m = re.match(r"^moved gate from (.+?) to Cursed Slumber$", rest)
            if m:
                reg = region_key(m.group(1).strip())
                fs.gates.discard(reg)
                if state.region_gate_owner.get(reg) == short:
                    state.region_gate_owner[reg] = ""
                # Move cultist to faction card (remove from map)
                for utype in ["Acolyte", "High Priest"]:
                    if fs.units_by_region[reg].get(utype, 0) > 0:
                        fs.units_by_region[reg][utype] -= 1
                        break

            # Cursed Slumber return: "moved gate from Cursed Slumber to Region"
            m = re.match(r"^moved gate from Cursed Slumber to (.+?)$", rest)
            if m:
                reg = region_key(m.group(1).strip())
                fs.gates.add(reg)
                state.region_gate_owner[reg] = short

            # Beyond One: "moved gate with Unit from Src to Dst"
            m = re.match(r"^moved gate with ([\w' -]+) from (.+?) to (.+?)$", rest)
            if m:
                unit = m.group(1).strip()
                src = region_key(m.group(2).strip())
                dst = region_key(m.group(3).strip())
                # Move the unit
                if fs.units_by_region[src].get(unit, 0) > 0:
                    fs.units_by_region[src][unit] -= 1
                fs.units_by_region[dst][unit] += 1
                # Move the gate
                fs.gates.discard(src)
                fs.gates.add(dst)
                if state.region_gate_owner.get(src) == short:
                    state.region_gate_owner[src] = ""
                state.region_gate_owner[dst] = short
                state.gate_locations.add(dst)

            # Call of the Faithful
            m = re.match(r"^Call of the Faithful: placed Acolyte (?:on the gate )?in (.+)$", rest)
            if m:
                reg = region_key(m.group(1).strip())
                fs.units_by_region[reg]["Acolyte"] += 1

            # Released prisoners — affects other factions
            m = re.match(r"^released (.+)$", rest)
            if m:
                # Parse released units — each is "<faction_class>UnitName"
                # From HTML: <span class='ww'>Acolyte</span>, <span class='gc'>Deep One</span>
                releases = re.findall(r"<span class='(\w+)'>([^<]+)</span>", raw_line)
                for vic_fc, vic_unit in releases:
                    vic_fc = vic_fc.upper()
                    if vic_fc in state.factions:
                        # Return to pool — we don't track pool, but unit disappears from captor
                        pass

            # Spent power (generic)
            m = re.match(r"^spent (\d+) Power", rest)
            if m:
                fs.power = max(0, fs.power - int(m.group(1)))

            # Hibernated
            m = re.match(r"^hibernated for extra (\d+) Power", rest)
            if m:
                fs.power += int(m.group(1))

        # ── CONTEXT TRACKING: battle region + effect region ──
        # "X battled Y in Region"
        m = re.search(r"battled [\w' -]+ in (.+)$", plain)
        if m:
            state.battle_region = region_key(m.group(1).strip())
            state.effect_region = state.battle_region

        # "sent Dread Curse / Zingaya / etc. to Region"
        m = re.search(r"sent .+? to <span class='(?:region|sea)'>([^<]+)</span>", raw_line)
        if m and not re.search(r"sent [\w' -]+ from", plain):
            state.effect_region = region_key(m.group(1).strip())

        # Helper: find which region a faction has a specific unit in
        def find_unit_region(faction_code, unit_name):
            fs = state.factions.get(faction_code)
            if not fs:
                return None
            for r, units in fs.units_by_region.items():
                if units.get(unit_name, 0) > 0:
                    return r
            return None

        # Helper: remove unit from faction, trying effect_region first, then searching
        def remove_unit(faction_code, unit_name):
            fs = state.factions.get(faction_code)
            if not fs:
                return
            # Try effect_region first (battle or ability target)
            er = getattr(state, 'effect_region', None) or getattr(state, 'battle_region', None)
            if er and fs.units_by_region[er].get(unit_name, 0) > 0:
                fs.units_by_region[er][unit_name] -= 1
                return
            # Fallback: find unit anywhere and remove
            found = find_unit_region(faction_code, unit_name)
            if found:
                fs.units_by_region[found][unit_name] -= 1

        IGNORE_CLASSES = {"kill", "pain", "miss", "region", "sea", "power", "inline-block", "str"}
        IGNORE_WORDS = {"killed", "were", "was", "pained", "eliminated", "and", "with", "to", "from", "in"}

        # Helper: extract faction units from HTML spans (filtering non-unit spans)
        def extract_units_from_spans(html, before_text=None):
            text = html.split(before_text)[0] if before_text and before_text in html else html
            spans = re.findall(r"<span class='(\w+)'>([^<]+)</span>", text)
            results = []
            for fc, name in spans:
                name_s = name.strip()
                if fc.lower() in IGNORE_CLASSES or name_s.lower() in IGNORE_WORDS:
                    continue
                fc_upper = fc.upper()
                if fc_upper in state.factions:
                    results.append((fc_upper, name_s))
            return results

        # ── KILLS: "was killed" / "were killed" — from battle, Dread Curse, etc. ──
        if re.search(r"were killed|was killed", plain) and not short:
            for fc, unit_name in extract_units_from_spans(raw_line):
                remove_unit(fc, unit_name)

        # ── RETREATS: "retreated to Region" ──
        if "retreated to" in plain:
            dst_match = re.search(r"retreated to <span class='(?:region|sea)'>([^<]+)</span>", raw_line)
            if dst_match:
                dst = region_key(dst_match.group(1).strip())
                er = getattr(state, 'effect_region', None) or getattr(state, 'battle_region', None)
                for fc, unit_name in extract_units_from_spans(raw_line, "retreated"):
                    if er and er != dst:
                        fs = state.factions.get(fc)
                        if fs:
                            if fs.units_by_region[er].get(unit_name, 0) > 0:
                                fs.units_by_region[er][unit_name] -= 1
                            fs.units_by_region[dst][unit_name] += 1

        # ── GENERIC "pained to Region" — Dread Curse, CG, etc. ──
        # Format: "<Unit> was pained to <Region>" (no "from")
        m = re.search(r"was <span class='pain'>pained</span> to <span class='(?:region|sea)'>([^<]+)</span>", raw_line)
        if m:
            dst = region_key(m.group(1).strip())
            er = getattr(state, 'effect_region', None) or getattr(state, 'battle_region', None)
            for fc, unit_name in extract_units_from_spans(raw_line, "was"):
                if er and er != dst:
                    fs = state.factions.get(fc)
                    if fs:
                        if fs.units_by_region[er].get(unit_name, 0) > 0:
                            fs.units_by_region[er][unit_name] -= 1
                        fs.units_by_region[dst][unit_name] += 1
                elif not er:
                    # No effect region — find unit and move it
                    src = find_unit_region(fc, unit_name)
                    if src and src != dst:
                        fs = state.factions.get(fc)
                        if fs:
                            fs.units_by_region[src][unit_name] -= 1
                            fs.units_by_region[dst][unit_name] += 1

        # Cyclopean Gaze pains: "Faction CG - FBunit: pained EnemyUnit from Src to Dst"
        m = re.search(r"Cyclopean Gaze - .+?: pained (.+?) from (.+?) to (.+?)$", plain)
        if m:
            unit_name = m.group(1).strip()
            src = region_key(m.group(2).strip())
            dst = region_key(m.group(3).strip())
            # Find victim faction from HTML spans (unit span class before "pained")
            cg_spans = re.findall(r"pained <span class='(\w+)'>([^<]+)</span>", raw_line)
            for vic_fc, vic_unit in cg_spans:
                vic_fc_upper = vic_fc.upper()
                if vic_fc_upper in state.factions and src != dst:
                    vfs = state.factions[vic_fc_upper]
                    if vfs.units_by_region[src].get(vic_unit.strip(), 0) > 0:
                        vfs.units_by_region[src][vic_unit.strip()] -= 1
                    vfs.units_by_region[dst][vic_unit.strip()] += 1

        # Submerge: "Cthulhu submerged in Region with Unit, Unit"
        m = re.search(r"submerged in (.+?)(?:\s+with (.+))?$", plain)
        if m and short:
            reg = region_key(m.group(1).strip())
            fs = state.factions.get(short)
            if fs:
                # Remove all listed units from the region (they go underwater/off-map)
                companions = m.group(2)
                if companions:
                    for uname in companions.split(","):
                        uname = uname.strip()
                        if uname and fs.units_by_region[reg].get(uname, 0) > 0:
                            fs.units_by_region[reg][uname] -= 1

        # Unsubmerge: "Cthulhu unsubmerged in Region with Unit, Unit"
        m = re.search(r"unsubmerged in (.+?)(?:\s+with (.+))?$", plain)
        if m and short:
            reg = region_key(m.group(1).strip())
            fs = state.factions.get(short)
            if fs:
                companions = m.group(2)
                if companions:
                    for uname in companions.split(","):
                        uname = uname.strip()
                        if uname:
                            fs.units_by_region[reg][uname] += 1

        # ── Generic unit state changes (covers ALL factions/abilities) ──
        # These use the full plain text (not faction-prefixed rest) to catch
        # events from any faction. Uses HTML spans to identify unit factions.
        IGNORE_CLASSES2 = {"kill", "pain", "miss", "region", "sea", "power",
                          "inline-block", "fb", "gc", "cc", "bg", "ys", "sl",
                          "ww", "ow", "an", "ts"}

        # Howl: "Unit was howled to Region"
        m = re.search(r"was howled to (.+?)$", plain)
        if m:
            dst = region_key(m.group(1).strip())
            br = getattr(state, 'battle_region', None)
            spans = re.findall(r"<span class='(\w+)'>([^<]+)</span>", raw_line)
            for sf, su in spans:
                if sf.lower() in {"region", "sea", "kill", "pain", "miss", "power", "inline-block"}:
                    continue
                if su.strip().startswith("howled"):
                    continue
                sf_upper = sf.upper()
                if sf_upper in state.factions and br and br != dst:
                    ufs = state.factions[sf_upper]
                    su_s = su.strip()
                    if ufs.units_by_region[br].get(su_s, 0) > 0:
                        ufs.units_by_region[br][su_s] -= 1
                    ufs.units_by_region[dst][su_s] += 1

        # Generic eliminations: "was eliminated", "were eliminated"
        # Covers: Berserkergang, UnholyGround, Eye Opens, Dread Curse, Zingaya, Ghroth, etc.
        if ("was eliminated" in plain or "were eliminated" in plain) and "Writhe" not in plain and "Cyclopean Gaze" not in plain:
            # Try to get region from "in <region>" in the text
            reg_match = re.search(r"in <span class='(?:region|sea)'>([^<]+)</span>", raw_line)
            if reg_match:
                state.effect_region = region_key(reg_match.group(1).strip())
            for fc, unit_name in extract_units_from_spans(raw_line):
                if unit_name.lower() not in ("eliminated",):
                    remove_unit(fc, unit_name)

        # CG elimination: "had nowhere to retreat and was eliminated"
        if "had nowhere to retreat and was eliminated" in plain and "Cyclopean Gaze" in plain:
            cg_elim = re.search(r"<span class='(\w+)'>([^<]+)</span> in <span class='(?:region|sea)'>([^<]+)</span>.*eliminated", raw_line)
            if cg_elim:
                ef = cg_elim.group(1).upper()
                eu = cg_elim.group(2).strip()
                er = region_key(cg_elim.group(3).strip())
                if ef in state.factions:
                    ufs = state.factions[ef]
                    if ufs.units_by_region[er].get(eu, 0) > 0:
                        ufs.units_by_region[er][eu] -= 1

        # Devour: "Unit was devoured by Opponent"
        if "was devoured" in plain:
            units = extract_units_from_spans(raw_line, "was devoured")
            if units:
                remove_unit(units[0][0], units[0][1])

        # Absorption: "Unit absorbed Target" — target removed
        if "absorbed" in plain and "strength" in plain:
            abs_match = re.search(r"absorbed <span class='(\w+)'>([^<]+)</span>", raw_line)
            if abs_match:
                af = abs_match.group(1).upper()
                au = abs_match.group(2).strip()
                if af in state.factions:
                    remove_unit(af, au)

        # Shriveled: "Unit was shriveled"
        if "was shriveled" in plain:
            units = extract_units_from_spans(raw_line, "was shriveled")
            if units:
                remove_unit(units[0][0], units[0][1])

        # Undulate: "Undulate: carried Unit for free from Src to Dst"
        m = re.search(r"Undulate: carried (.+?) for free from (.+?) to (.+?)$", plain)
        if m:
            uu = m.group(1).strip()
            src = region_key(m.group(2).strip())
            dst = region_key(m.group(3).strip())
            und_span = re.search(r"carried <span class='(\w+)'>", raw_line)
            if und_span:
                uf = und_span.group(1).upper()
                if uf in state.factions:
                    ufs = state.factions[uf]
                    if ufs.units_by_region[src].get(uu, 0) > 0:
                        ufs.units_by_region[src][uu] -= 1
                    ufs.units_by_region[dst][uu] += 1

        # Dematerialization: "sent Unit from Src to Dst with Dematerialization"
        m = re.search(r"sent ([\w' -]+) from (.+?) to (.+?) with Dematerialization$", plain)
        if m and short:
            su = m.group(1).strip()
            src = region_key(m.group(2).strip())
            dst = region_key(m.group(3).strip())
            dfs = state.factions.get(short)
            if dfs:
                if dfs.units_by_region[src].get(su, 0) > 0:
                    dfs.units_by_region[src][su] -= 1
                dfs.units_by_region[dst][su] += 1

        # Screaming Dead: "King in Yellow screamed from Src to Dst"
        m = re.search(r"screamed from (.+?) to (.+?)$", plain)
        if m and short:
            src = region_key(m.group(1).strip())
            dst = region_key(m.group(2).strip())
            sfs = state.factions.get(short)
            if sfs:
                if sfs.units_by_region[src].get("King in Yellow", 0) > 0:
                    sfs.units_by_region[src]["King in Yellow"] -= 1
                sfs.units_by_region[dst]["King in Yellow"] += 1

        # "followed along" — unit follows King in Yellow (same src→dst)
        # Hard to track without context; skip for now (rare)

        # Avatar: "avatared to Region" — Shub moves
        m = re.search(r"avatared to (.+?)$", plain)
        if m and short:
            dst = region_key(m.group(1).strip())
            afs = state.factions.get(short)
            if afs:
                for r_key in list(afs.units_by_region.keys()):
                    if afs.units_by_region[r_key].get("Shub-Niggurath", 0) > 0:
                        afs.units_by_region[r_key]["Shub-Niggurath"] -= 1
                        break
                afs.units_by_region[dst]["Shub-Niggurath"] += 1

        # "was sent back to Region" — avatar defender return
        m = re.search(r"was sent back to (.+?)$", plain)
        if m:
            dst = region_key(m.group(1).strip())
            br = getattr(state, 'battle_region', None)
            spans = re.findall(r"<span class='(\w+)'>([^<]+)</span>", raw_line)
            if spans and br:
                sf, su = spans[0]
                sf_upper = sf.upper()
                su_s = su.strip()
                if sf_upper in state.factions and br != dst:
                    ufs = state.factions[sf_upper]
                    if ufs.units_by_region[br].get(su_s, 0) > 0:
                        ufs.units_by_region[br][su_s] -= 1
                    ufs.units_by_region[dst][su_s] += 1

        # Byakhee flight: "flew to Dst from Src"
        m = re.search(r"flew to (.+?) from (.+?)$", plain)
        if m:
            dst = region_key(m.group(1).strip())
            src = region_key(m.group(2).strip())
            fly_span = re.findall(r"<span class='(\w+)'>([^<]+)</span>", raw_line)
            if fly_span:
                sf, su = fly_span[0]
                sf_upper = sf.upper()
                su_s = su.strip()
                if sf_upper in state.factions:
                    ufs = state.factions[sf_upper]
                    if ufs.units_by_region[src].get(su_s, 0) > 0:
                        ufs.units_by_region[src][su_s] -= 1
                    ufs.units_by_region[dst][su_s] += 1

        # Eye Opens elimination: "UnitName eliminated in Region by The Eye Opens"
        m = re.search(r"eliminated in (.+?) by The Eye Opens$", plain)
        if m:
            reg = region_key(m.group(1).strip())
            eo_spans = re.findall(r"<span class='(\w+)'>([^<]+)</span>", raw_line)
            for sf, su in eo_spans:
                su_s = su.strip()
                if sf.lower() in {"region", "sea", "fb", "inline-block"} or "Eye" in su_s or "eliminated" in su_s:
                    continue
                sf_upper = sf.upper()
                if sf_upper in state.factions:
                    ufs = state.factions[sf_upper]
                    if ufs.units_by_region[reg].get(su_s, 0) > 0:
                        ufs.units_by_region[reg][su_s] -= 1

        # "replaced Unit with Acolyte" (Dreams) or "replaced Unit in Region with Undead" (Curse)
        m = re.search(r"replaced (.+?) (?:in (.+?) )?with (.+?)$", plain)
        if m:
            old_unit = m.group(1).strip()
            reg_str = m.group(2)
            new_unit = m.group(3).strip()
            rep_reg = region_key(reg_str.strip()) if reg_str else None
            # Find faction from spans
            rep_spans = re.findall(r"replaced <span class='(\w+)'>([^<]+)</span>", raw_line)
            if rep_spans:
                rf, ru = rep_spans[0]
                rf_upper = rf.upper()
                if rf_upper in state.factions and rep_reg:
                    ufs = state.factions[rf_upper]
                    if ufs.units_by_region[rep_reg].get(ru.strip(), 0) > 0:
                        ufs.units_by_region[rep_reg][ru.strip()] -= 1
                    ufs.units_by_region[rep_reg][new_unit] += 1

        # Winner
        m = re.match(r"^(.+) won$", plain)
        if m:
            pass  # Just display it

        # Store display line and snapshot
        # Attach any pending weights to this display line
        weights_data = None
        if hasattr(state, '_pending_weights') and state._pending_weights:
            # Parse weights: extract chosen (BOT), top options (OPT), reasons (WHY)
            chosen = None
            options = []
            reasons = []
            for w in state._pending_weights:
                if w.startswith("[BOT"):
                    m = re.match(r"\[BOT FB @\d+\]\s+(.+?)\s+\((-?\d+)\)", w)
                    if m: chosen = {"action": m.group(1).strip(), "score": int(m.group(2))}
                elif w.startswith("[OPT"):
                    m = re.match(r"\[OPT [^]]+\]\s+(.+?)\s+=\s+(-?\d+)", w)
                    if m: options.append({"action": m.group(1).strip(), "score": int(m.group(2))})
                elif w.startswith("[WHY"):
                    m = re.match(r"\[WHY\]\s+(-?\d+)\s+=\s+(.+)", w)
                    if m: reasons.append({"score": int(m.group(1)), "reason": m.group(2).strip()})
            if chosen or options:
                # Top 5 options sorted by score
                options.sort(key=lambda x: -x["score"])
                weights_data = {
                    "chosen": chosen,
                    "options": options[:5],
                    "reasons": reasons[:3]
                }
            state._pending_weights = []

        display_lines.append({"text": plain, "html": raw_line, "faction": line_faction, "weights": weights_data})
        snapshots.append(state.clone().to_dict())

    return snapshots, display_lines, ap_indices


# ── Build HTML ────────────────────────────────────────────────────────
_prewarmed_images = None

def build_html(snapshots, display_lines, ap_indices, factions_in_game, title, unmatched_count=0, issues=None):
    """Generate self-contained HTML string with embedded images, JSON data,
    CSS, and JS viewer. The output file has zero external dependencies."""
    global _prewarmed_images
    images = _prewarmed_images if _prewarmed_images else collect_needed_images(factions_in_game, None)

    # Build image JS object
    images_json = json.dumps(images)

    # Build unit image map for JS
    unit_img_map = {}
    for f, units in UNIT_IMAGE_MAP.items():
        if f in factions_in_game:
            for utype, _ in units.items():
                key = f"unit_{f}_{utype}"
                unit_img_map[f"{f}:{utype}"] = key
    unit_img_json = json.dumps(unit_img_map)

    # Region coords for JS
    region_coords_json = json.dumps(REGION_COORDS)
    region_display_json = json.dumps(REGION_DISPLAY)

    # Map dimensions (must match placement bitmap resolution)
    if _map_id.startswith("library"):
        map_w = 3582
        map_h = 1793
        unit_scale = 2.0
        # Tome positions: 5U for library53/library5, 3U for library35/library3
        if _map_id in ("library53", "library5"):
            tome_positions_json = json.dumps({
                "Yr and the Nhhngr": [2083, 749],
                "Guardian under the Lake": [3193, 774],
                "Larvae of the Outer Gods": [3140, 1312],
                "Barrier of Naach-Tith": [2094, 1417]
            })
        else:
            tome_positions_json = json.dumps({
                "Yr and the Nhhngr": [2093, 552],
                "Guardian under the Lake": [3200, 537],
                "Larvae of the Outer Gods": [3216, 1235],
                "Barrier of Naach-Tith": [2091, 1353]
            })
    else:
        map_w = 1791
        map_h = 894
        unit_scale = 1.0
        tome_positions_json = json.dumps({})

    # Faction full names
    faction_full_json = json.dumps(FACTION_FULL)

    # Snapshots and display lines
    snapshots_json = json.dumps(snapshots)
    display_json = json.dumps(display_lines)
    ap_json = json.dumps(ap_indices)
    factions_json = json.dumps(factions_in_game)
    issues_json = json.dumps(issues or [])
    map_id_str = _map_id or ""

    faction_colors = {
        "gc": "#77a055", "cc": "#4977b3", "bg": "#cd3233", "ys": "#ffd000",
        "ww": "#88a9be", "sl": "#db6a33", "ow": "#6c4296", "an": "#47a5bc",
        "ts": "#BDE0BC", "fb": "#CB307E", "ds": "#3C2E18",
    }
    faction_bg_colors = {
        "gc": "#1a2a14", "cc": "#121e2e", "bg": "#2e0c0c", "ys": "#2e2a00",
        "ww": "#1a2228", "sl": "#2e1a0c", "ow": "#1a1028", "an": "#0e2228",
        "ts": "#1a2e1c", "fb": "#2e0c1e", "ds": "#1a1408",
    }

    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{html.escape(title)}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #111; color: #ddd; font-family: 'Segoe UI', Tahoma, sans-serif; overflow: hidden; height: 100vh; }}

#container {{ display: grid; grid-template-columns: 75% 25%; grid-template-rows: 65vh 35vh; height: 100vh; }}

/* Top-left: Map */
#map-panel {{ grid-column: 1; grid-row: 1; position: relative; overflow: hidden; background: #0a0a0a; padding: 0; margin: 0; }}
#map-img {{ width: 100%; height: 100%; object-fit: contain; object-position: left top; display: block; }}
#map-overlay {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }}

#ritual-tracker {{
    position: absolute; top: 8px; left: 8px; z-index: 10; cursor: pointer;
    transition: all 0.2s;
}}
#ritual-circle {{
    width: 36px; height: 36px; border-radius: 50%; background: rgba(30,10,10,0.85);
    border: 2px solid #a44; display: flex; align-items: center; justify-content: center;
    font-size: 18px; font-weight: bold; color: #f44; font-family: serif;
    text-shadow: 0 0 6px #f44; transition: all 0.2s;
}}
#ritual-circle:hover {{ border-color: #f88; transform: scale(1.1); }}
#ritual-expanded {{
    display: none; position: relative; background: rgba(0,0,0,0.92); border-radius: 6px;
    padding: 4px; border: 1px solid #555; margin-top: 4px;
}}
#ritual-expanded img.track-img {{ width: 500px; display: block; }}
.ritual-ring {{
    position: absolute; border: 3px solid #f44; border-radius: 50%;
    box-shadow: 0 0 8px #f44, inset 0 0 8px rgba(255,68,68,0.3);
    pointer-events: none;
}}
.ritual-glyph {{
    position: absolute; pointer-events: none;
    transform: translate(-50%, 0%);
}}
#ritual-tracker.expanded #ritual-expanded {{ display: block; }}
#ritual-tracker.expanded #ritual-circle {{ border-color: #f88; }}

.region-units {{
    position: absolute;
    display: flex;
    flex-direction: column;
    align-items: center;
    transform: translate(-50%, -100%);
    pointer-events: none;
    z-index: 1;
}}
.region-units-row {{
    display: flex;
    justify-content: center;
    align-items: flex-end;
}}
.unit-icon {{
    image-rendering: auto;
}}
/* FB and TS units are greyscale base images that need faction color tint */
.unit-icon.tint-fb {{
    filter: brightness(1.2) sepia(1) hue-rotate(295deg) saturate(2.5);
}}
.unit-icon.tint-ts {{
    filter: brightness(1.3) sepia(1) hue-rotate(90deg) saturate(0.8);
}}
.gate-icon {{
    image-rendering: auto;
    position: absolute;
    z-index: 0;
    filter: drop-shadow(0 0 6px var(--gate-glow, rgba(255,215,0,0.5)));
    opacity: 0.85;
}}

/* Top-right: Controls + Faction panels */
#right-panel {{ grid-column: 2; grid-row: 1; display: flex; flex-direction: column; background: #1a1a1a; border-left: 2px solid #333; overflow-y: auto; }}

/* Controls */
#controls {{
    padding: 10px 12px;
    background: #222;
    border-bottom: 1px solid #333;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
}}
#controls button {{
    background: #333; color: #ddd; border: 1px solid #555; padding: 4px 10px;
    border-radius: 4px; cursor: pointer; font-size: 13px;
}}
#controls button:hover {{ background: #444; }}
#controls button.active {{ background: #555; border-color: #888; }}
#step-display {{ color: #aaa; font-size: 13px; margin-left: 8px; }}
#speed-control {{ display: flex; align-items: center; gap: 4px; }}
#speed-control label {{ font-size: 12px; color: #888; }}
#speed-slider {{ width: 80px; }}
#btn-issues.has-issues {{ border-color: #cc6633; color: #ffaa66; }}
#issues-overlay {{
    position: fixed; inset: 0; background: rgba(0,0,0,0.78); z-index: 9999;
    display: flex; align-items: center; justify-content: center;
}}
#issues-overlay.hidden {{ display: none; }}
#issues-overlay-inner {{
    background: #1a1a1a; color: #ddd; border: 1px solid #444; border-radius: 6px;
    width: min(900px, 90vw); height: min(80vh, 700px);
    display: flex; flex-direction: column; overflow: hidden;
}}
#issues-overlay-header {{
    padding: 10px 14px; background: #262626; border-bottom: 1px solid #444;
    display: flex; align-items: center; justify-content: space-between;
}}
#issues-overlay-title {{ font-size: 15px; font-weight: 600; }}
#issues-overlay-close {{
    background: #333; color: #ddd; border: 1px solid #555; padding: 2px 10px;
    border-radius: 4px; cursor: pointer; font-size: 16px; line-height: 1;
}}
#issues-overlay-close:hover {{ background: #555; }}
#issues-overlay-summary {{
    padding: 8px 14px; background: #1f1f1f; border-bottom: 1px solid #333;
    font-size: 12px; color: #aaa;
}}
#issues-overlay-list {{
    flex: 1; overflow-y: auto; padding: 6px 0; font-size: 12px;
}}
.issue-row {{
    padding: 6px 14px; border-bottom: 1px solid #2a2a2a;
    display: grid; grid-template-columns: 60px 110px 1fr; gap: 10px;
    cursor: pointer;
}}
.issue-row:hover {{ background: #232323; }}
.issue-line-idx {{ color: #888; font-family: monospace; }}
.issue-kind {{ font-size: 11px; padding: 1px 6px; border-radius: 3px; align-self: start; }}
.issue-kind.unmatched {{ background: #4a1818; color: #ff9090; }}
.issue-kind.matched_noop {{ background: #443300; color: #e0c060; }}
.issue-text {{ color: #ccc; word-break: break-word; }}
.issue-handler {{ color: #888; font-style: italic; font-size: 11px; }}

#ap-buttons {{
    padding: 4px 12px 8px;
    background: #222;
    border-bottom: 1px solid #333;
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
}}
#ap-buttons button {{
    background: #2a2a2a; color: #aaa; border: 1px solid #444; padding: 2px 8px;
    border-radius: 3px; cursor: pointer; font-size: 11px;
}}
#ap-buttons button:hover {{ background: #3a3a3a; }}
#ap-buttons button.current {{ background: #444; color: #fff; border-color: #888; }}

/* Faction panels — scale to fit, no scrollbar */
#faction-panels {{
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    display: flex;
    flex-direction: column;
}}
.faction-panel {{
    flex: 0 0 auto;
    padding: 0.3vh 0.5vw;
    border-bottom: 1px solid #333;
}}
.faction-header {{
    display: flex;
    align-items: center;
    gap: 0.3vw;
    padding: 0.2vh 0.4vw;
    border-radius: 4px;
    margin-bottom: 0.2vh;
}}
.faction-bg {{
    width: 28px; height: 28px; border-radius: 4px;
}}
.faction-name {{ font-weight: bold; font-size: min(1.1vw, 1.8vh); }}
.faction-stats {{
    display: flex; gap: 0.6vw; font-size: min(0.9vw, 1.5vh); color: #bbb; padding-left: 4px;
}}
.faction-stats span {{ display: flex; align-items: center; gap: 3px; }}
.stat-label {{ color: #888; }}
.stat-power {{ color: #4af; }}
.stat-doom {{ color: #f44; }}
.stat-es {{ color: #fc4; }}
.stat-gates {{ color: #4f4; }}
.stat-dh {{ color: #f84; }}
.stat-ip {{ color: #a6f; }}
.stat-tomes {{ color: #f4a; }}
.faction-sb {{
    font-size: min(0.75vw, 1.3vh); color: #999; padding: 1px 0 0 4px;
}}
.sb-item {{ display: inline-block; margin-right: 0.3vw; }}
.sb-facedown {{ opacity: 0.4; text-decoration: line-through; }}
.sbr-toggle {{ cursor: pointer; text-decoration: underline; text-decoration-style: dotted; }}
.sbr-toggle:hover {{ color: #fff; }}
#sbr-overlay {{
    display: none; background: #1a1a1a; border: 1px solid #555; border-radius: 4px;
    padding: 6px 10px; margin: 2px 4px; font-size: 0.8em; color: #ccc;
    max-height: 40vh; overflow-y: auto;
}}
#sbr-overlay .sbr-faction {{ margin-bottom: 6px; }}
#sbr-overlay .sbr-faction-name {{ font-weight: bold; margin-bottom: 2px; }}
#sbr-overlay .sbr-done {{ text-decoration: line-through; color: #888; }}
#sbr-overlay .sbr-remaining {{ color: #ccc; }}
.faction-units-summary {{
    font-size: min(0.75vw, 1.3vh); color: #777; padding-left: 4px;
}}

/* Weights panel */
#weights-panel {{
    position: fixed; bottom: 0; right: 0; width: 600px; max-height: 300px;
    background: rgba(20,20,30,0.95); border: 1px solid #555; border-radius: 4px 4px 0 0;
    font-size: 16px; padding: 10px 16px; overflow-y: auto; z-index: 100;
    display: none; font-family: monospace; color: #ccc;
}}
#weights-panel.visible {{ display: block; }}
#weights-panel .w-chosen {{ color: #4f4; font-weight: bold; }}
#weights-panel .w-option {{ color: #aaa; }}
#weights-panel .w-score {{ color: #ff4; display: inline-block; width: 70px; text-align: right; margin-right: 8px; }}
#weights-panel .w-reason {{ color: #8af; font-style: italic; }}
#weights-panel .w-header {{ color: #fff; border-bottom: 1px solid #444; margin-bottom: 6px; padding-bottom: 4px; font-size: 18px; }}
#weights-toggle {{
    position: fixed; bottom: 0; right: 610px; background: #333; color: #aaa;
    border: 1px solid #555; padding: 4px 12px; cursor: pointer; z-index: 101;
    font-size: 14px; border-radius: 4px 4px 0 0;
}}

/* Game log */
#log-panel {{
    grid-column: 1 / -1; grid-row: 2; overflow-y: auto; padding: 8px 16px;
    font-size: 12px; line-height: 1.6; background: #151515; border-top: 2px solid #333;
    height: 35vh;
}}
.log-line {{ padding: 3px 8px; border-radius: 2px; white-space: normal; word-wrap: break-word; padding-left: 20px; text-indent: -12px; font-size: 22px; }}
.log-line.current {{ background: rgba(255,255,255,0.08); border-left: 3px solid #888; padding-left: 6px; }}

/* Faction colors */
.gc {{ color: #77a055; }} .fb {{ color: #CB307E; }} .cc {{ color: #4977b3; }} .bg {{ color: #cd3233; }}
.ys {{ color: #ffd000; }} .sl {{ color: #db6a33; }} .ww {{ color: #88a9be; }} .ow {{ color: #6c4296; }}
.an {{ color: #47a5bc; }} .ts {{ color: #BDE0BC; }} .ds {{ color: #b89270; }}

.power {{ color: #4af; }} .doom {{ color: #f44; }} .es {{ color: #fc4; }}
.kill {{ color: #f44; }} .pain {{ color: #fa4; }}
.region {{ color: #ccc; }} .sea {{ color: #68b; }}
.highlight {{ color: #666; }}
</style>
</head>
<body>
<div id="container">
    <div id="map-panel">
        <img id="map-img" src="" alt="CW Map">
        <div id="map-overlay"></div>
        <div id="ritual-tracker" onclick="this.classList.toggle('expanded')" title="Click to toggle ritual tracker">
            <div id="ritual-circle">5</div>
            <div id="ritual-expanded"><img id="ritual-img" src="" alt="Ritual Track"></div>
        </div>
    </div>
    <div id="right-panel">
        <div id="controls">
            <button id="btn-prev" title="Step Back">&laquo;</button>
            <button id="btn-play" title="Play/Pause">&#9654;</button>
            <button id="btn-next" title="Step Forward">&raquo;</button>
            <div id="speed-control">
                <label>Speed:</label>
                <input type="range" id="speed-slider" min="1" max="10" value="5">
            </div>
            <button id="btn-issues" title="Show log lines the replay engine couldn't fully process">Issues</button>
            <span id="step-display">0 / 0</span>
        </div>
        <div id="issues-overlay" class="hidden">
            <div id="issues-overlay-inner">
                <div id="issues-overlay-header">
                    <span id="issues-overlay-title">Replay Engine Issues</span>
                    <button id="issues-overlay-close" title="Close">&times;</button>
                </div>
                <div id="issues-overlay-summary"></div>
                <div id="issues-overlay-list"></div>
            </div>
        </div>
        <div id="ap-buttons"></div>
        <div id="faction-panels"></div>
        <div id="sbr-overlay"></div>
    </div>
    <div id="log-panel"></div>
    <div id="weights-panel"></div>
    <div id="weights-toggle" onclick="document.getElementById('weights-panel').classList.toggle('visible')">Weights</div>
</div>

<script>
const IMAGES = {images_json};
const UNIT_IMG = {unit_img_json};
const REGION_COORDS = {region_coords_json};
const REGION_DISPLAY = {region_display_json};
const FACTION_FULL = {faction_full_json};
const SNAPSHOTS = {snapshots_json};
const DISPLAY_LINES = {display_json};
const AP_INDICES = {ap_json};
const FACTIONS = {factions_json};
const UNMATCHED_COUNT = {unmatched_count};
const ISSUES = {issues_json};
const _MAP_ID = "{map_id_str}";

const FACTION_COLORS = {json.dumps(faction_colors)};
const FACTION_BG_COLORS = {json.dumps(faction_bg_colors)};

// Unit sizes from game DrawRect (width x height), used for proportional scaling
// Scale factor: acolyte (39x60) -> ~20x30px on map, so scale ~0.5
// No separate scale — DrawRect sizes are in map pixels (1791x894).
// Units scale with the map via getUnitSize(type, mapScale).
// Library maps are 2x resolution (3582 vs 1791), so units need 2x scale to match.
const UNIT_SCALE = {unit_scale};
const UNIT_SIZES = {{
    // Cultists
    "Acolyte": [39, 60], "High Priest": [70, 68],
    // Gate
    "Gate": [76, 76],
    // GOOs
    "Cthulhu": [117, 225], "Hastur": [150, 170], "Shub-Niggurath": [132, 185],
    "Nyarlathotep": [106, 163], "Tsathoggua": [152, 146], "Ithaqua": [164, 202],
    "Yog-Sothoth": [132, 174], "Ghatanothoa": [96, 176], "Glaaki": [88, 174], "Gla'aki": [88, 174],
    // Large monsters
    "Dark Young": [83, 131], "Starspawn": [69, 70], "Hunting Horror": [166, 77],
    "Rhan-Tegoth": [153, 135], "Rhan Tegoth": [153, 135], "Yothan": [122, 90], "Revenant": [90, 105],
    "Revenant of K'Naa": [90, 105],
    // Medium monsters
    "Ghoul": [39, 47], "Nightgaunt": [69, 90], "Shoggoth": [63, 69], "Undead": [44, 54], "Fungi from Yuggoth": [39, 47],
    "Byakhee": [57, 70], "Wizard": [45, 41], "Serpent Man": [70, 85],
    "Wendigo": [56, 68], "Gnoph-Keh": [61, 95], "Mutant": [40, 58],
    "Abomination": [62, 82], "Tomb Herd": [60, 80], "Tomb-Herd": [60, 80], "Desiccated": [60, 78],
    "Deep One": [36, 31], "Tendril": [48, 70], "Deep Tendril": [60, 80],
    // Special
    "King in Yellow": [85, 116], "Formless Spawn": [78, 94], "Spawn of Yog-Sothoth": [91, 100],
    // Misc
    "Flying Polyp": [69, 90], "Fungi": [39, 47], "Reanimated": [39, 47],
    "Un-Man": [44, 54], "Cathedral": [76, 76], "Crater": [76, 76], "Ice Age": [76, 76],
    // DS units (v5.1 — added 2026-05-13)
    "Avatar Thesis": [132, 174], "Avatar Antithesis": [132, 174], "Avatar Synthesis": [132, 174],
    "Larva Thesis": [50, 64], "Larva Antithesis": [50, 64], "Larva Synthesis": [50, 64],
    "Chaos Gate": [76, 76],
}};

function getUnitSize(unitType, mapScale) {{
    const sz = UNIT_SIZES[unitType];
    // DrawRect sizes are in map pixels (1791x894). Scale to rendered map size.
    const ms = mapScale ? mapScale.scaleX * UNIT_SCALE : UNIT_SCALE;
    if (sz) return [Math.round(sz[0] * ms), Math.round(sz[1] * ms)];
    return [Math.round(39 * ms), Math.round(60 * ms)]; // default = acolyte size
}}

const MAP_W = {map_w};
const MAP_H = {map_h};

let currentStep = 0;
let playing = false;
let playTimer = null;

// ── Placement bitmap for region-constrained unit placement ──
// Same bitmap the game uses (earth35-place.webp): each region has a unique RGB color.
// Units' BASE positions are checked against this bitmap to stay within region bounds.
let placeData = null;  // Uint8ClampedArray from canvas getImageData
let placeW = 0, placeH = 0;

function getPlaceColor(mapX, mapY) {{
    if (!placeData || mapX < 0 || mapX >= placeW || mapY < 0 || mapY >= placeH) return -1;
    const idx = (mapY * placeW + mapX) * 4;
    return (placeData[idx] << 16) | (placeData[idx+1] << 8) | placeData[idx+2];
}}

function loadPlacementBitmap() {{
    return new Promise((resolve) => {{
        const src = IMAGES['place'];
        if (!src) {{ resolve(); return; }}
        const img = new Image();
        img.onload = () => {{
            const canvas = document.createElement('canvas');
            canvas.width = img.width;
            canvas.height = img.height;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0);
            const imgData = ctx.getImageData(0, 0, img.width, img.height);
            placeData = imgData.data;
            placeW = img.width;
            placeH = img.height;
            resolve();
        }};
        img.onerror = () => resolve();
        img.src = src;
    }});
}}

// ── Init ──────────────────────────────────────────────────────────
async function init() {{
    // Set map image
    document.getElementById('map-img').src = IMAGES['map'] || '';
    document.getElementById('ritual-img').src = IMAGES['ritual_track'] || '';

    // Load placement bitmap BEFORE first render so unit placement has region data
    await loadPlacementBitmap();

    // Build AP buttons
    buildAPButtons();

    // Build log
    buildLog();

    // Set initial state
    if (SNAPSHOTS.length > 0) {{
        setStep(0);
    }}

    // Controls
    document.getElementById('btn-prev').onclick = () => {{ stop(); stepBy(-1); }};
    document.getElementById('btn-next').onclick = () => {{ stop(); stepBy(1); }};
    document.getElementById('btn-play').onclick = togglePlay;

    // ── Issues overlay ──
    // Shows every game log entry the replay engine couldn't fully process:
    // (a) lines no handler claimed at all (unmatched), and (b) lines a handler
    // claimed but that left state.summary_fingerprint() unchanged
    // (matched_noop). Either is a place where the visual may diverge from the
    // real game state. Each row is clickable — clicking jumps the replay to
    // the line's step.
    function buildIssuesOverlay() {{
        const list = document.getElementById('issues-overlay-list');
        const summary = document.getElementById('issues-overlay-summary');
        if (!ISSUES || ISSUES.length === 0) {{
            summary.textContent = 'No issues found. The replay engine processed every log line and each line produced a state change.';
            list.innerHTML = '';
            return;
        }}
        let unmatched_n = 0, noop_n = 0;
        const byHandler = {{}};
        for (const it of ISSUES) {{
            if (it.kind === 'unmatched') unmatched_n++;
            else noop_n++;
            const k = it.handler || '(unmatched)';
            byHandler[k] = (byHandler[k] || 0) + 1;
        }}
        const top = Object.entries(byHandler).sort((a,b) => b[1]-a[1]).slice(0, 6)
            .map(([k,v]) => v + 'x ' + k).join(' · ');
        summary.innerHTML = '<b>' + ISSUES.length + '</b> issues: ' +
            unmatched_n + ' unmatched, ' + noop_n + ' matched-but-no-state-change. ' +
            '<span style="color:#888">Top: ' + top + '</span>';
        const rows = ISSUES.map(it => {{
            const handler = it.handler ? ' <span class="issue-handler">[' + escapeHtml(it.handler) + ']</span>' : '';
            return '<div class="issue-row" data-line="' + it.line_index + '">' +
                '<span class="issue-line-idx">#' + it.line_index + '</span>' +
                '<span class="issue-kind ' + it.kind + '">' + (it.kind === 'unmatched' ? 'UNMATCHED' : 'NO-CHANGE') + '</span>' +
                '<span class="issue-text">' + escapeHtml(it.text) + handler + '</span>' +
                '</div>';
        }}).join('');
        list.innerHTML = rows;
        // Click-to-jump: align replay to the corresponding log line if mapping exists
        list.querySelectorAll('.issue-row').forEach(row => {{
            row.onclick = () => {{
                const lineIdx = parseInt(row.dataset.line, 10);
                // The viewer indexes by snapshot, not raw log line — best-effort
                // jump: find a display line whose original line_index matches.
                let target = null;
                for (let i = 0; i < DISPLAY_LINES.length; i++) {{
                    const dl = DISPLAY_LINES[i];
                    if (dl && (dl.line_index === lineIdx || dl.line_index === undefined && i === lineIdx)) {{
                        target = i; break;
                    }}
                }}
                if (target !== null) {{ stop(); setStep(target); }}
                document.getElementById('issues-overlay').classList.add('hidden');
            }};
        }});
    }}
    function escapeHtml(s) {{
        return String(s).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]);
    }}
    const btnIssues = document.getElementById('btn-issues');
    if (ISSUES && ISSUES.length > 0) {{
        btnIssues.classList.add('has-issues');
        btnIssues.textContent = 'Issues (' + ISSUES.length + ')';
    }}
    btnIssues.onclick = () => {{
        buildIssuesOverlay();
        document.getElementById('issues-overlay').classList.remove('hidden');
    }};
    document.getElementById('issues-overlay-close').onclick = () => {{
        document.getElementById('issues-overlay').classList.add('hidden');
    }};
    document.getElementById('issues-overlay').onclick = (e) => {{
        // Close when clicking the backdrop (not the inner panel)
        if (e.target.id === 'issues-overlay') {{
            document.getElementById('issues-overlay').classList.add('hidden');
        }}
    }};

    // Keyboard
    document.addEventListener('keydown', (e) => {{
        if (e.key === 'ArrowLeft' || e.key === 'a') {{ stop(); stepBy(-1); }}
        else if (e.key === 'ArrowRight' || e.key === 'd') {{ stop(); stepBy(1); }}
        else if (e.key === ' ') {{ e.preventDefault(); togglePlay(); }}
        else if (e.key === 'Home') {{ stop(); setStep(0); }}
        else if (e.key === 'End') {{ stop(); setStep(SNAPSHOTS.length - 1); }}
    }});

    document.getElementById('step-display').textContent = `0 / ${{SNAPSHOTS.length}}` + (UNMATCHED_COUNT > 0 ? `  (${{UNMATCHED_COUNT}} ignored)` : '');
}}

function buildAPButtons() {{
    const container = document.getElementById('ap-buttons');
    container.innerHTML = '';
    for (let i = 0; i < AP_INDICES.length; i++) {{
        const btn = document.createElement('button');
        btn.textContent = `AP${{i + 1}}`;
        btn.dataset.idx = AP_INDICES[i];
        btn.onclick = () => {{ stop(); setStep(AP_INDICES[i]); }};
        container.appendChild(btn);
    }}
}}

function buildLog() {{
    const panel = document.getElementById('log-panel');
    panel.innerHTML = '';
    for (let i = 0; i < DISPLAY_LINES.length; i++) {{
        const div = document.createElement('div');
        div.className = 'log-line';
        div.id = `log-${{i}}`;

        // Use sanitized HTML preserving span classes for faction colors
        let h = DISPLAY_LINES[i].html || '';
        // Remove outer div wrapper
        h = h.replace(/<div[^>]*>/g, '').replace(/<\\/div>/g, '');
        // Remove inline-block class but keep faction class
        h = h.replace(/inline-block/g, '');
        div.innerHTML = h;

        div.onclick = () => {{ stop(); setStep(i); }};
        panel.appendChild(div);
    }}
}}

function setStep(idx) {{
    if (idx < 0) idx = 0;
    if (idx >= SNAPSHOTS.length) idx = SNAPSHOTS.length - 1;
    currentStep = idx;

    const snap = SNAPSHOTS[idx];
    updateMap(snap);
    updateFactionPanels(snap);
    updateLogHighlight(idx);
    updateWeights(idx);
    // Update ritual tracker
    const rc = snap.ritualCost || 5;
    document.getElementById('ritual-circle').textContent = rc >= 999 ? '☠' : rc;

    // Update expanded ritual tracker with ring + glyphs
    const expanded = document.getElementById('ritual-expanded');
    // Remove old overlays (keep the track image)
    expanded.querySelectorAll('.ritual-ring, .ritual-glyph').forEach(e => e.remove());

    // 4p circle positions (from calibrated overlay.scala)
    const POS4P = [
        [30.5, 53.0], [37.4, 76.0], [43.6, 53.0], [49.3, 76.0],
        [55.8, 53.0], [62.0, 76.0], [69.9, 53.0], [77.7, 76.0], [89.0, 49.0]
    ];
    const marker = snap.ritualMarker || 0;
    const history = snap.ritualHistory || [];

    // Red ring on current position
    if (marker < POS4P.length) {{
        const [cx, cy] = POS4P[marker];
        const ring = document.createElement('div');
        ring.className = 'ritual-ring';
        const isID = marker >= POS4P.length - 1;
        if (isID) {{
            ring.style.cssText = `left:${{cx}}%;top:${{cy}}%;width:20%;aspect-ratio:3;transform:translate(-50%,-50%);`;
        }} else {{
            ring.style.cssText = `left:${{cx}}%;top:${{cy}}%;width:8%;aspect-ratio:1;transform:translate(-50%,-50%);`;
        }}
        expanded.appendChild(ring);
    }}

    // Faction glyphs at completed ritual positions
    for (let i = 0; i < history.length; i++) {{
        const fc = history[i];
        const glyphSrc = IMAGES[`glyph_${{fc}}`];
        if (!glyphSrc) continue;
        const posIdx = Math.min(i, POS4P.length - 1);
        const [cx, cy] = POS4P[posIdx];
        const glyph = document.createElement('img');
        glyph.src = glyphSrc;
        glyph.className = 'ritual-glyph';
        glyph.style.cssText = `left:${{cx}}%;top:${{cy}}%;width:6%;`;
        expanded.appendChild(glyph);
    }}
    updateAPHighlight(idx);
    document.getElementById('step-display').textContent = `${{idx + 1}} / ${{SNAPSHOTS.length}}` + (UNMATCHED_COUNT > 0 ? `  (${{UNMATCHED_COUNT}} ignored)` : '');
}}

function stepBy(delta) {{
    setStep(currentStep + delta);
}}

function togglePlay() {{
    if (playing) {{
        stop();
    }} else {{
        playing = true;
        document.getElementById('btn-play').innerHTML = '&#9646;&#9646;';
        document.getElementById('btn-play').classList.add('active');
        scheduleNext();
    }}
}}

function stop() {{
    playing = false;
    if (playTimer) {{ clearTimeout(playTimer); playTimer = null; }}
    document.getElementById('btn-play').innerHTML = '&#9654;';
    document.getElementById('btn-play').classList.remove('active');
}}

function scheduleNext() {{
    if (!playing) return;
    const speed = parseInt(document.getElementById('speed-slider').value);
    const delay = Math.max(50, 1200 - speed * 110);
    playTimer = setTimeout(() => {{
        if (currentStep < SNAPSHOTS.length - 1) {{
            stepBy(1);
            scheduleNext();
        }} else {{
            stop();
        }}
    }}, delay);
}}

function getMapScale() {{
    const img = document.getElementById('map-img');
    const rect = img.getBoundingClientRect();
    // object-fit: contain with object-position: left top
    const imgAspect = MAP_W / MAP_H;
    const contAspect = rect.width / rect.height;
    let renderW, renderH, offsetX, offsetY;
    if (contAspect > imgAspect) {{
        renderH = rect.height;
        renderW = renderH * imgAspect;
        offsetX = 0;  // left-aligned
        offsetY = 0;  // top-aligned
    }} else {{
        renderW = rect.width;
        renderH = renderW / imgAspect;
        offsetX = 0;  // left-aligned
        offsetY = 0;  // top-aligned
    }}
    return {{ scaleX: renderW / MAP_W, scaleY: renderH / MAP_H, offsetX, offsetY }};
}}

function updateMap(snap) {{
    const overlay = document.getElementById('map-overlay');
    overlay.innerHTML = '';
    const scale = getMapScale();
    const mapBottom = scale.offsetY + MAP_H * scale.scaleY;

    // Collect all units by region across all factions
    const regionUnits = {{}};  // region -> [{{faction, unit, count}}]
    const regionGates = {{}};  // region -> gate_owner or null

    // Gate locations (all regions with gates, even unowned)
    for (const reg of (snap.gateLocations || [])) {{
        regionGates[reg] = '';  // exists but unowned
    }}
    // Gate owners override
    for (const [reg, owner] of Object.entries(snap.gateOwners || {{}})) {{
        regionGates[reg] = owner;  // Include abandoned gates (owner='')
    }}

    // Units
    for (const [fc, fdata] of Object.entries(snap.factions || {{}})) {{
        for (const [reg, units] of Object.entries(fdata.units || {{}})) {{
            if (!regionUnits[reg]) regionUnits[reg] = [];
            for (const [utype, count] of Object.entries(units)) {{
                if (count > 0) {{
                    regionUnits[reg].push({{ faction: fc, unit: utype, count: count }});
                }}
            }}
        }}
    }}

    // Render each region (wrapped in try/catch so glyphs always render even if placement errors)
    const allRegions = new Set([...Object.keys(regionUnits), ...Object.keys(regionGates)]);
    for (const reg of allRegions) {{ try {{
        const coords = REGION_COORDS[reg];
        if (!coords) continue;

        const [rx, ry] = coords;
        const px = scale.offsetX + rx * scale.scaleX;
        const py = Math.min(scale.offsetY + ry * scale.scaleY, mapBottom - 2);

        // Gate rendered as a separate background element behind units
        if (regionGates[reg] !== undefined) {{
            const gateContainer = document.createElement('div');
            gateContainer.style.position = 'absolute';
            gateContainer.style.left = px + 'px';
            gateContainer.style.top = py + 'px';
            gateContainer.style.transform = 'translate(-50%, -50%)';
            gateContainer.style.pointerEvents = 'none';
            gateContainer.style.zIndex = '0';

            const gateImg = document.createElement('img');
            gateImg.src = IMAGES['gate'] || '';
            gateImg.className = 'gate-icon';
            const gateSz = getUnitSize('Gate', scale);
            gateImg.style.width = gateSz[0] + 'px';
            gateImg.style.height = gateSz[1] + 'px';
            gateImg.style.position = 'static';
            const owner = regionGates[reg];
            const glowColor = owner ? (FACTION_COLORS[owner.toLowerCase()] || 'rgba(255,215,0,0.5)') : 'rgba(128,128,128,0.4)';
            gateImg.style.setProperty('--gate-glow', glowColor);
            gateImg.style.filter = `drop-shadow(0 0 8px ${{glowColor}}) drop-shadow(0 0 4px ${{glowColor}})`;
            gateImg.title = owner ? `Gate (${{FACTION_FULL[owner] || owner}})` : 'Gate (uncontrolled)';
            gateContainer.appendChild(gateImg);
            overlay.appendChild(gateContainer);
        }}

        // ── Unit placement: uses the game's placement bitmap + collision avoidance ──
        // Game code: GlyphPlacement.scala findAnother() + CthulhuWarsSolo.scala 1013-1158
        // 1. Load placement bitmap (earth35-place.webp) — each region has unique color
        // 2. Gate controller placed at gate center
        // 3. Other units: generate 40 random positions within SAME REGION (checked via
        //    placement bitmap color), pick position with minimum bounding-box overlap
        // 4. Only the unit BASE (bottom-center) must be in the region; top can extend out

        const units = regionUnits[reg] || [];
        if (units.length === 0) continue;

        const GOO_SET = new Set(['Cthulhu','Hastur','Shub-Niggurath','Nyarlathotep','Tsathoggua',
            'Ithaqua','Rhan-Tegoth','Rhan Tegoth','Yog-Sothoth','Ghatanothoa','Glaaki','Gla\\u0027aki',
            'Avatar Thesis','Avatar Antithesis','Avatar Synthesis']);
        const MONSTER_SET = new Set(['Deep One','Shoggoth','Starspawn','Ghoul','Fungi','Dark Young',
            'Nightgaunt','Flying Polyp','Hunting Horror','Undead','Byakhee','King in Yellow',
            'Wizard','Serpent Man','Formless Spawn','Wendigo','Gnoph-Keh','Mutant','Abomination',
            'Spawn of Yog-Sothoth','Un-Man','Reanimated','Yothan','Tomb Herd','Tomb-Herd','Tendril','Deep Tendril','Fungi from Yuggoth',
            'Desiccated','Revenant','Revenant of K\\u0027Naa',
            'Larva Thesis','Larva Antithesis','Larva Synthesis','Chaos Gate']);
        const unitRank = (utype) => {{
            if (GOO_SET.has(utype)) return 4;
            if (MONSTER_SET.has(utype)) return 2;
            if (utype === 'High Priest') return 1;
            if (utype === 'Acolyte') return 1;
            return 0;
        }}

        const placed = [];
        const hasGate = regionGates[reg] !== undefined;
        if (hasGate) {{
            const gateSz = getUnitSize('Gate', scale);
            placed.push({{ x: px - gateSz[0]/2, y: py - gateSz[1]/2, w: gateSz[0], h: gateSz[1] }});
        }}

        const gateOwner = regionGates[reg] || null;
        const otherUnits = [];
        let controllerUnit = null;
        for (const u of units) {{
            const isCultist = (u.unit === 'Acolyte' || u.unit === 'High Priest' || u.unit === 'Dark Young');
            if (gateOwner && u.faction === gateOwner && isCultist && !controllerUnit) {{
                controllerUnit = u;
                if (u.count > 1) otherUnits.push({{...u, count: u.count - 1}});
            }} else {{
                otherUnits.push(u);
            }}
        }}

        const placeUnit = (u, ux, uy, title, zIdx) => {{
            const imgKey = UNIT_IMG[`${{u.faction}}:${{u.unit}}`];
            const src = imgKey ? (IMAGES[imgKey] || '') : '';
            if (!src) return;
            const sz = getUnitSize(u.unit, scale);
            const div = document.createElement('div');
            div.style.cssText = `position:absolute;left:${{ux}}px;top:${{uy}}px;pointer-events:none;z-index:${{zIdx}};`;
            const img = document.createElement('img');
            img.src = src;
            img.className = 'unit-icon';
            if (u.faction === 'FB') img.classList.add('tint-fb');
            if (u.faction === 'TS') img.classList.add('tint-ts');
            img.style.width = sz[0] + 'px';
            img.style.height = sz[1] + 'px';
            img.title = title;
            div.appendChild(img);
            overlay.appendChild(div);
            placed.push({{ x: ux, y: uy, w: sz[0], h: sz[1] }});
        }}

        const overlapScore = (cx, cy, cw, ch) => {{
            let total = 0;
            const cArea = cw * ch;
            for (const p of placed) {{
                const iw = Math.min(p.x + p.w, cx + cw) - Math.max(p.x, cx);
                const ih = Math.min(p.y + p.h, cy + ch) - Math.max(p.y, cy);
                if (iw > 0 && ih > 0) {{
                    const inter = iw * ih;
                    total += inter * (1.0 / (p.w * p.h) + 1.0 / cArea);
                }}
            }}
            return total;
        }}

        // Gate controller at gate center
        if (controllerUnit) {{
            const sz = getUnitSize(controllerUnit.unit, scale);
            const ux = px - sz[0] / 2;
            const uy = py - sz[1];
            placeUnit(controllerUnit, ux, uy,
                `${{controllerUnit.faction}} ${{controllerUnit.unit}} (on gate)`, 2);
        }}

        // Flatten and sort (low rank first = placed first = most displaced, like game)
        const flatUnits = [];
        for (const u of otherUnits) {{
            for (let c = 0; c < u.count; c++) flatUnits.push(u);
        }}
        flatUnits.sort((a, b) => unitRank(a.unit) - unitRank(b.unit));

        // Game's findAnother: random pixel in placement bitmap, check same region color.
        // placeData is the Uint8ClampedArray from the placement bitmap canvas.
        // Region color at gate center = reference color for this region.
        const regionColor = placeData ? getPlaceColor(rx, ry) : null;

        // Seeded RNG for deterministic layout
        let seed = 0;
        for (let i = 0; i < reg.length; i++) seed = ((seed << 5) - seed + reg.charCodeAt(i)) | 0;
        const nextRand = () => {{ seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; }}

        for (const u of flatUnits) {{
            const sz = getUnitSize(u.unit, scale);
            let bestX = px - sz[0]/2, bestY = py - sz[1];
            let bestScore = Infinity;

            // Game's findAnother: keep generating random map positions until
            // we have 40 that are IN the same region (checked via placement bitmap).
            // Then sort by distance and pick min overlap — same as game code.
            const candidates = [];
            let maxTries = 2000;
            while (candidates.length < 40 && maxTries > 0) {{
                maxTries--;
                const mapX = Math.floor(nextRand() * MAP_W);
                const mapY = Math.floor(nextRand() * MAP_H);
                if (placeData && regionColor !== null) {{
                    const candColor = getPlaceColor(mapX, mapY);
                    if (candColor !== regionColor) continue;
                }}
                candidates.push([mapX, mapY]);
            }}
            // Sort candidates by distance (game: 5*|dx| + |dy|, closest first)
            candidates.sort((a, b) => {{
                const da = Math.abs(a[0] - rx) * 5 + Math.abs(a[1] - ry);
                const db = Math.abs(b[0] - rx) * 5 + Math.abs(b[1] - ry);
                return da - db;
            }});
            // Pick candidate with minimum overlap (ties broken by sort = closer wins)
            for (const [mapX, mapY] of candidates) {{
                const screenX = scale.offsetX + mapX * scale.scaleX - sz[0] / 2;
                const screenY = Math.min(scale.offsetY + mapY * scale.scaleY - sz[1], mapBottom - sz[1]);
                const score = overlapScore(screenX, screenY, sz[0], sz[1]);
                if (score < bestScore) {{
                    bestScore = score;
                    bestX = screenX;
                    bestY = screenY;
                }}
            }}

            placeUnit(u, bestX, bestY, `${{u.faction}} ${{u.unit}}`, 1);
        }}
    }} catch(e) {{ console.warn('Unit placement error in region ' + reg, e); }} }}

    // Render faction glyphs at starting regions — placed away from gate using bitmap
    for (const [fc, fdata] of Object.entries(snap.factions || {{}})) {{
        const startReg = fdata.startRegion;
        if (!startReg) continue;
        const coords = REGION_COORDS[startReg];
        if (!coords) continue;
        const glyphSrc = IMAGES[`glyph_${{fc}}`];
        if (!glyphSrc) continue;

        const [rx, ry] = coords;
        const px = scale.offsetX + rx * scale.scaleX;
        const py = Math.min(scale.offsetY + ry * scale.scaleY, mapBottom - 2);
        const glyphSize = Math.round(80 * scale.scaleX);
        const halfGlyph = 20; // map pixels
        const halfGate = 38;

        // Use placement bitmap to find position farthest from gate within region
        let bestGx = rx, bestGy = ry - 60; // default: above gate
        if (placeData) {{
            const regionColor = getPlaceColor(rx, ry);
            let bestScore = -1;
            // Scan candidates within 150px radius
            for (let attempt = 0; attempt < 200; attempt++) {{
                const angle = (attempt / 200) * Math.PI * 2;
                for (let dist = 40; dist <= 150; dist += 20) {{
                    const cx = Math.round(rx + Math.cos(angle) * dist);
                    const cy = Math.round(ry + Math.sin(angle) * dist);
                    if (cx < halfGlyph || cx >= MAP_W - halfGlyph || cy < halfGlyph || cy >= MAP_H - halfGlyph) continue;
                    if (getPlaceColor(cx, cy) !== regionColor) continue;
                    // Check corners fit in region
                    if (getPlaceColor(cx - halfGlyph, cy - halfGlyph) !== regionColor) continue;
                    if (getPlaceColor(cx + halfGlyph, cy + halfGlyph) !== regionColor) continue;
                    // Score: distance from gate (prefer far), penalize gate overlap
                    const dx = Math.abs(cx - rx), dy = Math.abs(cy - ry);
                    const overlap = Math.max(0, halfGate + halfGlyph - dx) * Math.max(0, halfGate + halfGlyph - dy);
                    const score = dist * 10 - overlap;
                    if (score > bestScore) {{
                        bestScore = score;
                        bestGx = cx; bestGy = cy;
                    }}
                }}
            }}
        }}

        const gpx = scale.offsetX + bestGx * scale.scaleX;
        const gpy = Math.min(scale.offsetY + bestGy * scale.scaleY, mapBottom - 2);

        const gDiv = document.createElement('div');
        gDiv.style.cssText = `position:absolute;left:${{gpx}}px;top:${{gpy}}px;transform:translate(-50%,-50%);pointer-events:none;z-index:0;opacity:1.0;`;
        const gImg = document.createElement('img');
        gImg.src = glyphSrc;
        gImg.style.cssText = `width:${{glyphSize}}px;height:${{glyphSize}}px;`;
        gDiv.appendChild(gImg);
        overlay.appendChild(gDiv);
    }}

    // Library at Celaeno: render Custodian and Librarian on map.
    //
    // Starting positions (off-region, on the lower-floor map). From the game's
    // LibraryUnitPlacement object — coords are in joined VERTICAL image space
    // (lower-floor regions sit at y >= 1792). For horizontal mode, the
    // transform is (vx, vy < 1792 ? vy : vy - 1792) for lower-floor → LEFT.
    // Library5/Library53 use the 5L starting circles; library3/library35 use 3L.
    // Librarian = LEFT circle, Custodian = RIGHT circle (game convention).
    const LIBRARY_START_COORDS = {{
        // Horizontal-mode coords (lower-floor in LEFT half, y already - 1792)
        "library5":  {{librarian: [653, 118], custodian: [1164, 118]}},
        "library53": {{librarian: [653, 118], custodian: [1164, 118]}},
        "library3":  {{librarian: [642, 167], custodian: [1092, 167]}},
        "library35": {{librarian: [642, 167], custodian: [1092, 167]}},
    }};
    const libUnits = snap.libraryUnits || {{}};
    for (const unitType of ["librarian", "custodian"]) {{
        let ux, uy;
        const regKey = libUnits[unitType];
        if (regKey) {{
            const coords = REGION_COORDS[regKey];
            if (!coords) continue;
            [ux, uy] = coords;
        }} else {{
            // Off-map starting circle for this library variant
            const start = LIBRARY_START_COORDS[_MAP_ID];
            if (!start) continue;
            [ux, uy] = start[unitType];
        }}
        const upx = scale.offsetX + ux * scale.scaleX;
        const upy = scale.offsetY + uy * scale.scaleY;
        const uDiv = document.createElement('div');
        uDiv.style.cssText = `position:absolute;left:${{upx}}px;top:${{upy}}px;transform:translate(-50%,-50%);pointer-events:none;z-index:3;`;
        const uImg = document.createElement('img');
        uImg.src = IMAGES[unitType + '-icon'] || '';
        // Librarian ~30% taller than custodian (matches game: 117x182 vs 110x110)
        const uSize = unitType === 'librarian' ? 100 : 70;
        uImg.style.cssText = `height:${{Math.round(uSize * scale.scaleX * UNIT_SCALE)}}px;opacity:0.9;`;
        uDiv.appendChild(uImg);
        overlay.appendChild(uDiv);
    }}

    // Library at Celaeno: render tomes on map at tome region positions
    const TOME_POSITIONS = {tome_positions_json};
    const tomeImgKeys = {{
        "Barrier of Naach-Tith": "tome-barrier", "Guardian under the Lake": "tome-guardian",
        "Larvae of the Outer Gods": "tome-larvae", "Yr and the Nhhngr": "tome-yr"
    }};
    const libTomes = snap.libraryTomes || {{}};
    for (const [tomeName, pos] of Object.entries(TOME_POSITIONS)) {{
        if (!pos) continue;
        const tomeInfo = libTomes[tomeName];
        const isHeld = tomeInfo && tomeInfo.holder;
        if (isHeld) continue; // Tome is on faction card, not map
        const [trx, try_] = pos;
        const tpx = scale.offsetX + trx * scale.scaleX;
        const tpy = scale.offsetY + try_ * scale.scaleY;
        const tDiv = document.createElement('div');
        tDiv.style.cssText = `position:absolute;left:${{tpx}}px;top:${{tpy}}px;transform:translate(-50%,-50%);pointer-events:none;z-index:2;`;
        const tImg = document.createElement('img');
        // Unclaimed tomes on map show the BACK (generic card)
        tImg.src = IMAGES['library-tome-card'] || '';
        tImg.style.cssText = `height:${{Math.round(80 * scale.scaleX * UNIT_SCALE)}}px;`;
        tDiv.appendChild(tImg);
        overlay.appendChild(tDiv);
    }}
}}

function updateFactionPanels(snap) {{
    lastSbrSnap = snap;
    const container = document.getElementById('faction-panels');
    container.innerHTML = '';

    for (const fc of FACTIONS) {{
        const fdata = snap.factions[fc];
        if (!fdata) continue;

        const panel = document.createElement('div');
        panel.className = 'faction-panel';

        const fcLower = fc.toLowerCase();
        const color = FACTION_COLORS[fcLower] || '#ddd';
        const bgColor = FACTION_BG_COLORS[fcLower] || '#222';

        // Header
        const header = document.createElement('div');
        header.className = 'faction-header';
        header.style.background = bgColor;

        const glyphImg = IMAGES[`glyph_${{fc}}`];
        if (glyphImg) {{
            const glyph = document.createElement('img');
            glyph.src = glyphImg;
            glyph.style.cssText = 'width:min(2vw,3vh);height:min(2vw,3vh);vertical-align:middle;margin-right:0.2vw;';
            header.appendChild(glyph);
        }}

        const name = document.createElement('span');
        name.className = 'faction-name';
        name.style.color = color;
        name.textContent = FACTION_FULL[fc] || fc;
        header.appendChild(name);

        // Library: Silence Tokens + Tomes inline with faction name
        const silTokens = snap.silenceTokens && snap.silenceTokens[fc] || 0;
        const libTomes = snap.libraryTomes || {{}};
        const heldTomes = Object.entries(libTomes).filter(([t, info]) => info.holder === fc);
        const tomeImgMapH = {{"Barrier of Naach-Tith": "tome-barrier", "Guardian under the Lake": "tome-guardian",
            "Larvae of the Outer Gods": "tome-larvae", "Yr and the Nhhngr": "tome-yr"}};
        for (let i = 0; i < silTokens; i++) {{
            const tokImg = document.createElement('img');
            tokImg.src = IMAGES['silence-token'] || '';
            tokImg.style.cssText = 'height:min(1.6vw,2.2vh);vertical-align:middle;margin-left:0.2vw;';
            header.appendChild(tokImg);
        }}
        for (const [tomeName, info] of heldTomes) {{
            const tImg = document.createElement('img');
            const imgKey = info.face_up ? (tomeImgMapH[tomeName] || 'library-tome-card') : 'library-tome-card';
            tImg.src = IMAGES[imgKey] || '';
            tImg.style.cssText = 'height:min(1.6vw,2.2vh);vertical-align:middle;margin-left:0.2vw;cursor:pointer;' + (info.overdue ? 'border:1px solid red;' : '') + (!info.face_up ? 'opacity:0.5;' : '');
            tImg.title = tomeName + (info.overdue ? ' (Overdue)' : '') + (!info.face_up ? ' (face-down)' : '');
            header.appendChild(tImg);
        }}

        panel.appendChild(header);

        // Stats
        const stats = document.createElement('div');
        stats.className = 'faction-stats';
        stats.innerHTML = `
            <span><span class="stat-label">Pwr:</span> <span class="stat-power">${{fdata.power}}</span></span>
            <span><span class="stat-label">Doom:</span> <span class="stat-doom">${{fdata.doom}}</span></span>
            <span><span class="stat-label">ES:</span> <span class="stat-es">${{fdata.esTotal !== undefined ? fdata.esTotal : fdata.es}}${{(fdata.esRevealed && fdata.esRevealed > 0) ? ' (' + fdata.esRevealed + ' revealed)' : ''}}</span></span>
            <span><span class="stat-label">Gates:</span> <span class="stat-gates">${{fdata.gates.length}}</span></span>
            ${{fdata.deaths_head !== undefined ? '<span><span class="stat-label">DH:</span> <span class="stat-dh">' + fdata.deaths_head + '</span></span>' : ''}}
            ${{fdata.ip_discount !== undefined ? '<span><span class="stat-label">IP:</span> <span class="stat-ip">' + fdata.ip_discount + '</span></span>' : ''}}
            ${{fdata.flipped_tomes !== undefined && fdata.flipped_tomes > 0 ? '<span><span class="stat-label">Tomes\u2193:</span> <span class="stat-tomes">' + fdata.flipped_tomes + '</span></span>' : ''}}
        `;
        panel.appendChild(stats);

        // Spellbooks
        if (fdata.sb && fdata.sb.length > 0) {{
            const sbDiv = document.createElement('div');
            sbDiv.className = 'faction-sb';
            for (const sb of fdata.sb) {{
                const span = document.createElement('span');
                span.className = 'sb-item';
                if (fdata.sbDown && fdata.sbDown.includes(sb)) {{
                    span.classList.add('sb-facedown');
                }}
                span.style.color = color;
                span.textContent = sb;
                sbDiv.appendChild(span);
            }}
            panel.appendChild(sbDiv);
        }}

        // Unit summary
        const unitSummary = document.createElement('div');
        unitSummary.className = 'faction-units-summary';
        const uTotals = {{}};
        for (const [reg, units] of Object.entries(fdata.units || {{}})) {{
            for (const [u, n] of Object.entries(units)) {{
                uTotals[u] = (uTotals[u] || 0) + n;
            }}
        }}
        const parts = [];
        for (const [u, n] of Object.entries(uTotals)) {{
            if (n > 0) parts.push(`${{u}} x${{n}}`);
        }}
        if (parts.length > 0) {{
            unitSummary.textContent = parts.join(', ');
        }}
        panel.appendChild(unitSummary);

        // Faction card details (submerged, captured, etc.)
        if (fdata.cardDetails && fdata.cardDetails.length > 0) {{
            const cardDiv = document.createElement('div');
            cardDiv.className = 'faction-card-details';
            cardDiv.style.cssText = 'font-size:0.7em;color:#aaa;margin-top:2px;font-style:italic;';
            cardDiv.textContent = fdata.cardDetails.join(' | ');
            panel.appendChild(cardDiv);
        }}

        // SBR count toggle
        const totalSbrs = (fdata.sbrCompleted || []).length + (fdata.sbrRemaining || []).length;
        if (totalSbrs > 0) {{
            const sbrSpan = document.createElement('span');
            sbrSpan.className = 'sbr-toggle';
            sbrSpan.style.cssText = 'font-size:0.7em;color:' + color + ';margin-left:4px;';
            sbrSpan.textContent = 'SBRs: ' + (fdata.sbrCompleted || []).length + '/' + totalSbrs;
            sbrSpan.onclick = (function(f) {{ return function() {{ toggleSbrOverlay(f); }}; }})(fc);
            panel.appendChild(sbrSpan);
        }}

        container.appendChild(panel);
    }}
}}

let lastSbrSnap = null;
let sbrOpenFaction = null;
function toggleSbrOverlay(fc) {{
    const overlay = document.getElementById('sbr-overlay');
    if (overlay.style.display === 'block' && sbrOpenFaction === fc) {{
        overlay.style.display = 'none';
        sbrOpenFaction = null;
        return;
    }}
    if (!lastSbrSnap) return;
    const fdata = lastSbrSnap.factions[fc];
    if (!fdata) return;
    const completed = fdata.sbrCompleted || [];
    const remaining = fdata.sbrRemaining || [];
    overlay.innerHTML = '';
    overlay.onclick = function() {{ overlay.style.display = 'none'; sbrOpenFaction = null; }};
    const color = FACTION_COLORS[fc.toLowerCase()] || '#ccc';
    const nameEl = document.createElement('div');
    nameEl.className = 'sbr-faction-name';
    nameEl.style.color = color;
    nameEl.textContent = (FACTION_FULL[fc] || fc) + ' SBRs (' + completed.length + '/' + (completed.length + remaining.length) + ')';
    overlay.appendChild(nameEl);
    for (const s of completed) {{
        const li = document.createElement('div');
        li.style.textDecoration = 'line-through';
        li.style.color = '#888';
        li.textContent = s;
        overlay.appendChild(li);
    }}
    for (const s of remaining) {{
        const li = document.createElement('div');
        li.style.color = '#ccc';
        li.textContent = s;
        overlay.appendChild(li);
    }}
    overlay.style.display = 'block';
    sbrOpenFaction = fc;
}}

function updateLogHighlight(idx) {{
    // Remove previous highlight
    const prev = document.querySelector('.log-line.current');
    if (prev) prev.classList.remove('current');

    const el = document.getElementById(`log-${{idx}}`);
    if (el) {{
        el.classList.add('current');
        el.scrollIntoView({{ block: 'center', behavior: 'smooth' }});
    }}
}}

function updateWeights(idx) {{
    const panel = document.getElementById('weights-panel');
    const line = DISPLAY_LINES[idx];
    if (!line || !line.weights) {{
        panel.innerHTML = '<div class="w-header">No decision data for this step</div>';
        return;
    }}
    const w = line.weights;
    let html = '<div class="w-header">Decision Weights (top 5)</div>';
    if (w.chosen) {{
        html += `<div class="w-chosen"><span class="w-score">${{w.chosen.score}}</span> ✓ ${{w.chosen.action}}</div>`;
    }}
    if (w.options) {{
        for (const opt of w.options) {{
            if (w.chosen && opt.action === w.chosen.action && opt.score === w.chosen.score) continue;
            html += `<div class="w-option"><span class="w-score">${{opt.score}}</span>   ${{opt.action}}</div>`;
        }}
    }}
    if (w.reasons && w.reasons.length > 0) {{
        html += '<div style="margin-top:4px;border-top:1px solid #333;padding-top:3px;">';
        for (const r of w.reasons) {{
            html += `<div class="w-reason">${{r.score}} = ${{r.reason}}</div>`;
        }}
        html += '</div>';
    }}
    panel.innerHTML = html;
    panel.classList.add('visible');
}}

function updateAPHighlight(idx) {{
    const buttons = document.querySelectorAll('#ap-buttons button');
    let currentAP = -1;
    for (let i = AP_INDICES.length - 1; i >= 0; i--) {{
        if (idx >= AP_INDICES[i]) {{
            currentAP = i;
            break;
        }}
    }}
    buttons.forEach((btn, i) => {{
        btn.classList.toggle('current', i === currentAP);
    }});
}}

// Handle window resize
let resizeTimer;
window.addEventListener('resize', () => {{
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {{
        if (SNAPSHOTS.length > 0) {{
            updateMap(SNAPSHOTS[currentStep]);
        }}
    }}, 100);
}});

document.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>"""

    return html_out


# ── Main ──────────────────────────────────────────────────────────────
def main():
    print(f"Loading trace: {trace_path}")
    action_strings, html_lines = load_trace(trace_path)
    print(f"  {len(action_strings)} action strings, {len(html_lines)} HTML log lines")

    print("Building state snapshots...")
    # Use new comprehensive game state engine
    import sys as _sys
    _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from build_snapshots_v2 import build_snapshots_v2
    snapshots, display_lines, ap_indices, audit = build_snapshots_v2(html_lines)
    unmatched = audit.get("unmatched", {})
    matched_noop = audit.get("matched_noop", {})
    state_map_id = audit.get("map_id")
    print(f"  {len(snapshots)} snapshots, {len(ap_indices)} AP boundaries")
    if state_map_id:
        print(f"  Map (from Options line): {state_map_id}")
    if unmatched:
        print(f"  WARNING: {sum(unmatched.values())} unmatched events (no handler):")
        for text, count in sorted(unmatched.items(), key=lambda x: -x[1])[:5]:
            print(f"    {count:3d}x {text}")
    if matched_noop:
        total_noop = sum(d["count"] for d in matched_noop.values())
        print(f"  AUDIT: {total_noop} matched-but-no-state-change events across {len(matched_noop)} handlers:")
        for handler, d in sorted(matched_noop.items(), key=lambda kv: -kv[1]["count"])[:10]:
            print(f"    {d['count']:3d}x [{handler}]")
            for ex in d["examples"]:
                print(f"           e.g. {ex}")
    # Audit RTF generation suppressed (--no-audit-rtf is default behavior now);
    # the in-viewer Issues overlay covers the same info on demand.
    if os.environ.get("WRITE_AUDIT_RTF") == "1":
        try:
            audit_rtf = os.path.splitext(output_path)[0] + "-audit.rtf"
            _write_audit_rtf(audit_rtf, audit, title)
            print(f"  Audit RTF: {audit_rtf}")
        except Exception as _e:
            print(f"  (audit RTF skipped: {_e})")

    # Determine factions from snapshots
    factions_in_game = []
    if snapshots:
        last = snapshots[-1]
        factions_in_game = list(last.get("factions", {}).keys())
    if not factions_in_game:
        # Fallback: parse from action strings
        for a in action_strings:
            m = re.match(r"StartingRegionAction\((\w+),", a)
            if m and m.group(1) not in factions_in_game:
                factions_in_game.append(m.group(1))

    print(f"  Factions: {', '.join(factions_in_game)}")

    print("Embedding images...")
    # Pre-warm image cache and store for build_html
    global _prewarmed_images
    _prewarmed_images = collect_needed_images(factions_in_game, html_lines, action_strings)
    img_count = sum(1 for v in _prewarmed_images.values() if v)
    print(f"  {img_count} images embedded (map: {_map_id})")

    print("Generating HTML...")
    total_unmatched = sum(unmatched.values())
    issues_list = audit.get("issues", [])
    html_out = build_html(snapshots, display_lines, ap_indices, factions_in_game, title,
                          total_unmatched, issues=issues_list)

    with open(output_path, "w") as f:
        f.write(html_out)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Written: {output_path} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
