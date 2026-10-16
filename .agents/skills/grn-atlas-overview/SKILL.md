---
name: grn-atlas-overview
description: Overview of the GRN Atlas gene regulatory network database and all available skills. Use as a starting point to discover the major analysis types, high-level supported species coverage, and which skill to invoke for a given task. Not for exact per-species capability details, provenance manifests, or citation export; use grn-species, grn-provenance, or grn-citations for those specific requests.
metadata:
  author: grn-atlas
  version: "1.0"
---

## GRN Atlas

GRN Atlas is a multi-species gene regulatory network database covering the species currently loaded into the atlas build. In the current repository state that includes **human, mouse, Arabidopsis, tomato, petunia, pepper, and potato**, with additional onboarding work prepared for dahlia. It integrates curated TF-target interactions, expression data, pathway annotations, GWAS traits, TF binding motifs, and cross-species orthology.

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
| `grn-experiment-optimizer` | Re-rank follow-up experiments using budget, time, and assay constraints |
| `grn-literature-review` | Retrieve recent external literature for genes, edges, pathways, or phenotypes and classify support vs contradiction |
| `grn-consensus-ranking` | Rank competing candidates by a weighted consensus across atlas evidence layers |
| `grn-counterfactual-analysis` | Explain what evidence shifts would most likely overturn the current lead candidate |
| `grn-variant-effect` | Assess whether a promoter-region variant overlaps motif-supported regulatory sites |
| `grn-allele-affinity` | Quantitatively rescore a promoter variant (ref vs alt) for TF-binding change and predicted expression direction |
| `grn-gwas-to-mechanism` | Turn a trait/GWAS-associated gene into a regulatory mechanism sketch (traits + upstream + downstream, sign-aware) |
| `grn-biosafety-screen` | Screen a dsRNA for self and cross-species off-target silencing across atlas transcriptomes |
| `grn-network-control` | Find the minimal set of TFs to perturb to steer a target gene program, with sign-aware direction recommendations |
| `grn-differential-network` | Compare regulatory-edge activity between two tissues/conditions (gained/strengthened/weakened edges) |
| `grn-dynamics` | Boolean/attractor simulation of a signed regulatory module (fixed point vs cycle; steady-state ON/OFF after a perturbation) |
| `grn-feedback-control` | Discover signed feedback loops, feedback-capable backbones, control groups, biological control-system hypotheses, and structural controller genes across a species GRN |
| `grn-promoter-edit-prioritization` | Prioritize motif-supported promoter sites as editing targets |
| `grn-crispr-design` | Suggest sequence-only heuristic CRISPR guides |
| `grn-primer-design` | Suggest sequence-only heuristic primer pairs |
| `grn-celltype-regulation` | Report readiness and missing layers for cell-type / single-cell analysis |
| `grn-trajectory-regulation` | Report readiness and missing layers for trajectory / time-series analysis |
| `grn-combinatorial-perturbation` | Rank pairwise or triple perturbation combinations by predicted downstream impact |
| `grn-species-onboarding-plan` | Generate a staged plan for onboarding a new species |

## Additional skills

The table above highlights the most common entry points. The remaining callable skills
below complete the catalog; the authoritative, always-current list is every
`.agents/skills/grn-*/SKILL.md` (also cataloged in `docs/SKILL_INVENTORY.md`).

| Skill | What it does |
|---|---|
| `grn-benchmark-status` | View the living validation dashboard: atlas stats, BEELINE AUROC/AUPRC, per-species reports |
| `grn-organism-overview` | Comprehensive per-species overview: gene/interaction counts, TF coverage, sources, capabilities |
| `grn-shared-regulators` | Find TFs regulating two or more genes in common, with per-target direction and evidence |
| `grn-diff-regulation` | Which TFs/regulatory programs shift between two tissues or conditions (regulator-centric) |
| `grn-regulon-enrichment` | Which TF regulons are enriched in a gene list (hypergeometric + BH FDR) |
| `grn-pathway-enrichment` | Which pathways are over-represented in a gene list (hypergeometric) |
| `grn-pathway-activity` | Score pathway activity from gene-level statistics |
| `grn-tf-activity` | Infer TF activity from gene-level stats (log2FC/z-scores) via ULM/weighted mean |
| `grn-module` | Detect co-regulated modules/communities in a species network (leiden/louvain/infomap) |
| `grn-motif` / `grn-motif-query` | Query TF binding-motif hits in promoters (JASPAR 2024 PWMs) |
| `grn-signaling-to-tf` | Trace a receptor/ligand to downstream TF targets through the network |
| `grn-ligand-receptor` | Find candidate ligand-receptor signaling pairs from the network |
| `grn-family-rescue` | Rescue sparse edges by aggregating ortholog evidence across species (reduced confidence) |
| `grn-transfer-risk` | Assess orthology transfer risk for a gene across species |
| `grn-genome-browser` | Query genome coordinates, chromosomal positions, and cross-species ortholog mappings |
| `grn-infer` | Expression-inferred edges (GRNBoost2 / GENIE3): predicted regulators/targets of a gene |
| `grn-trait-association` | Query GWAS trait associations for a gene, or trait enrichment for a gene set |
| `grn-phenotype-targeting` | Turn a phenotype/trait/design objective into atlas-grounded candidate genes |
| `grn-decision-boundary` | One decision-ready summary: what's supported, ambiguous, what would flip it, smallest next step |
| `grn-dataset-import` / `grn-omics-import` | Map a gene list / import an expression matrix (bulk, pseudobulk, scRNA) |
| `grn-input-normalization` | Clean and normalize messy pasted input before atlas import |
| `grn-peak-import` / `grn-perturbation-import` | Import chromatin peaks / observed perturbation results |
| `grn-chromatin-support` | Chromatin peaks, enhancer-gene links, motif-in-peak, cis-support for a gene's edges |
| `grn-cis-support-audit` | Is a TF→target edge cis-supported (motif + peak + enhancer + prior)? Confidence tier + gaps |
| `grn-enhancer-network` | A gene's enhancer-linked neighborhood: linked peaks, TF motifs, co-linked targets |
| `grn-peak-gene-linkage` | Which gene(s) a region/peak likely regulates (peak_id or chr:start-end) |
| `grn-multiome-support-audit` | Multi-layer evidence triangulation for a TF→target claim; conflict-aware confidence |
| `grn-celltype-compare` | Compare TF activity between two cell types/clusters |
| `grn-celltype-upstream` | Upstream TFs for a gene set, constrained to those expressed in a cell type |
| `grn-celltype-regulon` | A TF's regulon filtered to a cell-type/state context vs the global regulon |
| `grn-trajectory-drivers` / `grn-transition-drivers` | TF drivers of state transitions / branch points |
| `grn-pseudotime-activity` | Score TF activity along a pseudotime-ordered gradient |
| `grn-crispr-compare` | Compare CRISPR strategies (KO, CRISPRi, CRISPRa) for a target |
| `grn-crispr-offtargets` | Scan the transcriptome for CRISPR guide off-targets (mismatch-tolerant) |
| `grn-crispr-vs-dsrna-compare` | Compare RNAi vs CRISPR for the same candidates; recommend a first modality |
| `grn-intervention-strategy-ranker` | Rank intervention modes (dsRNA/CRISPR/promoter edit) by feasibility, specificity, cost |
| `grn-edit-consequence` | Predicted regulatory/network consequences of a promoter/motif/coding edit |
| `grn-sirna-pool` | Score siRNAs in a dsRNA window for efficacy (Reynolds/Ui-Tei rules) |
| `grn-isoform-coverage` | Which transcript isoforms a dsRNA hits, and siRNA sites per isoform |
| `grn-perturbation-calibration` | Compare predicted downstream effects with observed perturbation data |
| `grn-literature-grounding` | Score how external literature terms map to atlas genes (exact/synonym/partial/ortholog) |
| `grn-tissue-coexpression` | Tissue-specific coexpression weights for regulatory edges |
| `grn-species-onboarding-status` | Per-species onboarding readiness score (genes, edges, TFs, transcriptome, orthologs) |
| `grn-workflow` | Run a packaged end-to-end workflow (deg-to-regulators, target-to-perturbation, import-to-activity) |

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
19. **Choose the highest-value feasible next step**: `grn-experiment-prioritization` → `grn-experiment-optimizer`
20. **Check the latest external evidence**: `grn-evidence-audit` → `grn-literature-review` → `grn-evidence-synthesis`
21. **Get a robust winner and ask what would flip it**: `grn-consensus-ranking` → `grn-counterfactual-analysis`
22. **Move from regulatory site to assay design**: `grn-variant-effect` → `grn-promoter-edit-prioritization` → `grn-crispr-design` / `grn-primer-design`
23. **Explore advanced future workflows honestly**: `grn-celltype-regulation` / `grn-trajectory-regulation` / `grn-combinatorial-perturbation` / `grn-species-onboarding-plan`
24. **Quantify a promoter variant's regulatory effect**: `grn-variant-effect` → `grn-allele-affinity` (ref vs alt binding change + predicted expression direction)
25. **Explain a trait/GWAS hit mechanistically**: `grn-gwas-to-mechanism` → `grn-enrichment` / `grn-evidence-synthesis`
26. **Check RNAi cross-species safety before synthesis**: `grn-dsrna` → `grn-biosafety-screen`
27. **Steer a whole gene program with the fewest interventions**: `grn-upstream` / `grn-shared-regulators` → `grn-network-control`
28. **Compare regulatory wiring between two tissues/conditions**: `grn-tissue-coexpression` → `grn-differential-network`
29. **Simulate a circuit's steady state / attractor after a perturbation**: `grn-regulon` → `grn-dynamics`
30. **Find feedback loops and biological control systems**: `grn-feedback-control` → `grn-dynamics` / `grn-evidence-synthesis`

## Execution Modes

All skills support two modes:

- **Direct mode** (default): queries the local SQLite database. Requires `pip install -r backend/requirements.txt` and a built database (`make db`).
- **HTTP mode** (`--http http://localhost:8000`): calls the running FastAPI server. Start it with `make backend`.
