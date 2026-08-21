# GRN Atlas Validation Run Summary

Date: August 21, 2026

Purpose: record the validation work that was executable in the repository before the milestone-specific benchmark scripts from the broader validation roadmap were implemented.

## What was executed

### 1. Milestone regression suite

Executed:

- `backend/tests/test_tf_activity.py`
- `backend/tests/test_phase2.py`
- `backend/tests/test_phase3.py`
- `backend/tests/test_phase4.py`

Result:

- **37 passed**
- **0 failed**

Runtime:

- ~48 seconds

Notes:

- warnings only; no test failures
- warnings include deprecated FastAPI `on_event`, Starlette/httpx deprecation, and one pytest warning about a test returning a dataset id

### 2. Existing gold-standard quality validation

Executed:

- `backend/scripts/validate_regulation_quality.py`

Artifacts refreshed:

- `backend/data/quality_report_petunia.json`
- `backend/data/quality_report_tomato.json`

Headline results:

#### Petunia

- recall: **93.8%** (30/32)
- specificity: **100.0%** (11/11)
- precision: **100.0%**

#### Tomato

- recall: **84.2%** (32/38)
- specificity: **100.0%** (12/12)
- precision: **100.0%**

### 3. Population-level network validation

Executed:

- `backend/scripts/validate_network_statistics.py`

Artifacts refreshed:

- `backend/data/network_stats_arabidopsis.json`
- `backend/data/network_stats_human.json`
- `backend/data/network_stats_pepper.json`
- `backend/data/network_stats_petunia.json`
- `backend/data/network_stats_potato.json`
- `backend/data/network_stats_rice.json`
- `backend/data/network_stats_tomato.json`
- `backend/data/network_validation_report.md`

Headline summary from the regenerated report:

| Species | Edges | Coherence (σ) | Multi-ev. z | Motif enrichment |
|---|---:|---:|---:|---:|
| arabidopsis | 919,449 | 4.87 | 2.88 | — |
| tomato | 248,288 | 36.39 | 1.86 | 38.43x |
| petunia | 236,727 | 34.38 | 3.5 | 31.46x |
| human | 17,946 | 6.61 | -3.47 | — |
| mouse | 17,692 | — | 0 | — |
| rice | 16,933 | — | 0 | 28.15x |
| potato | 11,409 | — | 0 | 3.26x |
| pepper | 2,212 | — | 0 | 20.66x |

### 4. Existing BEELINE-style benchmark

Executed:

- `backend/scripts/benchmark_beeline.py`

Artifact refreshed:

- `backend/data/beeline_benchmark_report.json`

Headline results:

#### Arabidopsis vs DAP-seq

- AUROC: **0.8801**
- AUPRC: **0.6990**
- precision@100: **0.9000**

#### Human DoRothEA vs TRRUST

- AUROC: **1.0000**
- AUPRC: **1.0000**
- precision@100: **1.0000**

#### Multi-evidence GO quality

- quality ratio: **0.97x**

## What this run proved

This run proved that:

1. the newly added roadmap milestone surfaces are present and pass current regression tests
2. the existing atlas-level biological validation still executes against the enlarged data build
3. benchmark artifacts can be refreshed successfully in this checkout

## What this run did not yet prove

This run did **not** complete the broader validation roadmap for the new roadmap milestones.

At the time of this run, the repository still lacked the milestone-specific benchmark scripts for:

- TF activity external perturbation benchmarking
- omics import benchmark bundle
- cell-type regulator recovery benchmarking
- chromatin support benchmarking
- trajectory workflow benchmarking
- RNAi comparison benchmarking
- CRISPR comparison benchmarking
- perturbation calibration benchmarking
- signaling-to-TF benchmarking
- transferability benchmarking
- workflow packaging benchmarking

## Working-tree impact from this run

Tracked files modified by the validation refresh:

- `backend/data/network_stats_arabidopsis.json`
- `backend/data/network_stats_human.json`
- `backend/data/network_stats_pepper.json`
- `backend/data/network_stats_petunia.json`
- `backend/data/network_stats_potato.json`
- `backend/data/network_stats_rice.json`
- `backend/data/network_stats_tomato.json`
- `backend/data/network_validation_report.md`
- `backend/data/quality_report_petunia.json`
- `backend/data/quality_report_tomato.json`
- `backend/data/beeline_benchmark_report.json`

## Conclusion

The executable validation already present in the repo completed successfully and refreshed the existing network-quality and benchmark artifacts.

The next step is to implement the milestone-specific benchmark suite described in:

- `docs/validation_roadmap_2026-08-21.md`

so that the newer roadmap additions can be validated milestone by milestone rather than only through regression tests and legacy atlas-level validation.
