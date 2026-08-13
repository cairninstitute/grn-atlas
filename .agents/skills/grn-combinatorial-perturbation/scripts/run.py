#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def _single_baseline(db, gene_id: str, action: str):
    import main as backend
    req = backend.PerturbRequest(interventions=[backend.PerturbInterv(gene_id=gene_id, action=action)])
    return common.run_async(backend.perturb(req))


def _postprocess(data, gene_ids, action):
    try:
        import main as backend
    except Exception:
        return data
    baselines = {}
    for gid in gene_ids:
        single = _single_baseline(backend.db, gid, action)
        baselines[gid] = {
            "affected_genes": single.get("affected_genes", 0),
            "up": single.get("up", 0),
            "down": single.get("down", 0),
            "unknown": single.get("unknown", 0),
        }
    enriched = []
    for combo in data.get("ranked_combinations", []):
        genes = [item["gene_id"] for item in combo.get("combo", [])]
        best_single = max((baselines.get(g, {}).get("affected_genes", 0) for g in genes), default=0)
        combo_affected = combo.get("affected_genes", 0)
        gain = combo_affected - best_single
        combo["single_gene_baseline"] = {g: baselines.get(g, {}) for g in genes}
        combo["combination_gain_summary"] = {
            "best_single_affected_genes": best_single,
            "combo_affected_genes": combo_affected,
            "delta_vs_best_single": gain,
        }
        combo["redundancy_signals"] = (
            ["combo effect is close to the best single-gene baseline"] if gain <= max(1, int(best_single * 0.1)) else []
        )
        enriched.append(combo)
    data["single_gene_baseline"] = baselines
    data["combo_recommended_next_step"] = (
        "prioritize the top-ranked combination only if its gain over the best single-gene intervention is material"
        if enriched else None
    )
    return data


def main():
    parser = argparse.ArgumentParser(description="Combinatorial perturbation ranking")
    common.add_common_args(parser)
    parser.add_argument("--gene-ids", required=True)
    parser.add_argument("--action", default="ko")
    parser.add_argument("--combo-size", type=int, default=2)
    parser.add_argument("--species")
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()
    payload = {
        "gene_ids": [g.strip() for g in args.gene_ids.split(",") if g.strip()],
        "action": args.action,
        "combo_size": args.combo_size,
        "species": args.species,
        "top": args.top,
    }
    if args.http:
        data = common.http_post(args.http, "/api/v1/perturb/combinatorial", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.combinatorial_perturbation(backend.CombinatorialPerturbationRequest(**payload)))
    common.output(_postprocess(data, payload["gene_ids"], args.action))


if __name__ == "__main__":
    main()
