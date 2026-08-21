from __future__ import annotations

import json

from validation_common import DATA_DIR, benchmark_payload, case_result, client, save_benchmark


def main() -> None:
    corpus = json.loads((DATA_DIR / "validation_corpora" / "sequence_design_cases.json").read_text())
    cases = []
    for case in corpus.get("crispr_cases", []):
        design = client.post("/api/v1/crispr/design", json={"sequence": case["sequence"], "pam": case.get("pam", "NGG")}).json()
        guides = design.get("guides", [])
        cases.append(case_result(
            case["case_id"],
            f"CRISPR comparator case: {case['case_id']}",
            "pass" if len(guides) >= case.get("expected_min_guides", 1) else "fail",
            metrics={"n_guides": len(guides), "top_priority_score": guides[0]["priority_score"] if guides else None},
            notes=["Comparator-style expectation uses curated sequence-level guide availability rather than a live external tool invocation."],
        ))
    payload = benchmark_payload(
        "benchmark_crispr_comparator",
        "PR2",
        "Comparator-style CRISPR validation against curated design expectations.",
        cases,
        notes=["This is comparator-ready infrastructure; it does not claim a live external-tool execution."],
    )
    out = save_benchmark("benchmark_crispr_comparator", payload)
    print(out)


if __name__ == "__main__":
    main()
