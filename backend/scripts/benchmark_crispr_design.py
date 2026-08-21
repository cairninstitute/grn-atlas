from __future__ import annotations

from validation_common import benchmark_payload, case_result, client, save_benchmark


def main() -> None:
    cases = []

    off = client.post("/api/v1/crispr/offtargets", json={"guide_sequence": "ATGGCTAGCTAGCTAGCTAG", "species": "arabidopsis", "max_mismatches": 2}).json()
    cases.append(
        case_result(
            "crispr_offtarget_scan",
            "CRISPR off-target scan executes",
            "pass" if "n_offtargets" in off else "fail",
            metrics={"n_offtargets": off.get("n_offtargets")},
        )
    )

    short = client.post("/api/v1/crispr/offtargets", json={"guide_sequence": "ATGG", "species": "human"})
    cases.append(
        case_result(
            "crispr_bad_length_rejected",
            "Short CRISPR guide is rejected",
            "pass" if short.status_code == 400 else "fail",
            metrics={"status_code": short.status_code},
        )
    )

    compare = client.post("/api/v1/crispr/compare", json={"gene_id": "TP53", "species": "human", "modes": ["knockout", "CRISPRi", "CRISPRa"]})
    compare_json = compare.json()
    status = "pass" if compare.status_code == 200 and len(compare_json.get("strategies", [])) == 3 else "partial"
    cases.append(
        case_result(
            "crispr_strategy_compare",
            "CRISPR strategy comparison for TP53",
            status,
            metrics={"status_code": compare.status_code, "n_strategies": len(compare_json.get("strategies", []))},
        )
    )

    payload = benchmark_payload(
        "benchmark_crispr_design",
        "M7",
        "Validate CRISPR off-target scanning and strategy comparison endpoints.",
        cases,
        notes=["This milestone currently validates heuristic design surfaces, not external CRISPOR/CHOPCHOP concordance."],
    )
    out = save_benchmark("benchmark_crispr_design", payload)
    print(out)


if __name__ == "__main__":
    main()
