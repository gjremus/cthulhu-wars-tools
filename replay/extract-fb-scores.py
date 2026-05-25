#!/usr/bin/env python3
"""Extract FB bot scoring rules from BotFB.scala and emit a CSV mirroring TS
schema. Each `expr |=> score -> "desc"` line becomes one row under a
phase-aware Section/Sub Section classification (matching TS user-edit CSV).

Sections (TS schema):
  1 Placement, 2 AP1, 3 AP2, 4 AP3, 5 All APs, 6 End Game,
  7 Gather Power, 8 First Player Order, 9 Doom Phase, 10 Spellbooks, 11 Removed

Sub Sections: 1 Start of section, 2 Entire section, 3 End of section
"""
import re
import csv
import os
import sys

BOT_PATH = "/Users/gremus/cthulhu-wars Library at Celaeno/solo/BotFB.scala"
OUT_PATH = "/Users/gremus/My Drive/Personal/Games/Cthulhu Wars/Firstborn/Bot/FB_BOT_ACTION_SCORES_USER_EDIT.csv"


# ── Action class → Section mapping ──
# Maps action class name to (default Section, default Sub Section). Conditions
# in the score expression may override Section (e.g., firstAP → "2 AP1").
ACTION_SECTION = {
    # Placement
    "StartingRegionAction": ("1 Placement", "1 Start of section"),
    # First player / play order
    "FirstPlayerAction": ("8 First Player Order", "2 Entire section"),
    "PlayDirectionAction": ("8 First Player Order", "2 Entire section"),
    # Spellbooks
    "SpellbookAction": ("10 Spellbooks", "2 Entire section"),
    # Doom-phase actions (DoomAction, RitualAction, reveal, devil's mark doom, etc.)
    "DoomAction": ("9 Doom Phase", "2 Entire section"),
    "DoomDoneAction": ("9 Doom Phase", "3 End of section"),
    "RitualAction": ("9 Doom Phase", "2 Entire section"),
    "ProvideDoomAction": ("9 Doom Phase", "2 Entire section"),
    "Provide3DoomAction": ("9 Doom Phase", "2 Entire section"),
    "RevealESAction": ("9 Doom Phase", "3 End of section"),
    "ElderSignAction": ("9 Doom Phase", "2 Entire section"),
    "FBDevilsMarkDoomAction": ("9 Doom Phase", "2 Entire section"),
    "FBDevilsMarkPlaceCraterAction": ("9 Doom Phase", "2 Entire section"),
    "FBDevilsMarkDoomCancelAction": ("9 Doom Phase", "2 Entire section"),
    "FBInfernalPactDoomMainAction": ("9 Doom Phase", "2 Entire section"),
    "FBInfernalPactDoomChooseAction": ("9 Doom Phase", "2 Entire section"),
    "FBInfernalPactDoomDoneAction": ("9 Doom Phase", "2 Entire section"),
    "FBInfernalPactDoomCancelAction": ("9 Doom Phase", "2 Entire section"),
    "FBInfernalPactCancelDoomAction": ("9 Doom Phase", "2 Entire section"),
    "InstantDeathTriggerAction": ("6 End Game", "1 Start of section"),
    # Gather Power phase
    "RecoverPowerAction": ("7 Gather Power", "2 Entire section"),
    "GatherPowerAction": ("7 Gather Power", "2 Entire section"),
    # All other action-phase actions → "5 All APs"; per-conditions may bump
    # to "2 AP1" / "3 AP2" / "4 AP3" via condition keywords.
}


# Keywords (case-insensitive) in score expressions / descriptions that suggest
# a more specific phase. Matched against `expr + " " + desc` lowered.
COND_AP1_PATTERNS = (r"\bfirstap\b", r"\bopener\b", r"\bap1\b")
COND_AP2_PATTERNS = (r"\bsecondap\b", r"\bap2\b")
COND_AP3_PATTERNS = (r"\bthirdap\b", r"\bap3\b")
COND_LATER_PATTERNS = (r"\blaterap\b",)
COND_END_GAME_PATTERNS = (
    r"\bidimminent\b", r"instant death", r"end ?game",
    r"realdoom\s*>=\s*\d", r"projecteddoom\s*>=\s*30",
    r"\bid\s+imminent\b", r"writhe[- ]?kill",
)


def parse_bot_scala(path):
    """Yield (action_class, expr_text, score_text, desc_text, line_no) per scoring rule."""
    src = open(path).read()
    lines = src.splitlines()
    case_re = re.compile(r"^\s+case\s+(\w+)\s*[(]")
    # Two desc forms:
    #   |=> SCORE -> "literal desc"
    #   |=> SCORE -> ("desc " + variable + " more")  -- parenthesized expr
    score_re = re.compile(r"^(\s*)(.*?)\s*\|=>\s*(.+?)\s*->\s*(.+?)\s*$")
    cur_case = None
    for i, line in enumerate(lines):
        m_case = case_re.match(line)
        if m_case:
            cur_case = m_case.group(1)
            continue
        if not cur_case:
            continue
        if line.strip().startswith("//"):
            continue
        m_score = score_re.match(line)
        if m_score:
            expr = m_score.group(2).strip()
            score = m_score.group(3).strip()
            desc_raw = m_score.group(4).strip()
            # Clean: strip outer quotes (literal) or outer parens (expr).
            # Handle: "literal" or ("text " + var)
            if desc_raw.startswith('"') and desc_raw.endswith('"'):
                desc = desc_raw[1:-1]
            elif desc_raw.startswith("(") and desc_raw.endswith(")"):
                # Expression — keep meaningful text parts
                inner = desc_raw[1:-1]
                # Replace + variable concatenations with placeholders
                # e.g. "crater tier " + craterScore  →  crater tier <var>
                desc = re.sub(r'"\s*\+\s*\w+(?:\s*\+\s*"|$)', '', inner)
                desc = desc.strip('"').strip()
            else:
                desc = desc_raw
            yield (cur_case, expr, score, desc, i + 1)


def normalize_score(s):
    s = s.replace("(", "").replace(")", "").strip()
    m = re.match(r"-?\d+", s)
    return m.group(0) if m else s


def split_conditions(expr):
    if not expr or expr == "true":
        return []
    parts = [p.strip() for p in re.split(r"\s+&&\s+", expr) if p.strip()]
    return [p.rstrip(")").lstrip("(").strip() for p in parts if p.strip()]


def classify(action, expr, desc):
    """Return (Section, Sub Section) for this row."""
    text = (expr + " " + desc).lower()
    # Default section by action class
    section, sub = ACTION_SECTION.get(action, ("5 All APs", "2 Entire section"))

    # Override by condition keywords. End-game checks first (highest signal).
    # Doom-phase actions referring to end-game stay in 9 Doom Phase (they fire
    # in the doom phase, near end of turn).
    if section not in ("9 Doom Phase",) and any(re.search(p, text) for p in COND_END_GAME_PATTERNS):
        section = "6 End Game"
        sub = "1 Start of section" if "instant" in text else "2 Entire section"
        return section, sub

    # If still default ("5 All APs") and action is a main-phase action,
    # promote to specific AP based on conditions.
    if section == "5 All APs":
        if any(re.search(p, text) for p in COND_AP1_PATTERNS):
            section = "2 AP1"
        elif any(re.search(p, text) for p in COND_AP3_PATTERNS):
            section = "4 AP3"
        elif any(re.search(p, text) for p in COND_AP2_PATTERNS):
            section = "3 AP2"
        # laterAP keeps "5 All APs" (it spans AP2+)

    # Sub section based on signal in description / expression
    # Mark "start of section" if it's a HARD BLOCK or an opener-only rule
    if "BLOCK" in desc or "never" in desc.lower():
        sub = "1 Start of section"
    elif "fallback" in desc.lower() or "low" in desc.lower() or "extra" in desc.lower() or "tiebreaker" in desc.lower():
        sub = "3 End of section"
    elif "first" in desc.lower() and section in ("2 AP1", "5 All APs"):
        sub = "1 Start of section"
    elif section == "9 Doom Phase" and ("revealed" in text or "reveal" in text):
        sub = "3 End of section"
    elif section == "6 End Game":
        if "imminent" in text or "instant" in text or "BLOCK" in desc:
            sub = "1 Start of section"
        else:
            sub = "2 Entire section"
    else:
        sub = "2 Entire section"

    return section, sub


def main():
    rows = []
    for n, (cls, expr, score, desc, lineno) in enumerate(parse_bot_scala(BOT_PATH), start=1):
        section, sub = classify(cls, expr, desc)
        conds = split_conditions(expr)
        score_val = normalize_score(score)
        row = {
            "#": 0,  # filled after sort
            "Section": section,
            "Sub Section": sub,
            "Similar": "",
            "Remove": "",
            "Count/2k": "",
            "Loses To": "",
            "Top AP Count": "",
            "TB Count": "",
            "TB Won": "",
            "User feedback": "",
            "Name": desc[:80],
            "Action": cls,
            "Description": desc,
            "Score": score_val,
            "Removed": "",
            "New": "",
            "Regularly Used": "",
        }
        for i in range(10):
            row[f"Cond{i+1}"] = conds[i] if i < len(conds) else ""
        row["_lineno"] = lineno
        rows.append(row)

    # Sort: by Section (numeric prefix), then Sub Section, then by Score desc
    def sort_key(r):
        sec_num = int(r["Section"].split(" ")[0]) if r["Section"][0].isdigit() else 99
        sub_num = int(r["Sub Section"].split(" ")[0]) if r["Sub Section"][0].isdigit() else 99
        score = int(r["Score"]) if r["Score"].lstrip("-").isdigit() else 0
        return (sec_num, sub_num, -score, r["_lineno"])
    rows.sort(key=sort_key)
    for i, r in enumerate(rows, start=1):
        r["#"] = i

    fieldnames = ["#", "Section", "Sub Section", "Similar", "Remove", "Count/2k",
                  "Loses To", "Top AP Count", "TB Count", "TB Won", "User feedback",
                  "Name", "Action", "Description", "Score", "Removed", "New",
                  "Regularly Used"] + [f"Cond{i+1}" for i in range(10)]
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"Wrote {len(rows)} rows to {OUT_PATH}")

    # Print section distribution
    from collections import Counter
    sec_counts = Counter(r["Section"] for r in rows)
    print("\nSection distribution:")
    for s in sorted(sec_counts.keys()):
        sub_breakdown = Counter(r["Sub Section"] for r in rows if r["Section"] == s)
        print(f"  {sec_counts[s]:>4d}  {s}")
        for sub, n in sorted(sub_breakdown.items()):
            print(f"           {n:>4d}  {sub}")


if __name__ == "__main__":
    main()
