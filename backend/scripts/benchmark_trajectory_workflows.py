from __future__ import annotations

from validation_common import benchmark_payload, case_result, client, rank_of, save_benchmark, top_symbols


def main() -> None:
    cases = []

    resp = client.post(
        "/api/v1/import/omics",
        json={
            "name": "validation trajectory",
            "species": "human",
            "data_type": "pseudobulk",
            "gene_values": {
                "TP53": [5.2, 3.1],
                "MDM2": [2.3, 4.5],
                "CDKN1A": [8.1, 6.2],
                "BAX": [1.5, 2.0],
                "BCL2": [3.0, 1.0],
            },
            "contrasts": [{"group_a": "early", "group_b": "late", "deg": {"TP53": 2.5, "MDM2": -1.8, "BAX": 1.2}}],
        },
    )
    imported = resp.json()
    ds_id = imported["dataset_id"]
    contrast_id = imported["contrasts"][0]["contrast_id"]

    drivers = client.post("/api/v1/trajectory/drivers", json={"dataset_id": ds_id, "contrasts": [contrast_id], "species": "human"}).json()
    rank = rank_of(drivers.get("drivers", []), lambda r: (r.get("symbol") or "").upper() == "TP53")
    cases.append(
        case_result(
            "trajectory_drivers_tp53",
            "Trajectory driver recovery for TP53-like contrast",
            "pass" if rank and rank <= 10 else "partial",
            metrics={"tp53_rank": rank, "top_drivers": top_symbols(drivers.get("drivers", []), limit=8)},
        )
    )

    activity = client.post(
        "/api/v1/trajectory/activity",
        json={"dataset_id": ds_id, "gene_values": {"TP53": 3.0, "MDM2": -2.0, "CDKN1A": 2.5, "BAX": 1.8, "BCL2": -1.5, "GADD45A": 2.1}, "species": "human"},
    ).json()
    rank = rank_of(activity.get("active_tfs", []), lambda r: (r.get("symbol") or "").upper() == "TP53")
    cases.append(
        case_result(
            "trajectory_activity_tp53",
            "Trajectory TF activity recovery for TP53-like signature",
            "pass" if rank and rank <= 10 else "partial",
            metrics={"tp53_rank": rank, "top_tfs": top_symbols(activity.get("active_tfs", []), limit=8)},
        )
    )

    payload = benchmark_payload(
        "benchmark_trajectory_workflows",
        "M5",
        "Validate trajectory driver and activity workflows on a simple TP53-like pseudobulk contrast.",
        cases,
        notes=["This is currently a contrast-level benchmark; it is not a full pseudotime trajectory benchmark with external lineage truth."],
    )
    out = save_benchmark("benchmark_trajectory_workflows", payload)
    print(out)


if __name__ == "__main__":
    main()
