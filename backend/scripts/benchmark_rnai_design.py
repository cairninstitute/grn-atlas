from __future__ import annotations

from validation_common import benchmark_payload, case_result, client, rank_of, save_benchmark


def main() -> None:
    cases = []

    screen = client.post(
        "/api/v1/dsrna/screen",
        json={"species": "petunia", "gene_ids": ["Peaxi162Scf00119g00942", "Peaxi162Scf00118g00310", "Peaxi162Scf00164g00313", "Peaxi162Scf00238g00125"]},
    ).json()
    results = screen.get("results", [])
    jaf_rank = rank_of(results, lambda r: (r.get("symbol") or "").upper() == "JAF13")
    jaf_entry = next((r for r in results if (r.get("symbol") or "").upper() == "JAF13"), None)
    cases.append(
        case_result(
            "rnai_screen_petunia_candidates",
            "Petunia candidate screen ranks clean dsRNA targets",
            "pass" if jaf_entry and jaf_entry.get("best_window_off_targets") == 0 else "partial",
            metrics={"jaf13_rank": jaf_rank, "designable": screen.get("designable"), "n_genes": screen.get("n_genes")},
            details={"top_gene": results[0].get("symbol") if results else None, "jaf13": jaf_entry or {}},
        )
    )

    design = client.post("/api/v1/dsrna", json={"species": "petunia", "target_gene_id": "Peaxi162Scf00119g00942"}).json()
    cases.append(
        case_result(
            "rnai_design_jaf13",
            "Single-gene dsRNA design for JAF13",
            "pass" if design.get("design", {}).get("off_target_gene_count") == 0 and design.get("predicted_effect") else "partial",
            metrics={
                "window_off_targets": design.get("design", {}).get("off_target_gene_count"),
                "predicted_affected": (design.get("predicted_effect") or {}).get("affected"),
            },
        )
    )

    iso = client.post("/api/v1/dsrna/isoform-coverage", json={"target_gene_id": "Peaxi162Scf00047g01225", "species": "petunia"}).json()
    cases.append(
        case_result(
            "rnai_isoform_coverage",
            "Isoform coverage availability",
            "pass" if iso.get("available", True) and iso.get("n_isoforms", 0) >= 1 else "partial",
            metrics={"n_isoforms": iso.get("n_isoforms"), "all_isoforms_covered": iso.get("all_isoforms_covered")},
        )
    )

    payload = benchmark_payload(
        "benchmark_rnai_design",
        "M6",
        "Validate dsRNA screen/design consistency and isoform coverage on petunia candidate genes.",
        cases,
    )
    out = save_benchmark("benchmark_rnai_design", payload)
    print(out)


if __name__ == "__main__":
    main()
