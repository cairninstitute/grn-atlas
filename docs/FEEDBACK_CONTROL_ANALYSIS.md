# Biological feedback and control-system discovery

GRN Atlas can scan a species-level signed regulatory network for candidate feedback
structures and structural intervention points. The implementation deliberately
separates what graph topology establishes from biological dynamics that require
kinetic or perturbation evidence.

The workflow now has three layers. The structural layer finds signed cycles, strongly
connected feedback cores, complete cycle-capable backbones, and feedback-vertex
controller candidates. The inter-core layer finds short signed regulatory paths through
acyclic bridge genes and chains related cores into larger groups. The biological
discovery layer assembles those loops into interpretable systems using pathway and GO
enrichment, then scores available cis, perturbation, tissue-coexpression, and signed
cross-species conservation support.

## Biological systems

Each returned system reports:

- whether it was annotation-supported or discovered from overlapping circuits alone;
- a candidate architecture such as oscillator scaffold, oscillator, toggle switch,
  reinforcing switch, mixed feedback controller, or negative-feedback controller;
- the signed subgraph and representative loops supporting the classification;
- pathway/GO enrichment and contextual evidence counts;
- whether the architecture is closed or partial; and
- an explicit boundary separating structural evidence from demonstrated dynamics.

For Arabidopsis, the workflow identifies the Circadian rhythm system from Reactome
enrichment and the measured LHY-PCL1/LUX negative loop. It reports an incomplete
oscillator scaffold because the current signed atlas lacks the full evening-to-PRR
and PRR-to-morning regulatory arms. The engine does not silently add those edges.

## Analysis model

The analysis uses only activation or repression edges whose sign evidence is
`measured` or `perturbation` by default. An opt-in evidence-completed view may also
include conflict-free candidates supported by confirmed direct signed evidence, or
by independent binding plus signed perturbation evidence. Candidates remain separate
from the observed interaction table. The analysis then:

1. Computes all strongly connected components (feedback cores) with igraph.
2. Exhaustively detects signed self-regulation and reciprocal pairs.
3. Searches for representative longer circuits with explicit length, state, and
   result limits.
4. Classifies circuits by net sign and recognizable structure, including positive
   and negative autoregulation, mutual activation, mutual repression, and
   three-repressor loops.
5. Computes an exact minimum feedback vertex set for small cores and a bounded,
   deterministic greedy approximation for larger cores.

An additional exploratory view can include explicitly labeled putative-direct,
perturbation-only, and conservatively transferred orthology candidates. A separate
multilayer view can add reviewed protein-activity, degradation, complex, and
post-transcriptional regulation without relabeling those mechanisms as transcription.
Neither view changes the observed graph.

Candidate-impact ranking identifies edges that would close an existing directed return
path, add feedback-capable genes, or merge current cores. Optional deterministic Monte
Carlo sampling reports each gene's frequency of membership in a feedback core when
candidate edges are sampled according to evidence confidence.

Feedback cores are exhaustive for the filtered graph. Longer circuit lists are not:
every response includes truncation and search-budget fields. A feedback vertex set
is a structural set of nodes whose removal breaks detected cycles; it does not
identify perturbation direction or prove control of a biological state.

Every edge internal to a strongly connected core belongs to at least one directed
cycle, so the stored core backbone is a complete index of cycle-capable genes and
edges. Small cores receive an exhaustive all-length simple-cycle catalog. Large cores
receive a compact set of short witness cycles covering their internal edges, plus a
filtered cursor-based endpoint for resumable simple-cycle enumeration. Explicit cycle
enumeration remains potentially exponential; completion is reported rather than
assumed.

Distinct strongly connected cores cannot have regulatory paths in both directions or
they would be one core. Darwin therefore discovers directional relationships between
cores: direct signed regulation or short signed paths whose internal nodes are not in
another returned core. Weakly connected components of this core relationship graph
are returned as larger control assemblies. These groups establish regulatory chaining,
not synchronized dynamics.

## API

Run or retrieve an analysis with:

```text
POST /api/v1/network/feedback-control
GET  /api/v1/network/feedback-control/{species}/latest
GET  /api/v1/network/feedback-control/candidates/{species}
GET  /api/v1/network/feedback-control/runs/{run_id}/cores/{core_id}/backbone
GET  /api/v1/network/feedback-control/runs/{run_id}/cores/{core_id}/cycles
```

The POST body accepts `species`, `min_confidence`, `evidence_tiers`,
`max_loop_length`, `max_cores`, `max_circuits`, `circuits_per_core`,
`max_search_states`, `max_controllers`, `max_systems`, `max_system_genes`,
`exact_cycle_max_nodes`, `exact_cycle_max_edges`, `exact_cycle_limit`,
`cycle_cover_max_edges`, `max_bridge_hops`, `discover_systems`, and `refresh`.
Set `include_candidates` to compare the evidence-completed hypothesis graph with the
default observed graph. `include_exploratory`, `include_multilayer`, and
`probabilistic_samples` activate the separately disclosed extension layers.

The Feedback view presents a network-layer selector, ranked biological systems first, linked groups of cores,
then the underlying complete backbones, compact cycle covers, filtered cycle queries,
and exact or approximate controller candidates. Edge color communicates activation or repression;
it does not imply that a candidate system has demonstrated switching or oscillation.

## Storage

Results are cached in `backend/data/feedback_analysis.sqlite3`, a derived sidecar
that is not part of the source atlas database. The cache key includes the algorithm
version, normalized parameters, and a hash of the filtered graph. Normalized tables
store runs, cores, complete core edges, exact and compact cycle catalogs, inter-core
relationships, core groups, representative circuits, and circuit edges. JSON snapshots
preserve the summary response for fast retrieval and reproducibility.

Keeping derived analyses outside `grn.sqlite3` avoids schema coupling and allows the
sidecar to be deleted and regenerated. The API describes this as a versioned
sidecar and does not expose its filesystem location.

## Scaling

The graph loader streams SQLite rows in batches into compact igraph attributes.
Full provenance is fetched for edges inside returned feedback cores and their short
inter-core paths, but not for unrelated acyclic background edges. SCC discovery is
linear in nodes plus edges. Cycle enumeration and large-core controller search are
explicitly bounded because exhaustive simple-cycle enumeration is exponential.

The committed benchmark creates 50,000-node synthetic networks with a fixed
500-node feedback core and progressively larger acyclic backgrounds. This measures
100-fold edge-volume growth without pretending that a 2.5-million-edge single SCC
is equivalent to ordinary database growth.

## Evidence-tier benchmark

`backend/scripts/benchmark_feedback_evidence_tiers.py` compares all four graph views
and writes `docs/benchmarks/feedback-evidence-tiers.json`. In the October 2026 rebuild:

| Species | Observed genes | Supported genes | Exploratory genes | Multilayer genes |
| --- | ---: | ---: | ---: | ---: |
| Arabidopsis | 156 | 190 | 227 | 227 |
| Human | 288 | 895 | 895 | 900 |
| Mouse | 350 | 352 | 352 | 352 |
| Rice | 25 | 25 | 25 | 25 |

Arabidopsis has 75 individually cycle-closing candidate edges in the current candidate
pool. The count of cores can fall while feedback membership rises because added edges
merge previously separate strongly connected components. Conservative orthology
transfer admitted no edge in this rebuild; that zero is retained rather than relaxing
the evidence rule. Human multilayer mode adds reviewed SIGNOR post-transcriptional edges.

| Scale | Signed edges | Analysis time | Peak RSS |
| ---: | ---: | ---: | ---: |
| 1x | 25,000 | 0.359 s | 125.3 MiB |
| 10x | 250,000 | 1.312 s | 206.0 MiB |
| 100x | 2,500,000 | 11.159 s | 497.9 MiB |

Machine-readable results are in `docs/benchmarks/feedback-control-scale.csv` and
`docs/benchmarks/feedback-control-scale.json`. Reproduce them with:

```bash
venv/bin/python backend/scripts/benchmark_feedback_control.py \
  --json docs/benchmarks/feedback-control-scale.json \
  --csv docs/benchmarks/feedback-control-scale.csv
```

Runtime and memory depend on hardware and graph topology. An unusually large,
dense feedback core remains bounded and reports incomplete representative circuit
or controller results rather than running an unbounded exhaustive search.

The biological synthesis benchmark completed all eight atlas species. It returned
annotation-supported systems where pathway or GO coverage exists and de novo topology
modules where it does not. Potato currently has no signed edge passing the default
evidence filter, so no control system is reported. Results are in
`docs/benchmarks/control-system-discovery.json` and `.csv`; reproduce them with:

```bash
venv/bin/python backend/scripts/benchmark_control_systems.py
```

## Verification gate

Independent structural truth tests, known-circuit recovery, exact and approximate
controller comparisons, pathological graph checks, score behavior, and persistence
validation are documented in `docs/FEEDBACK_CONTROL_VERIFICATION.md`. Reproduce the
machine-readable verification artifacts with:

```bash
venv/bin/python backend/scripts/verify_feedback_control.py \
  --json docs/benchmarks/feedback-control-verification.json \
  --csv docs/benchmarks/feedback-control-biological-recovery.csv \
  --markdown docs/FEEDBACK_CONTROL_VERIFICATION.md
```

## Evidence boundary

Topology can prioritize plausible switches, amplifiers, homeostatic loops,
oscillator candidates, and intervention points. Establishing those behaviors needs
context-matched expression, temporal measurements, protein turnover or delay
parameters, and ideally targeted perturbation data. The feature reports hypotheses,
not dynamical proof.
