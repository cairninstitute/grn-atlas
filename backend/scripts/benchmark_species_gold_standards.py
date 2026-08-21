from __future__ import annotations

import json

from validation_common import DATA_DIR, benchmark_payload, case_result, save_benchmark


def main() -> None:
    manifest = json.loads((DATA_DIR / "validation_corpora" / "species_gold_standard_manifest.json").read_text())
    cases = []
    for spec in manifest.get("species_targets", []):
        payload = json.loads((DATA_DIR / spec["report_file"]).read_text())
        gs = payload["gold_standard"]
        thresholds = spec["required_metrics"]
        status = "pass" if (
            gs["recall"] >= thresholds["recall_min"]
            and gs["specificity"] >= thresholds["specificity_min"]
            and gs["precision"] >= thresholds["precision_min"]
        ) else "partial"
        cases.append(case_result(
            f"{spec['species']}_gold_standard",
            f"{spec['species']} gold-standard quality threshold check",
            status,
            metrics={"recall": gs["recall"], "specificity": gs["specificity"], "precision": gs["precision"]},
        ))
    beeline = json.loads((DATA_DIR / "beeline_benchmark_report.json").read_text())
    for target in manifest.get("independent_network_benchmarks", []):
        row = next((r for r in beeline if r.get("species") == target["species"]), None)
        if not row:
            cases.append(case_result(
                f"{target['species']}_independent_benchmark",
                f"{target['species']} independent benchmark presence",
                "fail",
                notes=["Missing expected benchmark row."],
            ))
            continue
        thresholds = target["required_metrics"]
        status = "pass" if row["auroc"] >= thresholds["auroc_min"] and row["auprc"] >= thresholds["auprc_min"] else "partial"
        cases.append(case_result(
            f"{target['species']}_independent_benchmark",
            f"{target['species']} independent benchmark threshold check",
            status,
            metrics={"auroc": row["auroc"], "auprc": row["auprc"]},
        ))
    payload = benchmark_payload(
        "benchmark_species_gold_standards",
        "PR6",
        "Species-level quality threshold aggregation over gold-standard and independent benchmark reports.",
        cases,
    )
    out = save_benchmark("benchmark_species_gold_standards", payload)
    print(out)


if __name__ == "__main__":
    main()
