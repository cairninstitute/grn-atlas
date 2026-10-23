"""End-to-end deterministic CloneLab workflows."""

from __future__ import annotations

from .diagnostics import optimize_digests
from .gel import simulate_gel
from .hypotheses import construct_hypotheses
from .provenance import engine_provenance


def optimize_construct_design(
    vector_sequence: str,
    insert_sequence: str,
    *,
    insertion_start: int,
    candidate_enzymes: list[str],
    insertion_end: int | None = None,
    include_tandem: bool = True,
    min_fragment_bp: int = 50,
    max_fragment_bp: int = 20_000,
) -> dict:
    """Generate molecular states, rank digests, and simulate the best lanes."""
    hypotheses = construct_hypotheses(
        vector_sequence,
        insert_sequence,
        insertion_start=insertion_start,
        insertion_end=insertion_end,
        include_tandem=include_tandem,
    )
    optimization = optimize_digests(
        hypotheses,
        candidate_enzymes,
        min_fragment_bp=min_fragment_bp,
        max_fragment_bp=max_fragment_bp,
    )
    best = optimization["best_digest"]
    gel = simulate_gel([
        {
            "lane_id": hypothesis_id,
            "label": prediction["label"],
            "fragment_lengths": prediction["fragment_lengths"],
            "uncut_circular": prediction["uncut"],
        }
        for hypothesis_id, prediction in best["predictions"].items()
    ], min_visible_bp=min_fragment_bp, max_visible_bp=max_fragment_bp)
    return {
        "hypotheses": hypotheses,
        "optimization": optimization,
        "gel": gel,
        "provenance": engine_provenance(),
        "verification_scope": {
            "calculated": ["construct sequences", "junctions", "restriction sites", "fragment lengths", "digest ranking"],
            "simulated": ["gel migration", "band merging", "relative intensity"],
            "not_established": ["base-perfect sequence identity", "construct viability", "biological function"],
        },
    }
