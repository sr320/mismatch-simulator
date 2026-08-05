"""
Reference implementation of the mismatch / epigenetic-trap model.

See ../MODEL.md for the full specification, assumptions, and limitations.
This module is the authority: the JavaScript copy embedded in the
interactive simulator is cross-validated against it by
scripts/crossvalidate_js.py, which fails loudly on any numerical divergence.

Everything here is deliberately dependency-free (standard library only) so
the two implementations can be compared line-for-line without numpy's
vectorised semantics getting in the way.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Deterministic PRNG
# ---------------------------------------------------------------------------
# mulberry32, reimplemented with explicit 32-bit unsigned arithmetic so it
# produces bit-identical output to the JavaScript version in the simulator.
# Both arms of every comparison (memory vs. no-memory) must see the SAME
# environmental noise sequence, so a shared seeded stream is not a
# convenience here — it is required for the comparison to mean anything.


def _u32(x: int) -> int:
    return x & 0xFFFFFFFF


def _imul(a: int, b: int) -> int:
    """Equivalent of JavaScript's Math.imul, on unsigned 32-bit patterns."""
    return _u32(_u32(a) * _u32(b))


class Mulberry32:
    """Small, fast, fully specified PRNG. Identical in Python and JS."""

    def __init__(self, seed: int = 42):
        self.a = _u32(seed)

    def random(self) -> float:
        self.a = _u32(self.a + 0x6D2B79F5)
        a = self.a
        t = _imul(a ^ (a >> 15), 1 | a)
        t = _u32(_u32(t + _imul(t ^ (t >> 7), 61 | t)) ^ t)
        return _u32(t ^ (t >> 14)) / 4294967296.0

    def normal(self) -> float:
        """Box-Muller. Same construction as the JS side."""
        u1 = self.random()
        if u1 < 1e-12:
            u1 = 1e-12
        u2 = self.random()
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULTS: Dict[str, float] = {
    "trend": 0.35,               # stress units per YEAR
    "half_life": 60.0,           # days
    "induction_rate": 0.12,      # per day per stress unit
    "threshold": 0.8,            # stress units
    "gain": 1.0,                 # stress units of tolerance per unit memory
    "cost": 0.06,                # fitness penalty per unit memory
    "tolerance_width": 1.5,      # stress units
    "noise": 0.5,                # stress units SD
    "seasonal_amplitude": 1.5,   # stress units
    "inheritance": 0.0,          # fraction transferred at generation boundary
    "generation_days": 365.0,
    "years": 10.0,
}

M_MAX = 1.0


def _merge(params: Optional[Dict[str, float]]) -> Dict[str, float]:
    merged = dict(DEFAULTS)
    if params:
        merged.update({k: v for k, v in params.items() if k in DEFAULTS})
    return merged


# ---------------------------------------------------------------------------
# Core simulation
# ---------------------------------------------------------------------------


def simulate(params: Optional[Dict[str, float]] = None, seed: int = 42,
             keep_series: bool = True) -> Dict:
    """Run one lineage forward and return its trajectory and summary.

    Convention: on each day, fitness is evaluated using the memory state at
    the START of that day, then the memory state is advanced. Generation
    boundaries are applied after the day's update.

    Returns a dict with (optionally) the daily series and always a `summary`
    holding mean/geometric-mean fitness for the memory and no-memory arms
    and the resulting advantage.
    """
    p = _merge(params)

    n_days = int(round(p["years"] * 365.0))
    if n_days < 1:
        raise ValueError("years must correspond to at least one day")
    if p["half_life"] <= 0:
        raise ValueError("half_life must be positive")
    if p["tolerance_width"] <= 0:
        raise ValueError("tolerance_width must be positive")

    decay_k = math.log(2.0) / p["half_life"]
    trend_daily = p["trend"] / 365.0
    two_w_sq = 2.0 * p["tolerance_width"] * p["tolerance_width"]
    gen_days = int(round(p["generation_days"]))
    # Generation boundaries ALWAYS apply when generation_days is inside the
    # run: the lineage turns over whether or not anything is inherited, and
    # `inheritance` controls only how much of the induced state crosses the
    # boundary. inheritance=0 therefore means a full reset each generation,
    # not "no boundaries" — an earlier version conflated the two, which made
    # the parameter discontinuous at zero (0 behaved like 1). To model a
    # single long-lived individual with no turnover at all, set
    # generation_days >= the run length.
    apply_generations = gen_days > 0

    rng = Mulberry32(seed)

    memory = 0.0
    sum_w = 0.0
    sum_w_null = 0.0
    sum_log_w = 0.0
    sum_log_w_null = 0.0
    sum_mismatch_abs = 0.0
    peak_memory = 0.0

    # "Late window" = final 20% of the run. Under a directional trend the
    # run-mean is dominated by the early, low-stress years, which can hide
    # what the lineage's situation actually looks like after the change has
    # accumulated. The late window is the more honest read for Q8.
    late_start = int(n_days * 0.8)
    late_sum_w = 0.0
    late_sum_w_null = 0.0
    late_n = 0

    series_t: List[float] = []
    series_e: List[float] = []
    series_m: List[float] = []
    series_w: List[float] = []
    series_w_null: List[float] = []

    for i in range(n_days):
        t = float(i)

        env = (trend_daily * t
               + p["seasonal_amplitude"] * math.sin(2.0 * math.pi * t / 365.0)
               + p["noise"] * rng.normal())

        # --- fitness, using memory state at the start of the day ---
        prepared = p["gain"] * memory
        delta = env - prepared
        w = math.exp(-(delta * delta) / two_w_sq) * math.exp(-p["cost"] * memory)
        w_null = math.exp(-(env * env) / two_w_sq)

        sum_w += w
        sum_w_null += w_null
        sum_log_w += math.log(max(w, 1e-300))
        sum_log_w_null += math.log(max(w_null, 1e-300))
        sum_mismatch_abs += abs(delta)
        if memory > peak_memory:
            peak_memory = memory
        if i >= late_start:
            late_sum_w += w
            late_sum_w_null += w_null
            late_n += 1

        if keep_series:
            series_t.append(t)
            series_e.append(env)
            series_m.append(memory)
            series_w.append(w)
            series_w_null.append(w_null)

        # --- advance memory ---
        drive = env - p["threshold"]
        if drive < 0.0:
            drive = 0.0
        d_memory = (p["induction_rate"] * drive * (1.0 - memory / M_MAX)
                    - decay_k * memory)
        memory += d_memory
        if memory < 0.0:
            memory = 0.0
        elif memory > M_MAX:
            memory = M_MAX

        # --- generation boundary ---
        if apply_generations and ((i + 1) % gen_days == 0):
            memory *= p["inheritance"]

    n = float(n_days)
    mean_w = sum_w / n
    mean_w_null = sum_w_null / n
    late_n_f = float(late_n) if late_n > 0 else 1.0
    late_w = late_sum_w / late_n_f
    late_w_null = late_sum_w_null / late_n_f

    summary = {
        "n_days": n_days,
        "mean_fitness": mean_w,
        "mean_fitness_null": mean_w_null,
        "advantage": mean_w - mean_w_null,
        "late_fitness": late_w,
        "late_fitness_null": late_w_null,
        "late_advantage": late_w - late_w_null,
        "geo_mean_fitness": math.exp(sum_log_w / n),
        "geo_mean_fitness_null": math.exp(sum_log_w_null / n),
        "geo_advantage": math.exp(sum_log_w / n) - math.exp(sum_log_w_null / n),
        "mean_abs_mismatch": sum_mismatch_abs / n,
        "peak_memory": peak_memory,
        "trapped": (mean_w - mean_w_null) < 0.0,
    }

    out = {"summary": summary, "params": p, "seed": seed}
    if keep_series:
        out["series"] = {
            "t": series_t, "environment": series_e, "memory": series_m,
            "fitness": series_w, "fitness_null": series_w_null,
        }
    return out


def advantage(params: Optional[Dict[str, float]] = None, seed: int = 42) -> float:
    """Mean-fitness advantage of having memory over having none.

    Negative means the lineage would be better off with no environmental
    memory at all — the trap.
    """
    return simulate(params, seed=seed, keep_series=False)["summary"]["advantage"]


# ---------------------------------------------------------------------------
# Trap boundary
# ---------------------------------------------------------------------------


def find_trap_threshold(params: Optional[Dict[str, float]] = None,
                        seed: int = 42,
                        axis: str = "trend",
                        lo: float = 0.0,
                        hi: float = 3.0,
                        tolerance: float = 1e-3,
                        max_iter: int = 60) -> Optional[float]:
    """Bisect along `axis` for the value where advantage crosses zero.

    Returns None when the sign does not change across [lo, hi] — i.e. the
    boundary is not inside the bracket (memory is either always or never
    worth having over that range), which is itself a meaningful answer and
    should not be reported as a threshold.
    """
    p = _merge(params)

    def adv_at(x: float) -> float:
        q = dict(p)
        q[axis] = x
        return advantage(q, seed=seed)

    a_lo = adv_at(lo)
    a_hi = adv_at(hi)
    if a_lo == 0.0:
        return lo
    if a_hi == 0.0:
        return hi
    if (a_lo > 0.0) == (a_hi > 0.0):
        return None

    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        a_mid = adv_at(mid)
        if abs(hi - lo) < tolerance:
            return mid
        if (a_mid > 0.0) == (a_lo > 0.0):
            lo, a_lo = mid, a_mid
        else:
            hi, a_hi = mid, a_mid
    return 0.5 * (lo + hi)


def phase_sweep(params: Optional[Dict[str, float]] = None,
                seed: int = 42,
                x_axis: str = "trend",
                x_values: Optional[List[float]] = None,
                y_axis: str = "half_life",
                y_values: Optional[List[float]] = None) -> Dict:
    """Advantage across a 2-D parameter grid.

    The contour advantage = 0 in this grid is the trap boundary, and sweeping
    rate-of-change against memory half-life is the model's direct answer to
    framework Question 8.
    """
    p = _merge(params)
    if x_values is None:
        x_values = [i * (1.5 / 29.0) for i in range(30)]
    if y_values is None:
        y_values = [5.0 + i * (395.0 / 23.0) for i in range(24)]

    grid: List[List[float]] = []
    for y in y_values:
        row: List[float] = []
        for x in x_values:
            q = dict(p)
            q[x_axis] = x
            q[y_axis] = y
            row.append(advantage(q, seed=seed))
        grid.append(row)

    flat = [v for row in grid for v in row]
    return {
        "x_axis": x_axis, "x_values": x_values,
        "y_axis": y_axis, "y_values": y_values,
        "grid": grid,
        "min": min(flat), "max": max(flat),
        "fraction_trapped": sum(1 for v in flat if v < 0) / len(flat),
    }
