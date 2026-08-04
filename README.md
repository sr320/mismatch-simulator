# Mismatch simulator

A self-contained interactive teaching model for the environmental-memory trade-off:
when does anticipatory priming help, and when does a changing environment turn it
into an epigenetic trap?

Open `index.html` in a modern browser. It has no dependencies or build step.

## Model

The chart compares relative fitness of three conceptual strategies:

- **Frontloaded** — continuous, broad preparedness with a fixed constitutive cost.
- **Reactive** — condition-specific response after a lag and an inducible-plasticity cost.
- **Memory-primed** — recovered response speed when retained experience matches the next stress event, plus an explicit penalty for stale priming.

For stress interval `P`, memory half-life `H`, environmental turnover per
generation `v`, and plasticity cost `c`:

```text
r = 2^(-P/H)       retained memory between events
q = (1-v)^P        similarity of the next cue to retained experience
```

The mismatch threshold is the first displayed environmental-change rate at which
memory-primed relative fitness is no greater than the best frontloaded or reactive
alternative.

The coefficients in `MODEL_CONFIG` are conceptual defaults, not empirical
estimates. The app is therefore a hypothesis generator and teaching figure, not a
biological forecast.
