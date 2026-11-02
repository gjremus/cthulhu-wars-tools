#!/usr/bin/env python3
"""Merge a duplicate Claude Terminal Log row into the original and delete the duplicate.

Usage (run ON THE VM, against the live file):
    python3 tlog-merge-duplicate.py /opt/cwo/designer/data/terminal-log.json <keep_n> <drop_n>

- The kept row keeps its own prompt/user/designObject (the designer's original wording).
- If the kept row only has a placeholder summary, it takes the duplicate's real summary
  (references to "#<drop_n>" are rewritten to "#<keep_n>").
- Costs are added together; costNote/updatedAt are carried over if the kept row lacks them.
- Writes a timestamped .bak next to the file first, then replaces the file atomically.
Row numbers ("n") of other rows are NOT renumbered (numbers are never reused).
"""
import json, os, sys, time, shutil

PLACEHOLDERS = {"", "Queued.", "Working on it now.", "Waiting to be picked up."}


def main():
    path, keep_n, drop_n = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    log = json.load(open(path))
    entries = log["entries"]
    keep = next((e for e in entries if e.get("n") == keep_n), None)
    drop = next((e for e in entries if e.get("n") == drop_n), None)
    if not keep or not drop:
        sys.exit(f"row not found: keep={bool(keep)} drop={bool(drop)}")
    if keep.get("id") != drop.get("id"):
        sys.exit(f"refusing: ids differ ({keep.get('id')} vs {drop.get('id')})")

    shutil.copy2(path, f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}-merge-{keep_n}-{drop_n}")

    if keep.get("defaultSummary") or str(keep.get("summary", "")).strip() in PLACEHOLDERS:
        keep["summary"] = str(drop.get("summary", "")).replace(f"#{drop_n}", f"#{keep_n}")
        keep["defaultSummary"] = bool(drop.get("defaultSummary", False))
    elif drop.get("summary") and drop["summary"] not in keep["summary"]:
        keep["summary"] += "\n\n" + drop["summary"].replace(f"#{drop_n}", f"#{keep_n}")
    if "cost" in drop:
        keep["cost"] = round(keep.get("cost", 0.0) + drop["cost"], 4)
    if drop.get("costNote") and not keep.get("costNote"):
        keep["costNote"] = drop["costNote"]
    keep["updatedAt"] = max(keep.get("updatedAt", 0), drop.get("updatedAt", 0), int(time.time()))

    log["entries"] = [e for e in entries if e is not drop]
    tmp = path + ".tmp-merge"
    with open(tmp, "w") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    print(json.dumps(keep, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
