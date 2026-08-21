from __future__ import annotations

from validation_common import benchmark_payload, case_result, client, rank_of, save_benchmark, top_symbols


def main() -> None:
    cases = []

    resp = client.post(
        "/api/v1/import/omics",
        json={
            "name": "validation pseudo-celltype",
            "species": "human",
            "data_type": "pseudobulk",
            "gene_values": {
                "TP53": [5.0, 1.0],
                "MDM2": [1.0, 5.0],
                "CDKN1A": [4.0, 1.0],
                "BAX": [3.0, 1.0],
                "BCL2": [1.0, 4.0],
            },
            "sample_names": ["A", "B"],
            "contrasts": [{"group_a": "treated", "group_b": "control", "deg": {"TP53": 2.5, "MDM2": -1.8, "CDKN1A": 3.1, "BAX": 1.2, "BCL2": -1.7}}],
        },
    )
    ds_id = resp.json()["dataset_id"]

    reg = client.post("/api/v1/celltype/regulation", json={"dataset_id": ds_id, "cluster_id": "default", "species": "human"}).json()
    reg_rank = rank_of(reg.get("regulators", []), lambda r: (r.get("symbol") or "").upper() == "TP53")
    cases.append(
        case_result(
            "celltype_regulation_tp53",
            "Cell-type regulation recovers TP53 from TP53-like expression context",
            "pass" if reg_rank and reg_rank <= 10 else "partial",
            metrics={"tp53_rank": reg_rank, "top_regulators": top_symbols(reg.get("regulators", []), limit=8)},
            notes=["This endpoint currently uses expressed imported features rather than true cluster-specific regulons."],
        )
    )

    upstream = client.post(
        "/api/v1/celltype/upstream",
        json={"dataset_id": ds_id, "cluster_id": "default", "gene_ids": ["TP53", "MDM2", "CDKN1A"], "species": "human"},
    ).json()
    up_rank = rank_of(upstream.get("regulators", []), lambda r: (r.get("symbol") or "").upper() == "TP53")
    cases.append(
        case_result(
            "celltype_upstream_tp53",
            "Cell-type upstream analysis recovers TP53 from TP53 target set",
            "pass" if up_rank == 1 else "partial",
            metrics={"tp53_rank": up_rank, "top_regulators": top_symbols(upstream.get("regulators", []), limit=5)},
        )
    )

    compare = client.post(
        "/api/v1/celltype/compare",
        json={"dataset_id": ds_id, "cluster_a": "treated", "cluster_b": "control", "species": "human"},
    ).json()
    cases.append(
        case_result(
            "celltype_compare_has_differential_signal",
            "Cell-type compare returns differential regulators",
            "pass" if len(compare.get("differential_regulators", [])) > 0 else "fail",
            metrics={"n_deg": compare.get("n_deg"), "n_differential_regulators": len(compare.get("differential_regulators", []))},
            notes=["This checks that the contrast pipeline produces ranked outputs; it does not prove lineage-level correctness."],
        )
    )

    payload = benchmark_payload(
        "benchmark_celltype_regulation",
        "M3",
        "Validate cell-type / pseudobulk regulator workflows on a TP53-like imported dataset.",
        cases,
    )
    out = save_benchmark("benchmark_celltype_regulation", payload)
    print(out)


if __name__ == "__main__":
    main()
