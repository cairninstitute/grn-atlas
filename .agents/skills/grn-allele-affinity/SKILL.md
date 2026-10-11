---
name: grn-allele-affinity
description: "Use when the user wants a quantitative, allele-specific estimate of how a single-base promoter variant changes TF binding for a gene — not just whether it overlaps a motif. Good for prompts like 'how much does this A>G at position X weaken WRKY binding?', 'does this SNP abolish the site or just dent it?', or 'which TF binding sites does this promoter variant strengthen vs weaken, and what would that do to expression?'. Reports per-site delta log-odds (ref vs alt), a weakens/strengthens/little-effect call, likely site loss, and — when the TF->gene regulatory sign is known — the predicted direction of the expression change. Prefer this over grn-variant-effect when the user wants magnitude and direction rather than overlap. Requires the motif PWM cache (backend/scripts/cache_motif_pwms.py); without it, it degrades to overlap-only."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv, then `make allele-pwms` to build the PWM cache.
metadata:
  author: grn-atlas
  version: "1.0"
---

## grn-allele-affinity

Rescores motif-supported promoter sites that overlap a variant using the JASPAR
log-odds matrix, substituting the alternate base at the variant's matrix column.

Inputs:
- `--gene-id` the atlas gene whose promoter the variant sits in
- `--position` genomic coordinate of the variant
- `--ref` / `--alt` single DNA bases (A/C/G/T)
- optional `--assembly`, `--window-type` (default `promoter`), `--top`

Output per overlapping site:
- `delta_lod` — change in log2 binding odds (alt − ref) at the variant column
- `call` — `weakens_binding` / `strengthens_binding` / `little_effect`
- `likely_site_loss` — alt score falls below background
- `predicted_target_effect` — expression direction, asserted ONLY when the TF→gene edge
  has a curated (measured) sign; otherwise `direction: unknown` with the coexpression
  correlation returned as weak context (never as a direction)

Honesty notes:
- `delta_lod` is a predicted effect, not a measured one.
- The reference base is assumed to match the site; genomic sequence is not re-verified.
- A direction is only predicted from a curated sign. Expression correlation was validated
  as an unreliable sign predictor (see backend/data/sign_validation_report.json), so it is
  not used to claim activation/repression.
- When the PWM is not cached for a motif, that site is returned as overlap-only
  (`scored: false`) rather than guessed.
