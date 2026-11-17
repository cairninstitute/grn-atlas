# GRN Atlas — Population-Level Network Validation
Statistical validation across all regulatory edges, not just gold-standard spot-checks.
Each test uses an orthogonal data type to assess whether the inferred network
captures real biological signal.

## Summary
| Species | Edges | GO genes | Coherence (σ) | Multi-ev. z | Motif enrichment |
|---------|------:|--------:|-------------:|----------:|----------------:|
| arabidopsis | 2,022,227 | 17,349 | 22.21 | 0.9 | — |
| human | 1,162,591 | 2,041 | 5.35 | 0.46 | — |
| tomato | 393,741 | 12,939 | 34.45 | 0.87 | 33.01x |
| mouse | 339,900 | 0 | — | 0 | — |
| petunia | 236,745 | 11,667 | 31.33 | 2.77 | 29.9x |
| rice | 54,421 | 0 | — | 0 | 19.95x |
| potato | 11,409 | 0 | — | 0 | 2.27x |
| pepper | 2,212 | 0 | — | 0 | 24.42x |

## Arabidopsis

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 727
- **Mean real coherence:** 0.19411
- **Mean random coherence:** 0.16971
- **Enrichment:** 1.14×
- **Fraction of TFs above random:** 0.696

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0.18601
- **Permuted mean ± std:** 0.16196 ± 0.00108
- **Effect size:** 22.21 σ
- **p-value:** 0.0099

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=1351): mean overlap = 0.21848
- **Multi-source** (n=1722): mean overlap = 0.22835
- **Ratio:** 1.045×
- **Mann-Whitney z:** 0.9

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 0.7%
- **Random pairs coexpressed:** 0.7%
- **Rate ratio:** 1.05×
- **Mean importance (real):** 0.05676
- **Mean importance (random):** 0.05694

### Test 5 — Motif Enrichment in Inferred Targets
For TFs with known binding motifs, check whether Arabidopsis orthologs of
inferred targets have TF motif hits in promoters vs. non-targets.

- **TFs tested:** 0
- no TFs with both motifs and inferred targets


## Human

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 1828
- **Mean real coherence:** 0.06552
- **Mean random coherence:** 0.05466
- **Enrichment:** 1.2×
- **Fraction of TFs above random:** 0.858

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0.06196
- **Permuted mean ± std:** 0.05215 ± 0.00183
- **Effect size:** 5.35 σ
- **p-value:** 0.0099

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=362): mean overlap = 0.08464
- **Multi-source** (n=1439): mean overlap = 0.091
- **Ratio:** 1.075×
- **Mann-Whitney z:** 0.46

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


## Tomato

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 737
- **Mean real coherence:** 0.12674
- **Mean random coherence:** 0.10823
- **Enrichment:** 1.17×
- **Fraction of TFs above random:** 0.826

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0.12828
- **Permuted mean ± std:** 0.10914 ± 0.00056
- **Effect size:** 34.45 σ
- **p-value:** 0.0099

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=1252): mean overlap = 0.14293
- **Multi-source** (n=1439): mean overlap = 0.14056
- **Ratio:** 0.983×
- **Mann-Whitney z:** 0.87

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 0.8%
- **Random pairs coexpressed:** 0.6%
- **Rate ratio:** 1.33×
- **Mean importance (real):** 0.07358
- **Mean importance (random):** 0.06564

### Test 5 — Motif Enrichment in Inferred Targets
For TFs with known binding motifs, check whether Arabidopsis orthologs of
inferred targets have TF motif hits in promoters vs. non-targets.

- **TFs tested:** 442
- **Target motif rate:** 31.8%
- **Non-target motif rate:** 0.6%
- **Mean enrichment:** 33.01×
- **Median enrichment:** 25.13×
- **Fraction of TFs enriched:** 1.0


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


## Petunia

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 610
- **Mean real coherence:** 0.12619
- **Mean random coherence:** 0.10787
- **Enrichment:** 1.17×
- **Fraction of TFs above random:** 0.834

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0.12687
- **Permuted mean ± std:** 0.10849 ± 0.00059
- **Effect size:** 31.33 σ
- **p-value:** 0.0099

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=1604): mean overlap = 0.14293
- **Multi-source** (n=1683): mean overlap = 0.15027
- **Ratio:** 1.051×
- **Mann-Whitney z:** 2.77

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 0.9%
- **Random pairs coexpressed:** 0.6%
- **Rate ratio:** 1.51×
- **Mean importance (real):** 0.06215
- **Mean importance (random):** 0.05311

### Test 5 — Motif Enrichment in Inferred Targets
For TFs with known binding motifs, check whether Arabidopsis orthologs of
inferred targets have TF motif hits in promoters vs. non-targets.

- **TFs tested:** 403
- **Target motif rate:** 33.6%
- **Non-target motif rate:** 0.6%
- **Mean enrichment:** 29.9×
- **Median enrichment:** 23.6×
- **Fraction of TFs enriched:** 1.0


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

- **TFs tested:** 218
- **Target motif rate:** 42.5%
- **Non-target motif rate:** 0.6%
- **Mean enrichment:** 19.95×
- **Median enrichment:** 14.75×
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

- **TFs tested:** 167
- **Target motif rate:** 4.9%
- **Non-target motif rate:** 0.9%
- **Mean enrichment:** 2.27×
- **Median enrichment:** 1.93×
- **Fraction of TFs enriched:** 0.684


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
- **Mean enrichment:** 24.42×
- **Median enrichment:** 28.22×
- **Fraction of TFs enriched:** 1.0


---
*Generated by `validate_network_statistics.py`*
