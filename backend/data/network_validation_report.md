# GRN Atlas — Population-Level Network Validation
Statistical validation across all regulatory edges, not just gold-standard spot-checks.
Each test uses an orthogonal data type to assess whether the inferred network
captures real biological signal.

## Summary
| Species | Edges | GO genes | Coherence (σ) | Multi-ev. z | Motif enrichment |
|---------|------:|--------:|-------------:|----------:|----------------:|
| arabidopsis | 919,449 | 17,349 | 3.48 | 2.67 | — |
| tomato | 248,288 | 12,939 | 47.37 | 2.21 | 38.2x |
| petunia | 236,727 | 11,667 | 28.48 | 4.34 | 30.65x |
| human | 17,946 | 2,041 | 7.07 | -2.97 | — |
| mouse | 17,692 | 0 | — | 0 | — |
| rice | 16,933 | 0 | — | 0 | 25.46x |
| potato | 11,409 | 0 | — | 0 | 3.85x |
| pepper | 2,212 | 0 | — | 0 | 17.84x |

## Arabidopsis

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 584
- **Mean real coherence:** 0.17345
- **Mean random coherence:** 0.16991
- **Enrichment:** 1.02×
- **Fraction of TFs above random:** 0.476

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0.17549
- **Permuted mean ± std:** 0.17124 ± 0.00122
- **Effect size:** 3.48 σ
- **p-value:** 0.0099

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=1233): mean overlap = 0.18271
- **Multi-source** (n=1949): mean overlap = 0.20314
- **Ratio:** 1.112×
- **Mann-Whitney z:** 2.67

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 0.7%
- **Random pairs coexpressed:** 0.7%
- **Rate ratio:** 0.98×
- **Mean importance (real):** 0.05455
- **Mean importance (random):** 0.04978

### Test 5 — Motif Enrichment in Inferred Targets
For TFs with known binding motifs, check whether Arabidopsis orthologs of
inferred targets have TF motif hits in promoters vs. non-targets.

- **TFs tested:** 0
- no TFs with both motifs and inferred targets


## Tomato

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 730
- **Mean real coherence:** 0.12984
- **Mean random coherence:** 0.10809
- **Enrichment:** 1.2×
- **Fraction of TFs above random:** 0.89

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0.12966
- **Permuted mean ± std:** 0.10922 ± 0.00043
- **Effect size:** 47.37 σ
- **p-value:** 0.0099

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=1315): mean overlap = 0.14026
- **Multi-source** (n=1558): mean overlap = 0.14731
- **Ratio:** 1.05×
- **Mann-Whitney z:** 2.21

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 0.7%
- **Random pairs coexpressed:** 0.7%
- **Rate ratio:** 1.02×
- **Mean importance (real):** 0.06422
- **Mean importance (random):** 0.05342

### Test 5 — Motif Enrichment in Inferred Targets
For TFs with known binding motifs, check whether Arabidopsis orthologs of
inferred targets have TF motif hits in promoters vs. non-targets.

- **TFs tested:** 442
- **Target motif rate:** 40.3%
- **Non-target motif rate:** 0.6%
- **Mean enrichment:** 38.2×
- **Median enrichment:** 28.45×
- **Fraction of TFs enriched:** 1.0


## Petunia

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 610
- **Mean real coherence:** 0.12587
- **Mean random coherence:** 0.10812
- **Enrichment:** 1.16×
- **Fraction of TFs above random:** 0.826

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0.1239
- **Permuted mean ± std:** 0.10778 ± 0.00057
- **Effect size:** 28.48 σ
- **p-value:** 0.0099

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=1556): mean overlap = 0.13558
- **Multi-source** (n=1655): mean overlap = 0.148
- **Ratio:** 1.092×
- **Mann-Whitney z:** 4.34

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 0.9%
- **Random pairs coexpressed:** 0.8%
- **Rate ratio:** 1.13×
- **Mean importance (real):** 0.06985
- **Mean importance (random):** 0.06424

### Test 5 — Motif Enrichment in Inferred Targets
For TFs with known binding motifs, check whether Arabidopsis orthologs of
inferred targets have TF motif hits in promoters vs. non-targets.

- **TFs tested:** 403
- **Target motif rate:** 33.6%
- **Non-target motif rate:** 0.7%
- **Mean enrichment:** 30.65×
- **Median enrichment:** 25.26×
- **Fraction of TFs enriched:** 1.0


## Human

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 191
- **Mean real coherence:** 0.06084
- **Mean random coherence:** 0.0546
- **Enrichment:** 1.11×
- **Fraction of TFs above random:** 0.503

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0.06055
- **Permuted mean ± std:** 0.05067 ± 0.0014
- **Effect size:** 7.07 σ
- **p-value:** 0.0099

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=809): mean overlap = 0.07787
- **Multi-source** (n=2000): mean overlap = 0.07005
- **Ratio:** 0.9×
- **Mann-Whitney z:** -2.97

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 0.0%
- **Random pairs coexpressed:** 0.0%
- **Rate ratio:** None×
- **Mean importance (real):** 0
- **Mean importance (random):** 0

### Test 5 — Motif Enrichment in Inferred Targets
For TFs with known binding motifs, check whether Arabidopsis orthologs of
inferred targets have TF motif hits in promoters vs. non-targets.

- **TFs tested:** 0
- no TFs with both motifs and inferred targets


## Mouse

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 0
- **Mean real coherence:** 0
- **Mean random coherence:** 0
- **Enrichment:** None×
- **Fraction of TFs above random:** 0

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0
- **Permuted mean ± std:** 0.0 ± 0.0
- **Effect size:** 0.0 σ
- **p-value:** 1.0

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=0): mean overlap = 0
- **Multi-source** (n=0): mean overlap = 0
- **Ratio:** None×
- **Mann-Whitney z:** 0

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 0.0%
- **Random pairs coexpressed:** 0.0%
- **Rate ratio:** None×
- **Mean importance (real):** 0
- **Mean importance (random):** 0

### Test 5 — Motif Enrichment in Inferred Targets
For TFs with known binding motifs, check whether Arabidopsis orthologs of
inferred targets have TF motif hits in promoters vs. non-targets.

- **TFs tested:** 0
- no TFs with both motifs and inferred targets


## Rice

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 0
- **Mean real coherence:** 0
- **Mean random coherence:** 0
- **Enrichment:** None×
- **Fraction of TFs above random:** 0

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0
- **Permuted mean ± std:** 0.0 ± 0.0
- **Effect size:** 0.0 σ
- **p-value:** 1.0

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=0): mean overlap = 0
- **Multi-source** (n=0): mean overlap = 0
- **Ratio:** None×
- **Mann-Whitney z:** 0

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 0.0%
- **Random pairs coexpressed:** 0.0%
- **Rate ratio:** None×
- **Mean importance (real):** 0
- **Mean importance (random):** 0

### Test 5 — Motif Enrichment in Inferred Targets
For TFs with known binding motifs, check whether Arabidopsis orthologs of
inferred targets have TF motif hits in promoters vs. non-targets.

- **TFs tested:** 215
- **Target motif rate:** 59.2%
- **Non-target motif rate:** 0.7%
- **Mean enrichment:** 25.46×
- **Median enrichment:** 18.9×
- **Fraction of TFs enriched:** 1.0


## Potato

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 0
- **Mean real coherence:** 0
- **Mean random coherence:** 0
- **Enrichment:** None×
- **Fraction of TFs above random:** 0

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0
- **Permuted mean ± std:** 0.0 ± 0.0
- **Effect size:** 0.0 σ
- **p-value:** 1.0

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=0): mean overlap = 0
- **Multi-source** (n=0): mean overlap = 0
- **Ratio:** None×
- **Mann-Whitney z:** 0

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 0.0%
- **Random pairs coexpressed:** 0.0%
- **Rate ratio:** None×
- **Mean importance (real):** 0
- **Mean importance (random):** 0

### Test 5 — Motif Enrichment in Inferred Targets
For TFs with known binding motifs, check whether Arabidopsis orthologs of
inferred targets have TF motif hits in promoters vs. non-targets.

- **TFs tested:** 168
- **Target motif rate:** 5.0%
- **Non-target motif rate:** 0.4%
- **Mean enrichment:** 3.85×
- **Median enrichment:** 2.78×
- **Fraction of TFs enriched:** 0.964


## Pepper

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 0
- **Mean real coherence:** 0
- **Mean random coherence:** 0
- **Enrichment:** None×
- **Fraction of TFs above random:** 0

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0
- **Permuted mean ± std:** 0.0 ± 0.0
- **Effect size:** 0.0 σ
- **p-value:** 1.0

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=0): mean overlap = 0
- **Multi-source** (n=0): mean overlap = 0
- **Ratio:** None×
- **Mann-Whitney z:** 0

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 0.0%
- **Random pairs coexpressed:** 0.0%
- **Rate ratio:** None×
- **Mean importance (real):** 0
- **Mean importance (random):** 0

### Test 5 — Motif Enrichment in Inferred Targets
For TFs with known binding motifs, check whether Arabidopsis orthologs of
inferred targets have TF motif hits in promoters vs. non-targets.

- **TFs tested:** 45
- **Target motif rate:** 70.0%
- **Non-target motif rate:** 0.5%
- **Mean enrichment:** 17.84×
- **Median enrichment:** 16.48×
- **Fraction of TFs enriched:** 1.0


---
*Generated by `validate_network_statistics.py`*
