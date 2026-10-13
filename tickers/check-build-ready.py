#!/usr/bin/env python3
"""
Deterministic BUILD-READY detector for HomeBrews Faction Implementation Guides.
Runs AFTER the homebrews tick (called from run-all-tickers.sh). READ-ONLY on docs
(uses pandoc -t plain, never python-docx, never writes/moves/deletes a .docx).

A guide is BUILD-READY when its A.iii shows Section 1, Section 2, and Section 4 all
"Creator Audited" AND its "SECTION 3 — Detailed Task List" body has real generated
content (not just the §3.x outline). On the FIRST tick a guide becomes ready it:
  - fires a macOS notification (osascript),
  - appends a line to /tmp/cw-ticker-alerts.txt,
  - drops a dedupe flag /tmp/cw-build-ready.<slug>.flag so it never re-pings.
If a guide later drops out of ready (creator reopened a section), the flag is removed
so a fresh ping fires when it becomes ready again.

Never raises: any per-guide error is swallowed so the ticker run is unaffected.
"""
import os, re, sys, subprocess, glob, hashlib

HB = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
      "My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews")
PANDOC = "/Users/gremus/.local/bin/pandoc"
ALERTS = "/tmp/cw-ticker-alerts.txt"
SOLO = "/Users/gremus/Claude-Projects/cw-homebrew-wt/solo"   # built factions live here as Faction<ACR>.scala
SEC3_MIN_CHARS = 1500          # real Section 3 body must exceed the bare outline

def now():
    return subprocess.run(["date", "+%F %T"], capture_output=True, text=True).stdout.strip()

def slug(name):
    return hashlib.md5(name.encode("utf-8")).hexdigest()[:10]

def flagpath(name):
    return f"/tmp/cw-build-ready.{slug(name)}.flag"

def plain_text(path):
    r = subprocess.run([PANDOC, path, "-t", "plain"], capture_output=True, text=True, timeout=120)
    return r.stdout if r.returncode == 0 else ""

def status_ok(text):
    """All of Section 1, 2, 4 status lines == Creator Audited."""
    want = {"1": False, "2": False, "4": False}
    for m in re.finditer(r'Section\s+([124])\s+Status\s*:\s*([^\n]+)', text):
        if "creator audited" in m.group(2).strip().lower():
            want[m.group(1)] = True
    return all(want.values())

def section3_has_content(text):
    """Chars of real body between the uppercase 'SECTION 3' heading and SECTION 4/5."""
    lines = text.splitlines()
    starts = [i for i, l in enumerate(lines) if re.match(r'\s*SECTION\s+3\b', l)]
    if not starts:
        return False
    s = starts[-1]  # the content heading sits later than any A.iv reference
    end = len(lines)
    for j in range(s + 1, len(lines)):
        if re.match(r'\s*SECTION\s+[45]\b', lines[j]):
            end = j; break
    body = 0
    for l in lines[s + 1:end]:
        t = l.strip()
        if not t or t == ".":
            continue
        # skip the pure outline scaffolding: "§3.x ...", "Task 3.x.y — ..." title-only
        if re.match(r'§?3\.\d', t) and len(t) < 80:
            continue
        if re.match(r'Task\s+3\.\d', t) and len(t) < 80:
            continue
        body += len(t)
    return body >= SEC3_MIN_CHARS

def notify(title, subtitle, message):
    try:
        subprocess.run(["osascript", "-e",
            f'display notification "{message}" with title "{title}" '
            f'subtitle "{subtitle}" sound name "Glass"'],
            capture_output=True, timeout=15)
    except Exception:
        pass

def acronym(text, fname=""):
    """Faction acronym, from the A.iii line 'Faction name & acronym: <name>; <ACR>'
    (current format), else from a '(ACR)' parenthetical in the filename (older guides)."""
    m = re.search(r'Faction name\s*&\s*acronym\s*:\s*[^;\n]+;\s*([A-Za-z0-9]{1,6})\b', text)
    if m:
        return m.group(1).strip()
    m = re.search(r'\(([A-Za-z]{2,6})\)', os.path.basename(fname))
    return m.group(1).strip() if m else None

def already_built(acr):
    """True if this faction's source already exists in the HB worktree (so it's built, not new)."""
    if not acr:
        return False
    return os.path.exists(os.path.join(SOLO, f"Faction{acr}.scala"))

def faction_label(fname):
    # human name = filename up to "Faction Implementation Guide" / "Implementation Guide"
    base = os.path.basename(fname)
    base = re.split(r'\s*-?\s*(Faction )?Implementation Guide', base)[0].strip()
    return base or os.path.splitext(os.path.basename(fname))[0]

def main():
    if not os.path.isdir(HB):
        return
    guides = []
    for p in glob.glob(os.path.join(HB, "*Implementation Guide*.docx")):
        b = os.path.basename(p)
        low = b.lower()
        if any(x in low for x in ("sample", "template", ".bak", ".pre_", ".backup", "- backup", " old", "ignore")):
            continue
        if re.search(r'\(\d+\)\.docx$', b):   # Google Drive conflict copy
            continue
        guides.append(p)

    for p in guides:
        try:
            b = os.path.basename(p)
            low = b.lower()
            # FBE / Faceless Blight is owned by the dedicated FBE ticker — never ping for it.
            if "faceless blight" in low or "facelessblight" in low or "fbe" in low:
                continue
            fp = flagpath(b)
            text = plain_text(p)
            if not text:
                continue
            acr = acronym(text, p)
            # Only NEW factions get a build-ready ping. If Faction<ACR>.scala already
            # exists, the faction is already built — a finished guide there is normal,
            # not a call to build. If we can't resolve the acronym we can't confirm it's
            # new, so we don't ping (avoid false alarms); log it for visibility.
            if already_built(acr):
                continue
            ready = status_ok(text) and section3_has_content(text)
            already = os.path.exists(fp)
            if ready and not already and not acr:
                print(f"check-build-ready: {faction_label(p)} looks build-ready but its acronym "
                      f"couldn't be read from A.iii — NOT pinging (can't confirm it's a new faction).",
                      file=sys.stderr)
                continue
            if ready and not already:
                label = faction_label(p)
                notify("CW Ticker: Build Ready",
                       label,
                       f"{label} is ready for the attended Opus build — all sections Creator Audited.")
                try:
                    with open(ALERTS, "a") as f:
                        f.write(f"[{now()}] BUILD READY: {label} — all sections Creator Audited + "
                                f"Section 3 populated. Hand to attended Opus build. Ticker will NOT build it.\n")
                except Exception:
                    pass
                open(fp, "w").close()
                print(f"BUILD-READY ping fired: {label}")
            elif not ready and already:
                try: os.remove(fp)
                except Exception: pass
                print(f"BUILD-READY cleared (guide reopened): {faction_label(p)}")
        except Exception as e:
            print(f"check-build-ready: skipped {os.path.basename(p)}: {e}", file=sys.stderr)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"check-build-ready: fatal (ignored): {e}", file=sys.stderr)
    sys.exit(0)
