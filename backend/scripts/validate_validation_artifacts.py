from __future__ import annotations

import json
from pathlib import Path

from validation_common import DATA_DIR, RUNS_DIR, ensure_runs_dir, write_json
from validation_schemas import (
    validate_benchmark_payload,
    validate_corpus_manifest,
    validate_summary_payload,
)


def main() -> None:
    ensure_runs_dir()
    report: dict[str, object] = {
        "schema_version": "1.0",
        "status": "pass",
        "checks": [],
    }
    checks: list[dict[str, object]] = []

    for path in sorted(RUNS_DIR.glob("benchmark_*.json")):
        payload = json.loads(path.read_text())
        errors = validate_benchmark_payload(payload)
        checks.append({"file": str(path), "type": "benchmark", "status": "pass" if not errors else "fail", "errors": errors})

    summary_path = RUNS_DIR / "latest_summary.json"
    if summary_path.exists():
        payload = json.loads(summary_path.read_text())
        errors = validate_summary_payload(payload)
        checks.append({"file": str(summary_path), "type": "summary", "status": "pass" if not errors else "fail", "errors": errors})

    corpus_manifest_path = DATA_DIR / "validation_corpora" / "benchmark_corpus_manifest.json"
    if corpus_manifest_path.exists():
        payload = json.loads(corpus_manifest_path.read_text())
        errors = validate_corpus_manifest(payload)
        checks.append({"file": str(corpus_manifest_path), "type": "corpus_manifest", "status": "pass" if not errors else "fail", "errors": errors})

    report["checks"] = checks
    report["status"] = "pass" if all(c["status"] == "pass" for c in checks) else "fail"
    out = RUNS_DIR / "schema_report.json"
    write_json(out, report)
    print(out)


if __name__ == "__main__":
    main()
