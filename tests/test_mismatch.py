"""
Tests for model/mismatch.py.

Two kinds of test here:

1. Correctness tests — the integrator, the PRNG, the half-life semantics,
   and the null model behave as MODEL.md says they do.
2. Structural-claim tests — the model's non-obvious behavioural findings are
   pinned down as assertions, so that if a future change to the model breaks
   them, that shows up as a failing test rather than as a quietly different
   story in the interface. The most important of these is
   `test_monotone_trend_alone_never_traps`.
"""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.mismatch import (  # noqa: E402
    DEFAULTS,
    Mulberry32,
    advantage,
    find_trap_threshold,
    phase_sweep,
    simulate,
)


def P(**kw):
    p = dict(DEFAULTS)
    p.update(kw)
    return p


# ---------------------------------------------------------------------------
# PRNG
# ---------------------------------------------------------------------------


def test_prng_is_deterministic_for_a_seed():
    a = [Mulberry32(7).random() for _ in range(5)]
    b = [Mulberry32(7).random() for _ in range(5)]
    assert a == b


def test_prng_differs_across_seeds():
    assert Mulberry32(1).random() != Mulberry32(2).random()


def test_prng_stays_in_unit_interval():
    r = Mulberry32(123)
    vals = [r.random() for _ in range(2000)]
    assert all(0.0 <= v < 1.0 for v in vals)


def test_prng_normal_is_roughly_standard():
    r = Mulberry32(99)
    vals = [r.normal() for _ in range(20000)]
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    assert abs(mean) < 0.05
    assert abs(var - 1.0) < 0.10


# ---------------------------------------------------------------------------
# Memory dynamics
# ---------------------------------------------------------------------------


def test_half_life_semantics():
    """With no induction, memory must halve in exactly `half_life` days.

    This is the whole reason the decay term is written as (ln2/h)*M: `h` has
    to be directly comparable to a persistence number a real study reports.
    """
    h = 40.0
    k = math.log(2.0) / h
    m = 1.0
    for _ in range(int(h)):
        m += -k * m
    # Euler at dt=1 undershoots the exact exponential slightly; allow 2%.
    assert abs(m - 0.5) < 0.02


def test_euler_step_is_fine_enough():
    """dt = 1 day must agree with a 10x finer integration.

    Guards the fixed-step integrator claim in MODEL.md section 2.
    """
    k = math.log(2.0) / 40.0
    coarse = 1.0
    for _ in range(40):
        coarse += -k * coarse
    fine = 1.0
    for _ in range(400):
        fine += -(k / 10.0) * fine
    assert abs(coarse - fine) < 0.01


def test_memory_stays_in_bounds():
    r = simulate(P(induction_rate=1.0, threshold=0.0, noise=2.0, years=5))
    assert all(0.0 <= m <= 1.0 for m in r["series"]["memory"])


def test_no_induction_below_threshold():
    """A benign world that never crosses threshold must leave memory at zero."""
    r = simulate(P(trend=0.0, seasonal_amplitude=0.0, noise=0.0, threshold=5.0, years=3))
    assert max(r["series"]["memory"]) == 0.0


def test_memory_accumulates_above_threshold():
    r = simulate(P(trend=0.0, seasonal_amplitude=0.0, noise=0.0, threshold=0.0,
                   induction_rate=0.2, half_life=100, years=2))
    # Constant zero environment is still >= threshold=0, but drive is 0, so
    # use a positive constant instead via a trend that saturates quickly.
    r2 = simulate(P(trend=2.0, seasonal_amplitude=0.0, noise=0.0, threshold=0.0,
                    induction_rate=0.2, half_life=100, years=2))
    assert max(r2["series"]["memory"]) > max(r["series"]["memory"])


# ---------------------------------------------------------------------------
# Fitness and the null model
# ---------------------------------------------------------------------------


def test_zero_gain_zero_cost_matches_null_exactly():
    """With no protective gain and no cost, the memory arm IS the null arm."""
    r = simulate(P(gain=0.0, cost=0.0, years=3))
    for w, wn in zip(r["series"]["fitness"], r["series"]["fitness_null"]):
        assert abs(w - wn) < 1e-12
    assert abs(r["summary"]["advantage"]) < 1e-12


def test_perfect_match_gives_fitness_one():
    """A dead-calm baseline world means zero mismatch and no memory to pay for."""
    r = simulate(P(trend=0.0, seasonal_amplitude=0.0, noise=0.0, threshold=5.0, years=1))
    assert all(abs(w - 1.0) < 1e-12 for w in r["series"]["fitness"])


def test_both_arms_see_identical_environment():
    """The comparison is only meaningful if the noise draw is shared."""
    a = simulate(P(years=3), seed=5)["series"]["environment"]
    b = simulate(P(years=3, gain=0.0, cost=0.0), seed=5)["series"]["environment"]
    assert a == b


def test_cost_monotonically_reduces_advantage():
    prev = float("inf")
    for c in [0.0, 0.1, 0.2, 0.4, 0.8]:
        adv = advantage(P(cost=c))
        assert adv < prev
        prev = adv


def test_zero_cost_removes_most_trapping():
    """With cost=0 memory can be useless but is far less able to be harmful.

    MODEL.md section 3 makes this claim explicitly; it is the reason the cost
    term (framework Q7) is what turns inefficiency into a trap.
    """
    trapped_with_cost = advantage(P(trend=0.0, half_life=400, gain=1.5, cost=0.4))
    trapped_no_cost = advantage(P(trend=0.0, half_life=400, gain=1.5, cost=0.0))
    assert trapped_with_cost < trapped_no_cost


# ---------------------------------------------------------------------------
# Structural findings (see README, "What the model actually says")
# ---------------------------------------------------------------------------


def test_long_memory_in_a_reversing_world_is_a_trap():
    """The core finding: memory outlasting the environment's reversal
    timescale over-prepares the organism and costs more than it returns."""
    adv = advantage(P(trend=0.0, seasonal_amplitude=2.0, half_life=365,
                      gain=1.5, cost=0.10, years=10))
    assert adv < 0.0


def test_short_memory_in_the_same_world_is_not_a_trap():
    adv = advantage(P(trend=0.0, seasonal_amplitude=2.0, half_life=15,
                      gain=1.5, cost=0.10, years=10))
    assert adv > 0.0


def test_monotone_trend_alone_never_traps():
    """A structural property, and the model's actual answer to Q8 as posed.

    With an upward-shifting memory and a symmetric tolerance curve, a purely
    monotone increase in stress cannot make memory worse than no memory: the
    memory arm is always at least as close to its optimum as the null arm.
    Raising the trend drives the advantage toward zero (both strategies fail)
    but never below it.

    If a future change to the model makes this test fail, the README's
    central claim needs rewriting too.
    """
    base = dict(seasonal_amplitude=0.0, noise=0.0, half_life=120,
                gain=1.2, cost=0.10, years=15)
    for trend in [0.1, 0.3, 0.6, 1.0, 2.0, 3.0]:
        adv = advantage(P(trend=trend, **base))
        assert adv >= -1e-9, f"monotone trend {trend} produced advantage {adv}"


def test_advantage_is_non_monotonic_in_trend():
    """Advantage peaks at an intermediate rate of change: too slow and there
    is nothing worth anticipating, too fast and nothing survives either way."""
    seq = [advantage(P(trend=t, half_life=40, gain=1.5, cost=0.10,
                       seasonal_amplitude=2.0)) for t in [0.0, 0.4, 2.0]]
    assert seq[1] > seq[0]
    assert seq[1] > seq[2]


def test_transgenerational_transfer_deepens_the_trap_when_generations_are_short():
    """The intergenerational trap is governed by generation time relative to
    the environmental cycle, not by transfer fidelity on its own.

    When a lineage turns over faster than the environment cycles, high-
    fidelity transfer accumulates an induced state across many generations
    that no single generation's conditions justify, and the advantage falls.
    The first version of this test asserted the effect unconditionally and
    failed: at generation_days == the 365 d cycle, transfer is nearly
    neutral, and at inheritance=0 an annual reset lands at the start of the
    warming season and is actively harmful. The dependence on generation
    time is the real finding.
    """
    common = dict(trend=0.1, seasonal_amplitude=2.0, half_life=300, gain=1.2,
                  cost=0.12, years=15)
    for gen_days in [60, 90, 180]:  # all shorter than the 365 d cycle
        low = advantage(P(inheritance=0.0, generation_days=gen_days, **common))
        high = advantage(P(inheritance=0.9, generation_days=gen_days, **common))
        assert high < low, f"gen_days={gen_days}: {high} !< {low}"


def test_full_inheritance_is_invariant_to_generation_time():
    """inheritance=1 makes the generation boundary a no-op, so generation
    time must stop mattering entirely. A good structural check that the
    boundary logic does nothing it shouldn't."""
    common = dict(trend=0.1, seasonal_amplitude=2.0, half_life=300, gain=1.2,
                  cost=0.12, inheritance=1.0, years=15)
    vals = [advantage(P(generation_days=gd, **common))
            for gd in [60, 90, 180, 365, 730, 1460]]
    assert max(vals) - min(vals) < 1e-12, vals


def test_inheritance_is_monotonic_and_continuous_at_zero():
    """Regression test for a real bug.

    An earlier version treated inheritance=0 as "disable generation
    boundaries", which made it behave identically to inheritance=1 (full
    carryover) while inheritance=0.01 behaved like a near-total reset. The
    slider was discontinuous and non-monotonic at its own minimum. Memory
    carried across a lineage must increase monotonically with the transfer
    fraction, with no jump at zero.
    """
    common = dict(trend=0.1, seasonal_amplitude=2.0, half_life=300,
                  generation_days=365, years=12)
    peaks = [
        max(simulate(P(inheritance=phi, **common))["series"]["memory"][-365:])
        for phi in [0.0, 0.01, 0.25, 0.5, 0.75, 1.0]
    ]
    assert peaks == sorted(peaks), f"not monotonic in inheritance: {peaks}"
    assert peaks[1] - peaks[0] < 0.5 * (peaks[-1] - peaks[0]), \
        "discontinuous jump between inheritance=0 and inheritance=0.01"


def test_long_generation_time_means_no_turnover():
    """Setting generation_days beyond the run length is the documented way
    to model a single long-lived individual."""
    a = simulate(P(inheritance=0.0, generation_days=100000, years=4),
                 keep_series=False)["summary"]
    b = simulate(P(inheritance=1.0, generation_days=100000, years=4),
                 keep_series=False)["summary"]
    assert a["advantage"] == b["advantage"]


# ---------------------------------------------------------------------------
# Trap threshold and phase sweep
# ---------------------------------------------------------------------------


def test_find_trap_threshold_returns_none_when_no_crossing():
    """No sign change in the bracket must return None, not a fake number."""
    out = find_trap_threshold(P(cost=0.0, gain=1.0, half_life=30),
                              axis="trend", lo=0.0, hi=1.0)
    assert out is None


def test_find_trap_threshold_locates_a_real_crossing():
    """Sweeping half-life in a reversing world crosses from safe to trapped."""
    p = P(trend=0.0, seasonal_amplitude=2.0, gain=1.5, cost=0.12, years=10)
    lo_adv = advantage({**p, "half_life": 10})
    hi_adv = advantage({**p, "half_life": 450})
    assert lo_adv > 0 > hi_adv, "bracket must actually straddle the boundary"

    thr = find_trap_threshold(p, axis="half_life", lo=10, hi=450, tolerance=1e-2)
    assert thr is not None
    assert 10 < thr < 450
    # advantage should be near zero at the located boundary
    assert abs(advantage({**p, "half_life": thr})) < 5e-3


def test_phase_sweep_shape_and_content():
    sweep = phase_sweep(P(years=3), x_values=[0.0, 0.5, 1.0],
                        y_values=[10.0, 100.0, 400.0])
    assert len(sweep["grid"]) == 3
    assert all(len(row) == 3 for row in sweep["grid"])
    assert sweep["min"] <= sweep["max"]
    assert 0.0 <= sweep["fraction_trapped"] <= 1.0


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [
    {"half_life": 0.0},
    {"half_life": -5.0},
    {"tolerance_width": 0.0},
    {"years": 0.0},
])
def test_invalid_parameters_raise(bad):
    with pytest.raises(ValueError):
        simulate(P(**bad))


def test_unknown_parameters_are_ignored_not_silently_applied():
    a = simulate(P(), keep_series=False)["summary"]["advantage"]
    b = simulate(P(not_a_real_parameter=999), keep_series=False)["summary"]["advantage"]
    assert a == b
