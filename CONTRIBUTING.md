# Contributing

Before changing the model, read these two documents:

1. [`MODEL.md`](MODEL.md), the specification for every equation and
   assumption.
2. README: [Why there are two implementations of the model](README.md#why-there-are-two-implementations-of-the-model),
   which explains why the Python and JavaScript implementations must change
   together.

The Python reference implementation is `model/mismatch.py`. The browser copy
is in `simulator_template.html`; `index.html` is generated and must not be
edited directly. Parameter ranges and presets live in `data/parameters.json`.

## Development checks

Install the Python and browser dependencies:

```bash
pip install -r requirements.txt
npm ci
npx playwright install chromium
```

Before opening a pull request, run:

```bash
python3 -m pytest tests/ -q
python3 scripts/build_simulator.py
python3 scripts/crossvalidate_js.py
git diff --exit-code -- index.html
```

When changing model behavior:

1. Update `MODEL.md` first.
2. Change the Python and JavaScript implementations together.
3. Add or update tests.
4. Rebuild `index.html` and run the cross-validator.
5. Append the user-visible change and its rationale to `CHANGELOG.md`.

Presets must retain their `anchor_studies` and `anchor_note` provenance, and
must be checked to confirm that they demonstrate what their names claim.
