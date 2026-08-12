#!/usr/bin/env python3
"""Find shared upstream regulators across multiple target genes."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def _resolve_gene(db, raw_gene: str, species: str | None):
    raw = raw_gene.strip()
    if not raw:
        return None
    gene = db.get_gene(raw)
    if gene:
        return gene
    if species:
        gene = db.find_gene_by_symbol_species(raw, species)
        if gene:
            return gene
    hits = db.search_genes(raw, limit=1, species=species)
    return hits[0] if hits else None


def _network_http(base_url: str, gene_id: str, min_confidence: float, include_inferred: bool):
    payload = {
        "direction": "regulators",
        "regulation_type": ["activation", "repression", "unknown"],
        "min_confidence": min_confidence,
        "include_inferred": include_inferred,
    }
    return common.http_post(base_url, f"/api/v1/pathways/neighborhood/{gene_id}", payload)


def main():
    parser = argparse.ArgumentParser(description="Shared regulator analysis")
    common.add_common_args(parser)
    parser.add_argument("--gene-ids", required=True, help="Comma-separated target gene IDs or symbols")
    parser.add_argument("--species", default=None, help="Species name")
    parser.add_argument("--min-confidence", type=float, default=0.3, help="Minimum edge confidence")
    parser.add_argument("--top", type=int, default=25, help="Maximum shared regulators to return")
    parser.add_argument("--no-include-inferred", action="store_true", help="Exclude inferred edges")
    args = parser.parse_args()

    raw_genes = [g.strip() for g in args.gene_ids.split(",") if g.strip()]
    if len(raw_genes) < 2:
        common.output({"error": "Provide at least two target genes", "status_code": 400})
        sys.exit(0)

    include_inferred = not args.no_include_inferred

    if args.http:
        resolved = []
        network_by_target = {}
        for raw in raw_genes:
            resolved.append({"input": raw, "gene_id": raw, "symbol": raw, "species": args.species})
            network_by_target[raw] = _network_http(args.http, raw, args.min_confidence, include_inferred)
    else:
        db = common.init_db()
        resolved = []
        network_by_target = {}
        for raw in raw_genes:
            gene = _resolve_gene(db, raw, args.species)
            if not gene:
                common.output({"error": f"Gene not found: {raw}", "status_code": 404})
                sys.exit(0)
            if args.species and gene.species.lower() != args.species.lower():
                common.output({"error": f"Gene {raw} resolved to species {gene.species}, not {args.species}", "status_code": 400})
                sys.exit(0)
            resolved.append({
                "input": raw,
                "gene_id": gene.id,
                "symbol": gene.symbol,
                "species": gene.species,
            })
            regs = db.get_regulators(gene.id, min_confidence=args.min_confidence, include_inferred=include_inferred)
            network_by_target[gene.id] = {
                "gene": {"id": gene.id, "symbol": gene.symbol, "name": gene.name, "species": gene.species},
                "regulators": [r.model_dump() for r in regs],
            }

    target_keys = [r["gene_id"] for r in resolved]
    shared_reg_ids = None
    regulator_details = {}
    for target_key in target_keys:
        regs = network_by_target[target_key]["regulators"]
        reg_ids = {r["id"] for r in regs if r.get("is_tf", False)}
        shared_reg_ids = reg_ids if shared_reg_ids is None else (shared_reg_ids & reg_ids)
        for r in regs:
            if not r.get("is_tf", False):
                continue
            regulator_details.setdefault(r["id"], {
                "regulator_id": r["id"],
                "symbol": r["symbol"],
                "name": r["name"],
                "species": r["species"],
                "shared_targets": {},
                "mean_confidence": 0.0,
                "support_count": 0,
            })
            regulator_details[r["id"]]["shared_targets"][target_key] = {
                "target_gene_id": target_key,
                "regulation_type": r.get("regulation_type", "unknown"),
                "confidence": r.get("confidence", 0.0),
                "source_databases": r.get("source_databases", []),
                "pmids": r.get("pmids", []),
                "inferred": r.get("inferred", False),
            }

    shared_reg_ids = shared_reg_ids or set()
    results = []
    for reg_id in shared_reg_ids:
        item = regulator_details[reg_id]
        confidences = [v["confidence"] for v in item["shared_targets"].values()]
        item["support_count"] = len(item["shared_targets"])
        item["mean_confidence"] = round(sum(confidences) / len(confidences), 4) if confidences else 0.0
        item["shared_targets"] = [
            item["shared_targets"][k] for k in target_keys if k in item["shared_targets"]
        ]
        results.append(item)

    results.sort(key=lambda x: (-x["support_count"], -x["mean_confidence"], x["symbol"]))
    results = results[: args.top]

    common.output({
        "targets": resolved,
        "shared_regulators": results,
        "shared_regulator_count": len(results),
        "min_confidence": args.min_confidence,
        "include_inferred": include_inferred,
    })


if __name__ == "__main__":
    main()
