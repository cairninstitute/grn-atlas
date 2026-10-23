"""Compare manually measured bands with deterministic assay predictions."""

from __future__ import annotations

from functools import lru_cache


def _best_match(expected: tuple[int, ...], observed: tuple[int, ...], tolerance_fraction: float,
                tolerance_bp: int) -> tuple[int, float]:
    @lru_cache(maxsize=None)
    def solve(i: int, used: int) -> tuple[int, float]:
        if i == len(expected):
            return 0, 0.0
        best = solve(i + 1, used)
        for j, value in enumerate(observed):
            if used & (1 << j):
                continue
            tolerance = max(tolerance_bp, tolerance_fraction * max(expected[i], value))
            error = abs(expected[i] - value)
            if error <= tolerance:
                count, total_error = solve(i + 1, used | (1 << j))
                candidate = count + 1, total_error + error / max(expected[i], 1)
                if candidate[0] > best[0] or (candidate[0] == best[0] and candidate[1] < best[1]):
                    best = candidate
        return best
    return solve(0, 0)


def interpret_bands(
    observed_bands_bp: list[int],
    predictions: dict[str, list[int]],
    *,
    tolerance_fraction: float = 0.08,
    tolerance_bp: int = 25,
    max_missing: int = 0,
    max_unexpected: int = 0,
) -> dict:
    observed = tuple(sorted((int(value) for value in observed_bands_bp), reverse=True))
    if not observed or any(value <= 0 for value in observed):
        raise ValueError("observed bands must contain positive fragment sizes")
    ranked = []
    for hypothesis_id, values in predictions.items():
        expected = tuple(sorted((int(value) for value in values), reverse=True))
        matched, normalized_error = _best_match(expected, observed, tolerance_fraction, tolerance_bp)
        missing = len(expected) - matched
        unexpected = len(observed) - matched
        compatible = missing <= max_missing and unexpected <= max_unexpected
        score = matched / max(len(expected), len(observed), 1) - normalized_error / max(matched, 1)
        ranked.append({
            "hypothesis_id": hypothesis_id,
            "expected_bands_bp": list(expected),
            "matched_band_count": matched,
            "missing_band_count": missing,
            "unexpected_band_count": unexpected,
            "normalized_size_error": round(normalized_error, 6),
            "compatible": compatible,
            "score": round(score, 6),
        })
    ranked.sort(key=lambda item: (-int(item["compatible"]), -item["score"], item["hypothesis_id"]))
    compatible_ids = [item["hypothesis_id"] for item in ranked if item["compatible"]]
    return {
        "observed_bands_bp": list(observed),
        "tolerance_fraction": tolerance_fraction,
        "tolerance_bp": tolerance_bp,
        "rankings": ranked,
        "compatible_hypotheses": compatible_ids,
        "ambiguous": len(compatible_ids) != 1,
        "interpretation_boundary": "Band agreement supports compatibility with a predicted state; it does not establish base-perfect sequence identity.",
    }
