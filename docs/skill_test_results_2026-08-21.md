# Agent Skill Test Results — 2026-08-21

Historical snapshot: on Thursday, August 21, 2026, the then-current 90-skill inventory passed **90/90** direct HTTP one-by-one execution checks.

This file is kept for historical traceability. The current repository inventory on Saturday, August 22, 2026 is **100 documented skills** (**99 callable + 1 overview/router**), so this file should not be read as the current full-surface status page.

All skills in that Aug. 21 snapshot were tested via `scripts/run.py --http http://localhost:8000` against a running backend.

## Summary

| Status | Count |
|--------|-------|
| Pass   | 90    |
| Fail   | 0     |

## Bug found and fixed

- `grn-chromatin-support/scripts/run.py` line 24 had a template placeholder
  (`backend.{gene_id}()`) instead of actual code. Fixed to
  `backend.chromatin_gene_support(args.gene_id)`.

## All 90 skills tested in the Aug. 21 snapshot

grn-atlas-overview, grn-benchmark-status, grn-candidate-triage,
grn-cascade, grn-celltype-compare, grn-celltype-regulation,
grn-celltype-upstream, grn-centrality, grn-chromatin-support,
grn-citations, grn-coexpression, grn-combinatorial-perturbation,
grn-confidence-boundary, grn-consensus-ranking, grn-conservation,
grn-counterfactual-analysis, grn-coverage-report, grn-crispr-compare,
grn-crispr-design, grn-crispr-offtargets, grn-dataset-import,
grn-decision-boundary, grn-diff-regulation, grn-differential-expression,
grn-dsrna, grn-dsrna-screen, grn-enrichment, grn-evidence-audit,
grn-evidence-synthesis, grn-experiment-optimizer,
grn-experiment-prioritization, grn-export, grn-expression,
grn-family-rescue, grn-gene-info, grn-gene-search, grn-genome-browser,
grn-hypothesis-compare, grn-infer, grn-input-normalization,
grn-isoform-coverage, grn-ligand-receptor, grn-literature-review,
grn-minimal-validation, grn-module, grn-motif, grn-motif-query,
grn-network, grn-network-patterns, grn-omics-import,
grn-organism-overview, grn-orthology, grn-pathway-activity,
grn-pathway-enrichment, grn-pathfinding, grn-peak-import,
grn-perturbation, grn-perturbation-calibration, grn-perturbation-import,
grn-phenotype-targeting, grn-primer-design,
grn-promoter-edit-prioritization, grn-provenance,
grn-pseudotime-activity, grn-regulon, grn-regulon-compare,
grn-regulon-enrichment, grn-research-brief, grn-shared-regulators,
grn-signaling-to-tf, grn-sirna-pool, grn-species,
grn-species-onboarding-plan, grn-species-onboarding-status, grn-stats,
grn-study-packet, grn-study-report, grn-subgraph, grn-tf-activity,
grn-tissue-coexpression, grn-trait-association, grn-trajectory-drivers,
grn-trajectory-regulation, grn-transfer-risk, grn-transferability,
grn-upstream, grn-user-gene-set-analysis, grn-validation-plan,
grn-variant-effect, grn-workflow
