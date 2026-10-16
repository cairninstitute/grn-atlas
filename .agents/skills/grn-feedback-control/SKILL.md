---
name: grn-feedback-control
description: "Discover biological control systems, complete feedback-capable backbones, linked groups of feedback cores, signed regulatory loops, and candidate structural controller genes across a species GRN. Use for questions about oscillators, positive or negative feedback, toggle switches, repressilators, control loops, or feedback-vertex intervention points."
compatibility: Requires the GRN Atlas backend virtualenv or a running GRN Atlas server.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
venv/bin/python .agents/skills/grn-feedback-control/scripts/run.py --species arabidopsis
venv/bin/python .agents/skills/grn-feedback-control/scripts/run.py --species human --min-confidence 0.7 --max-loop-length 5
```

### Parameters

- `--species` — required species name.
- `--min-confidence` — minimum edge confidence; default `0.5`.
- `--evidence-tiers` — comma-separated `measured,perturbation` selection.
- `--max-loop-length` — longest representative circuit; default `6`, maximum `10`.
- `--max-cores` — maximum feedback cores returned.
- `--max-circuits` — total representative-circuit limit.
- `--circuits-per-core` — representative-circuit limit for one core.
- `--max-search-states` — hard search-work budget per core.
- `--max-controllers` — control candidates retained per core.
- `--max-systems` — maximum biological control-system hypotheses returned.
- `--max-system-genes` — largest annotation-defined system considered.
- `--exact-cycle-max-nodes` — largest core eligible for an exhaustive cycle catalog.
- `--exact-cycle-max-edges` — edge ceiling for exhaustive cycle cataloging.
- `--exact-cycle-limit` — safety ceiling; reaching it changes the catalog status to bounded.
- `--cycle-cover-max-edges` — largest core for which edge-covering witness cycles are materialized.
- `--max-bridge-hops` — longest signed path used to connect separate feedback cores.
- `--max-macro-circuits` — maximum cross-core macro-feedback witnesses returned.
- `--max-macro-search-edges` — search ceiling for newly admitted condensation edges.
- `--include-candidates` — opt into conflict-free evidence-completed hypotheses; observed signed edges remain the default.
- `--include-exploratory` — additionally include explicitly labeled putative-direct, perturbation-only, and conserved-orthology hypotheses.
- `--include-multilayer` — include reviewed protein-activity, degradation, complex, and post-transcriptional edges.
- `--probabilistic-samples` — estimate candidate-dependent core membership over up to 200 deterministic Monte Carlo samples.
- `--topology-only` — skip annotation and context synthesis for topology benchmarks.
- `--refresh` — recompute and replace an identical cached run.
- `--http URL` — optional running backend URL.

### Output interpretation

- `systems` combines signed loops with pathway/GO enrichment and available cis, perturbation, and tissue-coexpression support.
- Candidate mode can add an edge only from confirmed direct signed evidence or from independent binding plus signed perturbation evidence. It never silently changes the observed network.
- Supported cross-species candidates additionally require a passing source-held-out species/sign/mapping calibration class and independent recipient binding or cis evidence.
- Unvalidated nonconflicting orthology or reciprocal-unique-synteny projections appear only in exploratory mode and preserve their donor provenance.
- Perturbation signs are aggregated across experiments with gain/loss direction normalization. Conflicting calls are retained for audit but excluded from every graph.
- Binding-plus-perturbation signs enter the supported tier only when that species/sign class passes held-out precision, lift, sample-size, and confidence-bound gates. Failed classes remain exploratory.
- Ordinary expression correlation is context only and never determines activation or repression.
- Exploratory mode is a separate opt-in tier and never changes observed or supported-candidate results.
- Candidate-impact ranks identify edges that would close cycles or merge cores; impact is a validation priority, not evidence that the edge exists.
- Probabilistic membership reports stability under candidate uncertainty rather than treating every candidate as certain.
- Multilayer mode keeps non-transcriptional regulation explicitly labeled instead of recasting it as transcription.
- `annotation_supported` systems have a recognizable biological annotation; `de_novo_topology` systems are unlabeled circuit-overlap hypotheses.
- Architecture labels distinguish oscillator scaffolds, oscillator candidates, toggle switches, reinforcing switches, mixed feedback, and negative-feedback controllers.
- `partial_architecture` means that a relevant loop is present but the filtered atlas does not contain every regulatory arm needed for the proposed system behavior.
- `feedback_cores` are strongly connected signed regions and are exhaustively identified for the filtered graph.
- Every internal edge of a returned feedback core is indexed as cycle-capable. The complete backbone is available through the core-backbone endpoint and Feedback view.
- Small cores have exhaustive, all-length simple-cycle catalogs. Large cores expose resumable filtered enumeration and never imply that representative cycles are exhaustive.
- `cycle_cover` is a compact set of short witness cycles selected to cover internal feedback edges; it is not a mathematical minimum-cycle basis.
- `core_relationships` are shortest measured/perturbation signed paths between distinct cores through acyclic bridge genes. `core_groups` are weakly connected assemblies of those relationships.
- `macro_circuits` compare the observed SCC condensation DAG with the selected augmented evidence layer. They report shortest gene-level witnesses where newly admitted edges join at least two observed feedback cores into one larger core.
- A macro-circuit preserves its observed parent-core identities, net sign, evidence bottleneck, introduced closing edges, and added feedback-capable genes. It does not imply shared tissue or timing.
- Self-loops and reciprocal loops are exhaustively detected within returned cores.
- The legacy `circuits` field remains a bounded representative ranking. Use `cycle_catalog`, the cycle query endpoint, and its cursor/completion fields for exhaustive work.
- Positive-loop polarity suggests switch or memory behavior; negative-loop polarity suggests homeostasis, adaptation, or oscillation. These are hypotheses, not demonstrated dynamics.
- A feedback vertex set identifies structural intervention points. It does not establish perturbation direction or guarantee attractor control.
- Exact controller sets are used only for small cores. Large cores use a bounded greedy approximation and report whether all detected feedback was broken.

### Verification boundary

- The current verification report is `docs/FEEDBACK_CONTROL_VERIFICATION.md`; machine-readable details are in `docs/benchmarks/feedback-control-verification.json`.
- Small-graph feedback cores, cycles through length 6, polarity, and exact controller sets are checked against independent NetworkX or brute-force truth.
- Known-circuit recovery is measured only when every required signed edge exists in the filtered atlas.
- Circuit scores are monotonic heuristic rankings, not calibrated probabilities.
- Perturbation calibration is class-specific. A passing human activation class does not validate human repression or transfer to another species.
- System scores rank evidence coherence; they are not probabilities that the proposed dynamics occur in vivo.
- Missing observed arms may appear in candidate mode only when the normalized evidence layers satisfy the completion policy; absence remains explicit.

### Routing notes

- Use this skill for species-wide feedback discovery or control-loop questions.
- Use `grn-network-patterns` for feed-forward loops and bi-fans without feedback-control analysis.
- Follow with `grn-dynamics` for qualitative behavior of one selected, fully signed small circuit.
- Follow with evidence or multiome audits before presenting a circuit as a biological mechanism.
