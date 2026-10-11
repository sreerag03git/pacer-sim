"""Regenerate the golden regression fixture (tests/golden_seed7.json).

Run this ONLY when you intend to change the engine's documented output:

    python -m tests._make_golden

It records the engine's own output for seed 7 so the regression test can assert
byte-identical reproduction. It is never run by the test itself.
"""

from __future__ import annotations

import json
import os

from engine.config import ControllerMode
from tests.golden_util import GOLDEN_CONFIG, golden_payload


def main() -> None:
    payload = golden_payload(GOLDEN_CONFIG)
    here = os.path.dirname(__file__)
    path = os.path.join(here, "golden_seed7.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"wrote {path}")
    for row in payload["headline"]:
        print(
            f"  {row['mode']:14s} blow={row['blowout_runs']:3d}/{row['n_runs']}  "
            f"dark={row['mean_homes_dark']:.2f}  peak={row['mean_peak_pu']:.3f}"
        )


if __name__ == "__main__":
    main()
