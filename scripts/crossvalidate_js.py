#!/usr/bin/env python3
"""
Cross-validate the JavaScript model in the built simulator against the
Python reference implementation in model/mismatch.py.

Why this exists: the interactive artifact ships its own copy of the model in
JavaScript, because it has to run in a browser with no server. Two
implementations of the same equations is exactly the situation where they
silently drift apart and the picture on screen stops matching the picture in
the tests. This script loads the REAL built HTML in headless Chromium, runs
its actual `simulate()` over a grid of parameter sets plus the shipped
presets, and compares every summary statistic against Python.

Any divergence beyond floating-point noise is a build failure.

Usage:
    python3 scripts/crossvalidate_js.py
Exit code 0 = implementations agree; 1 = they do not.
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from model.mismatch import DEFAULTS, simulate  # noqa: E402

BUILT = os.path.join(ROOT, "index.html")
CHROMIUM = "/opt/pw-browsers/chromium"

# Absolute tolerance for a summary statistic. The two implementations do the
# same IEEE-754 double operations in the same order, so agreement should be
# near-exact; anything above this means a genuine logic difference, not
# accumulated rounding.
TOL = 1e-9

# Parameter sets spanning the interesting corners of the model: the trap
# region, the safe region, monotone-trend-only, heavy transgenerational
# transfer, zero cost, extreme half-lives, and short generations.
CASES = [
    {},
    {"trend": 0.0, "half_life": 400, "gain": 1.5, "cost": 0.15, "years": 12},
    {"trend": 1.8, "half_life": 5, "noise": 2.0, "years": 6},
    {"trend": 0.6, "half_life": 180, "inheritance": 0.9, "generation_days": 90, "years": 15},
    {"cost": 0.0, "gain": 0.0, "years": 4},
    {"seasonal_amplitude": 0.0, "noise": 0.0, "trend": 1.0, "half_life": 120, "years": 15},
    {"half_life": 1, "induction_rate": 1.0, "threshold": 0.0, "years": 3},
    {"half_life": 500, "inheritance": 1.0, "generation_days": 30, "years": 20},
    {"tolerance_width": 0.25, "noise": 1.5, "years": 8},
    {"inheritance": 0.0, "generation_days": 60, "half_life": 300, "years": 10},
]

SEEDS = [42, 7, 20260805]

KEYS = ["mean_fitness", "mean_fitness_null", "advantage", "late_fitness",
        "late_fitness_null", "late_advantage", "geo_mean_fitness",
        "geo_mean_fitness_null", "geo_advantage", "mean_abs_mismatch",
        "peak_memory"]


def build_jobs():
    jobs = []
    for i, override in enumerate(CASES):
        p = dict(DEFAULTS)
        p.update(override)
        for seed in SEEDS:
            jobs.append({"name": f"case{i}", "params": p, "seed": seed})

    with open(os.path.join(ROOT, "data", "parameters.json")) as fh:
        cfg = json.load(fh)
    for pre in cfg["presets"]:
        p = dict(DEFAULTS)
        p.update(pre["values"])
        jobs.append({"name": f"preset:{pre['id']}", "params": p, "seed": 42})
    return jobs


RUNNER = r"""
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const browser = await chromium.launch({ executablePath: %CHROMIUM% });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://%BUILT%');
  await page.waitForTimeout(400);

  const out = await page.evaluate((jobs) => {
    return jobs.map(j => ({
      name: j.name, seed: j.seed,
      summary: simulate(j.params, j.seed, false).summary
    }));
  }, jobs);

  await browser.close();
  fs.writeFileSync(process.argv[3], JSON.stringify({ results: out, errors }));
})();
"""


def main():
    if not os.path.exists(BUILT):
        print(f"Built simulator not found at {BUILT}. Run scripts/build_simulator.py first.")
        return 1

    jobs = build_jobs()
    print(f"Cross-validating {len(jobs)} parameter/seed combinations "
          f"({len(CASES)} cases x {len(SEEDS)} seeds + shipped presets)...\n")

    with tempfile.TemporaryDirectory() as td:
        jobs_path = os.path.join(td, "jobs.json")
        out_path = os.path.join(td, "out.json")
        runner_path = os.path.join(td, "runner.js")

        with open(jobs_path, "w") as fh:
            json.dump(jobs, fh)
        with open(runner_path, "w") as fh:
            fh.write(RUNNER.replace("%CHROMIUM%", json.dumps(CHROMIUM))
                           .replace("%BUILT%", BUILT))

        proc = subprocess.run(["node", runner_path, jobs_path, out_path],
                              capture_output=True, text=True, cwd=ROOT)
        if proc.returncode != 0:
            print("Headless browser run failed:")
            print(proc.stdout)
            print(proc.stderr)
            return 1

        with open(out_path) as fh:
            payload = json.load(fh)

    if payload.get("errors"):
        print("The page reported JavaScript errors:")
        for e in payload["errors"]:
            print("   ", e)
        return 1

    failures = []
    worst = 0.0
    worst_where = ""

    for job, js in zip(jobs, payload["results"]):
        assert job["name"] == js["name"] and job["seed"] == js["seed"]
        py = simulate(job["params"], seed=job["seed"], keep_series=False)["summary"]
        for k in KEYS:
            a, b = py[k], js["summary"][k]
            diff = abs(a - b)
            if diff > worst:
                worst, worst_where = diff, f"{job['name']} seed={job['seed']} {k}"
            if diff > TOL:
                failures.append((job["name"], job["seed"], k, a, b, diff))
        if py["trapped"] != js["summary"]["trapped"]:
            failures.append((job["name"], job["seed"], "trapped",
                             py["trapped"], js["summary"]["trapped"], "bool mismatch"))

    n_comparisons = len(jobs) * (len(KEYS) + 1)
    if failures:
        print(f"DIVERGENCE — {len(failures)} of {n_comparisons} comparisons exceeded {TOL}:\n")
        for name, seed, k, a, b, d in failures[:40]:
            print(f"  {name:<22} seed={seed:<9} {k:<24} py={a!r:<24} js={b!r:<24} diff={d}")
        if len(failures) > 40:
            print(f"  ... and {len(failures) - 40} more")
        print("\nThe JavaScript model in simulator_template.html and the Python "
              "reference in model/mismatch.py have drifted apart. Fix before shipping.")
        return 1

    print(f"All {n_comparisons} comparisons agree within {TOL}.")
    print(f"Largest observed difference: {worst:.3e}  ({worst_where})")
    print("\nThe JavaScript model in the built simulator is numerically identical "
          "to the Python reference implementation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
