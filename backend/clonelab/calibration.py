"""Versioned, source-traceable gel migration calibration profiles."""

from __future__ import annotations

import json
import re
from pathlib import Path

CALIBRATION_DIR = Path(__file__).with_name("calibrations")
DEFAULT_CALIBRATION_ID = "neb_n0550_1pct_tbe_image_v1"


def list_calibrations() -> list[dict]:
    profiles = []
    for path in sorted(CALIBRATION_DIR.glob("*.json")):
        payload = json.loads(path.read_text())
        profiles.append({key: payload[key] for key in (
            "calibration_id", "label", "evidence_type", "gel_system", "source"
        )})
    return profiles


def load_calibration(calibration_id: str = DEFAULT_CALIBRATION_ID) -> dict:
    if not re.fullmatch(r"[a-z0-9_-]+", calibration_id):
        raise ValueError("invalid calibration identifier")
    path = CALIBRATION_DIR / f"{calibration_id}.json"
    if not path.exists():
        raise ValueError(f"unknown gel calibration: {calibration_id}")
    payload = json.loads(path.read_text())
    points = payload.get("points", [])
    if len(points) < 2:
        raise ValueError(f"calibration {calibration_id} has fewer than two points")
    sizes = [int(point["size_bp"]) for point in points]
    migrations = [float(point["migration_normalized"]) for point in points]
    if sizes != sorted(sizes, reverse=True):
        raise ValueError("calibration sizes must be strictly descending")
    if migrations != sorted(migrations) or any(not 0 <= value <= 1 for value in migrations):
        raise ValueError("calibration migrations must increase within [0, 1]")
    return payload


def calibration_points(calibration_id: str = DEFAULT_CALIBRATION_ID) -> list[tuple[int, float]]:
    profile = load_calibration(calibration_id)
    return [
        (int(point["size_bp"]), float(point["migration_normalized"]))
        for point in profile["points"]
    ]
