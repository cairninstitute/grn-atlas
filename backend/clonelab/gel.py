"""Render-ready, explicitly simulated agarose gel predictions."""

from __future__ import annotations

import math

from .calibration import DEFAULT_CALIBRATION_ID, calibration_points, load_calibration

MODEL_VERSION = "source_calibrated_log_piecewise_v2"

# Normalized migration measurements for an illustrative 1% agarose profile.
# These are model defaults, not instrument calibration data.
DEFAULT_CALIBRATION = [
    (10_000, 0.08), (5_000, 0.20), (3_000, 0.31), (2_000, 0.40),
    (1_500, 0.48), (1_000, 0.58), (700, 0.67), (500, 0.74),
    (300, 0.84), (200, 0.90), (100, 0.97),
]

LADDERS = {
    "neb_1kb_plus_n0550": [10_002, 8_001, 6_001, 5_001, 4_001, 3_001, 2_017, 1_517, 1_200, 1_000, 900, 800, 700, 600, 517, 500, 400, 300, 200, 100],
    "1kb_plus_illustrative": [10_000, 8_000, 6_000, 5_000, 4_000, 3_000, 2_000, 1_500, 1_000, 500],
    "100bp_illustrative": [1_500, 1_000, 900, 800, 700, 600, 500, 400, 300, 200, 100],
}


def migration_for_size(size_bp: int, calibration: list[tuple[int, float]] | None = None) -> float:
    """Interpolate migration against log10 fragment size."""
    if size_bp <= 0:
        raise ValueError("fragment sizes must be positive")
    points = sorted(calibration or DEFAULT_CALIBRATION, reverse=True)
    if len(points) < 2:
        raise ValueError("at least two gel calibration points are required")
    logs = [(math.log10(size), distance) for size, distance in points]
    query = math.log10(size_bp)
    if query >= logs[0][0]:
        left, right = logs[0], logs[1]
    elif query <= logs[-1][0]:
        left, right = logs[-2], logs[-1]
    else:
        left, right = next(
            (logs[index], logs[index + 1])
            for index in range(len(logs) - 1)
            if logs[index][0] >= query >= logs[index + 1][0]
        )
    fraction = (query - left[0]) / (right[0] - left[0])
    return round(max(0.0, min(1.0, left[1] + fraction * (right[1] - left[1]))), 6)


def simulate_gel(
    lanes: list[dict],
    *,
    ladder: str | None = "neb_1kb_plus_n0550",
    calibration: list[tuple[int, float]] | None = None,
    calibration_id: str | None = DEFAULT_CALIBRATION_ID,
    min_visible_bp: int = 50,
    max_visible_bp: int = 20_000,
    resolution_fraction: float = 0.02,
) -> dict:
    """Return lane/band geometry while retaining fragment-level traceability."""
    if ladder is not None and ladder not in LADDERS:
        raise ValueError(f"unknown ladder: {ladder}")
    profile = None
    if calibration is None and calibration_id is not None:
        profile = load_calibration(calibration_id)
        calibration = calibration_points(calibration_id)
    rendered = []
    lane_inputs = list(lanes)
    if ladder:
        lane_inputs.insert(0, {"lane_id": "ladder", "label": ladder, "fragment_lengths": LADDERS[ladder]})
    for lane_index, lane in enumerate(lane_inputs):
        lengths = [int(value) for value in lane.get("fragment_lengths", [])]
        if any(value <= 0 for value in lengths):
            raise ValueError("fragment sizes must be positive")
        if lane.get("uncut_circular"):
            rendered.append({
                "lane_id": lane["lane_id"], "label": lane.get("label", lane["lane_id"]),
                "lane_index": lane_index, "bands": [], "hidden_fragments": [],
                "warning": "Uncut circular DNA is not assigned a linear-fragment migration position.",
            })
            continue
        visible = sorted((value for value in lengths if min_visible_bp <= value <= max_visible_bp), reverse=True)
        hidden = sorted(
            (value for value in lengths if value < min_visible_bp or value > max_visible_bp),
            reverse=True,
        )
        groups: list[list[int]] = []
        for length in visible:
            position = migration_for_size(length, calibration)
            if groups and abs(position - migration_for_size(round(sum(groups[-1]) / len(groups[-1])), calibration)) < resolution_fraction:
                groups[-1].append(length)
            else:
                groups.append([length])
        bands = []
        total_mass = sum(visible) or 1
        for band_index, group in enumerate(groups):
            representative = round(sum(group) / len(group))
            position = migration_for_size(representative, calibration)
            bands.append({
                "band_id": f"{lane['lane_id']}_band_{band_index + 1}",
                "representative_bp": representative,
                "source_fragments_bp": group,
                "merged": len(group) > 1,
                "migration": position,
                "migration_interval": [max(0.0, round(position - 0.01, 6)), min(1.0, round(position + 0.01, 6))],
                "relative_intensity": round(sum(group) / total_mass, 6),
            })
        rendered.append({
            "lane_id": lane["lane_id"], "label": lane.get("label", lane["lane_id"]),
            "lane_index": lane_index, "bands": bands, "hidden_fragments": hidden,
            "warning": None,
        })
    return {
        "simulation": True,
        "model": MODEL_VERSION,
        "model_boundary": (
            "Predicted migration is calibrated to a manufacturer reference image, not a local instrument run."
            if profile else "Predicted migration is illustrative unless calibrated to a measured gel system."
        ),
        "calibration": ({
            "calibration_id": profile["calibration_id"],
            "label": profile["label"],
            "evidence_type": profile["evidence_type"],
            "gel_system": profile["gel_system"],
            "source": profile["source"],
            "limitation": profile["measurement"]["limitation"],
        } if profile else None),
        "ladder": ladder,
        "resolution_fraction": resolution_fraction,
        "lanes": rendered,
    }
