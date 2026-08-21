from __future__ import annotations

import json

from validation_common import CORPUS_DIR, benchmark_payload, case_result, client, rank_of, save_benchmark, top_symbols


def main() -> None:
    cases = []
    corpus = json.loads((CORPUS_DIR / "trajectory_cases.json").read_text())
    for case in corpus.get("cases", []):
        resp = client.post("/api/v1/import/omics", json=case["dataset_payload"])
        imported = resp.json()
        ds_id = imported["dataset_id"]
        contrast_id = imported["contrasts"][0]["contrast_id"]
        species = case["species"]
        expected = case["expected_driver"]

        drivers = client.post("/api/v1/trajectory/drivers", json={"dataset_id": ds_id, "contrasts": [contrast_id], "species": species}).json()
        rank = rank_of(drivers.get("drivers", []), lambda r, expected=expected: (r.get("symbol") or "").upper() == expected.upper())
        cases.append(
            case_result(
                f"{case['case_id']}_drivers",
                f"Trajectory driver recovery for {expected}-like contrast",
                "pass" if rank and rank <= case.get("top_threshold", 10) else "partial",
                metrics={f"{expected.lower()}_rank": rank, "top_drivers": top_symbols(drivers.get("drivers", []), limit=8)},
            )
        )

        activity = client.post(
            "/api/v1/trajectory/activity",
            json={"dataset_id": ds_id, "gene_values": case["activity_gene_values"], "species": species},
        ).json()
        rank = rank_of(activity.get("active_tfs", []), lambda r, expected=expected: (r.get("symbol") or "").upper() == expected.upper())
        cases.append(
            case_result(
                f"{case['case_id']}_activity",
                f"Trajectory TF activity recovery for {expected}-like signature",
                "pass" if rank and rank <= case.get("top_threshold", 10) else "partial",
                metrics={f"{expected.lower()}_rank": rank, "top_tfs": top_symbols(activity.get("active_tfs", []), limit=8)},
            )
        )

    payload = benchmark_payload(
        "benchmark_trajectory_workflows",
        "PR3",
        "Validate trajectory driver and activity workflows against curated corpus-backed cases.",
        cases,
        notes=["This is currently a contrast-level benchmark contract; real pseudotime datasets can be added into the corpus without changing runner behavior."],
    )
    out = save_benchmark("benchmark_trajectory_workflows", payload)
    print(out)


if __name__ == "__main__":
    main()
