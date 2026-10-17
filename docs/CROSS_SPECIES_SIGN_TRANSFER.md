# Cross-species regulatory edge and sign transfer

GRN Atlas projects signed donor interactions through explicit one-to-one orthology and
reciprocal-unique synteny. Transfers are stored as evidence candidates and never modify
the observed interaction graph.

## Evidence policy

Edge existence and sign receive separate ranking scores. Recipient binding, cis support,
and tissue coexpression are retained separately; coexpression never assigns a sign.
Legacy `Inferred:*` interactions cannot serve as donors, preventing recursive transfer.
Donor-sign conflicts are retained in the audit table and excluded from graph evidence.
Duplicate identifier namespaces are resolved only when a same-symbol gene is uniquely
anchored by native measured evidence, or when at least ten such anchors establish a
90%-consistent species namespace. Ambiguous aliases remain unresolved.

A transfer enters the supported tier only when its species, sign, and mapping class passes
source- and publication-disjoint calibration and the individual edge has independent
recipient binding or cis evidence. All other nonconflicting projections remain exploratory.

## Reproduction

```bash
make cross-species-transfer
```

The normalized mappings and projection audit are stored in
`orthology_transfer_mappings` and `orthology_transfer_candidates`. Machine-readable
calibration, feedback ablation, and release-gate reports are under `docs/benchmarks/`.

## October 2026 evaluation

The release build normalized 102,106 accepted directional mappings, canonicalized 3,138
directional mappings that crossed duplicate identifier namespaces, and produced 16,089
signed projections. It excluded 26 donor-sign conflicts. Calibration excluded 3,093
recipient observations that reused a donor evidence source, leaving 1,087 independent
human/mouse cases.

All four explicit one-to-one mammalian transfer classes passed the preregistered gates.
Activation precision was 93.9% in human and 94.2% in mouse; repression precision was 85.8%
and 86.5%, respectively. The corresponding 95% Wilson lower bounds remained above each
recipient's sign baseline. Of the projected edges, 161 human edges (131 activation and 30
repression) also had independent recipient binding or cis support and entered the supported
tier. Mouse classes calibrate successfully, but individual mouse candidates currently lack
overlapping recipient binding/cis evidence and therefore remain exploratory. Plant synteny
classes still lack independent recipient truth cases and remain exploratory.

In the feedback ablation, supported transfer adds 26 nonredundant human graph edges and 17
feedback edges, but no new feedback core or macro-circuit. Exploratory transfer contributes
10,645 mouse graph edges and 3,049 feedback edges without creating a new mouse core; potato
still gains two small exploratory cores. These structural changes are hypotheses rather than
known-circuit recovery and are reported separately from the supported result.

## Interpretation boundary

Conserved TF identity, target orthology, and promoter synteny do not prove conservation of
a regulatory edge or its sign. Transferred edges are hypotheses until recipient-species
binding and perturbation evidence establish the relationship in the relevant context.
