# CloneLab validation fixtures

The first diagnostic-optimization tests use synthetic circular molecules whose restriction
sites and fragment lengths are fully inspectable in the test source. The molecules contain one
EcoRI reference cut and zero or one XhoI cut:

- `intended`: EcoRI/XhoI distances are 200 bp and 800 bp.
- `reverse`: EcoRI/XhoI distances are 400 bp and 600 bp.
- `empty`: EcoRI cuts once; XhoI does not cut.

Therefore EcoRI alone and XhoI alone cannot distinguish all three circular hypotheses, while the
EcoRI + XhoI double digest has signatures `[800, 200]`, `[600, 400]`, and `[1000]`.

These synthetic fixtures test optimizer truth without relying on its own output as an oracle.
Authenticated external plasmid fixtures and independent cross-tool output are added before the
reference-validation release gate described in the implementation plan.

`make clonelab-data` fetches the versioned NCBI pUC19 reference `L09137.2` and verifies its
2,686 bp sequence against the committed SHA-256 identity before use. The fetched GenBank file is
local data and is not committed. This authenticates molecular identity but does not by itself
constitute an independent restriction-engine comparison.
