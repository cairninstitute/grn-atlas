from __future__ import annotations

import json

from validation_common import CORPUS_DIR, benchmark_payload, case_result, client, rank_of, save_benchmark, top_symbols


def main() -> None:
    cases = []
    corpus = json.loads((CORPUS_DIR / "celltype_cases.json").read_text())
    for case in corpus.get("cases", []):
        resp = client.post("/api/v1/import/omics", json=case["dataset_payload"])
        ds_id = resp.json()["dataset_id"]
        species = case["species"]
        expected = case["expected_regulator"]

        reg = client.post("/api/v1/celltype/regulation", json={"dataset_id": ds_id, "cluster_id": "default", "species": species}).json()
        reg_rank = rank_of(reg.get("regulators", []), lambda r, expected=expected: (r.get("symbol") or "").upper() == expected.upper())
        cases.append(
            case_result(
                f"{case['case_id']}_regulation",
                f"Cell-type regulation recovers {expected}",
                "pass" if reg_rank and reg_rank <= case.get("top_threshold", 10) else "partial",
                metrics={f"{expected.lower()}_rank": reg_rank, "top_regulators": top_symbols(reg.get("regulators", []), limit=8)},
                notes=["This endpoint currently uses expressed imported features rather than true cluster-specific regulons."],
            )
        )

        upstream = client.post(
            "/api/v1/celltype/upstream",
            json={"dataset_id": ds_id, "cluster_id": "default", "gene_ids": list(case["dataset_payload"]["gene_values"].keys())[:3], "species": species},
        ).json()
        up_rank = rank_of(upstream.get("regulators", []), lambda r, expected=expected: (r.get("symbol") or "").upper() == expected.upper())
        cases.append(
            case_result(
                f"{case['case_id']}_upstream",
                f"Cell-type upstream analysis recovers {expected}",
                "pass" if up_rank and up_rank <= case.get("top_threshold", 5) else "partial",
                metrics={f"{expected.lower()}_rank": up_rank, "top_regulators": top_symbols(upstream.get("regulators", []), limit=5)},
            )
        )

        contrast = case["dataset_payload"]["contrasts"][0]
        compare = client.post(
            "/api/v1/celltype/compare",
            json={"dataset_id": ds_id, "cluster_a": contrast["group_a"], "cluster_b": contrast["group_b"], "species": species},
        ).json()
        cases.append(
            case_result(
                f"{case['case_id']}_compare",
                "Cell-type compare returns differential regulators",
                "pass" if len(compare.get("differential_regulators", [])) > 0 else "fail",
                metrics={"n_deg": compare.get("n_deg"), "n_differential_regulators": len(compare.get("differential_regulators", []))},
                notes=["This checks that the contrast pipeline produces ranked outputs; it does not prove lineage-level correctness."],
            )
        )

    payload = benchmark_payload(
        "benchmark_celltype_regulation",
        "PR3",
        "Validate cell-type / pseudobulk regulator workflows against curated corpus-backed cases.",
        cases,
        notes=["The current corpus includes curated proxy cases. Real external single-cell datasets can be added without changing the benchmark contract."],
    )
    out = save_benchmark("benchmark_celltype_regulation", payload)
    print(out)


if __name__ == "__main__":
    main()
