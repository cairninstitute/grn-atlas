"""Resolution-aware diagnostic restriction digest optimization."""

from __future__ import annotations

import itertools
import math
from collections import defaultdict
from typing import Iterable

from .restriction import digest_sequence


def _merge_visible_bands(
    fragment_lengths: Iterable[int],
    *,
    min_fragment_bp: int,
    max_fragment_bp: int,
    min_separation_bp: int,
    relative_resolution: float,
) -> tuple[tuple[int, ...], list[list[int]], list[int]]:
    visible = sorted(
        (length for length in fragment_lengths if min_fragment_bp <= length <= max_fragment_bp),
        reverse=True,
    )
    hidden = sorted(
        (length for length in fragment_lengths if length < min_fragment_bp or length > max_fragment_bp),
        reverse=True,
    )
    groups: list[list[int]] = []
    for length in visible:
        if not groups:
            groups.append([length])
            continue
        representative = sum(groups[-1]) / len(groups[-1])
        required = max(min_separation_bp, relative_resolution * max(representative, length))
        if abs(representative - length) < required:
            groups[-1].append(length)
        else:
            groups.append([length])
    signature = tuple(round(sum(group) / len(group)) for group in groups)
    return signature, groups, hidden


def _normalized_priors(hypotheses: list[dict]) -> dict[str, float]:
    if all(hypothesis.get("prior") is not None for hypothesis in hypotheses):
        total = sum(float(hypothesis["prior"]) for hypothesis in hypotheses)
        if total <= 0:
            raise ValueError("hypothesis priors must have a positive sum")
        return {hypothesis["hypothesis_id"]: float(hypothesis["prior"]) / total for hypothesis in hypotheses}
    uniform = 1.0 / len(hypotheses)
    return {hypothesis["hypothesis_id"]: uniform for hypothesis in hypotheses}


def _candidate_enzyme_sets(enzymes: list[str], max_enzymes: int) -> Iterable[tuple[str, ...]]:
    for size in range(1, max_enzymes + 1):
        yield from itertools.combinations(enzymes, size)


def _signatures_distinct(
    left: list[int | str],
    right: list[int | str],
    *,
    min_separation_bp: int,
    relative_resolution: float,
) -> bool:
    """Return whether two lane signatures contain a resolvable difference."""
    if len(left) != len(right):
        return True
    for left_band, right_band in zip(left, right):
        if isinstance(left_band, str) or isinstance(right_band, str):
            if left_band != right_band:
                return True
            continue
        required = max(min_separation_bp, relative_resolution * max(left_band, right_band))
        difference = abs(left_band - right_band)
        if difference > 0 and difference >= required:
            return True
    return False


def _indistinguishable_groups(ids: list[str], pairwise: list[dict]) -> list[list[str]]:
    """Build conservative connected groups from unresolved hypothesis pairs."""
    parent = {item: item for item in ids}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for comparison in pairwise:
        if not comparison["distinguishable"]:
            union(comparison["left"], comparison["right"])
    groups: dict[str, list[str]] = defaultdict(list)
    for item in ids:
        groups[find(item)].append(item)
    return [sorted(members) for members in groups.values()]


def optimize_digests(
    hypotheses: list[dict],
    candidate_enzymes: list[str],
    *,
    max_enzymes_per_digest: int = 2,
    min_fragment_bp: int = 50,
    max_fragment_bp: int = 20_000,
    min_separation_bp: int = 25,
    relative_resolution: float = 0.05,
    top: int = 10,
) -> dict:
    """Rank enzyme sets by how well their resolvable patterns distinguish hypotheses."""
    if len(hypotheses) < 2:
        raise ValueError("at least two molecular hypotheses are required")
    ids = [hypothesis["hypothesis_id"] for hypothesis in hypotheses]
    if len(ids) != len(set(ids)):
        raise ValueError("hypothesis_id values must be unique")
    enzymes = list(dict.fromkeys(name.strip() for name in candidate_enzymes if name.strip()))
    if not enzymes:
        raise ValueError("at least one candidate enzyme is required")
    priors = _normalized_priors(hypotheses)
    total_pairs = len(hypotheses) * (len(hypotheses) - 1) // 2
    max_entropy = math.log2(len(hypotheses))
    rankings = []

    for enzyme_set in _candidate_enzyme_sets(enzymes, max_enzymes_per_digest):
        predictions = {}
        uncut_count = 0
        hidden_count = 0
        for hypothesis in hypotheses:
            digest = digest_sequence(
                hypothesis["sequence"],
                enzyme_set,
                topology=hypothesis.get("topology", "circular"),
                include_fragment_sequences=False,
            )
            if digest["uncut"]:
                uncut_count += 1
                signature = ("uncut_circular",) if hypothesis.get("topology", "circular") == "circular" else (len(hypothesis["sequence"]),)
                band_groups = []
                hidden = []
            else:
                signature, band_groups, hidden = _merge_visible_bands(
                    digest["fragment_lengths"],
                    min_fragment_bp=min_fragment_bp,
                    max_fragment_bp=max_fragment_bp,
                    min_separation_bp=min_separation_bp,
                    relative_resolution=relative_resolution,
                )
            hidden_count += len(hidden)
            predictions[hypothesis["hypothesis_id"]] = {
                "label": hypothesis.get("label") or hypothesis["hypothesis_id"],
                "fragment_lengths": digest["fragment_lengths"],
                "cut_sites": [
                    {
                        "enzyme": site["enzyme"],
                        "recognition_start": site["recognition_start"],
                        "top_cut": site["top_cut"],
                    }
                    for site in digest["sites"]
                ],
                "visible_signature": list(signature),
                "merged_band_groups": band_groups,
                "hidden_fragments": hidden,
                "uncut": digest["uncut"],
                "warnings": digest["warnings"],
            }

        distinguishable_pairs = 0
        pairwise = []
        for left, right in itertools.combinations(ids, 2):
            distinct = _signatures_distinct(
                predictions[left]["visible_signature"],
                predictions[right]["visible_signature"],
                min_separation_bp=min_separation_bp,
                relative_resolution=relative_resolution,
            )
            distinguishable_pairs += int(distinct)
            pairwise.append({"left": left, "right": right, "distinguishable": distinct})

        unresolved_groups = _indistinguishable_groups(ids, pairwise)
        unique_ids = sorted(members[0] for members in unresolved_groups if len(members) == 1)
        group_probabilities = [sum(priors[item] for item in members) for members in unresolved_groups]
        information_bits = -sum(p * math.log2(p) for p in group_probabilities if p > 0)
        pair_fraction = distinguishable_pairs / total_pairs if total_pairs else 0.0
        unique_fraction = len(unique_ids) / len(hypotheses)
        entropy_fraction = information_bits / max_entropy if max_entropy else 0.0
        complexity_penalty = 0.03 * (len(enzyme_set) - 1)
        topology_penalty = 0.08 * (uncut_count / len(hypotheses))
        hidden_penalty = min(0.08, 0.01 * hidden_count)
        score = max(
            0.0,
            0.55 * pair_fraction + 0.30 * unique_fraction + 0.15 * entropy_fraction
            - complexity_penalty - topology_penalty - hidden_penalty,
        )
        rankings.append({
            "enzymes": list(enzyme_set),
            "score": round(score, 6),
            "information_bits": round(information_bits, 6),
            "pairwise_distinguishable": distinguishable_pairs,
            "pairwise_total": total_pairs,
            "unique_hypotheses": unique_ids,
            "unique_fraction": round(unique_fraction, 6),
            "signature_groups": [
                {
                    "hypotheses": members,
                    "signatures": {
                        hypothesis_id: predictions[hypothesis_id]["visible_signature"]
                        for hypothesis_id in members
                    },
                }
                for members in sorted(unresolved_groups)
            ],
            "predictions": predictions,
            "pairwise": pairwise,
            "uncut_hypotheses": uncut_count,
            "hidden_fragment_count": hidden_count,
            "fully_discriminatory": len(unique_ids) == len(hypotheses),
        })

    rankings.sort(key=lambda item: (
        -int(item["fully_discriminatory"]),
        -item["score"],
        len(item["enzymes"]),
        item["enzymes"],
    ))
    best = rankings[0] if rankings else None
    return {
        "hypotheses": ids,
        "candidate_enzyme_count": len(enzymes),
        "candidate_digest_count": len(rankings),
        "resolution_model": {
            "min_fragment_bp": min_fragment_bp,
            "max_fragment_bp": max_fragment_bp,
            "min_separation_bp": min_separation_bp,
            "relative_resolution": relative_resolution,
            "model_type": "deterministic_resolvable_signature_v1",
        },
        "best_digest": best,
        "rankings": rankings[:top],
        "no_unique_digest": not any(item["fully_discriminatory"] for item in rankings),
        "claim_boundary": {
            "insert_presence": "Supported only for hypothesis pairs with distinct predicted signatures.",
            "insert_orientation": "Supported only when forward and reverse hypotheses have distinct predicted signatures.",
            "sequence_identity": "A restriction pattern does not establish base-perfect sequence identity.",
        },
    }
