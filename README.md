# Mismatch Simulator

An interactive artifact for the epigenetic trap, built against the Roberts
Lab conceptual framework's unresolved Question 8:

> **Q8 — Mismatch threshold.** At what rate of environmental change does
> anticipatory memory tip from adaptive to maladaptive?

Open `index.html` in any browser. Move the sliders. The
question becomes something you can push on rather than something you can
only restate.

**The model is a toy.** Its parameter *ranges* are anchored to real
persistence measurements from the [Conditioning Atlas](#provenance); its
*functional forms* are assumptions chosen to be interpretable, not derived
from marine invertebrate physiology and not fitted to any dataset. It exists
to sharpen the question and generate testable predictions. No number it
produces should appear in a manuscript as a result. `MODEL.md` states every
equation and every assumption.

---

## What the model actually says

The headline result is not the one the question's phrasing anticipates, and
it is the main reason this was worth building.

**Under purely monotone directional change, anticipatory memory is never
worse than no memory.** If stress only ever rises and the induced state
shifts tolerance upward, the memory-carrying lineage is always at least as
close to its optimum as the null lineage. Raising the rate of change drives
the *advantage* toward zero — both strategies fail together — but never
below it. `tests/test_mismatch.py::test_monotone_trend_alone_never_traps`
pins this down as a structural property, not a parameter accident.

**The trap appears when memory outlasts the timescale on which the
environment reverses.** A state induced by a summer heat pulse is still
being maintained, and paid for, in winter. The controlling quantity is the
ratio of memory half-life to environmental reversal time — not the rate of
the trend. On the simulator's phase diagram the trap region sits in the
upper *left*: long memory, slow change.

So the model's answer to Q8 as posed is that **rate of change is the wrong
axis**. The productive reframing is: *how long does an induced state persist,
relative to how long the environment stays in the state that induced it?*
That is a question the lab can answer with a decay time-course, and the
Conditioning Atlas shows it currently cannot be answered at all (below).

Two secondary findings, both pinned by tests:

- **Advantage is non-monotonic in the rate of change.** It peaks at an
  intermediate rate: too slow and there is nothing worth anticipating, too
  fast and nothing survives either way.
- **The intergenerational trap depends on generation time, not transfer
  fidelity alone.** High-fidelity transgenerational transfer deepens the
  trap only when a lineage turns over *faster* than the environment cycles.
  At generation times at or beyond the cycle length, transfer is close to
  neutral. This corrected an assumption that was wrong in the first draft —
  see `CHANGELOG.md`.

## Does the atlas support the model? Honestly: not yet

The model predicts that longer-persisting memory should be over-represented
among experiments where conditioning left animals worse off. That is
checkable against the Conditioning Atlas, which scores each row's outcome
direction and records a persistence window. `scripts/atlas_signal_check.py`
runs the check and is the authority; the summary:

**The raw association is there.** Rows scored `Worsened` report substantially
longer persistence than rows scored `Improved` (median 81 d vs 7 d;
one-sided Mann-Whitney p ≈ 0.046, n = 10 vs 39).

**It does not survive scrutiny, and should not be cited as support.**
`Worsened` rows are overwhelmingly transgenerational (79% multi-generation
vs 25% of `Improved` rows), and transgenerational studies have long
persistence windows *by design* — the window spans a generation regardless
of how long any induced state actually lasts. Stratifying to
within-generation rows leaves n = 2 `Worsened` observations, which supports
nothing in either direction. The confound is structural; no reanalysis of
the current atlas can break it.

What would break it is a study design the atlas does not contain:
within-generation conditioning, assaying both the molecular state and a
fitness proxy at **four or more timepoints** spanning a decay window long
enough for the state to actually fade. That same design would test the
model's exponential-decay assumption directly. It is the highest-value
missing experiment for this whole line of work, and it falls out of the
model rather than out of intuition.

## What's here

| File | What it is | Edit by hand? |
|---|---|---|
| `MODEL.md` | Every equation, every assumption, every documented simplification, and what would have to be true for the model to describe a real system. | Yes — this is the spec |
| `data/parameters.json` | Slider ranges, the six preset scenarios and their anchor studies, the atlas persistence-bound evidence block, and the 14 observed `Worsened` rows. **Source of truth for the built artifact.** | Yes |
| `model/mismatch.py` | Reference implementation: `simulate`, `advantage`, `find_trap_threshold`, `phase_sweep`. Standard library only. **This is the authority.** | Yes |
| `tests/test_mismatch.py` | 30 tests: integrator correctness, PRNG, half-life semantics, null-model identities, and the structural findings above pinned as assertions. | Yes |
| `simulator_template.html` | The real source for the interactive artifact — layout, styling, charts, and the JavaScript copy of the model. | Yes |
| `index.html` | The self-contained built artifact. | **No — generated** |
| `scripts/build_simulator.py` | Injects `data/parameters.json` into the template. | Yes |
| `scripts/crossvalidate_js.py` | Runs the built artifact's real JavaScript in headless Chromium and compares it against `model/mismatch.py` over 36 parameter/seed combinations. Fails on any divergence. | Yes |
| `scripts/atlas_signal_check.py` | Reproduces the atlas confound analysis above. | Yes |
| `CHANGELOG.md` | What changed and why, including the two bugs the tests caught. | Yes — append |

## Running it

```bash
pip install -r requirements.txt --break-system-packages   # pytest + scipy only
npm ci                                                    # browser driver for cross-validation
npx playwright install chromium                           # Chromium for cross-validation
python3 -m pytest tests/ -q                # 30 tests
python3 scripts/build_simulator.py         # regenerate the artifact
python3 scripts/crossvalidate_js.py        # verify JS == Python  (needs node + playwright)
python3 scripts/atlas_signal_check.py      # reproduce the atlas analysis
```

`model/mismatch.py` itself has no dependencies beyond the standard library.
`scipy` is only used by the atlas check, `pytest` only by the tests, and
`playwright` (npm) only by the cross-validation.

## Why there are two implementations of the model

The interactive artifact must run in a browser with no server, so it ships
its own copy of the model in JavaScript. Two implementations of the same
equations is exactly the situation where they quietly drift apart and the
picture on screen stops matching the picture in the tests.

`scripts/crossvalidate_js.py` prevents that. It loads the **real built
HTML** in headless Chromium, calls its actual `simulate()` across a grid of
parameter sets plus every shipped preset, and compares all eleven summary
statistics against the Python reference. Current agreement is to **1.8e-15**
— essentially bit-exact, because both run the same IEEE-754 operations in
the same order, including a hand-matched `mulberry32` PRNG so even the noise
draws are identical.

**If you edit the JS model block in `simulator_template.html`, edit
`model/mismatch.py` alongside it and re-run that script.** It is the only
thing standing between the artifact and silent divergence.

## Maintenance

See [`CONTRIBUTING.md`](CONTRIBUTING.md) before changing the model. In
particular, read `MODEL.md` and ["Why there are two implementations of the
model"](#why-there-are-two-implementations-of-the-model) before editing
either implementation.

### Changing the model

1. Update `MODEL.md` first — the specification is the contract.
2. Change `model/mismatch.py` and the JS block in `simulator_template.html`
   together.
3. Add or update tests. If a change breaks
   `test_monotone_trend_alone_never_traps` or the transgenerational tests,
   the README's "What the model actually says" section needs rewriting too —
   those tests exist to make that coupling impossible to miss.
4. `python3 -m pytest tests/ -q && python3 scripts/build_simulator.py && python3 scripts/crossvalidate_js.py`
5. Append to `CHANGELOG.md`.

### Adding or retuning a preset

Presets live in `data/parameters.json`. Each carries `anchor_studies` and an
`anchor_note` naming the real experiments it is drawn from — keep that
discipline, since a preset with no provenance is just a number someone
liked. **Verify the preset actually demonstrates what its name claims**: the
first `urchin_trap` preset did not produce a trap at all, which is exactly
the kind of thing that survives to release if nobody checks. Rebuild and
re-run the cross-validation afterward (it exercises every shipped preset).

### Refreshing the atlas anchors

`data/parameters.json`'s `atlas_evidence` and `observed_trap_instances`
blocks are derived from the Conditioning Atlas's `merged.json`. If the atlas
gains rows, re-derive them and re-run `scripts/atlas_signal_check.py` to see
whether the confound has broken — new within-generation, multi-timepoint
studies are precisely what would change that answer.

## Provenance

- Persistence bounds, preset anchors, and the observed-trap list come from
  the **Conditioning Atlas** (109 conditioning experiments extracted from
  105 papers across PubMed, Consensus, and Scite; every DOI checked for
  editorial notices). Those rows are themselves a screening resource, not a
  registered systematic review — see that project's README.
- Read every persistence number as a **censored bound, not a measurement**.
  "Persisted" means the effect was still detectable at the last timepoint
  tested (a *lower* bound on half-life); "decayed" means it was substantially
  gone by then (a rough upper bound). Most atlas rows tested a single
  timepoint. Coral thermal priming alone spans 8 d (Glass 2023, decayed) to
  365 d (Wong 2021, still present) — two orders of magnitude, same taxon,
  same stressor.
- Related projects in this series: **Conditioning Atlas** (the priming
  literature, structured), **Framework Sentinel** (weekly scoring of new
  literature against all ten framework questions), **Held-Out Prediction
  Rig** (Question 10).
