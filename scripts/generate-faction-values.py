#!/usr/bin/env python3
"""
generate-faction-values.py - build/refresh solo/faction-values/<acr>.json from the designer.

Scans a designer faction's BUILT design for every "fixed number" - the exact same list
the designer's Simple Update screen shows (port of Rules.fixedNumbers() in
designer/www/rules.js): unit qty / cost / awakenPower / dice / pains / kills, setup power /
aeStart / unit qty, SBR num, SB cost / effect (+ power 2 and side B), UFA cost / effect,
token qty / effect, custom num, Alternate Economy fixed increments.

Every one of those gets an entry in faction-values/<acr>.json with a "designer" link,
so faction-values.py sync can apply a designer "Push design to build" automatically.

MERGE, never destroy:
  * existing keys are kept (the Scala code reads them by name) and keep their value
    (that is what the game uses right now); a design/game mismatch is reported only.
  * hand-made keys without a designer link (numbers from rule text) are kept.
  * missing fixed numbers are ADDED with the built design's value.
Then it reports which keys the Scala code actually reads (<ACR>Values.<key>), so a key
nobody reads ("UNWIRED") is visible - a simple update to an unwired key changes nothing.

Usage (run with /usr/bin/python3):
  generate-faction-values.py <ACR|fid> [...]     generate/merge for these factions
  generate-faction-values.py --all-built          every built designer faction with Scala code
  options:
    --dry-run        show what would change, write nothing
    --data-dir DIR   read <DIR>/<fid>/faction.json, v/<n>.json, live-values.json locally
                     instead of over SSH from the VM
    --no-gen         don't run faction-values.py gen afterwards
    --strict         exit 1 if any designer-linked key is not read by the Scala code

Called automatically at the end of every faction build (see the admin queue prompt,
QUICK UPDATE VALUES FILE section). Only standard-library Python.
"""

import json
import os
import re
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

SOLO = Path(os.environ.get("CW_SOLO", "/Users/gremus/Claude-Projects/cw-homebrew-wt/solo"))
VALUES_DIR = SOLO / "faction-values"
FV_TOOL = Path(__file__).resolve().parent / "faction-values.py"
SSH_KEY = Path.home() / ".ssh" / "oracle_cw_ed25519"
SSH_HOST = "oracle-cw-server@cwo.freeddns.org"
REMOTE = "/opt/cwo/designer/data/factions"
# Base-game factions are read-only copies in the designer: their code is core HRF, never touched.
BASE_ACRONYMS = {"GC", "CC", "BG", "YS", "SL", "WW", "OW", "AN"}

FIELD_SUFFIX = {"qty": "count", "cost": "cost", "dice": "combat", "awakenPower": "awakenCost",
                "pains": "pains", "kills": "kills", "num": "num", "effect": "effect"}


# ---------------------------------------------------------------- data access

class Source:
    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir else None

    def read(self, rel):
        if self.data_dir:
            p = self.data_dir / rel
            return json.loads(p.read_text()) if p.exists() else None
        if not re.fullmatch(r"[A-Za-z0-9_./-]+", rel) or ".." in rel:
            raise ValueError(rel)
        r = subprocess.run(["ssh", "-i", str(SSH_KEY), "-o", "ConnectTimeout=15", "-o", "BatchMode=yes",
                            SSH_HOST, f"cat {REMOTE}/{rel} 2>/dev/null"],
                           capture_output=True, text=True, timeout=60)
        return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None

    def list_fids(self):
        if self.data_dir:
            return sorted(p.name for p in self.data_dir.iterdir() if (p / "faction.json").exists())
        r = subprocess.run(["ssh", "-i", str(SSH_KEY), "-o", "ConnectTimeout=15", "-o", "BatchMode=yes",
                            SSH_HOST, f"ls {REMOTE}"], capture_output=True, text=True, timeout=60)
        return sorted(n for n in r.stdout.split() if re.fullmatch(r"[A-Za-z0-9_-]+", n))


def get_path(obj, path):
    for part in path.split("."):
        if isinstance(obj, dict):
            obj = obj.get(part)
        elif isinstance(obj, list):  # "rows.<id>" / "units.<id>"
            obj = next((r for r in obj if isinstance(r, dict) and r.get("id") == part), None)
        else:
            return None
        if obj is None:
            return None
    return obj


def set_path(obj, path, value):
    *head, last = path.split(".")
    tgt = get_path(obj, ".".join(head)) if head else obj
    if isinstance(tgt, dict):
        tgt[last] = value


def built_design(src, fid, faction):
    """Same resolution as designer_server.built_design_with_overrides()."""
    build = faction.get("build", {})
    live = build.get("liveVersion")
    if not live:
        # Mid-build (not marked built yet): the build works from the current design.
        return faction.get("design"), "current design (faction not marked built yet)"
    built = src.read(f"{fid}/v/{live}.json") if str(live).isdigit() else None
    resolved = live
    if built is None:
        anchor = build.get("requestedAt") or build.get("builtAt")
        resolved = None
        if anchor:
            for v in sorted(faction.get("versions", []), key=lambda v: v.get("n", 0)):
                if v.get("created", 0) <= anchor and not v.get("deleted"):
                    resolved = v.get("n")
        built = src.read(f"{fid}/v/{resolved}.json") if resolved is not None else None
    if built is None:
        return faction.get("design"), "current design (built snapshot not found)"
    lv = src.read(f"{fid}/live-values.json") or {}
    for h in lv.get("history", []):
        if h.get("liveVersion") == live and get_path(built, h["path"].rsplit(".", 1)[0]) is not None:
            set_path(built, h["path"], h["to"])
    return built, f"built version {resolved} + {lv.get('rev', 0)} pushed simple update(s)"


# ---------------------------------------------------------------- fixed numbers (port of Rules.fixedNumbers)

def sb_two(sb, row):
    return bool(row.get("twoSided")) if row.get("twoSided") is not None else bool(sb.get("twoSided"))


def fixed_numbers(d):
    out = []

    def add(section, row_id, field, name, value):
        if row_id:
            path = f"{section}.{'units' if section == 'setup' else 'rows'}.{row_id}.{field}"
        else:
            path = f"{section}.{field}"
        out.append({"section": section, "rowId": row_id, "field": field, "name": name, "value": value, "path": path})

    ae = d.get("ae") or {}
    if ae.get("enabled"):
        for r in ae.get("rows", []):
            if r.get("kind") == "fixed" and r.get("qty") is not None:
                add("ae", r["id"], "qty", r.get("desc") or "Increment", r["qty"])
    ufa = d.get("ufa") or {}
    if ufa:
        if ufa.get("hasCost") and ufa.get("cost") is not None:
            add("ufa", None, "cost", ufa.get("name") or "UFA", ufa["cost"])
        if ufa.get("hasEffect") and ufa.get("effect") is not None:
            add("ufa", None, "effect", ufa.get("name") or "UFA", ufa["effect"])
    setup = d.get("setup") or {}
    if setup:
        if setup.get("power") is not None:
            add("setup", None, "power", "Faction Setup", setup["power"])
        if ae.get("enabled") and setup.get("aeStart") is not None:
            add("setup", None, "aeStart", ae.get("name") or "AE", setup["aeStart"])
        for u in setup.get("units", []):
            if u.get("qty") is not None and u.get("name"):
                add("setup", u["id"], "qty", u["name"], u["qty"])
    for u in (d.get("units") or {}).get("rows", []):
        if not u.get("name"):
            continue
        if u.get("qty") is not None:
            add("units", u["id"], "qty", u["name"], u["qty"])
        if u.get("costType") == "Fixed" and u.get("cost") is not None:
            add("units", u["id"], "cost", u["name"], u["cost"])
        if u.get("costType") == "Awakening" and u.get("awakenPower") is not None:
            add("units", u["id"], "awakenPower", u["name"], u["awakenPower"])
        if u.get("combatType") == "Fixed Dice" and u.get("dice") is not None:
            add("units", u["id"], "dice", u["name"], u["dice"])
        if u.get("combatType") == "Fixed Results":
            if u.get("pains") is not None:
                add("units", u["id"], "pains", u["name"], u["pains"])
            if u.get("kills") is not None:
                add("units", u["id"], "kills", u["name"], u["kills"])
    for i, r in enumerate((d.get("sbr") or {}).get("rows", [])):
        if r.get("hasNum") and r.get("num") is not None:
            add("sbr", r["id"], "num", f"SBR {i + 1}", r["num"])
    sb = d.get("sb") or {}
    for r in sb.get("rows", []):
        if r.get("cost") is not None and r.get("name"):
            add("sb", r["id"], "cost", r["name"], r["cost"])
        if r.get("hasEffect") and r.get("effect") is not None and r.get("name"):
            add("sb", r["id"], "effect", r["name"], r["effect"])
        extra = []
        if r.get("dual"):
            extra.append(("2", " (power 2)"))
        if sb_two(sb, r):
            extra.append(("B", " (side B)"))
            if r.get("dualB"):
                extra.append(("B2", " (side B, power 2)"))
        for sfx, tag in extra:
            nm = r.get("name" + sfx)
            if not nm:
                continue
            if r.get("cost" + sfx) is not None:
                add("sb", r["id"], "cost" + sfx, nm + tag, r["cost" + sfx])
            if r.get("hasEffect" + sfx) and r.get("effect" + sfx) is not None:
                add("sb", r["id"], "effect" + sfx, nm + tag, r["effect" + sfx])
    for r in (d.get("tokens") or {}).get("rows", []):
        if r.get("qty") is not None and r.get("name"):
            add("tokens", r["id"], "qty", r["name"], r["qty"])
        if r.get("hasEffect") and r.get("effect") is not None and r.get("name"):
            add("tokens", r["id"], "effect", r["name"], r["effect"])
    for r in (d.get("custom") or {}).get("rows", []):
        if r.get("hasNum") and r.get("num") is not None and r.get("name"):
            add("custom", r["id"], "num", r["name"], r["num"])
    return out


# ---------------------------------------------------------------- naming

def camel(s):
    s = re.sub(r"\(.*?\)", " ", s or "")
    words = re.findall(r"[A-Za-z0-9]+", s.replace("'", ""))
    out = "".join(w[:1].upper() + w[1:] for w in words)
    if not out or not out[0].isalpha():
        out = "X" + out
    return out


def plural(n):
    return n if n.endswith("s") else n + "s"


def describe(n, d):
    """(key, what, min, max) for a new entry."""
    sec, f, name = n["section"], n["field"], n["name"]
    base_name = re.sub(r"\s*\((power 2|side B|side B, power 2)\)$", "", name)
    if sec == "units":
        k = camel(name)
        what = {"qty": f"{plural(name)} in the faction", "cost": f"{name} summon cost (Power)",
                "awakenPower": f"Power to Awaken {name}", "dice": f"{name} combat dice",
                "pains": f"{name} fixed Pain results", "kills": f"{name} fixed Kill results"}[f]
        return f"{k}.{FIELD_SUFFIX[f]}", what, (1 if f == "qty" else 0), (12 if f == "qty" else 30)
    if sec == "setup":
        if f == "power":
            return "Setup.power", "Starting Power", 0, 20
        if f == "aeStart":
            return "Setup.aeStart", f"Starting {name}", 0, 20
        return f"Setup.{camel(name)}", f"{plural(name)} placed during setup", 0, 12
    if sec == "sbr":
        row = get_path(d, f"sbr.rows.{n['rowId']}") or {}
        idx = int(name.split()[-1])
        return f"SBR{idx}Req.num", f"SBR {idx}: number in \"{(row.get('text') or '')[:70]}\"", 0, 60
    if sec == "sb":
        sfx = f[len("cost"):] if f.startswith("cost") else f[len("effect"):]
        k = camel(base_name) if sfx in ("", "2") else camel(base_name)
        kind = "cost" if f.startswith("cost") else "effect"
        tag = "" if sfx == "" else {"2": "Power2", "B": "", "B2": "Power2"}[sfx]
        return (f"{k}.{kind}{tag}", f"{name} {'action cost (Power)' if kind == 'cost' else 'fixed effect amount'}",
                0, 20)
    if sec == "ufa":
        return f"{camel(name)}.{f}", f"{name} (Unique Faction Ability) {'cost' if f == 'cost' else 'effect amount'}", 0, 20
    if sec == "tokens":
        return f"{camel(name)}.{FIELD_SUFFIX[f]}", f"{name} token {'count' if f == 'qty' else 'effect amount'}", 0, 20
    if sec == "custom":
        return f"{camel(name)}.num", f"{name} (Other Custom) number", 0, 60
    if sec == "ae":
        return f"AE{camel(name)}.qty", f"Alternate Economy increment: {name}", 0, 20
    return f"{camel(name)}.{f}", name, 0, 99


def skip_reason(n, value, design, own_setup):
    """Fixed numbers that are not faction numbers at all (nothing in the faction code to change).
    If the designer ever sets them to something non-standard they ARE added (and show UNWIRED,
    i.e. that change needs a rebuild)."""
    if n["section"] == "sb" and n["field"].startswith("cost") and value == 0:
        return "spellbook has no Power cost (passive/triggered) - a cost would be a rules change"
    if n["section"] == "units" and n["name"] == "Acolyte" and (n["field"], value) in (("cost", 1), ("dice", 0)):
        return "standard Acolyte rule (shared core Acolyte unit, same for every faction)"
    if n["section"] == "setup" and n["rowId"]:
        row = get_path(design, f"setup.units.{n['rowId']}") or {}
        if row.get("onMap") is False:
            return "not placed on the map at setup (it is the unit pool, already covered by the unit count)"
    if not own_setup and n["section"] == "setup" and (
            (n["field"] == "power" and value == 8) or (n["name"] == "Acolyte" and value == 6)):
        return "standard setup rule (8 Power / 6 Acolytes placed by the core setup, faction has no own setup code)"
    return None


def has_own_setup(acr):
    """True if the faction places its own starting Acolytes (so setup numbers live in faction code)."""
    p = SOLO / f"Faction{acr}.scala"
    return p.exists() and "place(Acolyte" in p.read_text(errors="ignore")


def scala_ident(key):
    return key.replace(".", "_")


def scala_readers(acr):
    """Set of identifiers X used as <ACR>Values.X anywhere in the Scala (except the generated file)."""
    used = set()
    pat = re.compile(rf"\b{acr}Values\.([A-Za-z0-9_]+)")
    for p in SOLO.glob("*.scala"):
        if p.name == "FactionValues.scala":
            continue
        try:
            used.update(pat.findall(p.read_text(errors="ignore")))
        except OSError:
            pass
    return used


# ---------------------------------------------------------------- merge

def merge(acr, faction, fid, design, how, dry_run):
    path = VALUES_DIR / f"{acr.lower()}.json"
    existing = json.loads(path.read_text(), object_pairs_hook=OrderedDict) if path.exists() else None
    doc = existing or OrderedDict([("acronym", acr), ("faction", faction.get("name", acr)),
                                   ("designerFid", fid), ("values", OrderedDict())])
    doc.setdefault("designerFid", fid)
    vals = doc["values"]
    by_link = {v.get("designer"): k for k, v in vals.items() if v.get("designer")}
    nums = fixed_numbers(design)
    own_setup = has_own_setup(acr)
    report ={"added": [], "linked": [], "mismatch": [], "kept": 0, "skipped": []}
    for n in nums:
        value = n["value"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
            continue
        value = int(value)
        skip = skip_reason(n, value, design, own_setup)
        if skip and n["path"] not in by_link:
            report["skipped"].append((n["path"], value, skip))
            continue
        if n["path"] in by_link:
            k = by_link[n["path"]]
            report["kept"] += 1
            if vals[k]["value"] != value:
                report["mismatch"].append((k, vals[k]["value"], value))
            continue
        key, what, lo, hi = describe(n, design)
        if key in vals and not vals[key].get("designer"):
            # Same-named hand-made key: link it to the designer field instead of duplicating
            vals[key]["designer"] = n["path"]
            report["linked"].append(key)
            if vals[key]["value"] != value:
                report["mismatch"].append((key, vals[key]["value"], value))
            by_link[n["path"]] = key
            continue
        base, i = key, 2
        while key in vals:
            key = f"{base}{i}"
            i += 1
        lo = min(lo, value)
        hi = max(hi, value)
        vals[key] = OrderedDict([("value", value)] + ([("min", lo)] if lo else []) +
                                [("max", hi), ("what", what), ("designer", n["path"])])
        by_link[n["path"]] = key
        report["added"].append((key, value, n["path"]))

    readers = scala_readers(acr)
    unwired = [k for k in vals if scala_ident(k) not in readers]
    print(f"\n=== {faction.get('name')} ({acr}, fid {fid}) - source: {how}")
    print(f"    fixed numbers in design: {len(nums)}  already linked: {report['kept']}  "
          f"newly linked: {len(report['linked'])}  added: {len(report['added'])}  total keys: {len(vals)}")
    for k, v, p in report["added"]:
        print(f"    + {k} = {v}   ({p})")
    for k in report["linked"]:
        print(f"    ~ {k} now linked to {vals[k]['designer']}")
    for p, v, why in report["skipped"]:
        print(f"    . skipped {p} = {v}: {why}")
    for k, game, des in report["mismatch"]:
        print(f"    ! {k}: game/json = {game}, built design = {des}  (json kept; run faction-values.py sync to take the design value)")
    if unwired:
        print(f"    UNWIRED ({len(unwired)} keys not read by any Scala code - a simple update to these changes nothing yet):")
        for k in unwired:
            print(f"      - {k}  ({vals[k].get('designer', 'no designer link')})")
    else:
        print("    all keys are read by the Scala code")
    if not dry_run:
        path.write_text(render_json(doc))
        print(f"    wrote {path}")
    return unwired, [k for k in unwired if vals[k].get("designer")]


def render_json(doc):
    """fm.json style: one value per line, aligned."""
    vals = doc["values"]
    width = max(len(json.dumps(k)) + 1 for k in vals) if vals else 0
    lines = ["{"]
    head = [k for k in doc if k not in ("values", "images")]
    for k in head:
        lines.append(f"  {json.dumps(k)}: {json.dumps(doc[k], ensure_ascii=False)},")
    lines.append('  "values": {')
    items = list(vals.items())
    for i, (k, v) in enumerate(items):
        body = ", ".join(f"{json.dumps(f)}: {json.dumps(x, ensure_ascii=False)}" for f, x in v.items())
        lines.append(f"    {(json.dumps(k) + ':').ljust(width)} {{{body}}}" + ("," if i < len(items) - 1 else ""))
    lines.append("  }" + ("," if "images" in doc else ""))
    if "images" in doc:
        lines.append(f'  "images": {json.dumps(doc["images"])}')
    lines.append("}")
    return "\n".join(lines) + "\n"


def has_scala(acr):
    return (SOLO / f"Faction{acr}.scala").exists()


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    dry = "--dry-run" in args
    strict = "--strict" in args
    no_gen = "--no-gen" in args
    data_dir = None
    if "--data-dir" in args:
        data_dir = args[args.index("--data-dir") + 1]
    targets = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] != "--data-dir")]
    src = Source(data_dir)

    factions = {}
    for fid in src.list_fids():
        f = src.read(f"{fid}/faction.json")
        if f:
            factions[fid] = f
    chosen = []
    if "--all-built" in args:
        for fid, f in factions.items():
            acr = f.get("acronym", "")
            if f.get("build", {}).get("status") == "built" and acr not in BASE_ACRONYMS and has_scala(acr):
                chosen.append(fid)
    for t in targets:
        hit = [fid for fid, f in factions.items() if fid == t or f.get("acronym", "").upper() == t.upper()]
        if not hit:
            print(f"ERROR: no designer faction '{t}'", file=sys.stderr)
            return 1
        chosen.extend(h for h in hit if h not in chosen)

    strict_fail = []
    for fid in chosen:
        f = factions[fid]
        acr = f["acronym"].upper()
        if acr in BASE_ACRONYMS:
            print(f"{acr}: base-game faction (core code) - skipped")
            continue
        design, how = built_design(src, fid, f)
        if design is None:
            print(f"{acr}: not built - skipped")
            continue
        _, linked_unwired = merge(acr, f, fid, design, how, dry)
        if linked_unwired:
            strict_fail.append((acr, linked_unwired))

    if not dry and not no_gen and chosen:
        sys.stdout.flush()
        subprocess.run(["/usr/bin/python3", str(FV_TOOL), "gen"], check=False)
    if strict and strict_fail:
        for acr, ks in strict_fail:
            print(f"STRICT: {acr} has designer-linked keys the code never reads: {', '.join(ks)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
