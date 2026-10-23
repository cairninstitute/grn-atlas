#!/usr/bin/env python3
"""Fit alternating calibration bands and score the held-out band centers."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clonelab.calibration import DEFAULT_CALIBRATION_ID, load_calibration  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibration", default=DEFAULT_CALIBRATION_ID)
    parser.add_argument("--output", default=ROOT.parent / "docs/clonelab/validation/gel-calibration-validation.json", type=Path)
    args = parser.parse_args()
    profile = load_calibration(args.calibration)
    sizes = np.array([point["size_bp"] for point in profile["points"]], dtype=float)
    observed = np.array([point["migration_normalized"] for point in profile["points"]], dtype=float)
    train = np.arange(len(sizes)) % 2 == 0
    held_out = ~train
    coefficients = np.polyfit(np.log10(sizes[train]), observed[train], 3)
    predicted = np.polyval(coefficients, np.log10(sizes[held_out]))
    errors = np.abs(predicted - observed[held_out])
    rows = [
        {"size_bp": int(size), "observed": round(float(actual), 6),
         "predicted": round(float(expect), 6), "absolute_error": round(float(error), 6)}
        for size, actual, expect, error in zip(sizes[held_out], observed[held_out], predicted, errors)
    ]
    mae = float(errors.mean())
    maximum = float(errors.max())
    passed = mae <= 0.01 and maximum <= 0.02
    result = {
        "schema": "clonelab-gel-calibration-validation-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "calibration_id": args.calibration,
        "method": "cubic regression in log10(bp), alternating bands used for fit and held-out test",
        "fit_band_count": int(train.sum()), "held_out_band_count": int(held_out.sum()),
        "mean_absolute_migration_error": round(mae, 6),
        "maximum_absolute_migration_error": round(maximum, 6),
        "thresholds": {"mean_max": 0.01, "individual_max": 0.02},
        "held_out": rows,
        "release_gate": "pass" if passed else "fail",
        "boundary": profile["measurement"]["limitation"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "release_gate": result["release_gate"], "mae": round(mae, 6)}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
