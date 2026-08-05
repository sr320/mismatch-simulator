# Mismatch Simulator — changelog

## 2026-08-05 — Initial build

### Model

- Specified the model in `MODEL.md`: environment (trend + seasonality +
  seeded noise), memory with an explicit **half-life** parameterisation so
  the slider is directly comparable to a persistence number a real study
  reports, Gaussian mismatch fitness, an energetic maintenance cost coupling
  to framework Question 7, and discrete transgenerational transfer at
  generation boundaries.
- Implemented the reference model in `model/mismatch.py` (standard library
  only): `simulate`, `advantage`, `find_trap_threshold` (bisection, returns
  `None` rather than a fabricated number when the bracket contains no
  crossing), and `phase_sweep`.
- Added a `late_advantage` metric over the final fifth of a run. Under a
  directional trend the run-mean is dominated by the early low-stress years,
  which can hide what the lineage's situation looks like after the change has
  actually accumulated.

### Parameters

- Derived slider ranges and six preset scenarios from the **Conditioning
  Atlas** (109 experiments), with per-preset `anchor_studies` and provenance
  notes: coral thermal priming short (Louis 2025 / Glass 2023 /
  Hazraty-Kari 2023) and long (Drury 2022 / Wong 2021), oyster immune
  priming (Lafont 2017a/b, 2020), oyster transgenerational pH (Parker 2015 /
  Venkataraman 2019 / Spencer 2020), urchin multigenerational (Uthicke 2021 /
  2024), and a stationary control world.
- Recorded the atlas's persistence bounds per taxon × stressor, explicitly
  labelled as **censored bounds rather than measurements**, and the 14 of 109
  rows scored `Worsened` — the empirical footprint of the trap.

### Findings

- **Central result, and not the expected one:** under purely monotone
  directional change an upward-shifting memory is never worse than no memory
  — the advantage falls toward zero as both strategies fail, but never below
  it. The trap instead requires the environment to *reverse* on a timescale
  shorter than the memory's half-life. Q8's "rate of change" is therefore the
  wrong axis; the ratio of memory half-life to environmental reversal time is
  the controlling quantity. Pinned by
  `test_monotone_trend_alone_never_traps`.
- Advantage is **non-monotonic in the rate of change**, peaking at an
  intermediate rate.
- Tested the model's central prediction against the atlas
  (`scripts/atlas_signal_check.py`): `Worsened` rows do report longer
  persistence than `Improved` rows (median 81 d vs 7 d, one-sided p ≈ 0.046),
  **but the association is confounded** — 79% of `Worsened` rows are
  transgenerational vs 25% of `Improved`, and transgenerational studies have
  long persistence windows by design. Stratifying leaves n = 2. Recorded as
  consistent-with but **not evidence for**, with the confound and the study
  design that would break it written up in `README.md`.

### Bugs caught by tests before release

- **`inheritance = 0` was disabling generation boundaries entirely**, so it
  behaved identically to `inheritance = 1` (full carryover) while
  `inheritance = 0.01` behaved like a near-total reset. The slider was
  discontinuous and non-monotonic at its own minimum. Fixed so boundaries
  always apply and `inheritance` controls only how much crosses them;
  modelling a single long-lived individual is now done by setting
  `generation_days` beyond the run length. Regression test added.
- **A test asserted that transgenerational transfer always deepens the
  trap.** It failed, and the test was wrong, not the code: transfer deepens
  the trap only when generation time is *shorter* than the environmental
  cycle. At `generation_days == 365` against a 365 d cycle the effect is
  nearly neutral, and an `inheritance = 0` annual reset landing at the start
  of the warming season is itself harmful. Test rewritten to assert the real
  dependence, and a `test_full_inheritance_is_invariant_to_generation_time`
  structural check added alongside it.
- **The `urchin_trap` preset did not produce a trap** (advantage +0.044) —
  a preset whose entire purpose is to demonstrate one. Retuned to a
  configuration that is genuinely trapped (−0.072) and verified robust across
  five noise seeds and a range of cost, half-life, and seasonality values.

### Artifact

- Built the interactive simulator: twelve parameter sliders, six anchored
  presets, a live time-series chart (environment, memory, and performance
  against a no-memory null on the identical noise draw), and a phase diagram
  over rate-of-change × half-life with the trap boundary contour and the
  current settings marked. Real atlas studies are plotted as anchors on the
  half-life axis. Light/dark themes; no external dependencies.
- Added `scripts/crossvalidate_js.py`: loads the **built** HTML in headless
  Chromium, runs its actual `simulate()` over 36 parameter/seed combinations
  including every shipped preset, and compares all eleven summary statistics
  against the Python reference. Agreement is **1.8e-15** — bit-exact in
  practice, including a hand-matched `mulberry32` PRNG so the noise draws
  themselves are identical.
- 30 tests passing; artifact verified in both themes with no console errors.
