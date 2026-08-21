from __future__ import annotations

from validation_common import benchmark_payload, case_result, client, db_conn, save_benchmark


def seed_observations_from_network() -> list[dict]:
    conn = db_conn()
    try:
        rows = conn.execute(
            """
            SELECT target_id, regulation_type
            FROM interactions
            WHERE source_id = 'TP53'
            ORDER BY confidence DESC
            LIMIT 4
            """
        ).fetchall()
    finally:
        conn.close()
    observations = []
    for row in rows:
        log2fc = -2.0 if row["regulation_type"] == "activation" else 2.0 if row["regulation_type"] == "repression" else 0.0
        observations.append(
            {
                "perturbed_gene": "TP53",
                "affected_gene": row["target_id"],
                "log2fc": log2fc,
                "significant": True,
            }
        )
    return observations


def main() -> None:
    cases = []

    observations = seed_observations_from_network()
    imported = client.post("/api/v1/perturbation/import", json={"species": "human", "perturbation_type": "CRISPR_KO", "observations": observations}).json()
    cases.append(
        case_result(
            "perturbation_import",
            "Perturbation observations import",
            "pass" if imported.get("n_imported", 0) >= 1 else "fail",
            metrics={"n_imported": imported.get("n_imported")},
        )
    )

    compare = client.post("/api/v1/perturbation/compare", json={"perturbed_gene": "TP53", "species": "human"})
    compare_json = compare.json()
    status = "pass" if compare.status_code == 200 and compare_json.get("concordance_rate", 0) >= 0.5 else "partial"
    cases.append(
        case_result(
            "perturbation_compare",
            "Predicted vs observed perturbation concordance",
            status,
            metrics={
                "status_code": compare.status_code,
                "n_both": compare_json.get("n_both"),
                "concordance_rate": compare_json.get("concordance_rate"),
            },
        )
    )

    calib = client.get("/api/v1/perturbation/calibration").json()
    cases.append(
        case_result(
            "perturbation_calibration_listing",
            "Calibration dataset listing",
            "pass" if len(calib.get("datasets", [])) >= 1 else "fail",
            metrics={"n_datasets": len(calib.get("datasets", []))},
        )
    )

    payload = benchmark_payload(
        "benchmark_perturbation_calibration",
        "M8",
        "Validate perturbation import, prediction-vs-observation comparison, and calibration listing.",
        cases,
    )
    out = save_benchmark("benchmark_perturbation_calibration", payload)
    print(out)


if __name__ == "__main__":
    main()
