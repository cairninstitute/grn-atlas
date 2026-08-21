from __future__ import annotations

from validation_common import benchmark_payload, case_result, client, save_benchmark


def main() -> None:
    cases = []

    listed = client.get("/api/v1/workflows/list").json()
    workflow_ids = {w["id"] for w in listed.get("workflows", [])}
    cases.append(
        case_result(
            "workflow_list",
            "Workflow list surface",
            "pass" if {"deg-to-regulators", "target-to-perturbation", "import-to-activity"} <= workflow_ids else "fail",
            metrics={"workflow_ids": sorted(workflow_ids)},
        )
    )

    deg = client.post("/api/v1/workflows/run", json={"workflow_type": "deg-to-regulators", "species": "human", "gene_ids": ["TP53", "MDM2", "CDKN1A", "BAX", "BCL2"]}).json()
    cases.append(
        case_result(
            "workflow_deg_to_regulators",
            "DEG → regulators packaged workflow",
            "pass" if deg.get("status") == "complete" and len((deg.get("results") or {}).get("top_regulators", [])) >= 1 else "fail",
            metrics={"status": deg.get("status"), "n_top_regulators": len((deg.get("results") or {}).get("top_regulators", []))},
        )
    )

    target = client.post("/api/v1/workflows/run", json={"workflow_type": "target-to-perturbation", "species": "petunia", "gene_ids": ["Peaxi162Scf00119g00942"]})
    target_json = target.json()
    cases.append(
        case_result(
            "workflow_target_to_perturbation",
            "Target → perturbation packaged workflow",
            "pass" if target.status_code == 200 and len(target_json.get("strategies", [])) >= 2 else "partial",
            metrics={"status_code": target.status_code, "n_strategies": len(target_json.get("strategies", []))},
        )
    )

    imported = client.post("/api/v1/import/omics", json={"name": "workflow import", "species": "human", "data_type": "bulk", "gene_values": {"TP53": [5.0], "MDM2": [3.0], "CDKN1A": [8.0]}}).json()
    import_activity = client.post("/api/v1/workflows/run", json={"workflow_type": "import-to-activity", "dataset_id": imported["dataset_id"]}).json()
    cases.append(
        case_result(
            "workflow_import_to_activity",
            "Import → activity packaged workflow",
            "pass" if import_activity.get("status") == "ready" else "fail",
            metrics={"status": import_activity.get("status"), "next_action": import_activity.get("next_action")},
        )
    )

    packet = client.post("/api/v1/research/study-packet", json={"gene_ids": ["Peaxi162Scf00119g00942", "Peaxi162Scf00118g00310"], "species": "petunia", "intent": "rnai"})
    report = client.post("/api/v1/research/study-report", json={"gene_ids": ["Peaxi162Scf00119g00942", "Peaxi162Scf00118g00310"], "species": "petunia", "intent": "rnai"})
    cases.append(
        case_result(
            "study_packet_and_report",
            "Collaborator packet/report generation",
            "pass" if packet.status_code == 200 and report.status_code == 200 else "partial",
            metrics={"packet_status": packet.status_code, "report_status": report.status_code},
        )
    )

    payload = benchmark_payload(
        "benchmark_workflow_packaging",
        "M12",
        "Validate packaged workflow execution and collaborator-facing packet/report surfaces.",
        cases,
    )
    out = save_benchmark("benchmark_workflow_packaging", payload)
    print(out)


if __name__ == "__main__":
    main()
