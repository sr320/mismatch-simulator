#!/usr/bin/env python3
"""
Build index.html from simulator_template.html + data/parameters.json.

simulator_template.html is the real source (edit layout, styling, the JS
model, and the charts there). Never hand-edit the generated file — it is
overwritten every time this script runs.

Usage:
    python3 scripts/build_simulator.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    with open(os.path.join(ROOT, "data", "parameters.json")) as fh:
        config = json.load(fh)

    with open(os.path.join(ROOT, "simulator_template.html")) as fh:
        tpl = fh.read()

    if "__DATA__" not in tpl:
        raise SystemExit("simulator_template.html is missing its __DATA__ placeholder")

    html = tpl.replace("__DATA__", json.dumps(config, separators=(",", ":")))
    out = os.path.join(ROOT, "index.html")
    with open(out, "w") as fh:
        fh.write(html)

    print(f"Wrote {out} ({len(html)/1024:.1f} KB)")
    print(f"Presets: {len(config['presets'])}, parameters: {len(config['parameters'])}")


if __name__ == "__main__":
    main()
