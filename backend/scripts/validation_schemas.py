from __future__ import annotations

from typing import Any


def _require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_benchmark_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _require(isinstance(payload, dict), "payload must be an object", errors)
    if errors:
        return errors
    for key in ("benchmark", "milestone", "description", "run_at_utc", "status", "summary", "cases", "notes"):
        _require(key in payload, f"missing key: {key}", errors)
    _require(payload.get("status") in {"pass", "partial", "fail"}, "status must be pass/partial/fail", errors)
    _require(isinstance(payload.get("cases"), list), "cases must be a list", errors)
    summary = payload.get("summary", {})
    _require(isinstance(summary, dict), "summary must be an object", errors)
    for key in ("cases_total", "cases_pass", "cases_partial", "cases_fail"):
        _require(key in summary, f"summary missing {key}", errors)
    for i, case in enumerate(payload.get("cases", [])):
        prefix = f"case[{i}]"
        _require(isinstance(case, dict), f"{prefix} must be an object", errors)
        if not isinstance(case, dict):
            continue
        for key in ("case_id", "title", "status", "metrics", "details", "notes"):
            _require(key in case, f"{prefix} missing {key}", errors)
        _require(case.get("status") in {"pass", "partial", "fail"}, f"{prefix} invalid status", errors)
    return errors


def validate_summary_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("run_at_utc", "suite_status", "script_runs", "benchmarks", "legacy_artifacts"):
        _require(key in payload, f"missing key: {key}", errors)
    _require(payload.get("suite_status") in {"pass", "fail"}, "suite_status must be pass/fail", errors)
    _require(isinstance(payload.get("script_runs"), list), "script_runs must be a list", errors)
    _require(isinstance(payload.get("benchmarks"), list), "benchmarks must be a list", errors)
    for i, run in enumerate(payload.get("script_runs", [])):
        prefix = f"script_runs[{i}]"
        _require(isinstance(run, dict), f"{prefix} must be an object", errors)
        if not isinstance(run, dict):
            continue
        for key in ("script", "returncode", "stdout", "stderr", "status"):
            _require(key in run, f"{prefix} missing {key}", errors)
    return errors


def validate_corpus_manifest(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("schema_version", "corpus_version", "datasets"):
        _require(key in payload, f"missing key: {key}", errors)
    _require(isinstance(payload.get("datasets"), dict), "datasets must be an object", errors)
    return errors
