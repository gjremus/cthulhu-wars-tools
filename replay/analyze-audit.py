#!/usr/bin/env python3
"""Analyze a SimRunner --audit CSV and emit an RTF summary of major deviations.

Usage: python3 analyze-audit.py <audit.csv> <out.rtf> [title]

Reads the per-decision audit CSV (idx,turn,phase,ask_class,num_options,actual,
bot_pick,matched,actual_w,top_w,runner_w,margin,top_reasons) and produces an
RTF with:
  - Overall stats (total decisions, match rate, weight distribution)
  - Top 20 individual deviations (by absolute margin)
  - Per ask_class breakdown for classes with diverged decisions, ranked by
    aggregate margin impact (count * mean_margin), showing example rows.
  - "Stuck-state" decisions where every option has heavily negative weights
    (bot has no good option — strong signal that scoring no longer fits).
"""
import csv
import html
import re
import sys
from collections import defaultdict
from statistics import mean


def clean(s, n=80):
    """Strip HTML span tags and CW boilerplate, truncate."""
    s = re.sub(r"<[^>]+>", "", s or "")
    s = s.replace("Firstborn", "FB").replace("BlackGoat", "BG").replace(
        "YellowSign", "YS").replace("Sleeper", "SL")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n]


def rtf_escape(s):
    """Escape for RTF body text."""
    s = s.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    out = []
    for ch in s:
        if ord(ch) > 127:
            out.append(f"\\u{ord(ch)}?")
        else:
            out.append(ch)
    return "".join(out)


def main():
    if len(sys.argv) < 3:
        print("Usage: analyze-audit.py <audit.csv> <out.rtf> [title]")
        sys.exit(1)

    csv_path = sys.argv[1]
    rtf_path = sys.argv[2]
    title = sys.argv[3] if len(sys.argv) > 3 else "FB Bot Decision Audit"

    rows = list(csv.DictReader(open(csv_path)))
    for r in rows:
        for k in ("turn", "num_options", "actual_w", "top_w", "runner_w", "margin"):
            r[k] = int(r[k])
        r["matched"] = r["matched"] == "true"

    # ── Overall stats ─────────────────────────────────────────────────
    total = len(rows)
    matched = sum(1 for r in rows if r["matched"])
    diverged = [r for r in rows if not r["matched"]]
    big_margin = [r for r in rows if r["margin"] >= 1000]
    stuck = [r for r in rows if r["top_w"] <= -100000]
    avg_actual = mean(r["actual_w"] for r in rows) if rows else 0
    avg_top = mean(r["top_w"] for r in rows) if rows else 0

    # ── Top individual deviations by margin ────────────────────────────
    top_deviations = sorted(rows, key=lambda r: -r["margin"])[:20]

    # ── Per-class aggregation: impact = count * mean_margin ────────────
    by_class = defaultdict(list)
    for r in rows:
        by_class[r["ask_class"]].append(r)
    class_stats = []
    for cls, rs in by_class.items():
        diverged_rs = [r for r in rs if r["margin"] > 0]
        if not diverged_rs:
            continue
        impact = sum(r["margin"] for r in diverged_rs)
        class_stats.append({
            "cls": cls,
            "n": len(rs),
            "n_div": len(diverged_rs),
            "div_rate": len(diverged_rs) / len(rs),
            "mean_margin": mean(r["margin"] for r in diverged_rs),
            "max_margin": max(r["margin"] for r in diverged_rs),
            "impact": impact,
            "examples": sorted(diverged_rs, key=lambda r: -r["margin"])[:3],
        })
    class_stats.sort(key=lambda c: -c["impact"])

    # ── Stuck-state by class ───────────────────────────────────────────
    stuck_by_class = defaultdict(list)
    for r in stuck:
        stuck_by_class[r["ask_class"]].append(r)

    # ── Build RTF ──────────────────────────────────────────────────────
    out = []
    out.append(r"{\rtf1\ansi\deff0{\fonttbl{\f0 Helvetica;}{\f1 Courier;}}")
    out.append(r"{\colortbl;\red0\green0\blue0;\red128\green0\blue0;\red0\green100\blue0;}")
    out.append(r"\fs28\b " + rtf_escape(title) + r"\b0\par\par")

    out.append(r"\fs24\b Overall\b0\par")
    out.append(r"\fs20")
    out.append(rf"Total scored decisions: \b {total}\b0\par")
    out.append(rf"Matched bot pick: \b {matched}\b0 ({matched*100//total if total else 0}\%)\par")
    out.append(rf"Diverged from bot pick: \b {len(diverged)}\b0 ({len(diverged)*100//total if total else 0}\%)\par")
    out.append(rf"Large-margin divergences (margin >= 1000): \b {len(big_margin)}\b0\par")
    out.append(rf"Stuck-state decisions (top option still weight <= -100000): \b {len(stuck)}\b0\par")
    out.append(rf"Mean actual-pick weight: \b {avg_actual:.0f}\b0  /  Mean top-pick weight: \b {avg_top:.0f}\b0\par\par")

    out.append(r"\fs24\b Top 20 single-decision deviations (highest margin)\b0\par")
    out.append(r"\fs18")
    out.append(r"Margin = top_w - actual_w (how much the bot preferred its pick over what was played).\par\par")
    for r in top_deviations:
        out.append(rf"\b T{r['turn']} {rtf_escape(r['ask_class'])}\b0  margin=\b {r['margin']}\b0  ")
        out.append(rf"top_w={r['top_w']} actual_w={r['actual_w']}\par")
        out.append(rf"  actual: {rtf_escape(clean(r['actual'], 100))}\par")
        out.append(rf"  bot would pick: {rtf_escape(clean(r['bot_pick'], 100))}\par")
        if r["top_reasons"]:
            out.append(rf"  reasons (actual): {rtf_escape(clean(r['top_reasons'], 150))}\par")
        out.append(r"\par")

    out.append(r"\fs24\b Per-ask-class impact ranking\b0\par")
    out.append(r"\fs18")
    out.append(r"Impact = sum of margins across diverged decisions in that class. ")
    out.append(r"High impact means rewriting this class's scoring has the most leverage.\par\par")
    for cs in class_stats[:15]:
        out.append(rf"\b {rtf_escape(cs['cls'])}\b0  ")
        out.append(rf"n={cs['n']} diverged={cs['n_div']} ({cs['div_rate']*100:.0f}\%) ")
        out.append(rf"mean_margin={cs['mean_margin']:.0f} max={cs['max_margin']} ")
        out.append(rf"\b impact={cs['impact']}\b0\par")
        for ex in cs["examples"]:
            out.append(rf"  T{ex['turn']} margin={ex['margin']}: ")
            out.append(rf"{rtf_escape(clean(ex['actual'], 70))} \cf2 -> \cf0 {rtf_escape(clean(ex['bot_pick'], 70))}\par")
            if ex["top_reasons"]:
                out.append(rf"    reasons: {rtf_escape(clean(ex['top_reasons'], 140))}\par")
        out.append(r"\par")

    if stuck:
        out.append(r"\fs24\b Stuck-state decisions (every option deeply negative)\b0\par")
        out.append(r"\fs18")
        out.append(r"Bot's top option has weight <= -100000 — every available choice is heavily penalized. ")
        out.append(r"Strong signal that current scoring framework doesn't model the situation.\par\par")
        stuck_class_counts = sorted(stuck_by_class.items(), key=lambda kv: -len(kv[1]))
        for cls, rs in stuck_class_counts[:10]:
            out.append(rf"\b {rtf_escape(cls)}\b0  n={len(rs)}  ")
            example_turns = sorted(set(r['turn'] for r in rs))
            out.append(rf"turns: {example_turns}\par")
            ex = rs[0]
            out.append(rf"  example T{ex['turn']}: top_w={ex['top_w']} actual_w={ex['actual_w']}\par")
            out.append(rf"  actual: {rtf_escape(clean(ex['actual'], 100))}\par")
            if ex["top_reasons"]:
                out.append(rf"  reasons: {rtf_escape(clean(ex['top_reasons'], 150))}\par")
            out.append(r"\par")

    out.append(r"}")

    with open(rtf_path, "w") as f:
        f.write("".join(out))

    print(f"Wrote RTF: {rtf_path}")
    print(f"  total={total} matched={matched} diverged={len(diverged)} stuck={len(stuck)}")
    print(f"  top classes by impact:")
    for cs in class_stats[:5]:
        print(f"    {cs['cls']:35s} impact={cs['impact']:>10d}  n={cs['n']}  div={cs['n_div']}")


if __name__ == "__main__":
    main()
