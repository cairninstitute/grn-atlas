# Regulatory evidence expansion

GRN Atlas separates observed signed interactions from evidence used to propose missing
regulatory edges. External records are normalized into `regulatory_evidence`; they are
never inserted directly into `interactions` by the expansion pipeline.

## Sources and release policy

- JASPAR 2026 CORE plants supplies motif models. Motif matches remain predicted binding.
- PLAZA Dicots 5 supplies plant coordinates, descriptions, and syntenic orthology.
- ChIP-Atlas supplies direct unsigned occupancy for Arabidopsis, human, and mouse.
- TFLink small-scale records supply direct unsigned human and mouse evidence.
- Expression Atlas contributes only manually reviewed perturbation contrasts. The
  committed rice OsERF48 manifest records the contrast direction and significance type.
- PCBase has a reviewed-manifest loader for rice and tomato peaks. Datasets remain
  blocked until their genome assembly is explicitly verified or lifted to the atlas
  assembly.
- funRiceGenes and funPlantGenes are audited but not ingested because no suitable
  row-level signed export with traceable provenance was identified.
- AGRIS has both a strict confirmed-direct-signed import and a separately named expanded
  evidence import. Unconfirmed unsigned predictions are excluded.
- ConnecTF experiment files are retained at experiment resolution with TF, assay,
  tissue/treatment metadata, log2 fold change, significance, and binding versus
  perturbation semantics.
- Conserved-edge transfer requires strict one-to-one orthology and either support from
  two donor species or independent cis support in the recipient species.

The unconfirmed unsigned AGRIS predictions remain excluded. Signed putative-direct
records are retained only in the explicitly exploratory tier.

Rice Expression Atlas identifiers are aligned with the official IC4R MSU/RAP-DB
crosswalk and stored as searchable aliases.

## Candidate policy

`build_regulatory_candidates.py` creates a separate hypothesis table with two tiers.
Supported edges require confirmed direct signed evidence or signed perturbation plus
independent binding, and a passing species/sign calibration gate. Exploratory edges may use putative-direct signed evidence,
perturbation-only evidence, or conservative orthology transfer. Conflicting signs remain
excluded from every graph.

`build_perturbation_evidence.py` normalizes gain- and loss-of-function observations,
aggregates experiment-level calls, and stores accepted and conflicting consensus records
without changing `interactions`. Single-experiment perturbation-only calls are rejected;
novel evidence requires independent binding or at least two agreeing experiments.
`calibrate_perturbation_signs.py` evaluates each species/sign class against independently
curated `measured` edges. Literature-derived direction markers are excluded from consensus
generation to prevent self-validation. Only classes passing precision, class-base-rate
lift, sample-size, and Wilson-bound gates can produce supported candidates.

The observed feedback graph remains the default. API, UI, and skill users must explicitly
request `include_candidates` to analyze the evidence-completed graph. Candidate edges are
visually disclosed and receive a lower evidence score.

Exploratory completion additionally requires `include_exploratory` and ordinarily uses
the explicit 0.40 confidence floor. `rank_cycle_closing_candidates.py` records which
candidate edges close a directed return path, how many feedback genes they could add,
and whether they could merge existing cores. This impact score prioritizes validation;
it is not evidence for the edge.

Candidate-dependent core stability can be estimated with deterministic Monte Carlo
sampling. `probabilistic_samples` reports the fraction of sampled graphs in which each
gene remains inside a feedback core.

Reviewed protein activity, protein degradation, complex formation, and
post-transcriptional edges live in `regulatory_layer_edges`. They enter feedback analysis
only with `include_multilayer`; their mechanism remains attached to each edge.
The current rebuild separates 50 mapped, deduplicated SIGNOR post-transcriptional edges
from the ordinary transcriptional evidence layer; these add five human feedback genes.

## Reproduction

From a fresh clone:

```bash
make bootstrap
```

The relevant individual stages are:

```bash
make external-regulation
make evidence-expansion
make qualify-evidence
```

Qualification reports source mapping, novel-pair yield, sign agreement and conflicts,
evidence-layer counts, and observed-versus-completed feedback-core gain. The AGRIS report
uses a copied database for an ablation, so the release database is not mutated.

## Interpretation boundary

Occupancy does not establish regulatory sign, perturbation response does not establish
direct binding, and a structurally closed feedback loop does not establish oscillation or
state control. Completion is a ranked hypothesis layer intended to identify experiments,
not a replacement for observed network evidence.
