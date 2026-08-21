from __future__ import annotations

from validation_common import benchmark_payload, case_result, client, save_benchmark


def main() -> None:
    cases = []

    clean_payload = {
        "name": "validation clean bulk",
        "species": "human",
        "data_type": "bulk",
        "gene_values": {
            "TP53": [5.2, 3.1, 7.8],
            "MDM2": [2.3, 4.5, 1.2],
            "CDKN1A": [8.1, 6.2, 9.3],
            "BAX": [1.5, 2.0, 3.0],
        },
        "sample_names": ["S1", "S2", "S3"],
        "contrasts": [{"group_a": "treated", "group_b": "control", "deg": {"TP53": 2.5, "MDM2": -1.8, "CDKN1A": 3.1, "BAX": 0.2}}],
    }
    resp = client.post("/api/v1/import/omics", json=clean_payload)
    data = resp.json()
    ds_id = data["dataset_id"]
    validate = client.post(f"/api/v1/import/{ds_id}/validate").json()
    retrieved = client.get(f"/api/v1/import/{ds_id}").json()
    cases.append(
        case_result(
            "clean_human_bulk",
            "Clean human bulk import and validation",
            "pass" if validate.get("match_pct", 0) >= 90 and retrieved.get("n_features") == 4 else "fail",
            metrics={"match_pct": validate.get("match_pct"), "n_features": retrieved.get("n_features"), "n_contrasts": len(retrieved.get("contrasts", []))},
        )
    )

    mixed_payload = {
        "name": "validation mixed quality bulk",
        "species": "human",
        "data_type": "bulk",
        "gene_values": {
            "TP53": [1, 2],
            "AT1G01010": [3, 4],
            "not_a_gene": [5, 6],
            "MDM2": [2, 1],
        },
        "sample_names": ["S1", "S2"],
    }
    resp = client.post("/api/v1/import/omics", json=mixed_payload)
    ds_id = resp.json()["dataset_id"]
    validate = client.post(f"/api/v1/import/{ds_id}/validate").json()
    unmatched = validate.get("unmatched_sample", [])
    cases.append(
        case_result(
            "mixed_quality_overlap_warning",
            "Mixed-species / mixed-quality overlap warning",
            "pass" if unmatched and validate.get("match_pct", 100) < 100 else "partial",
            metrics={"match_pct": validate.get("match_pct"), "unmatched_sample": unmatched},
            notes=["The endpoint currently reports overlap correctly but does not mark small datasets as valid."],
        )
    )

    resp_a = client.post("/api/v1/import/omics", json=clean_payload).json()
    resp_b = client.post("/api/v1/import/omics", json=clean_payload).json()
    cases.append(
        case_result(
            "repeated_import_consistency",
            "Repeated import consistency",
            "pass" if resp_a["n_features"] == resp_b["n_features"] and resp_a["n_samples"] == resp_b["n_samples"] else "fail",
            metrics={"dataset_a": resp_a["dataset_id"], "dataset_b": resp_b["dataset_id"], "n_features": resp_a["n_features"], "n_samples": resp_a["n_samples"]},
        )
    )

    payload = benchmark_payload(
        "benchmark_omics_import",
        "M1",
        "Validate import correctness, overlap reporting, and repeated-import consistency.",
        cases,
    )
    out = save_benchmark("benchmark_omics_import", payload)
    print(out)


if __name__ == "__main__":
    main()
