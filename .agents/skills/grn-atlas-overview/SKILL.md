---
name: grn-atlas-overview
description: Overview of the GRN Atlas gene regulatory network database and all available skills. Use as a starting point to discover what analyses are available, which species are supported, and which skill to invoke for a given task.
metadata:
  author: grn-atlas
  version: "1.0"
---

## GRN Atlas

GRN Atlas is a multi-species gene regulatory network database covering **human, mouse, Arabidopsis, tomato, and petunia**. It integrates curated TF-target interactions, expression data, pathway annotations, GWAS traits, TF binding motifs, and cross-species orthology.

## Available Skills

| Skill | What it does |
|---|---|
| `grn-gene-search` | Search genes by name/symbol/keyword |
| `grn-gene-info` | Get detailed gene metadata by ID or symbol |
| `grn-network` | Explore regulators and targets of a gene |
| `grn-pathfinding` | Find regulatory paths between two genes |
| `grn-subgraph` | Extract the regulatory subgraph for a gene set |
| `grn-enrichment` | GO, pathway, trait, or motif enrichment analysis |
| `grn-expression` | Per-sample TPM expression profile |
| `grn-coexpression` | Find co-expressed gene partners |
| `grn-perturbation` | Predict effects of gene knockout or overexpression |
| `grn-dsrna` | Design or analyze dsRNA for RNAi silencing |
| `grn-orthology` | Cross-species orthologs with their networks |
| `grn-conservation` | Compare regulatory edge conservation between species |
| `grn-export` | Export edges with coordinates and motif sites |
| `grn-regulon` | Extract full TF regulon (direct + indirect targets) |
| `grn-regulon-compare` | Compare two TFs' regulons (overlap, Jaccard, significance) |
| `grn-upstream` | Predict upstream regulators for a gene set |
| `grn-network-patterns` | Detect structural motifs (FFL, autoregulation, bi-fan) |
| `grn-centrality` | Compute centrality metrics (degree, betweenness, closeness, eigenvector) |
| `grn-cascade` | Predict regulatory cascade from upstream interventions |
| `grn-citations` | Export BibTeX citations for atlas data sources |
| `grn-dsrna-screen` | Batch dsRNA designability screen across gene sets |
| `grn-stats` | Atlas-wide or per-species database statistics |
| `grn-provenance` | Data sources, methods, citations, and freshness audit |
| `grn-species` | Per-species capability matrix |
| `grn-evidence-audit` | Summarize what evidence layers support a gene or edge |
| `grn-coverage-report` | Report whether a species is ready for a given analysis intent |
| `grn-candidate-triage` | Rank a gene list for a research goal |
| `grn-experiment-prioritization` | Recommend the next analyses or experiments to run |
| `grn-confidence-boundary` | State what the atlas supports, does not support, and leaves ambiguous |
| `grn-transferability` | Assess whether a candidate-level story transfers across species |
| `grn-minimal-validation` | Compress a validation plan into the smallest defensible next step |
| `grn-evidence-synthesis` | Turn atlas evidence into a writing-ready summary with PMIDs and citations |
| `grn-hypothesis-compare` | Compare competing candidate hypotheses and explain the current winner |
| `grn-research-brief` | Build a structured research brief and next-step workflow |
| `grn-validation-plan` | Build an execution-ready validation checklist and decision matrix |
| `grn-study-packet` | Assemble a shareable collaborator handoff packet with brief, plan, provenance, and citations |
| `grn-study-report` | Turn a study packet into a collaborator-facing narrative report with markdown and citations |
| `grn-dataset-import` | Parse a user gene list/CSV/TSV and map its rows onto atlas genes with ambiguity reporting |
| `grn-user-gene-set-analysis` | Run a first-pass atlas workflow over a user-provided gene set: enrichment, upstream, triage, subgraph |
| `grn-differential-expression` | Compare atlas tissues/groups or ingest a DEG table to surface genes with the largest expression shifts |

## Typical Workflows

1. **Find a gene and explore its network**: `grn-gene-search` → `grn-network` → `grn-enrichment`
2. **Compare regulation across species**: `grn-gene-info` → `grn-orthology` → `grn-conservation`
3. **Predict perturbation effects**: `grn-gene-search` → `grn-perturbation` → `grn-enrichment`
4. **Design an RNAi experiment**: `grn-gene-search` → `grn-dsrna-screen` → `grn-dsrna` → `grn-perturbation`
5. **Find co-regulated gene modules**: `grn-coexpression` → `grn-subgraph` → `grn-enrichment`
6. **Upstream analysis**: `grn-upstream` → `grn-regulon` → `grn-enrichment`
7. **Compare TF programs**: `grn-regulon-compare` → `grn-enrichment`
8. **Plan a follow-up study**: `grn-candidate-triage` → `grn-experiment-prioritization` → `grn-research-brief`
9. **State the confidence boundary before acting**: `grn-evidence-audit` → `grn-confidence-boundary`
10. **Assess cross-species transfer before extrapolating**: `grn-orthology` → `grn-transferability`
11. **Reduce a full validation matrix to the minimum next move**: `grn-validation-plan` → `grn-minimal-validation`
12. **Turn atlas evidence into a writing-ready summary**: `grn-evidence-audit` → `grn-evidence-synthesis`
13. **Choose between competing candidates**: `grn-candidate-triage` → `grn-hypothesis-compare`
14. **Turn a brief into a go/no-go plan**: `grn-research-brief` → `grn-validation-plan`
15. **Prepare a collaborator handoff packet**: `grn-research-brief` → `grn-validation-plan` → `grn-study-packet`
16. **Prepare a collaborator-readable report**: `grn-study-packet` → `grn-study-report`
17. **Analyze a user-provided hit list**: `grn-dataset-import` → `grn-user-gene-set-analysis`
18. **Compare conditions or tissues**: `grn-differential-expression` → `grn-upstream` → `grn-enrichment`

## Execution Modes

All skills support two modes:

- **Direct mode** (default): queries the local SQLite database. Requires `pip install -r backend/requirements.txt` and a built database (`make db`).
- **HTTP mode** (`--http http://localhost:8000`): calls the running FastAPI server. Start it with `make backend`.
