# Cross-species regulatory edge and sign transfer

GRN Atlas projects signed donor interactions and direct-signed evidence through explicit
one-to-one orthology and reciprocal-unique synteny. It also emits separately labeled,
penalized hypotheses for syntenic families with at most two genes on either side. Transfers
are stored as evidence candidates and never modify the observed interaction graph.

## Evidence policy

Edge existence and sign receive separate ranking scores. Recipient binding, cis support,
and tissue coexpression are retained separately; coexpression never assigns a sign.
Legacy `Inferred:*` interactions cannot serve as donors, preventing recursive transfer.
Calibrated perturbation consensus may be a supported donor; uncalibrated perturbation
consensus remains exploratory. Bounded-paralog projections are always exploratory and are
excluded from transfer calibration.
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

The expanded build normalized 102,106 accepted directional mappings, added 83,338
penalized bounded-paralog mappings, canonicalized 3,138 mappings that crossed duplicate
identifier namespaces, and produced 35,027 signed projections. Of these, 31,050 are
unvalidated, 1,864 contain a donor-sign conflict, and 2,113 meet edge-level qualification
rules before class calibration.

After excluding shared sources/publications, exploratory-only donors, conflicts, and paralog
hypotheses, human one-to-one activation and repression transfer retained 391 and 167 test
cases. Precision was 93.9% and 86.2%, respectively, and both classes passed the preregistered
gates. Mouse retained only 42 independent cases after the stricter exclusions, below the
50-case gate. A total of 187 human edges (150 activation, 37 repression) also had independent
recipient binding or cis support and entered the supported tier. Plant classes still have
zero independent recipient truth cases, so every plant transfer remains exploratory.

Plant transfer hypotheses increased from 869 to 13,459: pepper 218, petunia 3,586, potato
3,047, rice 295, and tomato 6,313. The reviewed Expression Atlas manifest now adds two rice
TF perturbations, including 109 significant OsbZIP58 target responses. These responses remain
exploratory and do not become transfer donors without replication and species/sign calibration.

In the feedback ablation, supported transfer adds 32 nonredundant human graph edges and 19
feedback edges, but no new feedback core or macro-circuit. Exploratory transfer adds two
potato feedback cores, one tomato core and three tomato macro-circuits, and five petunia
macro-circuits. Petunia's core count decreases by one because added edges merge previously
separate strongly connected components. These structural changes are hypotheses rather than
known-circuit recovery and are reported separately from the supported result.

## Interpretation boundary

Conserved TF identity, target orthology, and promoter synteny do not prove conservation of
a regulatory edge or its sign. Transferred edges are hypotheses until recipient-species
binding and perturbation evidence establish the relationship in the relevant context.
