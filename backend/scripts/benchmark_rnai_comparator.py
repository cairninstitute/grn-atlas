from __future__ import annotations

import json

from validation_common import DATA_DIR, benchmark_payload, case_result, client, rank_of, save_benchmark


def main() -> None:
    corpus = json.loads((DATA_DIR / "validation_corpora" / "sequence_design_cases.json").read_text())
    cases = []
    for case in corpus.get("rnai_cases", []):
        screen = client.post("/api/v1/dsrna/screen", json={"species": case["species"], "gene_ids": case["screen_gene_ids"]}).json()
        results = screen.get("results", [])
        top_symbol = results[0]["symbol"] if results else None
        top_rank = rank_of(results, lambda r, sym=case["expected_top_symbol"]: (r.get("symbol") or "").upper() == sym.upper())
        cases.append(case_result(
            f"{case['case_id']}_screen",
            f"RNAi comparator screen: {case['case_id']}",
            "pass" if top_rank == 1 else "partial",
            metrics={"top_symbol": top_symbol, "expected_top_rank": top_rank, "n_results": len(results)},
            notes=["Comparator-style expectation uses curated reference ranking rather than a live external tool invocation."],
        ))
        design = client.post("/api/v1/dsrna", json={"species": case["species"], "target_gene_id": case["single_design_target"]}).json()
        cases.append(case_result(
            f"{case['case_id']}_design",
            f"RNAi comparator single-design: {case['case_id']}",
            "pass" if design.get("design", {}).get("off_target_gene_count") == 0 else "partial",
            metrics={"off_target_gene_count": design.get("design", {}).get("off_target_gene_count"), "mode": design.get("mode")},
            notes=["This checks curated reference expectations analogous to external RNAi design review."],
        ))
    payload = benchmark_payload(
        "benchmark_rnai_comparator",
        "PR2",
        "Comparator-style dsRNA validation against curated design expectations.",
        cases,
        notes=["This is comparator-ready infrastructure; it does not claim a live external-tool execution."],
    )
    out = save_benchmark("benchmark_rnai_comparator", payload)
    print(out)


if __name__ == "__main__":
    main()
