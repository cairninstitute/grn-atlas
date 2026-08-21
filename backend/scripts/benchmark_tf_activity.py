from __future__ import annotations

import json

from validation_common import (
    CORPUS_DIR,
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
    corpus = json.loads((CORPUS_DIR / "activity_cases.json").read_text())
    for case in corpus.get("tf_activity_cases", []):
        for method in ("ulm", "wmean"):
            resp = client.post(
                "/api/v1/activity/tf",
                json={
                    "gene_values": case["gene_values"],
                    "species": case["species"],
                    "method": method,
                    "top": 10,
                    "min_regulon_size": 2,
                },
            )
            data = resp.json()
            rank = rank_of(data.get("regulators", []), lambda r, exp=case["expected_tf"]: (r.get("symbol") or "").upper() == exp.upper())
            cases.append(
                case_result(
                    f"{case['case_id']}_{method}",
                    f"{case['expected_tf']} literal signature recovery ({method})",
                    "pass" if rank and rank <= case.get("top_threshold", 5) else "fail",
                    metrics={"expected_rank": rank, "top_symbols": top_symbols(data.get("regulators", []))},
                    details={"matched_genes": data.get("matched_genes"), "method": method, "case_id": case["case_id"]},
                    notes=["Curated literal signature case from the activity benchmark corpus."],
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
        "Validate TF activity scoring on expanded literal benchmark signatures and synthetic regulon-recovery cases.",
        cases,
        notes=[
            "Literal signature cases come from the validation corpus and broaden beyond TP53.",
            "Synthetic regulon cases measure internal score consistency, not external biological truth.",
        ],
    )
    out = save_benchmark("benchmark_tf_activity", payload)
    print(out)


if __name__ == "__main__":
    main()
