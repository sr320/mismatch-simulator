#!/usr/bin/env python3
"""
Test the model's central prediction against the Conditioning Atlas.

The model predicts that memory persisting longer than the environment's
reversal timescale should be over-represented among experiments where
conditioning left animals WORSE off. The Conditioning Atlas scores each row's
`direction` (Improved / Mixed / Worsened / No effect) and records a
`persistence_days` window, so the prediction is checkable.

Result (2026-08-05): the raw association is present and nominally
significant, but it is CONFOUNDED by study design and does not survive
stratification. This script exists so that conclusion is reproducible rather
than asserted. See README.md, "Does the atlas support the model?".

Usage:
    python3 scripts/atlas_signal_check.py [path/to/atlas/merged.json]
"""
import collections
import json
import re
import statistics
import sys

DEFAULT_ATLAS = "/home/claude/atlas/merged.json"


def parse_days(s):
    """Largest number mentioned in a persistence_days field, or None."""
    if not s or "not reported" in s.lower():
        return None
    m = re.findall(r"([0-9]+(?:\.[0-9]+)?)", s)
    return max(float(x) for x in m) if m else None


def is_multigen(row):
    g = row.get("generations", "")
    return ("F0-F1" in g) or ("F1" in g) or ("F2" in g)


def main(path=DEFAULT_ATLAS):
    try:
        rows = json.load(open(path))
    except FileNotFoundError:
        print(f"Atlas not found at {path}.")
        print("Pass the path to the Conditioning Atlas merged.json as an argument.")
        return 1

    print("=" * 72)
    print("MODEL PREDICTION: longer-persisting memory should be over-represented")
    print("among experiments scored 'Worsened'.")
    print("=" * 72)

    by_dir = collections.defaultdict(list)
    for r in rows:
        d = parse_days(r.get("persistence_days"))
        if d is not None:
            by_dir[r["direction"]].append(d)

    print("\n[1] Persistence by outcome direction (all rows with a parseable window)")
    for k in ["Improved", "Mixed", "Worsened", "No effect"]:
        v = sorted(by_dir.get(k, []))
        if not v:
            continue
        frac = sum(1 for x in v if x > 90) / len(v)
        print(f"    {k:<11} n={len(v):<4} median={statistics.median(v):>7.1f} d"
              f"  mean={statistics.mean(v):>7.1f} d  frac>90d={frac:.2f}")

    improved, worsened = by_dir.get("Improved", []), by_dir.get("Worsened", [])
    try:
        from scipy.stats import mannwhitneyu
        u, p = mannwhitneyu(worsened, improved, alternative="greater")
        print(f"\n    Mann-Whitney U, one-sided (Worsened > Improved): "
              f"U={u:.1f}, p={p:.4f}, n={len(worsened)} vs {len(improved)}")
    except ImportError:
        print("\n    (scipy not available - skipping the test)")

    print("\n[2] CONFOUND CHECK: study design vs. outcome")
    tab = collections.defaultdict(collections.Counter)
    for r in rows:
        tab[r["direction"]]["multi" if is_multigen(r) else "within"] += 1
    for k in ["Improved", "Mixed", "Worsened", "No effect"]:
        c = tab[k]
        tot = sum(c.values())
        if tot:
            print(f"    {k:<11} within-gen={c['within']:<4} multi-gen={c['multi']:<4}"
                  f"  frac multi-gen={c['multi']/tot:.2f}")

    print("\n[3] STRATIFIED: within-generation rows only")
    strat = collections.defaultdict(list)
    for r in rows:
        if is_multigen(r):
            continue
        d = parse_days(r.get("persistence_days"))
        if d is not None:
            strat[r["direction"]].append(d)
    for k in ["Improved", "Mixed", "Worsened"]:
        v = sorted(strat.get(k, []))
        if v:
            print(f"    {k:<11} n={len(v):<3} median={statistics.median(v):>7.1f} d"
                  f"  mean={statistics.mean(v):>7.1f} d")

    print("\n" + "=" * 72)
    print("CONCLUSION")
    print("=" * 72)
    print("""
The raw association is present: rows scored 'Worsened' report substantially
longer persistence windows than rows scored 'Improved' (median 81 d vs 7 d),
and the one-sided test is nominally significant (p ~ 0.046).

It does NOT survive scrutiny. 'Worsened' rows are overwhelmingly
transgenerational (79% multi-generation, vs 25% of 'Improved' rows), and
transgenerational studies have long persistence windows BY DESIGN - the
window spans a whole generation regardless of how long any induced state
actually lasts. Stratifying to within-generation rows leaves n=2 'Worsened'
observations, which supports nothing in either direction.

So: this observation is CONSISTENT WITH the model's prediction and is worth
stating, but it is not evidence for it. The confound is structural, not a
sampling accident, and no reanalysis of the current atlas can break it.

Breaking it requires a study design the atlas does not currently contain:
within-generation conditioning, assayed for both the molecular state and a
fitness proxy at four or more timepoints spanning a decay window long enough
for the state to actually fade. That single design would also test the
model's exponential-decay assumption (MODEL.md, section 6.1). It is the
highest-value missing experiment for this whole line of work.
""".strip())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ATLAS))
