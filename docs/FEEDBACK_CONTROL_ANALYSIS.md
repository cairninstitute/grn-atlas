# Species-wide feedback and control analysis

GRN Atlas can scan a species-level signed regulatory network for candidate feedback
structures and structural intervention points. The implementation deliberately
separates what graph topology establishes from biological dynamics that require
kinetic or perturbation evidence.

## Analysis model

The analysis uses only activation or repression edges whose sign evidence is
`measured` or `perturbation` by default. It then:

1. Computes all strongly connected components (feedback cores) with igraph.
2. Exhaustively detects signed self-regulation and reciprocal pairs.
3. Searches for representative longer circuits with explicit length, state, and
   result limits.
4. Classifies circuits by net sign and recognizable structure, including positive
   and negative autoregulation, mutual activation, mutual repression, and
   three-repressor loops.
5. Computes an exact minimum feedback vertex set for small cores and a bounded,
   deterministic greedy approximation for larger cores.

Feedback cores are exhaustive for the filtered graph. Longer circuit lists are not:
every response includes truncation and search-budget fields. A feedback vertex set
is a structural set of nodes whose removal breaks detected cycles; it does not
identify perturbation direction or prove control of a biological state.

## API

Run or retrieve an analysis with:

```text
POST /api/v1/network/feedback-control
GET  /api/v1/network/feedback-control/{species}/latest
```

The POST body accepts `species`, `min_confidence`, `evidence_tiers`,
`max_loop_length`, `max_cores`, `max_circuits`, `circuits_per_core`,
`max_search_states`, `max_controllers`, and `refresh`.

The Advanced > Feedback view presents species-level summary counts, ranked feedback
cores, exact or approximate controller candidates, representative signed circuits,
and all truncation caveats. Edge color communicates activation or repression; it
does not imply that the candidate circuit has demonstrated switching or oscillation.

## Storage

Results are cached in `backend/data/feedback_analysis.sqlite3`, a derived sidecar
that is not part of the source atlas database. The cache key includes the algorithm
version, normalized parameters, and a hash of the filtered graph. Normalized tables
store runs, cores, core genes, circuits, and circuit edges, while JSON snapshots
preserve the complete API response for fast retrieval and reproducibility.

Keeping derived analyses outside `grn.sqlite3` avoids schema coupling and allows the
sidecar to be deleted and regenerated. The API describes this as a versioned
sidecar and does not expose its filesystem location.

## Scaling

The graph loader streams SQLite rows in batches into compact igraph attributes.
Full edge provenance is fetched only for the bounded set of circuits returned to
the user. SCC discovery is linear in nodes plus edges. Cycle enumeration and large
core controller search are explicitly bounded because exhaustive simple-cycle
enumeration is exponential.

The committed benchmark creates 50,000-node synthetic networks with a fixed
500-node feedback core and progressively larger acyclic backgrounds. This measures
100-fold edge-volume growth without pretending that a 2.5-million-edge single SCC
is equivalent to ordinary database growth.

| Scale | Signed edges | Analysis time | Peak RSS |
| ---: | ---: | ---: | ---: |
| 1x | 25,000 | 0.141 s | 113.1 MiB |
| 10x | 250,000 | 0.550 s | 194.4 MiB |
| 100x | 2,500,000 | 4.943 s | 485.9 MiB |

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
