# Post-Release Hardening Execution Summary

Date: Friday, August 21, 2026

This document records the implementation and execution status for PR1 through PR7 from `docs/post_release_hardening_plan_2026-08-21.md`.

## Status

- PR1 — implemented and exercised
- PR2 — implemented and exercised
- PR3 — implemented and exercised
- PR4 — implemented and exercised
- PR5 — implemented and exercised
- PR6 — implemented and exercised
- PR7 — implemented and exercised

## What changed

### PR1 / PR7

- added benchmark artifact schema validators:
  - `backend/scripts/validation_schemas.py`
  - `backend/scripts/validate_validation_artifacts.py`
- added benchmark corpus metadata and git SHA stamping in `backend/scripts/validation_common.py`
- updated `backend/scripts/run_validation_suite.py` to append schema validation and emit manifest metadata
- added a dedicated post-release runner:
  - `backend/scripts/run_post_release_hardening_suite.py`
- extended `/api/v1/benchmark/status` to expose artifact-health state, manifest parse warnings, and schema status
- added frontend dashboard regression coverage:
  - `src/components/ValidationDashboard.test.jsx`
- added backend benchmark-status regression coverage:
  - `backend/tests/test_benchmark_status_artifacts.py`

### PR2

- added curated comparator corpora in `backend/data/validation_corpora/sequence_design_cases.json`
- added dsRNA comparator benchmark:
  - `backend/scripts/benchmark_rnai_comparator.py`
- added CRISPR comparator benchmark:
  - `backend/scripts/benchmark_crispr_comparator.py`

### PR3

- added corpus-backed cell-type cases in `backend/data/validation_corpora/celltype_cases.json`
- added corpus-backed trajectory cases in `backend/data/validation_corpora/trajectory_cases.json`
- rewired:
  - `backend/scripts/benchmark_celltype_regulation.py`
  - `backend/scripts/benchmark_trajectory_workflows.py`

### PR4

- hardened signaling benchmark reporting in `backend/scripts/benchmark_signaling_to_tf.py`
- benchmark now separates direct-edge coverage from fallback coverage

### PR5

- expanded activity corpus in `backend/data/validation_corpora/activity_cases.json`
- widened TF activity validation to TP53, MYC, RELA, STAT1, and HIF1A
- widened pathway activity validation to p53, inflammatory, interferon, and hypoxia signatures

### PR6

- added species gold-standard manifest:
  - `backend/data/validation_corpora/species_gold_standard_manifest.json`
- added species threshold aggregator:
  - `backend/scripts/benchmark_species_gold_standards.py`

## Executed validation

Frontend:

- `npm test -- --run src/components/ValidationDashboard.test.jsx src/components/WorkflowWorkspace.test.jsx src/components/GeneSearchInput.test.jsx`

Backend targeted tests:

- `backend/venv/bin/python -m pytest -q backend/tests/test_tf_activity.py backend/tests/test_benchmark_status_artifacts.py backend/tests/test_sequence_design_api.py backend/tests/test_phase3.py`

Post-release hardening suite:

- `backend/venv/bin/python backend/scripts/run_post_release_hardening_suite.py`

Primary artifacts:

- `backend/data/validation_runs/post_release_hardening_summary.json`
- `backend/data/validation_runs/post_release_hardening_summary.md`
- `backend/data/validation_runs/schema_report.json`

## Result summary

From `post_release_hardening_summary.json`:

- suite_status: `pass`
- schema validation: `pass`
- PR2 comparator benchmarks: pass
- PR3 cell-type / trajectory benchmarks: pass
- PR4 signaling benchmark: pass
- PR6 species gold-standard threshold checks: pass
- PR5 expanded activity/pathway benchmark families: pass

## Known limitation

The legacy full validation runner still spends a long time in `backend/scripts/validate_network_statistics.py`. That runtime issue did not block PR1–PR7 execution because the dedicated post-release hardening runner completed cleanly and produced the required artifacts.
