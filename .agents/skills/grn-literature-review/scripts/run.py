#!/usr/bin/env python3
"""External literature review for GRN Atlas questions."""
import argparse
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common
import research_workflows as rw


class _LiteratureTimeout(Exception):
    pass


def _timeout_handler(signum, frame):
    raise _LiteratureTimeout()


def _fallback_phenotype(species: str | None, query: str | None, years_back: int) -> dict:
    phenotype = query or "phenotype query"
    fallback = {
        "scope": "phenotype",
        "search_term": f"{species or 'species'} {phenotype}",
        "years_back": years_back,
        "atlas_boundary": "External literature retrieval timed out; heuristic phenotype cues were returned instead.",
        "results": [],
        "summary": {},
        "candidate_summary": {
            "candidate_genes": [],
            "mechanisms": [],
        },
        "warnings": ["external literature retrieval timed out; returned heuristic phenotype cues"],
        "query": phenotype,
        "rewritten_query": f"{species or 'species'} {phenotype}",
    }
    q = phenotype.lower()
    if any(token in q for token in ["color", "colour", "pigment", "anthocyanin", "flavonoid", "flower"]):
        fallback["candidate_summary"]["candidate_genes"] = [
            {"name": "MYB", "mentions": 1},
            {"name": "bHLH", "mentions": 1},
            {"name": "WD40", "mentions": 1},
            {"name": "DFR", "mentions": 1},
            {"name": "CHS", "mentions": 1},
        ]
        fallback["candidate_summary"]["mechanisms"] = [
            {"name": "anthocyanin", "mentions": 1},
            {"name": "flavonoid", "mentions": 1},
            {"name": "pigment", "mentions": 1},
        ]
    elif any(token in q for token in ["aba", "drought", "stress"]):
        fallback["candidate_summary"]["candidate_genes"] = [
            {"name": "ABF", "mentions": 1},
            {"name": "AREB", "mentions": 1},
            {"name": "PIF", "mentions": 1},
        ]
        fallback["candidate_summary"]["mechanisms"] = [
            {"name": "ABA signaling", "mentions": 1},
            {"name": "stress response", "mentions": 1},
        ]
    if species:
        cues = rw.derive_family_cues(fallback)
        fallback["atlas_grounded_candidates"] = rw.rescue_candidates_from_family_cues(species, cues)
        fallback["unmapped_literature_candidates"] = []
    return fallback


def _postprocess(data, species):
    if not species or data.get("scope") != "phenotype":
        if isinstance(data, dict):
            summary = data.get("summary", {}) or {}
            data["evidence_classes"] = summary
        return data
    if "atlas_grounded_candidates" in data:
        data["evidence_classes"] = data.get("summary", {}) or {}
        return data
    cues = rw.derive_family_cues(data)
    rescued = rw.rescue_candidates_from_family_cues(species, cues)
    candidate_names = [x.get("name") for x in (data.get("candidate_summary") or {}).get("candidate_genes", []) if x.get("name")]
    imported = rw.import_and_resolve("\n".join(candidate_names), species, "literature_candidates.txt") if candidate_names else {}
    direct_mapped = []
    seen = set()
    for gene in imported.get("mapped_genes", []) if imported else []:
        gene_id = gene.get("gene_id") or gene.get("id")
        if gene_id and gene_id not in seen:
            direct_mapped.append({
                "gene_id": gene_id,
                "symbol": gene.get("symbol") or gene_id,
                "species": gene.get("species") or species,
                "matched_via": "direct_literature_name",
            })
            seen.add(gene_id)
    rescued_out = []
    for gene in rescued:
        gene_id = gene.get("gene_id")
        if gene_id and gene_id not in seen:
            rescued_out.append(gene)
            seen.add(gene_id)
    data["atlas_grounded_candidates"] = direct_mapped + rescued_out
    data["unmapped_literature_candidates"] = [row.get("input") for row in imported.get("unmapped_rows", [])] if imported else candidate_names
    data["evidence_classes"] = data.get("summary", {}) or {}
    data["direct_perturbation_candidates"] = [
        item for item in direct_mapped
        if any(tok in (item.get("symbol") or "").upper() for tok in ["AN2", "JAF13", "DFR", "ABI5", "FLC", "CHS", "MYB"])
    ]
    data["mechanistic_family_cues"] = cues
    data["species_mismatch_candidates"] = candidate_names[:]
    data["grounding_summary"] = {
        "direct_mapped_count": len(direct_mapped),
        "family_rescued_count": len(rescued_out),
        "unmapped_count": len(data["unmapped_literature_candidates"]),
    }
    return data


def main():
    parser = argparse.ArgumentParser(description="GRN Atlas literature review")
    common.add_common_args(parser)
    parser.add_argument("--scope", required=True, choices=["gene", "edge", "pathway", "phenotype"])
    parser.add_argument("--gene-id")
    parser.add_argument("--source-id")
    parser.add_argument("--target-id")
    parser.add_argument("--query")
    parser.add_argument("--species")
    parser.add_argument("--years-back", type=int, default=5)
    parser.add_argument("--max-results", type=int, default=10)
    args = parser.parse_args()

    params = {
        "scope": args.scope,
        "gene_id": args.gene_id,
        "source_id": args.source_id,
        "target_id": args.target_id,
        "query": args.query,
        "species": args.species,
        "years_back": args.years_back,
        "max_results": args.max_results,
    }
    params = {k: v for k, v in params.items() if v is not None}

    try:
        if args.http:
            data = common.http_get(args.http, "/api/v1/literature/review", params)
        else:
            sys.path.insert(0, str(common.BACKEND_DIR))
            import main as backend
            if args.scope == "phenotype":
                signal.signal(signal.SIGALRM, _timeout_handler)
                signal.alarm(20)
            try:
                data = common.run_async(backend.literature_review(**params))
            finally:
                if args.scope == "phenotype":
                    signal.alarm(0)
    except _LiteratureTimeout:
        data = _fallback_phenotype(args.species, args.query, args.years_back)

    common.output(_postprocess(data, args.species))


if __name__ == "__main__":
    main()
