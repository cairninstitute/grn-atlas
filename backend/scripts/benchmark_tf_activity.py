from __future__ import annotations

from validation_common import (
    benchmark_payload,
    case_result,
    client,
    find_tf_with_targets,
    rank_of,
    save_benchmark,
    synthetic_regulon_values,
    top_symbols,
)


def main() -> None:
    cases = []

    literal = {
        "TP53": 3.0,
        "MDM2": -2.0,
        "CDKN1A": 2.5,
        "BAX": 1.8,
        "BCL2": -1.5,
        "GADD45A": 2.1,
    }
    for method in ("ulm", "wmean"):
        resp = client.post(
            "/api/v1/activity/tf",
            json={
                "gene_values": literal,
                "species": "human",
                "method": method,
                "top": 10,
                "min_regulon_size": 2,
            },
        )
        data = resp.json()
        rank = rank_of(data.get("regulators", []), lambda r: (r.get("symbol") or "").upper() == "TP53")
        cases.append(
            case_result(
                f"human_tp53_literal_{method}",
                f"Human TP53-like signature recovery ({method})",
                "pass" if rank and rank <= 5 else "fail",
                metrics={"expected_rank": rank, "top_symbols": top_symbols(data.get("regulators", []))},
                details={"matched_genes": data.get("matched_genes"), "method": method},
                notes=["Known TP53-associated genes were used as input; this is the most decision-relevant activity sanity check."],
            )
        )

    for species in ("human", "arabidopsis"):
        tf = find_tf_with_targets(species, min_targets=12)
        if not tf:
            cases.append(
                case_result(
                    f"synthetic_{species}",
                    f"Synthetic regulon self-consistency ({species})",
                    "fail",
                    notes=["No sufficiently large TF regulon was available for this species."],
                )
            )
            continue
        resp = client.post(
            "/api/v1/activity/tf",
            json={
                "gene_values": synthetic_regulon_values(tf["id"], limit=12),
                "species": species,
                "method": "ulm",
                "top": 10,
                "min_regulon_size": 3,
            },
        )
        data = resp.json()
        rank = rank_of(data.get("regulators", []), lambda r, tf_id=tf["id"]: r.get("gene_id") == tf_id)
        cases.append(
            case_result(
                f"synthetic_{species}",
                f"Synthetic regulon self-consistency ({species})",
                "pass" if rank and rank <= 3 else "partial",
                metrics={
                    "seed_tf": tf["symbol"],
                    "seed_tf_id": tf["id"],
                    "seed_tf_rank": rank,
                    "top_symbols": top_symbols(data.get("regulators", [])),
                },
                details={"n_targets_seeded": len(synthetic_regulon_values(tf["id"], limit=12)), "species": species},
                notes=["This is a self-consistency benchmark, not an external perturbation benchmark."],
            )
        )

    payload = benchmark_payload(
        "benchmark_tf_activity",
        "M2",
        "Validate TF activity scoring on literal known-biology and synthetic regulon-recovery cases.",
        cases,
        notes=[
            "Literal TP53 recovery is the most biologically relevant check in this script.",
            "Synthetic regulon cases measure internal score consistency, not external biological truth.",
        ],
    )
    out = save_benchmark("benchmark_tf_activity", payload)
    print(out)


if __name__ == "__main__":
    main()
