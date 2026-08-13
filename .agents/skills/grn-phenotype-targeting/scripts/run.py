#!/usr/bin/env python3
"""Phenotype-first targeting workflow."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common
import research_workflows as rw


def _ground_candidates(species: str, literature_data: dict, max_candidates: int):
    candidate_names = [x.get("name") for x in (literature_data.get("candidate_summary") or {}).get("candidate_genes", []) if x.get("name")]
    grounded = []
    unresolved = []
    if candidate_names:
        imported = rw.import_and_resolve("\n".join(candidate_names), species, "literature_candidates.txt")
        unresolved = [row.get("input") for row in imported.get("unmapped_rows", []) if row.get("input")]
        grounded.extend(imported.get("mapped_genes", []))
    cues = rw.derive_family_cues(literature_data)
    rescued = rw.rescue_candidates_from_family_cues(species, cues)
    seen = set()
    normalized_grounded = []
    for gene in grounded:
        gene_id = gene.get("gene_id") or gene.get("id")
        if not gene_id or gene_id in seen:
            continue
        normalized_grounded.append({
            "gene_id": gene_id,
            "symbol": gene.get("symbol") or gene_id,
            "species": gene.get("species") or species,
            "matched_via": "direct_literature_name",
            "match_query": gene.get("symbol") or gene_id,
            "is_tf": gene.get("is_tf"),
        })
        seen.add(gene_id)
    for gene in rescued:
        gene_id = gene.get("gene_id")
        if not gene_id or gene_id in seen:
            continue
        normalized_grounded.append(gene)
        seen.add(gene_id)
    return normalized_grounded[:max_candidates], unresolved, cues


def _fallback_literature_payload(species: str, phenotype: str) -> dict:
    phenotype_lower = phenotype.lower()
    candidate_genes = []
    mechanisms = []
    if any(token in phenotype_lower for token in ["color", "colour", "pigment", "anthocyanin", "flavonoid", "flower"]):
        candidate_genes = [
            {"name": "MYB", "mentions": 1},
            {"name": "bHLH", "mentions": 1},
            {"name": "WD40", "mentions": 1},
            {"name": "DFR", "mentions": 1},
            {"name": "CHS", "mentions": 1},
        ]
        mechanisms = [
            {"name": "anthocyanin", "mentions": 1},
            {"name": "flavonoid", "mentions": 1},
            {"name": "pigment", "mentions": 1},
        ]
    elif any(token in phenotype_lower for token in ["aba", "drought", "stress"]):
        candidate_genes = [
            {"name": "ABF", "mentions": 1},
            {"name": "AREB", "mentions": 1},
            {"name": "PIF", "mentions": 1},
        ]
        mechanisms = [
            {"name": "ABA signaling", "mentions": 1},
            {"name": "stress response", "mentions": 1},
        ]
    return {
        "scope": "phenotype",
        "search_term": f"{species} {phenotype}",
        "years_back": 5,
        "atlas_boundary": "Fallback heuristic cues were used because external literature retrieval was unavailable or slow.",
        "results": [],
        "summary": {},
        "candidate_summary": {
            "candidate_genes": candidate_genes,
            "mechanisms": mechanisms,
        },
        "warnings": ["fallback literature cue generation was used"],
        "query": phenotype,
        "rewritten_query": f"{species} {phenotype}",
    }


def _bounded_literature(species: str, phenotype: str, years_back: int) -> dict:
    script = Path(__file__).resolve().parents[2] / "grn-literature-review" / "scripts" / "run.py"
    cmd = [
        sys.executable,
        str(script),
        "--scope", "phenotype",
        "--query", phenotype,
        "--species", species,
        "--years-back", str(years_back),
        "--max-results", "10",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout)
    except Exception:
        pass
    return _fallback_literature_payload(species, phenotype)


def main():
    parser = argparse.ArgumentParser(description="Phenotype-first targeting workflow")
    common.add_common_args(parser)
    parser.add_argument("--species", required=True)
    parser.add_argument("--phenotype", required=True)
    parser.add_argument("--intent", default="experiment")
    parser.add_argument("--max-candidates", type=int, default=8)
    parser.add_argument("--years-back", type=int, default=5)
    args = parser.parse_args()

    if args.http:
        common.output({"error": "grn-phenotype-targeting currently supports direct mode only", "status_code": 501})
        return

    backend = rw.get_backend()
    domain_info = rw.classify_phenotype_domain(args.phenotype)
    literature_data = _bounded_literature(args.species, args.phenotype, args.years_back)
    grounded, unresolved, cues = _ground_candidates(args.species, literature_data, args.max_candidates)
    grounded_ids = [g["gene_id"] for g in grounded]

    triage = consensus = coverage = experiments = confidence = None
    if grounded_ids:
        triage = common.run_async(
            backend.candidate_triage(
                backend.CandidateTriageRequest(
                    gene_ids=grounded_ids,
                    intent=args.intent,
                    species=args.species,
                    top_n=min(args.max_candidates, len(grounded_ids)),
                )
            )
        )
        consensus = common.run_async(
            backend.consensus_ranking(
                backend.ConsensusRankingRequest(
                    gene_ids=grounded_ids,
                    intent=args.intent,
                    species=args.species,
                    top_n=min(args.max_candidates, len(grounded_ids)),
                    include_external=True,
                    years_back=args.years_back,
                )
            )
        )
        coverage = common.run_async(backend.coverage_report(species=args.species, intent=args.intent, gene_id=None))
        experiments = common.run_async(
            backend.experiment_prioritize(
                backend.ExperimentPrioritizationRequest(
                    gene_ids=grounded_ids,
                    intent=args.intent,
                    species=args.species,
                    max_recommendations=5,
                )
            )
        )
        confidence = common.run_async(
            backend.confidence_boundary(
                backend.ConfidenceBoundaryRequest(
                    gene_ids=grounded_ids,
                    intent=args.intent,
                    species=args.species,
                    max_candidates=min(3, len(grounded_ids)),
                    max_experiments=3,
                )
            )
        )

    output = {
        "title": f"Phenotype targeting for {args.phenotype}",
        "species": args.species,
        "intent": args.intent,
        "phenotype_summary": {
            "query": args.phenotype,
            "species": args.species,
            "years_back": args.years_back,
        },
        "phenotype_domain": domain_info["phenotype_domain"],
        "candidate_generation_mode": domain_info["candidate_generation_mode"],
        "ranking_profile": domain_info["ranking_profile"],
        "literature_cues": {
            "search_term": literature_data.get("search_term"),
            "candidate_families_or_cues": cues,
            "candidate_mentions": (literature_data.get("candidate_summary") or {}).get("candidate_genes", []),
            "mechanism_mentions": (literature_data.get("candidate_summary") or {}).get("mechanisms", []),
        },
        "atlas_grounded_candidates": grounded,
        "family_level_analog_candidates": rw.family_level_analogs(args.species, (grounded[0]["symbol"] if grounded else None)),
        "unmapped_literature_candidates": unresolved,
        "ranking_table": (consensus or triage or {}).get("ranked_candidates", []),
        "intervention_readiness_summary": {
            "coverage": coverage,
            "next_experiments": (experiments or {}).get("plans", experiments),
        },
        "support_boundary": confidence,
        "recommended_follow_up_mode": (
            ((experiments or {}).get("plans") or [{}])[0].get("recommended_experiments", [{}])[0].get("experiment")
            if experiments else None
        ),
        "atlas_boundary": literature_data.get("atlas_boundary"),
    }
    common.output(output)


if __name__ == "__main__":
    main()
