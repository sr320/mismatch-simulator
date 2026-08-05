# The mismatch model

The Roberts Lab conceptual framework's unresolved Question 8 asks:

> **Q8 — Mismatch threshold.** At what rate of environmental change does
> anticipatory memory tip from adaptive to maladaptive?

This document specifies the toy dynamical model this repository uses to make
that question answerable — not for real organisms, but as a precise
statement of what "the epigenetic trap" would have to mean mechanically, and
what quantities would have to be measured to locate the threshold in a real
system.

**Read this first: the model is a toy.** Its parameter *ranges* are anchored
to real measurements from the Conditioning Atlas; its *functional forms* are
assumptions chosen for interpretability, not derived from marine
invertebrate physiology and not fitted to any dataset. It generates
intuition and testable predictions. It does not forecast outcomes for any
real population, and no number it produces should appear in a manuscript as
a result.

---

## 1. Environment

Time `t` runs in days. The environmental stress level is

```
E(t) = trend_daily * t  +  A * sin(2*pi*t / 365)  +  sigma * xi(t)
```

| Symbol | Name | Meaning |
|---|---|---|
| `trend_daily` | rate of change | directional trend, entered in the UI as stress units per **year** and divided by 365 internally |
| `A` | seasonal amplitude | predictable annual cycling |
| `sigma` | noise | SD of unpredictable day-to-day variation, `xi(t) ~ N(0,1)` i.i.d. |

`E` is measured in **stress units above the local long-term baseline**, so
`E = 0` is "the environment this lineage is historically adapted to." For
thermal scenarios, read one unit as one degree C.

Noise is drawn from a seeded PRNG so that every run is reproducible and,
critically, so that the memory and no-memory arms of a comparison experience
**exactly the same environmental sequence**. Comparing two organisms across
different noise draws would confound the thing being measured.

## 2. Memory

The organism carries an internal anticipatory state `M(t) >= 0` — the
induced epigenetic/physiological condition. It is induced by supra-threshold
stress and decays exponentially back to baseline:

```
dM/dt  =  induction_rate * max(0, E(t) - threshold) * (1 - M/M_max)   -   (ln 2 / h) * M
```

- The induction term is zero unless stress exceeds `threshold`, and
  saturates as `M` approaches the ceiling `M_max` (fixed at 1 — memory is
  expressed as a fraction of maximum possible induction, so `gain` below
  carries the units).
- The decay term is written as `(ln 2 / h) * M` specifically so that **`h` is
  the memory half-life in days** and nothing else. That makes `h` the one
  parameter the Conditioning Atlas directly constrains, and makes the slider
  in the interface comparable to a number a real experiment reports.

Integrated with fixed-step Euler at `dt = 1 day`. Step size is validated
against a 10x-finer integration in the test suite.

## 3. Phenotype, mismatch, and fitness

The organism's phenotype is tuned for the stress level

```
E_prepared(t) = gain * M(t)
```

so an animal with no memory is prepared for baseline (`E_prepared = 0`) and
a fully-induced animal is prepared for `gain` units of stress. The
**mismatch** is the gap between what it is prepared for and what it actually
gets:

```
delta(t) = E(t) - E_prepared(t)
```

Instantaneous performance is Gaussian in the mismatch and exponentially
penalised by the metabolic burden of holding the induced state:

```
W(t) = exp( -delta(t)^2 / (2 * w^2) )  *  exp( -cost * M(t) )
```

| Term | Framework link |
|---|---|
| `exp(-delta^2 / 2w^2)` | the mismatch cost itself — `w` is tolerance breadth |
| `exp(-cost * M)` | **Question 7**, the energetic cost of maintaining high-turnover regulatory states |

The cost term is what makes the trap a *trap* rather than a mild
inefficiency. With `cost = 0`, memory can be useless but never actively
harmful, and the trap boundary disappears — this is a deliberately available
setting, and the test suite asserts that behaviour.

Run-level performance is the mean of `W(t)` over the simulation.

**Documented simplification.** The Gaussian is symmetric: being prepared for
more stress than arrives is penalised exactly as hard as being prepared for
less. Real tolerance curves are typically asymmetric. The `cost` term does
partial duty here — over-preparation is separately penalised by the energetic
term even when the mismatch is small — but a genuinely asymmetric performance
curve would be a reasonable extension.

## 4. Transgenerational transfer

When `inheritance > 0`, the simulation follows a **lineage** rather than an
individual. At each generation boundary (every `generation_days`), the
memory state is multiplied by the inheritance fidelity:

```
M(t_gen+) = inheritance * M(t_gen-)
```

The new individual then continues accumulating from that inherited starting
point. This is the intergenerational form of the trap: with high fidelity
and a fast trend, a lineage carries forward a state induced by conditions
its ancestors experienced and its descendants will never see.

Note that this makes `inheritance` and `h` partially redundant as ways of
extending memory — a deliberate feature, since the interesting question is
whether *cross-generation* persistence traps a lineage differently from
simply having a long within-generation half-life. The phase diagram can be
computed against either axis.

## 5. The null model and the trap boundary

The comparison organism is the **same organism with no plasticity at all**:
`gain = 0` and `cost = 0`, so its phenotype is fixed at baseline and it pays
nothing to maintain it. It experiences the identical environmental sequence.

```
W_null(t) = exp( -E(t)^2 / (2 * w^2) )
```

Define the **advantage** of having memory:

```
advantage = mean(W_memory) - mean(W_null)
```

- `advantage > 0` — anticipatory memory pays for itself.
- `advantage < 0` — **the trap**: the lineage would do better with no
  environmental memory at all than with the memory it has.

The **trap boundary** is the contour `advantage = 0` in whatever parameter
plane is being swept. Sweeping *rate of environmental change* against
*memory half-life* and drawing that contour is the model's direct answer to
Q8 as posed: for a given memory half-life, the boundary gives the rate of
change at which that memory stops being worth having.

`find_trap_threshold()` locates the boundary along the rate axis by bisection
for a fixed set of other parameters.

## 6. What would have to be true for this to describe a real system

The model makes commitments that are, in principle, measurable — this list is
the point of building it:

1. **Memory decays approximately exponentially with a characteristic
   half-life.** The atlas cannot currently confirm this: nearly every
   included study tested a single post-conditioning timepoint, giving a
   censored bound rather than a decay curve. A study measuring the same
   induced marker at four or more timepoints across a decay window would
   test the functional form directly. This is the single highest-value
   missing measurement for the whole model.
2. **Maintaining an induced state carries a measurable metabolic cost that
   scales with the degree of induction.** Framework Question 7. If `cost` is
   effectively zero in real animals, the trap as modelled here cannot occur
   and the 14 observed "Worsened" outcomes in the atlas need a different
   explanation.
3. **Protective gain saturates.** Modelled via the `(1 - M/M_max)` ceiling.
4. **The environment's predictable component is what memory tracks.** Memory
   integrates recent experience, so it necessarily lags; the model says the
   lag is harmless when change is slow relative to `h` and lethal when it is
   fast.

## 7. Known limitations

- **No genetic adaptation.** Selection across generations is absent; only
  the plastic response is modelled. Over the 10-30 year horizons the
  simulator runs, real populations would also be evolving.
- **No population structure, mortality, or demography.** `W(t)` is a
  performance index for a single lineage, not a population growth rate.
- **One stressor.** The atlas shows multi-stressor conditioning frequently
  behaves non-additively (Framework Sentinel's Thyrring_2026 hit is a direct
  example); this model has a single stress axis.
- **Arithmetic, not geometric, mean fitness.** Geometric mean is the
  standard fitness measure in a variable environment. Arithmetic mean is
  used here because it is easier to reason about interactively and because
  the trap boundary's *sign* is what matters, not its magnitude — but the
  two can rank strategies differently when variance is large. `simulate()`
  returns both; the interface displays the arithmetic mean.
- **Parameters other than half-life are weakly constrained.** Induction
  rate, cost, tolerance breadth, and gain are set to plausible values, not
  measured ones. The phase diagram's *shape* is more trustworthy than any
  specific threshold value it reports.
