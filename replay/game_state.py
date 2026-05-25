"""
Comprehensive Game State for Cthulhu Wars replay/analysis engine.
Tracks every aspect of game state, updated per log event.
"""
from dataclasses import dataclass, field
from typing import Optional, Any
from collections import defaultdict
import copy


# ── Static Roster Data ──────────────────────────────────────────────

@dataclass
class UnitDef:
    name: str
    category: str          # "GOO", "terror", "monster", "cultist", "building"
    cost: int
    count: int             # max in pool
    combat: Any = 1        # int or "dynamic:formula"
    can_control_gate: bool = False
    note: str = ""


FACTION_ROSTER = {
    "FB": {
        "full_name": "Firstborn",
        "units": [
            UnitDef("Ghatanothoa", "GOO", 6, 1, "dynamic:power"),
            UnitDef("Revenant of K'Naa", "monster", 3, 2, "dynamic:desiccated_count"),
            UnitDef("Desiccated", "monster", 2, 6, 1, note="0 on ocean"),
            UnitDef("Acolyte", "cultist", 1, 6, 0, can_control_gate=True),
            UnitDef("Crater", "building", 0, 10),
        ],
        "sbr_names": ["No Acolytes in Start Area", "Awaken Ghatanothoa", "2 Facedown Spellbooks",
                       "2nd Ghatanothoa Awakening", "Most Doom / More Gates", "3rd Ghatanothoa Awakening"],
        "no_high_priest": True,
        "library": ["Augury", "Carnage", "The Eye Opens", "Cyclopean Gaze", "Devil's Mark", "Call of the Faithful"],
        "custom_stats": {"infernal_pact_discount": 0, "ghatanothoa_awakenings": 0, "augury_kills": 0},
    },
    "GC": {
        "full_name": "Great Cthulhu",
        "units": [
            UnitDef("Cthulhu", "GOO", 4, 1, 6),
            UnitDef("Starspawn", "monster", 3, 2, 3),
            UnitDef("Shoggoth", "monster", 2, 2, 2),
            UnitDef("Deep One", "monster", 1, 4, 1),
            UnitDef("Acolyte", "cultist", 1, 6, 0, can_control_gate=True),
            UnitDef("High Priest", "cultist", 3, 1, 0, can_control_gate=True),
        ],
        "library": ["Absorb", "Devolve", "Dreams", "Regenerate", "Submerge", "Y'ha Nthlei"],
        "sbr_names": ["First Doom Phase", "Kill/Devour 1 enemy unit", "Kill/Devour 2 enemy units",
                       "Awaken Cthulhu", "Ocean gates", "Five spellbooks"],
        "custom_stats": {"submerged_region": None, "submerged_companions": []},
    },
    "BG": {
        "full_name": "Black Goat",
        "units": [
            UnitDef("Shub-Niggurath", "GOO", 8, 1, "dynamic:bg_shub"),
            UnitDef("Dark Young", "monster", 3, 3, 2, can_control_gate=True),
            UnitDef("Fungi from Yuggoth", "monster", 2, 4, 1),
            UnitDef("Ghoul", "monster", 1, 2, 0),
            UnitDef("Acolyte", "cultist", 1, 6, 0, can_control_gate=True),
            UnitDef("High Priest", "cultist", 3, 1, 0, can_control_gate=True),
        ],
        "library": ["Avatar", "Blood Sacrifice", "Frenzy", "Ghroth", "Necrophagy", "The Red Sign"],
        "sbr_names": ["Units in 4 Areas", "Units in 6 Areas", "Units in 8 Areas",
                       "Share Areas with all enemies", "Eliminate two cultists", "Awaken Shub-Niggurath"],
        "custom_stats": {},
    },
    "CC": {
        "full_name": "Crawling Chaos",
        "units": [
            UnitDef("Nyarlathotep", "GOO", 10, 1, "dynamic:cc_nyarly"),
            UnitDef("Hunting Horror", "monster", 3, 2, 2),
            UnitDef("Flying Polyp", "monster", 2, 3, 1),
            UnitDef("Nightgaunt", "monster", 1, 3, 1),
            UnitDef("Acolyte", "cultist", 1, 6, 0, can_control_gate=True),
            UnitDef("High Priest", "cultist", 3, 1, 0, can_control_gate=True),
        ],
        "library": ["Emissary", "Flight", "Harbinger", "Madness", "Seek and Destroy", "Thousand Forms"],
        "sbr_names": ["Pay 4 Power", "Pay 6 Power", "Control 3 Gates / Have 12 Power",
                       "Control 4 Gates / Have 15 Power", "Capture cultist", "Awaken Nyarlathotep"],
        "custom_stats": {},
    },
    "YS": {
        "full_name": "Yellow Sign",
        "units": [
            UnitDef("Hastur", "GOO", 10, 1, "dynamic:ritual_cost"),
            UnitDef("King in Yellow", "GOO", 4, 1, "dynamic:ys_kiy"),
            UnitDef("Byakhee", "monster", 2, 4, "dynamic:ys_byakhee"),
            UnitDef("Undead", "monster", 1, 6, "dynamic:ys_undead"),
            UnitDef("Acolyte", "cultist", 1, 6, 0, can_control_gate=True),
            UnitDef("High Priest", "cultist", 3, 1, 0, can_control_gate=True),
        ],
        "library": ["Desecration", "Feast", "Passion", "Screaming Dead", "Shriek of the Byakhee", "The Third Eye"],
        "sbr_names": ["Provide 3 Doom", "Awaken King in Yellow", "Desecrate /^\\ Glyph",
                       "Desecrate (*) Glyph", "Desecrate ||| Glyph", "Awaken Hastur"],
        "custom_stats": {"desecrated_regions": []},
    },
    "OW": {
        "full_name": "Opener of the Way",
        "units": [
            UnitDef("Yog-Sothoth", "GOO", 6, 1, "dynamic:ow_yog"),
            UnitDef("Spawn of Yog-Sothoth", "monster", 4, 2, 3),
            UnitDef("Abomination", "monster", 3, 3, 2),
            UnitDef("Mutant", "monster", 2, 4, 1),
            UnitDef("Acolyte", "cultist", 1, 6, 0, can_control_gate=True),
            UnitDef("High Priest", "cultist", 3, 1, 0, can_control_gate=True),
        ],
        "library": ["Beyond One", "Dread Curse of Azathoth", "Interstellar Travel", "Million Favored Ones", "The Key and the Gate", "They Break Through"],
        "sbr_names": ["8 gates on map", "10 gates on map", "12 gates on map",
                       "Units at 2 enemy gates", "Lose unit in battle", "Awaken Yog-Sothoth"],
        "custom_stats": {},
    },
    "SL": {
        "full_name": "Sleeper",
        "units": [
            UnitDef("Tsathoggua", "GOO", 8, 1, "dynamic:sl_tsath"),
            UnitDef("Formless Spawn", "monster", 3, 4, "dynamic:sl_fs"),
            UnitDef("Serpent Man", "monster", 2, 3, 1),
            UnitDef("Wizard", "monster", 1, 2, 0),
            UnitDef("Acolyte", "cultist", 1, 6, 0, can_control_gate=True),
            UnitDef("High Priest", "cultist", 3, 1, 0, can_control_gate=True),
        ],
        "library": ["Ancient Sorcery", "Cursed Slumber", "Death From Below", "Demand Sacrifice", "Lethargy", "Capture Monster"],
        "sbr_names": ["Pay 3 Someone gains 3", "Pay 3 Everybody gains 1", "Pay 3 Everybody loses 1",
                       "Roll 6 dice in Battle", "Perform ritual", "Awaken Tsathoggua"],
        "custom_stats": {"cursed_slumber_units": []},
    },
    "WW": {
        "full_name": "Windwalker",
        "units": [
            UnitDef("Ithaqua", "GOO", 6, 1, "dynamic:ww_ithaqua"),
            UnitDef("Rhan Tegoth", "GOO", 6, 1, 3),
            UnitDef("Gnoph-Keh", "monster", "dynamic:ww_gnoph_cost", 4, 3),
            UnitDef("Wendigo", "monster", 1, 4, 1),
            UnitDef("Acolyte", "cultist", 1, 6, 0, can_control_gate=True),
            UnitDef("High Priest", "cultist", 3, 1, 0, can_control_gate=True),
        ],
        "library": ["Arctic Wind", "Berserkergang", "Cannibalism", "Herald of the Outer Gods", "Howl", "Ice Age"],
        "sbr_names": ["Starting Player", "Opposite Gate", "Another Faction All Spellbooks",
                       "Anytime Spellbook", "Awaken Rhan Tegoth", "Awaken Ithaqua"],
        "custom_stats": {"ice_age_region": None, "hibernating": False},
    },
    "AN": {
        "full_name": "The Ancients",
        "units": [
            UnitDef("Yothan", "terror", 6, 3, 7),
            UnitDef("Reanimated", "monster", 4, 3, 2),
            UnitDef("Un-Man", "monster", 3, 3, 1),
            UnitDef("Cathedral", "building", 3, 6),
            UnitDef("Acolyte", "cultist", 1, 6, 0, can_control_gate=True),
            UnitDef("High Priest", "cultist", 3, 1, 0, can_control_gate=True),
        ],
        "library": ["Dematerialization", "Festival", "Lineage", "Omen", "Unholy Ground", "Zingaya"],
        "sbr_names": ["Cathedral /^\\ Glyph", "Cathedral (*) Glyph", "Cathedral ||| Glyph",
                       "Cathedral no Glyph", "Give lowest cost monster", "Give highest cost monster"],
        "custom_stats": {},
    },
    "TS": {
        "full_name": "Tombstalker",
        "units": [
            UnitDef("Gla'aki", "GOO", 6, 1, "dynamic:ts_glaaki"),
            UnitDef("Deep Tendril", "monster", 3, 3, "dynamic:ts_tendril"),
            UnitDef("Tomb-Herd", "monster", 2, 6, "dynamic:ts_tombherd"),
            UnitDef("Acolyte", "cultist", 1, 6, 0, can_control_gate=True),
        ],
        "no_high_priest": True,
        "library": ["Death March", "Eleven Revelations", "Green Decay", "Grasping Dead", "Oleaginous", "Shepherd of the Crypt"],
        "sbr_names": ["Awaken Gla'aki", "Tomb-Herd Killed", "Roll a Kill",
                       "Roll 3 Pains", "Gla'aki battled GOO", "Ritual OR Control Enemy Gate"],
        "custom_stats": {"deaths_head": 0, "cursed_tomes_owned": [], "cursed_tomes_on_card": []},
    },
    "DS": {
        "full_name": "Daemon Sultan",
        "units": [
            UnitDef("Avatar Thesis", "GOO", 0, 1, "dynamic:ds_thesis",
                    note="cost is azathoth_track at awaken time; combat = azathoth_track"),
            UnitDef("Avatar Antithesis", "GOO", 8, 1, "dynamic:ds_antithesis",
                    note="cost = 8 - azathoth_track; combat = 8 - azathoth_track"),
            UnitDef("Avatar Synthesis", "GOO", 8, 1, "dynamic:ds_synthesis",
                    note="combat = azathoth die roll (max 1)"),
            UnitDef("Larva Thesis", "monster", 1, 2, 0, note="feeds Avatar Thesis combat"),
            UnitDef("Larva Antithesis", "monster", 1, 2, 0, note="feeds Avatar Antithesis combat"),
            UnitDef("Larva Synthesis", "monster", 1, 2, 0, note="feeds Avatar Synthesis combat"),
            UnitDef("Chaos Gate", "building", 0, 3, 0, can_control_gate=True,
                    note="treated as a gate; abandoned-gate satisfaction"),
            UnitDef("Acolyte", "cultist", 1, 6, 0, can_control_gate=True),
            UnitDef("High Priest", "cultist", 3, 1, 0, can_control_gate=True),
        ],
        "library": ["Animate Matter", "Chaos Gate", "Consummation", "Fiendish Growth",
                    "Traitors", "Undirected Energy"],
        "sbr_names": ["One Larva of Each Type", "Abandoned Gate at Gather Power",
                       "Power/Doom Offer", "Awaken Avatar Thesis",
                       "Awaken Avatar Antithesis", "Awaken Avatar Synthesis"],
        # azathoth_track: 0..8 set when Avatar Thesis is awakened, drives strength of
        #   Thesis (= track) and Antithesis (= 8 - track); also determines bidding
        #   strength for the Azathoth Synthesis auction.
        # azathoth_die: most recent Azathoth combat die roll, used by AvatarSynthesis
        #   combat strength.
        # chaos_gates: list of regions where DS has placed a Chaos Gate.
        "custom_stats": {"azathoth_track": 0, "azathoth_die": 0, "chaos_gates": []},
    },
}

# Gate-controlling unit types across all factions
GATE_CONTROLLERS = {"Acolyte", "High Priest", "Dark Young"}

# iGOO (Independent Great Old Ones) — neutral GOOs that any faction can awaken
# [2026-05-24] MNU build adds 10 new IGOOs.
IGOO_NAMES = {"Byatis", "Abhoth", "Daoloth", "Nyogtha", "Tulzscha", "Y'Golonac",
              "Azathoth", "Cthugha", "Mother Hydra", "Yig", "Father Dagon",
              "The Bloated Woman", "Bloated Woman", "Atlach-Nacha", "Bokrug",
              "Gla'aki (IGOO)"}
IGOO_COSTS = {"Byatis": 4, "Abhoth": 4, "Daoloth": 6, "Nyogtha": 6, "Tulzscha": 4, "Y'Golonac": 2,
              "Azathoth": 8, "Cthugha": 6, "Mother Hydra": 4, "Yig": 4,
              "Father Dagon": 4, "The Bloated Woman": 4, "Bloated Woman": 4,
              "Atlach-Nacha": 4, "Bokrug": 6, "Gla'aki (IGOO)": 6}

# Neutral monster unit names (from loyalty cards).
# [2026-05-24] MNU build adds 14 new monsters/terrors.
NEUTRAL_MONSTERS = {"Ghast", "Gug", "Shantak", "Star Vampire", "Voonith", "Dimensional Shambler", "Gnorri", "Filth",
                    # MNU monsters
                    "Moonbeast", "Giant Blind Albino Penguins", "Albino Penguins",
                    "Elder Thing", "Leng Spider", "Satyr",
                    "Insects from Shaggai", "Parasitized Acolyte",
                    "Servitor of the Outer Gods",
                    # MNU terrors
                    "Dhole", "Great Race of Yith", "Quachil Uttaus",
                    "The Shadow Pharaoh", "Hound of Tindalos",
                    "Brown Jenkin", "Elder Shoggoth"}

# All GOO names for uniqueness enforcement
ALL_GOOS = set()
for fc, data in FACTION_ROSTER.items():
    for u in data["units"]:
        if u.category == "GOO":
            ALL_GOOS.add(u.name)
ALL_GOOS.update(IGOO_NAMES)


# ── State Dataclasses ───────────────────────────────────────────────

@dataclass
class SpellbookEntry:
    name: str
    face_up: bool = True


@dataclass
class RequirementEntry:
    text: str
    complete: bool = False


@dataclass
class CapturedUnit:
    owner_faction: str
    unit_name: str
    quantity: int = 1


@dataclass
class RegionUnit:
    name: str
    category: str      # GOO/terror/monster/cultist/building
    quantity: int
    on_gate: bool = False


@dataclass
class GateInfo:
    exists: bool = False
    owner: Optional[str] = None   # faction code or None (abandoned)


@dataclass
class BuildingInfo:
    type: str          # "Cathedral", "Crater", "Desecration"
    faction: str       # owning faction code


@dataclass
class RegionState:
    """State of a single map region. Units are stored per-faction as lists of RegionUnit.
    Buildings (Cathedrals, Craters) are tracked separately from units.
    Gates are tracked via GateInfo which records existence and current owner."""
    name: str
    display_name: str
    is_ocean: bool = False
    gate: GateInfo = field(default_factory=GateInfo)
    buildings: list = field(default_factory=list)
    units: dict = field(default_factory=lambda: defaultdict(list))
    # units[faction_code] = [RegionUnit, ...]

    def get_unit_count(self, faction: str, unit_name: str) -> int:
        for u in self.units.get(faction, []):
            if u.name == unit_name:
                return u.quantity
        return 0

    def add_unit(self, faction: str, unit_name: str, quantity: int = 1, category: str = ""):
        for u in self.units.get(faction, []):
            if u.name == unit_name:
                u.quantity += quantity
                return
        if faction not in self.units:
            self.units[faction] = []
        cat = category or _get_category(unit_name)
        self.units[faction].append(RegionUnit(unit_name, cat, quantity))

    def remove_unit(self, faction: str, unit_name: str, quantity: int = 1) -> bool:
        for u in self.units.get(faction, []):
            if u.name == unit_name and u.quantity >= quantity:
                u.quantity -= quantity
                if u.quantity <= 0:
                    self.units[faction].remove(u)
                return True
        return False

    def has_unit(self, faction: str, unit_name: str) -> bool:
        return self.get_unit_count(faction, unit_name) > 0

    def faction_units(self, faction: str) -> list:
        return self.units.get(faction, [])

    def all_enemy_units(self, exclude_faction: str) -> list:
        result = []
        for fc, units in self.units.items():
            if fc != exclude_faction:
                result.extend(units)
        return result

    def has_enemy_goo(self, exclude_faction: str) -> bool:
        for u in self.all_enemy_units(exclude_faction):
            if u.category == "GOO" and u.quantity > 0:
                return True
        return False

    def enemy_cultist_count(self, exclude_faction: str) -> int:
        total = 0
        for u in self.all_enemy_units(exclude_faction):
            if u.category == "cultist" and u.quantity > 0:
                total += u.quantity
        return total

    def total_units(self, faction: str) -> int:
        return sum(u.quantity for u in self.units.get(faction, []))


def _get_category(unit_name: str) -> str:
    if unit_name in ALL_GOOS:
        return "GOO"
    for fc, data in FACTION_ROSTER.items():
        for u in data["units"]:
            if u.name == unit_name:
                return u.category
    # Fallback heuristics
    if unit_name in ("Acolyte", "High Priest"):
        return "cultist"
    if unit_name in ("Cathedral", "Crater"):
        return "building"
    return "monster"


@dataclass
class FactionState:
    """Per-faction state: power/doom/ES economy, unit pool, captured prisoners,
    spellbooks with face-up/down tracking, controlled gates, and faction-specific
    custom stats (submerged companions, cursed slumber, deaths head, etc.)."""
    code: str
    name: str = ""
    power: int = 8
    doom: int = 0
    elder_signs_hidden: int = 0
    elder_signs_revealed: list = field(default_factory=list)

    # Pool tracking (units NOT on map)
    pool: dict = field(default_factory=lambda: defaultdict(int))

    # Captured prisoners
    captured: list = field(default_factory=list)

    # Spellbooks
    spellbooks: list = field(default_factory=list)
    requirements: list = field(default_factory=list)

    # Gates controlled
    gates: set = field(default_factory=set)

    # Starting region
    start_region: Optional[str] = None

    # Faction-specific custom stats
    custom: dict = field(default_factory=dict)

    # Flipped tomes (cursed tomes held face-down — doom penalty at game end)
    flipped_tomes: int = 0

    def has_spellbook(self, name: str) -> bool:
        return any(s.name == name for s in self.spellbooks)

    def spellbook_face_up(self, name: str) -> bool:
        for s in self.spellbooks:
            if s.name == name:
                return s.face_up
        return False

    def add_spellbook(self, name: str):
        if not self.has_spellbook(name):
            self.spellbooks.append(SpellbookEntry(name, True))

    def flip_spellbook(self, name: str, face_up: bool):
        for s in self.spellbooks:
            if s.name == name:
                s.face_up = face_up
                return

    def init_pool(self):
        """Initialize unit pool from FACTION_ROSTER. All non-building units start
        in pool at max count; they leave pool when placed on map via place_unit()."""
        roster = FACTION_ROSTER.get(self.code, {})
        for u in roster.get("units", []):
            if u.category != "building":
                self.pool[u.name] = u.count
        self.custom = dict(roster.get("custom_stats", {}))
        self.name = roster.get("full_name", self.code)

    def to_dict(self):
        """Serialize to dict for JS viewer. Builds cardDetails list from custom
        state (captured prisoners, submerged units, cursed slumber, deaths head, etc.)
        and SBR completion status for display in faction panel."""
        card_details = []
        if self.captured:
            cap_summary = {}
            for c in self.captured:
                key = f"{c.get('unit','?')}"
                cap_summary[key] = cap_summary.get(key, 0) + c.get('qty', 1)
            cap_str = ", ".join(f"{v}x {k}" for k, v in cap_summary.items())
            card_details.append(f"Captured: {cap_str}")
        # Submerged (GC)
        sub = self.custom.get("submerged_region")
        if sub:
            card_details.append(f"Submerged in {sub}")
        # Cursed Slumber (SL)
        cs = self.custom.get("cursed_slumber_units")
        if cs:
            card_details.append(f"Cursed Slumber: {len(cs)} units")
        # Deaths Head (TS)
        dh = self.custom.get("deaths_head")
        if dh and dh > 0:
            card_details.append(f"Death's Head: {dh}")
        # Infernal Pact discount (FB)
        ip = self.custom.get("infernal_pact_discount")
        if ip and ip > 0:
            card_details.append(f"IP discount: {ip}")

        # SBR status — match achieved requirements against predefined SBR names
        completed_reqs = set(r.text.strip() for r in self.requirements if r.complete)
        roster = FACTION_ROSTER.get(self.code, {})
        all_sbrs = roster.get("sbr_names", [])
        # Alternate names for SBRs that can be achieved in multiple ways
        SBR_ALTS = {
            "Most Doom / More Gates": ["Most Doom", "More Gates than First Player"],
        }
        completed_sbrs = []
        remaining_sbrs = []
        for sbr in all_sbrs:
            alts = SBR_ALTS.get(sbr, [sbr])
            matched = False
            for alt in alts:
                for cr in completed_reqs:
                    if alt.lower() in cr.lower() or cr.lower() in alt.lower():
                        matched = True
                        break
                if matched:
                    break
            if not matched:
                for cr in completed_reqs:
                    if sbr.lower() in cr.lower() or cr.lower() in sbr.lower():
                        matched = True
                        break
            if matched:
                completed_sbrs.append(sbr)
            else:
                remaining_sbrs.append(sbr)

        # v5 (2026-05-13): also expose esRevealed and esTotal so the panel can
        # show the running total earned (hidden + revealed), not just the
        # current hidden count which goes to 0 after a reveal.
        return {
            "code": self.code,
            "name": self.name,
            "power": self.power,
            "doom": self.doom,
            "es": self.elder_signs_hidden,
            "esRevealed": len(self.elder_signs_revealed),
            "esTotal": self.elder_signs_hidden + len(self.elder_signs_revealed),
            "gates": sorted(self.gates),
            "sb": [s.name for s in self.spellbooks],
            "sbDown": sorted([s.name for s in self.spellbooks if not s.face_up]),
            "startRegion": self.start_region,
            "cardDetails": card_details,
            "sbrCompleted": completed_sbrs,
            "sbrRemaining": remaining_sbrs,
            **({"deaths_head": self.custom.get("deaths_head")} if "deaths_head" in self.custom else {}),
            **({"ip_discount": self.custom.get("infernal_pact_discount")} if "infernal_pact_discount" in self.custom else {}),
            "flipped_tomes": self.flipped_tomes,
        }


@dataclass
class BattleState:
    region: Optional[str] = None
    attacker: Optional[str] = None
    defender: Optional[str] = None


@dataclass
class EventRecord:
    line_index: int
    plain_text: str
    matched: bool = False
    handler_name: Optional[str] = None
    state_changed: bool = False
    changes: list = field(default_factory=list)
    faction: Optional[str] = None


OCEAN_REGIONS = {
    "ArcticOcean", "NorthAtlantic", "SouthAtlantic",
    "NorthPacific", "SouthPacific", "IndianOcean"
}

REGION_NAMES = [
    "ArcticOcean", "Scandinavia", "Europe", "NorthAsia", "SouthAsia", "Arabia",
    "EastAfrica", "WestAfrica", "NorthAtlantic", "SouthAtlantic", "Antarctica",
    "SouthPacific", "SouthAmerica", "NorthAmerica", "NorthPacific", "IndianOcean", "Australia",
    # Library at Celaeno regions
    "FloatingTower", "Byakhiary", "Horrorium", "Fountain", "YrandtheNhhngr",
    "GuardianundertheLake", "Gloomloft", "CursedHall", "BarrierofNaach-Tith",
    "LarvaeoftheOuterGods", "LakeofHaliOverlook", "LakeofHaliBalcony",
    "ChamberofSn'gac", "Oubliette", "BlueHall", "ScorchedChamber", "PorphyrHall",
    "RedHall", "BlackHall", "ChamberofApkallu", "Hyperquarium", "CharnelHall", "TheCrawlingOnes",
]


class FullGameState:
    """Central game state mutated by event handlers. Owns all regions (17 land/ocean),
    all faction states, ritual track, battle context, and accumulated debug weights.
    Cloneable via deepcopy; serializable to snapshot dict via to_snapshot()."""
    def __init__(self):
        self.round_num = 0
        self.phase = "setup"
        self.active_faction: Optional[str] = None
        self.faction_order: list = []
        self.first_player: Optional[str] = None

        self.factions: dict[str, FactionState] = {}
        self.regions: dict[str, RegionState] = {}

        # Special pseudo-regions
        self.submerged = RegionState("Submerged", "Submerged")
        self.faction_cards: dict[str, RegionState] = {}
        self.cursed_slumber = RegionState("CursedSlumber", "Cursed Slumber")

        # Ritual tracking
        self.ritual_cost = 5
        self.ritual_marker = 0
        self.ritual_track = [5, 6, 7, 7, 8, 8, 9, 10, 999]
        self.ritual_history: list = []

        # Battle
        self.battle = BattleState()
        self.effect_region: Optional[str] = None

        # Writhe undo stacks (FB) — kept so undo events can reverse prior writhe
        # kills (acolyte→desc swap) and pain relocations within a single writhe.
        # Each kill entry:  ("kill", region, unit_class_killed)
        # Each pain entry:  ("pain", unit_name, from_region, to_region)
        self.writhe_action_stack: list = []

        # Global state
        self.cathedrals: list = []
        self.desecrated: list = []
        self.ice_ages: list = []
        self.craters: list = []
        self.deaths_head: int = 0
        self.gate_locations: set = set()

        # Variant flags
        self.variant_flags: list = []

        # Event tracking
        self.events: list = []
        self._pending_weights: list = []

        # Map identification + map-specific objects (first-class state, so
        # changes to them participate in summary_fingerprint and the
        # matched-no-state-change audit). map_id is set from the "Options"
        # log line (e.g., "MapLibrary35" / "MapLibrary53" / "MapEarth35").
        # Library-only objects stay as empty dicts on non-Library maps.
        self.map_id: Optional[str] = None
        # Library at Celaeno state — promoted from prior getattr-based
        # dicts so it's part of FullGameState's initialized contract.
        self.library_tomes: dict = {}      # tome_name -> {"face_up": bool, "holder": faction_code | None}
        self.silence_tokens: dict = {}     # faction_code -> count
        self.library_units: dict = {}      # "custodian"/"librarian" -> region_key

        # Init regions
        for rname in REGION_NAMES:
            display = ""
            for c in rname:
                if c.isupper() and display:
                    display += " "
                display += c
            self.regions[rname] = RegionState(
                name=rname,
                display_name=display,
                is_ocean=(rname in OCEAN_REGIONS)
            )

    def ensure_faction(self, code: str):
        if code not in self.factions:
            fs = FactionState(code)
            fs.init_pool()
            self.factions[code] = fs
            if code not in self.faction_order:
                self.faction_order.append(code)

    def get_region(self, region_key: str) -> Optional[RegionState]:
        return self.regions.get(region_key)

    def find_unit(self, faction: str, unit_name: str) -> Optional[str]:
        for rkey, reg in self.regions.items():
            if reg.has_unit(faction, unit_name):
                return rkey
        return None

    def remove_unit_anywhere(self, faction: str, unit_name: str) -> Optional[str]:
        """Remove a unit from the map, returning it to pool. Tries effect_region and
        battle region first (most kills happen there), then searches all regions."""
        for try_reg in [self.effect_region, self.battle.region]:
            if try_reg and try_reg in self.regions:
                if self.regions[try_reg].remove_unit(faction, unit_name):
                    fs = self.factions.get(faction)
                    if fs:
                        fs.pool[unit_name] = fs.pool.get(unit_name, 0) + 1
                    return try_reg
        # Search all regions
        for rkey, reg in self.regions.items():
            if reg.remove_unit(faction, unit_name):
                fs = self.factions.get(faction)
                if fs:
                    fs.pool[unit_name] = fs.pool.get(unit_name, 0) + 1
                return rkey
        return None

    def place_unit(self, faction: str, unit_name: str, region_key: str):
        reg = self.regions.get(region_key)
        if not reg:
            return
        reg.add_unit(faction, unit_name)
        fs = self.factions.get(faction)
        if fs:
            if fs.pool.get(unit_name, 0) > 0:
                fs.pool[unit_name] -= 1

    def move_unit(self, faction: str, unit_name: str, src: str, dst: str):
        src_reg = self.regions.get(src)
        dst_reg = self.regions.get(dst)
        if src_reg and dst_reg:
            if src_reg.remove_unit(faction, unit_name):
                dst_reg.add_unit(faction, unit_name)

    def relocate_unit(self, faction: str, unit_name: str, dst: str) -> Optional[str]:
        """Move a unit to dst from wherever it currently is. Returns the source
        region (or None if no unit was found to move). Used by retreat / flight /
        scream / follow-along handlers where the source region isn't always
        encoded in the log line but the destination is.

        When multiple instances of the unit exist on the map, prefer a source
        that is NOT dst (otherwise the call would be a no-op when one instance
        already happens to be at dst, e.g. after a prior incomplete handler)."""
        dst_reg = self.regions.get(dst)
        if not dst_reg:
            return None
        # Find a source region that is NOT dst (preferred over finding "any")
        src = None
        for rkey, reg in self.regions.items():
            if rkey == dst:
                continue
            if reg.has_unit(faction, unit_name):
                src = rkey
                break
        if src is None:
            # Fallback: even if the unit is at dst, no other instance exists.
            # Don't move at all in that case (the visual is already correct).
            if dst_reg.has_unit(faction, unit_name):
                return dst
        if src:
            self.move_unit(faction, unit_name, src, dst)
            return src
        # Try pseudo-regions (submerged, cursed_slumber, faction_cards)
        for pseudo in (self.submerged, self.cursed_slumber):
            if pseudo.has_unit(faction, unit_name):
                pseudo.remove_unit(faction, unit_name)
                dst_reg.add_unit(faction, unit_name)
                return pseudo.name
        for card_fc, card in self.faction_cards.items():
            if card.has_unit(faction, unit_name):
                card.remove_unit(faction, unit_name)
                dst_reg.add_unit(faction, unit_name)
                return f"card.{card_fc}"
        # Fallback: place from pool
        self.place_unit(faction, unit_name, dst)
        return None

    def clone(self):
        return copy.deepcopy(self)

    def to_snapshot(self) -> dict:
        """Freeze current state to a JSON-serializable dict for the JS viewer.
        Builds units_by_region from RegionState data to match the JS viewer's
        expected format: factions.FC.units.RegionKey.UnitName = count."""
        factions_dict = {}
        for code, fs in self.factions.items():
            # Build units_by_region for backward compat with JS viewer
            units = {}
            for rkey, reg in self.regions.items():
                for u in reg.faction_units(code):
                    if u.quantity > 0:
                        if rkey not in units:
                            units[rkey] = {}
                        units[rkey][u.name] = u.quantity
            fd = fs.to_dict()
            fd["units"] = units
            factions_dict[code] = fd

        gate_owners = {}
        gate_locs = sorted(self.gate_locations)
        for rkey, reg in self.regions.items():
            if reg.gate.exists:
                gate_owners[rkey] = reg.gate.owner or ""

        # Library at Celaeno state. Critical: copy these mutable dicts so each
        # snapshot freezes the state AS OF that frame. Without copies, the JS
        # viewer would see the final state at every frame — making custodian/
        # librarian appear in their last-known regions from the very first
        # frame, never reflecting earlier moves.
        import copy as _copy
        lib_tomes = _copy.deepcopy(self.library_tomes)
        sil_tokens = dict(self.silence_tokens)
        lib_units = dict(self.library_units)

        return {
            "round": self.round_num,
            "ritualCost": self.ritual_cost,
            "ritualMarker": self.ritual_marker,
            "ritualHistory": list(self.ritual_history),
            "factions": factions_dict,
            "gateOwners": gate_owners,
            "gateLocations": gate_locs,
            "libraryTomes": lib_tomes,
            "silenceTokens": sil_tokens,
            "libraryUnits": lib_units,
        }

    def summary_fingerprint(self) -> str:
        """Compact string encoding the FULL game state for every faction
        (all 11: GC/CC/BG/YS/SL/WW/OW/AN/TS/FB/DS), all units in all regions
        (both Earth and Library maps), all faction-specific custom stats
        (DS azathoth_track, FB infernal_pact_discount/ghatanothoa_awakenings,
        TS deaths_head/cursed_tomes, etc.), and all globals.

        Used by process_line() to detect whether a handler changed game state,
        and by build_snapshots_v2 to flag handlers that match a line but leave
        state unchanged.

        Any addition to a faction's visible state (pool counts, ES, captured
        cultists, SB face-up status, requirements, gates, etc.) participates
        in the fingerprint so changes register in the audit.
        """
        parts = []
        # ── Map + phase ────────────────────────────────────────────────
        if self.map_id:
            parts.append(f"map={self.map_id}")
        parts.append(f"round={self.round_num}")
        if self.first_player:
            parts.append(f"fp={self.first_player}")
        if self.active_faction:
            parts.append(f"af={self.active_faction}")
        parts.append(f"rcost={self.ritual_cost}")
        parts.append(f"rmark={self.ritual_marker}")
        # ── Per-faction full state ─────────────────────────────────────
        for code in sorted(self.factions.keys()):
            fs = self.factions[code]
            # Spellbooks (with per-SB face-up status)
            sb_list = sorted(
                (f"{getattr(s, 'name', s)}{'^' if getattr(s, 'face_up', True) else 'v'}"
                 for s in (getattr(fs, "spellbooks", []) or [])),
            )
            sb = ",".join(sb_list)
            # Elder signs: hidden count + revealed list (face values matter)
            esh = getattr(fs, "elder_signs_hidden", 0) or 0
            esr = sorted(getattr(fs, "elder_signs_revealed", []) or [])
            esr_s = ",".join(str(v) for v in esr)
            gates = len(getattr(fs, "gates", []) or [])
            captured = len(getattr(fs, "captured", []) or [])
            reqs = len(getattr(fs, "requirements", []) or [])
            ftomes = getattr(fs, "flipped_tomes", 0) or 0
            parts.append(
                f"{code}:p{fs.power}d{fs.doom}g{gates}esh{esh}esr[{esr_s}]"
                f"sb[{sb}]cap{captured}req{reqs}ft{ftomes}"
            )
            # Pool counts (units NOT on map; changes when units placed/eliminated)
            pool = getattr(fs, "pool", None) or {}
            for uname in sorted(pool):
                v = pool[uname]
                if v:
                    parts.append(f"{code}.pool.{uname}={v}")
            # Faction-specific custom stats: DS azathoth_track, FB
            # infernal_pact_discount, TS deaths_head, etc. Stringified so
            # nested values (lists/dicts) participate.
            custom = getattr(fs, "custom", None) or {}
            for k in sorted(custom):
                parts.append(f"{code}.custom.{k}={custom[k]}")
        # ── Unit positions on map ──────────────────────────────────────
        for rkey in sorted(self.regions.keys()):
            reg = self.regions[rkey]
            if reg.gate.exists:
                parts.append(f"{rkey}.gate={reg.gate.owner or ''}")
            for fc, units in sorted(reg.units.items()):
                for u in units:
                    if u.quantity > 0:
                        parts.append(f"{rkey}.{fc}.{u.name}={u.quantity}")
        # ── Pseudo-regions: Submerged, CursedSlumber, faction-cards ────
        for pseudo_name, pseudo in (("Submerged", self.submerged),
                                    ("CursedSlumber", self.cursed_slumber)):
            for fc, units in sorted(pseudo.units.items()):
                for u in units:
                    if u.quantity > 0:
                        parts.append(f"{pseudo_name}.{fc}.{u.name}={u.quantity}")
        for fc, card in sorted(self.faction_cards.items()):
            for sub_fc, units in sorted(card.units.items()):
                for u in units:
                    if u.quantity > 0:
                        parts.append(f"card.{fc}.{sub_fc}.{u.name}={u.quantity}")
        # ── Library at Celaeno state ───────────────────────────────────
        for tome in sorted(self.library_tomes.keys()):
            t = self.library_tomes[tome]
            holder = t.get("holder", "") if isinstance(t, dict) else ""
            face_up = t.get("face_up", True) if isinstance(t, dict) else True
            overdue = t.get("overdue", False) if isinstance(t, dict) else False
            parts.append(f"tome.{tome}={'up' if face_up else 'dn'}/{holder or '-'}{'/od' if overdue else ''}")
        for fc in sorted(self.silence_tokens.keys()):
            parts.append(f"silence.{fc}={self.silence_tokens[fc]}")
        for unit_type in sorted(self.library_units.keys()):
            parts.append(f"libunit.{unit_type}={self.library_units[unit_type]}")
        # ── Battle state (live battle visible in viewer) ───────────────
        b = self.battle
        if getattr(b, "region", None):
            atk = getattr(b, "attacker", "") or ""
            dfn = getattr(b, "defender", "") or ""
            parts.append(f"battle={b.region}/{atk}vs{dfn}")
        # ── Globals ────────────────────────────────────────────────────
        if self.cathedrals:
            parts.append(f"cath={','.join(sorted(self.cathedrals))}")
        if self.desecrated:
            parts.append(f"desc={','.join(sorted(self.desecrated))}")
        if self.ice_ages:
            parts.append(f"ice={','.join(sorted(self.ice_ages))}")
        if self.craters:
            parts.append(f"craters={','.join(sorted(self.craters))}")
        if self.deaths_head:
            parts.append(f"dh={self.deaths_head}")
        if self.gate_locations:
            parts.append(f"gates={','.join(sorted(self.gate_locations))}")
        return "|".join(parts)
