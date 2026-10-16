# Perturbation-derived signed feedback

GRN Atlas now converts context-specific TF perturbation observations into a versioned,
conflict-aware candidate evidence layer. It does not modify the observed interaction graph.

## Pipeline

1. Normalize gain-of-function and loss-of-function experiments into an activation score.
2. Aggregate observations by TF, target, and independent experiment.
3. Retain sign conflicts for audit and reject weak or unreplicated perturbation-only calls.
4. Join accepted signs to independent direct-binding evidence.
5. Calibrate each species and predicted-sign class against curated measured edges.
6. Admit only passing binding-plus-perturbation classes to the supported tier; keep all
   other qualified calls exploratory.

Literature-derived direction markers are excluded from consensus generation. Ordinary
coexpression is retained as biological context and is never used to assign a sign.

## October 2026 evaluation

The input contained 1,789,835 non-literature TF-target perturbation pairs. Consensus
qualification accepted 91,066 pairs, including 13,874 with independent binding and
77,192 supported by at least two experiments. It retained 104,817 conflicting pairs and
rejected 1,593,952 weak or unreplicated calls.

Calibration covered 4,372 consensus calls overlapping independently curated signed edges.
Overall agreement was 55.2%, below the 84.9% species-majority baseline. Human activation
was the only class to pass the release gate: 87.7% precision across 2,301 cases, compared
with an 85.0% class base rate. Human repression and both mouse classes remain exploratory;
plant classes lack sufficient independent calibration overlap.

Source ablation attributes 55 additional supported human feedback genes and 462 feedback
edges to the gated perturbation consensus. Exploratory analysis adds 229 human feedback
genes and 5,416 feedback edges, 70 mouse genes and 417 edges, and one Arabidopsis gene and
three edges. These are structural hypotheses, not demonstrated dynamical systems.

A logistic sign-model experiment combined perturbation score, effect magnitude, consistency,
experiment and dataset counts, and direct-binding support. TF-grouped cross-validation reached
0.528 balanced accuracy and 0.536 ROC AUC; repression precision was 0.164. It failed the
predeclared deployment gate, so the pipeline emits no model-inferred signs. This negative result
prevents a larger but misleading network from being presented as regulatory direction.

Machine-readable reports:

- `docs/benchmarks/perturbation-sign-calibration.json`
- `docs/benchmarks/perturbation-feedback-ablation.json`
- `docs/benchmarks/inferred-sign-model.json`
- `docs/benchmarks/perturbation-release-gates.json`
- `docs/benchmarks/feedback-evidence-tiers.json`

Reproduce the derived layer with:

```bash
make perturbation-evidence
make qualify-evidence
venv/bin/python backend/scripts/benchmark_perturbation_feedback.py
```
