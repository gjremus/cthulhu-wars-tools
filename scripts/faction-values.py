#!/usr/bin/env python3
"""
faction-values.py - change a designer faction's fixed numbers WITHOUT Claude.

Every fixed number of a designer faction (unit cost / combat / count, spellbook
costs, spellbook-requirement thresholds, UFA numbers, ...) lives in ONE JSON file:

    <solo>/faction-values/<acr>.json        (e.g. fm.json, dgt.json, prm.json)

This script turns those JSON files into ONE generated Scala file:

    <solo>/FactionValues.scala              (object FMValues, DGTValues, ...)

The faction code, the requirement text AND the in-game overlay text all read
from that generated object, so changing a number in the JSON changes the rules,
the card text and the requirement text together. Nobody edits Scala by hand.

Commands
--------
  list  <ACR>                         show every value, what it means, designer link
  set   <ACR> <key> <value> [...]     change one or more values (validated), regenerate
  gen                                 regenerate FactionValues.scala from all JSON files
  check                               fail (exit 1) if FactionValues.scala is out of date
  sync  [<ACR> ...]                   pull "Push design to build" numbers + image swaps
                                      from the designer site into the JSON / webp folder
  apply [--deploy] [--title T]        gen + compile check + git commit (+ deploy-hb)

Typical owner flow (no Claude anywhere):
  faction-values.py set FM BoneSculptor.cost 2 BoneSculptor.combat 2
  faction-values.py apply --deploy
or, after pressing "Push design to build" in the designer:
  faction-values.py sync && faction-values.py apply --deploy

Only standard-library Python. Run with /usr/bin/python3.
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

SOLO = Path(os.environ.get("CW_SOLO", "/Users/gremus/Claude-Projects/cw-homebrew-wt/solo"))
VALUES_DIR = SOLO / "faction-values"
GENERATED = SOLO / "FactionValues.scala"
DESIGNER_API = os.environ.get("CW_DESIGNER_API", "https://cwo.freeddns.org/designer/api")
DEPLOY = Path("/Users/gremus/Claude-Projects/cthulhu-wars-tools/server-deploy/deploy-hb-to-vm.sh")
SSH_KEY = Path.home() / ".ssh" / "oracle_cw_ed25519"
SSH_HOST = "oracle-cw-server@cwo.freeddns.org"
REMOTE_DESIGNER_DATA = "/opt/cwo/designer/data/factions"
JAVA_HOME = "/Users/gremus/.local/jdk/zulu21.50.19-ca-jdk21.0.11-macosx_aarch64/Contents/Home"

KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*(\.[A-Za-z][A-Za-z0-9]*)?$")


def die(msg, code=1):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(code)


def load_all():
    if not VALUES_DIR.is_dir():
        die(f"{VALUES_DIR} does not exist")
    out = {}
    for p in sorted(VALUES_DIR.glob("*.json")):
        d = json.loads(p.read_text())
        acr = d.get("acronym")
        if not acr or not re.fullmatch(r"[A-Z0-9]{2,4}", acr):
            die(f"{p.name}: missing/invalid 'acronym'")
        validate(d, p.name)
        out[acr] = (p, d)
    return out


def validate(d, where):
    vals = d.get("values")
    if not isinstance(vals, dict) or not vals:
        die(f"{where}: 'values' must be a non-empty object")
    for k, v in vals.items():
        if not KEY_RE.match(k):
            die(f"{where}: bad key '{k}' (use Name or Name.field, letters/digits only)")
        if not isinstance(v, dict) or "value" not in v:
            die(f"{where}: '{k}' must be an object with a 'value'")
        x = v["value"]
        if isinstance(x, bool) or not isinstance(x, int):
            die(f"{where}: '{k}' value must be a whole number, got {x!r}")
        lo, hi = v.get("min", 0), v.get("max", 99)
        if not (lo <= x <= hi):
            die(f"{where}: '{k}' = {x} is outside the allowed range {lo}..{hi}")


def scala_ident(key):
    return key.replace(".", "_")


def render_scala(all_factions):
    lines = [
        "package cws",
        "",
        "// ============================================================================",
        "// GENERATED FILE - DO NOT EDIT BY HAND.",
        "// Source: solo/faction-values/<acr>.json",
        "// Regenerate: /usr/bin/python3 cthulhu-wars-tools/scripts/faction-values.py gen",
        "// Every fixed number of a designer faction lives here so it can be changed",
        "// programmatically (no Claude). Faction code + overlay text both read these.",
        "// ============================================================================",
        "",
    ]
    for acr, (p, d) in sorted(all_factions.items()):
        lines.append(f"// {d.get('faction', acr)} ({acr}) - from faction-values/{p.name}")
        lines.append(f"object {acr}Values {{")
        width = max(len(scala_ident(k)) for k in d["values"])
        for k, v in d["values"].items():
            what = v.get("what", "").replace("*/", "")
            lines.append(f"    val {scala_ident(k).ljust(width)} = {v['value']}" + (f"  // {what}" if what else ""))
        lines.append("}")
        lines.append("")
    return "\n".join(lines)


def cmd_gen(quiet=False):
    allf = load_all()
    text = render_scala(allf)
    old = GENERATED.read_text() if GENERATED.exists() else None
    if old != text:
        GENERATED.write_text(text)
        if not quiet:
            print(f"wrote {GENERATED}")
    elif not quiet:
        print(f"{GENERATED.name} already up to date")
    return old != text


def cmd_check():
    allf = load_all()
    text = render_scala(allf)
    if not GENERATED.exists() or GENERATED.read_text() != text:
        die("FactionValues.scala is OUT OF DATE - run: faction-values.py gen")
    print("FactionValues.scala matches the JSON files.")


def find(acr):
    allf = load_all()
    acr = acr.upper()
    if acr not in allf:
        die(f"no faction-values file for {acr} (have: {', '.join(sorted(allf))})")
    return allf[acr]


def cmd_list(acr):
    p, d = find(acr)
    print(f"{d.get('faction', acr)} ({d['acronym']})  file: {p}")
    print(f"{'key':34} {'value':>5}  {'range':>7}  {'designer field':34} what")
    for k, v in d["values"].items():
        rng = f"{v.get('min', 0)}..{v.get('max', 99)}"
        print(f"{k:34} {v['value']:>5}  {rng:>7}  {v.get('designer', '-'):34} {v.get('what', '')}")
    if d.get("images"):
        print("\nImages (swap via designer Simple Update -> 'sync' -> 'apply --deploy'):")
        for img in d["images"]:
            print("  webp/images/" + img)


def cmd_set(acr, pairs):
    if not pairs or len(pairs) % 2:
        die("usage: set <ACR> <key> <value> [<key> <value> ...]")
    p, d = find(acr)
    changes = []
    for k, raw in zip(pairs[0::2], pairs[1::2]):
        if k not in d["values"]:
            die(f"{acr} has no value '{k}'. Run: faction-values.py list {acr}")
        if not re.fullmatch(r"-?\d+", raw):
            die(f"'{raw}' is not a whole number")
        old = d["values"][k]["value"]
        d["values"][k]["value"] = int(raw)
        changes.append((k, old, int(raw)))
    validate(d, p.name)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
    for k, o, n in changes:
        print(f"{acr} {k}: {o} -> {n}")
    cmd_gen()
    log_change(acr, changes, "set")


def log_change(acr, changes, how):
    with open(VALUES_DIR / "CHANGELOG.txt", "a") as f:
        import time
        ts = time.strftime("%Y-%m-%d %H:%M")
        for k, o, n in changes:
            f.write(f"{ts}  {acr}  {k}: {o} -> {n}  ({how})\n")


def http_json(url):
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read().decode())


def cmd_sync(acrs):
    """Pull designer 'Push design to build' numbers and image swaps."""
    allf = load_all()
    targets = [a.upper() for a in acrs] or sorted(allf)
    any_change = False
    images_changed = False
    for acr in targets:
        if acr not in allf:
            print(f"{acr}: no faction-values file, skipped")
            continue
        p, d = allf[acr]
        by_designer = {v["designer"]: k for k, v in d["values"].items() if v.get("designer")}
        try:
            live = http_json(f"{DESIGNER_API}/live/{acr}/values")
        except Exception as e:
            print(f"{acr}: designer live values unavailable ({e}); numbers skipped")
            live = {"values": {}}
        changes = []
        unmapped = []
        for path, value in (live.get("values") or {}).items():
            k = by_designer.get(path)
            if not k:
                unmapped.append(path)
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
                print(f"{acr}: {path} = {value!r} is not a whole number, skipped")
                continue
            if d["values"][k]["value"] != int(value):
                changes.append((k, d["values"][k]["value"], int(value)))
                d["values"][k]["value"] = int(value)
        for path in unmapped:
            print(f"{acr}: designer pushed {path} but no value in {p.name} is linked to it "
                  f"(add \"designer\": \"{path}\" to the matching value) - skipped")
        if changes:
            validate(d, p.name)
            p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
            log_change(acr, changes, f"designer push rev {live.get('rev')}")
            for k, o, n in changes:
                print(f"{acr} {k}: {o} -> {n}  (designer push)")
            any_change = True
        else:
            print(f"{acr}: numbers already match the designer")

        fid = d.get("designerFid")
        if fid and re.fullmatch(r"[A-Za-z0-9_-]+", fid) and SSH_KEY.exists():
            if pull_image_swaps(acr, fid):
                images_changed = True
    if any_change:
        cmd_gen()
    if images_changed:
        (VALUES_DIR / ".images-changed").write_text("1\n")
    return any_change or images_changed


def pull_image_swaps(acr, fid):
    """Copy designer image swaps (VM: data/factions/<fid>/imageSwaps/*.webp) into webp/images."""
    import tempfile, shutil, filecmp
    tmp = Path(tempfile.mkdtemp(prefix=f"swap-{acr}-"))
    ssh = ["-i", str(SSH_KEY), "-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=no"]
    r = subprocess.run(["ssh", *ssh, SSH_HOST, f"ls {REMOTE_DESIGNER_DATA}/{fid}/imageSwaps 2>/dev/null"],
                       capture_output=True, text=True, timeout=60)
    names = [n for n in r.stdout.split() if re.fullmatch(rf"{acr.lower()}-[a-z0-9-]+\.webp", n)]
    changed = False
    for n in names:
        r = subprocess.run(["scp", "-q", *ssh, f"{SSH_HOST}:{REMOTE_DESIGNER_DATA}/{fid}/imageSwaps/{n}", str(tmp / n)],
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            print(f"{acr}: could not download image swap {n}: {r.stderr.strip()}")
            continue
        dest = SOLO / "webp" / "images" / n
        if dest.exists() and filecmp.cmp(dest, tmp / n, shallow=False):
            continue
        shutil.copy2(tmp / n, dest)
        print(f"{acr}: image swapped -> webp/images/{n}")
        changed = True
    shutil.rmtree(tmp, ignore_errors=True)
    return changed


def git(*args, check=True):
    return subprocess.run(["git", "-C", str(SOLO), *args], capture_output=True, text=True, check=check)


def cmd_apply(argv):
    deploy = "--deploy" in argv
    title = "Faction values update"
    if "--title" in argv:
        title = argv[argv.index("--title") + 1]
    cmd_gen()
    # Compile check BEFORE anything is committed (fastLinkJS is quicker than the deploy build)
    env = dict(os.environ, JAVA_HOME=JAVA_HOME, PATH=f"{JAVA_HOME}/bin:" + os.environ.get("PATH", ""))
    print("==> compile check (sbt compile) ...")
    r = subprocess.run(["sbt", "-J-Xmx6G", "compile"], cwd=SOLO, env=env, capture_output=True, text=True)
    if r.returncode != 0 or "[error]" in r.stdout:
        print("\n".join(l for l in r.stdout.splitlines() if "[error]" in l)[:4000])
        die("compile failed - nothing committed or deployed. Undo with: git -C <solo> checkout faction-values FactionValues.scala")
    print("    compile OK")

    files = ["faction-values", "FactionValues.scala"]
    git("add", "--", *files)
    flag = VALUES_DIR / ".images-changed"
    images = flag.exists()
    if images:
        git("add", "-f", "--", "webp/images")
        flag.unlink()
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        print("Nothing changed - nothing to commit.")
        if not deploy:
            return
    else:
        summary = git("diff", "--cached", "--", "faction-values/CHANGELOG.txt", check=False).stdout
        added = "\n".join(l[1:] for l in summary.splitlines() if l.startswith("+") and not l.startswith("+++"))
        msg = f"{title}\n\nProgrammatic faction value update (faction-values.py, no hand-edited code).\n\n{added or '(image swaps only)'}\n"
        git("commit", "-q", "-m", msg)
        print("committed " + git("rev-parse", "--short", "HEAD").stdout.strip())
        push = subprocess.run(["git", "-C", str(SOLO), "push", "-q"], capture_output=True, text=True)
        if push.returncode != 0:
            print("warning: git push failed (deploy will retry): " + push.stderr.strip()[:300])
    if deploy:
        args = [str(DEPLOY)] + (["--assets"] if images else [])
        print("==> " + " ".join(args))
        sys.exit(subprocess.run(args).returncode)
    else:
        print("Not deployed. Run again with --deploy, or run deploy-hb-to-vm.sh yourself.")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "list" and len(args) == 1:
        cmd_list(args[0])
    elif cmd == "set" and len(args) >= 3:
        cmd_set(args[0], args[1:])
    elif cmd == "gen":
        cmd_gen()
    elif cmd == "check":
        cmd_check()
    elif cmd == "sync":
        cmd_sync(args)
    elif cmd == "apply":
        cmd_apply(args)
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
