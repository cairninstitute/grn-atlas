from __future__ import annotations

from validation_common import benchmark_payload, case_result, client, db_conn, save_benchmark


def pick_arabidopsis_to_tomato_gene() -> str:
    conn = db_conn()
    try:
        row = conn.execute(
            """
            SELECT o.gene_a
            FROM orthologs o
            JOIN genes g ON g.id = o.gene_a
            WHERE o.species_a = 'arabidopsis' AND o.species_b = 'tomato'
            ORDER BY COALESCE(o.score, 0) DESC
            LIMIT 1
            """
        ).fetchone()
        return row["gene_a"] if row else "AT1G56650"
    finally:
        conn.close()


def main() -> None:
    cases = []

    gene_id = pick_arabidopsis_to_tomato_gene()
    risk = client.post("/api/v1/orthology/transfer-risk", json={"gene_id": gene_id, "target_species": "tomato"})
    risk_json = risk.json()
    cases.append(
        case_result(
            "transfer_risk_arabidopsis_to_tomato",
            "Arabidopsis to tomato transfer-risk scoring",
            "pass" if risk.status_code == 200 and len(risk_json.get("risks", [])) >= 1 else "partial",
            metrics={"status_code": risk.status_code, "n_risks": len(risk_json.get("risks", [])), "gene_id": gene_id},
        )
    )

    rescue = client.post("/api/v1/family-rescue", json={"gene_id": gene_id})
    rescue_json = rescue.json()
    cases.append(
        case_result(
            "family_rescue",
            "Family-rescue augmentation",
            "pass" if rescue.status_code == 200 else "fail",
            metrics={"status_code": rescue.status_code, "rescued_edges": rescue_json.get("rescued_edges")},
        )
    )

    known = client.get("/api/v1/species/onboarding/arabidopsis").json()
    unknown = client.get("/api/v1/species/onboarding/dahlia").json()
    cases.append(
        case_result(
            "species_onboarding_readiness",
            "Known vs unknown species onboarding readiness",
            "pass" if known.get("readiness_level") in ("full", "partial") and unknown.get("readiness_level") == "minimal" else "fail",
            metrics={"arabidopsis_readiness": known.get("readiness_level"), "dahlia_readiness": unknown.get("readiness_level")},
        )
    )

    payload = benchmark_payload(
        "benchmark_transferability",
        "M11",
        "Validate transfer-risk, family-rescue, and species onboarding readiness surfaces.",
        cases,
    )
    out = save_benchmark("benchmark_transferability", payload)
    print(out)


if __name__ == "__main__":
    main()
