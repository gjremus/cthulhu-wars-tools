#!/usr/bin/env python3
"""Build www/library/ (the "CW / Necro" picture picker) from library-src/.

game.json  -> pictures copied from the homebrew build's solo/webp/images/
drive.json -> pictures from the owner's Drive "Neutral Units" folder, shrunk to
              256px PNGs with sips. Drive files that are online-only can't be read;
              they are skipped and listed, so just rerun once the folder is offline.
Only entries whose picture made it into www/library/ are listed in library.json.
"""
import json, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SRC = HERE / "library-src"
OUT = HERE / "www" / "library"
GAME_IMAGES = Path.home() / "Claude-Projects/cw-homebrew-wt/solo/webp/images"
DRIVE = Path.home() / ("Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/"
                       "Personal/Games/Cthulhu Wars/Neutral Units")
ORDER = ["Cultist", "Monster", "Terror", "GOO", "Elder God"]


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    entries, missing = [], []

    for e in json.load(open(SRC / "game.json")):
        src = GAME_IMAGES / e["file"]
        if src.exists():
            shutil.copyfile(src, OUT / e["file"])
            entries.append({k: e[k] for k in ("name", "type", "faction", "file")})
        else:
            missing.append("game: " + e["file"])

    for e in json.load(open(SRC / "drive.json")):
        src, dst = DRIVE / e["source"], OUT / e["file"]
        r = subprocess.run(["sips", "-s", "format", "png", "-Z", "256", str(src), "--out", str(dst)],
                           capture_output=True, text=True)
        if r.returncode == 0 and dst.exists() and dst.stat().st_size > 0:
            entries.append({k: e.get(k) for k in ("name", "type", "faction", "file", "wiki")})
        else:
            dst.unlink(missing_ok=True)
            missing.append("drive: " + e["source"])

    entries.sort(key=lambda e: (ORDER.index(e["type"]), e["name"].lower(), e["faction"]))
    json.dump(entries, open(OUT / "library.json", "w"), indent=1)
    print(f"{len(entries)} pictures in library; {len(missing)} skipped")
    for m in missing:
        print("  skipped", m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
