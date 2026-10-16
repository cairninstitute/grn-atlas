# Cross-species regulatory edge and sign transfer

GRN Atlas projects signed donor interactions through explicit one-to-one orthology and
reciprocal-unique synteny. Transfers are stored as evidence candidates and never modify
the observed interaction graph.

## Evidence policy

Edge existence and sign receive separate ranking scores. Recipient binding, cis support,
and tissue coexpression are retained separately; coexpression never assigns a sign.
Legacy `Inferred:*` interactions cannot serve as donors, preventing recursive transfer.
Donor-sign conflicts are retained in the audit table and excluded from graph evidence.

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

The release build normalized 102,106 accepted directional mappings and produced 13,486
signed projections. It excluded 26 donor-sign conflicts and retained 13,460 projections
as exploratory. After inferred donors and shared-source/publication validation were removed,
no species/sign/mapping class had independent recipient truth cases, so no transfer was
promoted to the supported tier.

Exploratory transfer added 12,617 mouse graph edges, 342 feedback genes, 2,842 feedback
edges, and one feedback core. It also created two four-gene/four-edge potato cores. Petunia,
rice, and tomato gained edges but no additional feedback structure. Supported graphs and
known-circuit recovery were unchanged.

## Interpretation boundary

Conserved TF identity, target orthology, and promoter synteny do not prove conservation of
a regulatory edge or its sign. Transferred edges are hypotheses until recipient-species
binding and perturbation evidence establish the relationship in the relevant context.
