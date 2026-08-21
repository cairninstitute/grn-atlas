from __future__ import annotations

from validation_common import benchmark_payload, case_result, client, save_benchmark


def main() -> None:
    cases = []

    import_payload = {
        "species": "arabidopsis",
        "peaks": [
            {"chrom": "Chr1", "start": 1000, "end": 2000, "score": 50.5, "peak_type": "promoter"},
            {"chrom": "Chr1", "start": 5000, "end": 6000, "score": 30.2, "peak_type": "enhancer"},
        ],
        "links": [{"peak_id": "Chr1:1000-2000", "gene_id": "AT1G01010", "score": 0.8, "link_type": "proximity"}],
    }
    imported = client.post("/api/v1/chromatin/import-peaks", json=import_payload).json()
    cases.append(
        case_result(
            "chromatin_import",
            "Chromatin peaks and links import",
            "pass" if imported.get("n_peaks") == 2 and imported.get("n_links") == 1 else "fail",
            metrics={"n_peaks": imported.get("n_peaks"), "n_links": imported.get("n_links")},
        )
    )

    peaks = client.get("/api/v1/chromatin/peaks/arabidopsis").json()
    cases.append(
        case_result(
            "chromatin_peak_listing",
            "Chromatin peak listing",
            "pass" if len(peaks.get("peaks", [])) >= 1 else "fail",
            metrics={"returned_peaks": len(peaks.get("peaks", []))},
        )
    )

    gene_support = client.get("/api/v1/chromatin/gene/AT1G01010").json()
    cis_support = client.post("/api/v1/chromatin/cis-support?gene_id=AT1G01010").json()
    linked = len(gene_support.get("linked_peaks", []))
    edges = len(cis_support.get("edges", []))
    status = "pass" if linked >= 1 else "fail"
    if linked >= 1 and edges == 0:
        status = "partial"
    cases.append(
        case_result(
            "chromatin_gene_support",
            "Gene-level chromatin support retrieval",
            status,
            metrics={"linked_peaks": linked, "cis_supported_edges": edges},
            notes=["A linked peak proves storage/query integrity. Non-zero cis-supported edges would show stronger regulatory integration."],
        )
    )

    payload = benchmark_payload(
        "benchmark_chromatin_support",
        "M4",
        "Validate chromatin peak import, retrieval, and cis-support integration.",
        cases,
    )
    out = save_benchmark("benchmark_chromatin_support", payload)
    print(out)


if __name__ == "__main__":
    main()
