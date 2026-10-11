---
name: grn-differential-network
description: "Use when the user wants to compare regulatory wiring between two tissues or conditions — which edges are active/strong in one context but not the other. Good for prompts like 'which regulatory edges are active in corolla but not style?', 'how does the network rewire between root and shoot?', or 'differential network between these two tissues'. Returns edges gained in each tissue, strengthened/weakened edges, and the edge sign where known. Uses per-tissue TF-target coexpression as the activity proxy (not measured physical rewiring). Prefer this over grn-diff-regulation when the question is about EDGE rewiring rather than TF-activity shifts, and over grn-tissue-coexpression when comparing two contexts rather than listing one."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Needs per-tissue weights (`make db` runs compute_tissue_weights). Available for arabidopsis, tomato, petunia.
metadata:
  author: grn-atlas
  version: "1.0"
---

## grn-differential-network

Inputs:
- `--species` (arabidopsis / tomato / petunia — the species with tissue-resolved expression)
- `--tissue-a`, `--tissue-b` the two contexts to compare (invalid names return the available list)
- optional `--min-delta` (default 0.3), `--top` (default 40)

Output:
- `gained_in_<tissue_a>` / `gained_in_<tissue_b>` — edges active (|coexpr r|≥0.3) in one tissue only
- `strengthened_in_a` / `weakened_in_a` — edges active in both, ranked by coexpression delta
- counts + each edge's sign (measured/perturbation) where known

Honesty notes:
- This is a **coexpression-based activity contrast**, not measured physical rewiring.
- An edge counts as "active" in a tissue only if |coexpression r| ≥ 0.3 there.
- Signs are shown only when curated or experiment-derived; correlation is never a sign.
