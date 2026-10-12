# Feedback-control verification report

**Status: PASS**

## Acceptance gates

| Gate | Result |
| --- | --- |
| core recall complete | PASS |
| core precision complete | PASS |
| cycle recall complete | PASS |
| cycle precision complete | PASS |
| polarity exact | PASS |
| exact fvs optimal | PASS |
| exact fvs acyclic | PASS |
| greedy fvs acyclic | PASS |
| covered biological circuits recovered | PASS |
| pathological cases bounded | PASS |
| score behavior consistent | PASS |
| persistence consistent | PASS |

## Independent structural truth

NetworkX exhaustive enumeration was used on 35 small signed graphs. Production-scale cycle output remains explicitly bounded.

| Metric | Result |
| --- | ---: |
| Feedback-core recall | 100.0% |
| Feedback-core precision | 100.0% |
| Signed-cycle recall through length 6 | 100.0% |
| Signed-cycle precision through length 6 | 100.0% |
| Cycle-polarity accuracy | 100.0% |
| Exact FVS optimality | 100.0% |
| Greedy FVS mean size / optimum | 1.005x |
| Greedy FVS worst size / optimum | 1.25x |

## Biological recovery

| Reference circuit | Atlas coverage | Core | Signed circuit | Attribution |
| --- | --- | --- | --- | --- |
| human NF-kB inhibitor feedback | complete | yes | yes | recovered |
| human E2F-MYC mutual activation | complete | yes | yes | recovered |
| human E2F-RB negative feedback | complete | yes | yes | recovered |
| mouse p53-Mdm2 negative feedback | complete | yes | yes | recovered |
| Arabidopsis LHY-LUX/PCL1 negative feedback | complete | yes | yes | recovered |
| Arabidopsis CCA1-LUX/PCL1 negative feedback | complete | yes | yes | recovered |

### Arabidopsis clock coverage

The atlas supports 1 of 3 required module-level arms. A closed three-module loop is not recoverable from the current signed edges alone.

- Supported: morning represses evening
- Missing: evening regulates daytime PRRs
- Missing: daytime PRRs repress morning

## Robustness

| Case | Nodes | Edges | Seconds | Truncation explicit |
| --- | ---: | ---: | ---: | --- |
| large-scc | 1,000 | 3,000 | 0.0238 | yes |
| many-small-sccs | 600 | 600 | 0.0113 | yes |
| dense-core | 30 | 870 | 0.0081 | yes |
| acyclic | 200 | 199 | 0.0010 | not needed |

## Scores and persistence

- Score ordering checks: PASS
- Score interpretation: heuristic ranking, not a calibrated probability
- Cache invalidation and normalized persistence: PASS

## Interpretation

- Circuit confidence scores are heuristic rankings, not calibrated probabilities.
- Complete small-graph recall does not make bounded large-graph cycle output exhaustive.
- Structural feedback does not establish switching, homeostasis, or oscillation dynamics.
