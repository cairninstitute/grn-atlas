---
name: grn-dynamics
description: "Use when the user wants to simulate the qualitative dynamics of a regulatory module — will it settle into a stable state (fixed point) or oscillate (cycle), and which genes end up ON/OFF after a perturbation. Good for prompts like 'simulate this network after knocking out TF X', 'does this module reach a steady state or oscillate?', or 'what stable state does this regulatory circuit fall into?'. Runs a Boolean/threshold attractor simulation on the SIGNED induced subnetwork of the provided genes; perturbed genes are clamped (knockout/overexpression). Prefer this over grn-perturbation (one-step propagation) and grn-cascade when the question is about steady states / attractors of a multi-gene circuit. Requires signed edges among the genes; it is a qualitative Boolean abstraction, not a kinetic simulation."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Works best on modules with signed edges (curated or perturbation-derived); run `make enrich`/`make knocktf` to densify signs.
metadata:
  author: grn-atlas
  version: "1.0"
---

## grn-dynamics

Inputs:
- `--genes` comma-separated gene ids/symbols defining the module to simulate (≥2)
- optional `--species`, `--perturb` (e.g. `TF1=0,TF2=1` to clamp knockout/overexpression),
  `--initial` (`on`/`off` default for unclamped nodes), `--max-steps` (default 50)

Output:
- `attractor` — `fixed_point` / `cycle` (with period) / `no_convergence`
- `final_state`, `genes_on_at_steady_state`, `genes_changed_from_initial`
- `n_signed_edges`, `n_unsigned_edges_excluded`, `signed_coverage` — how much of the module is signed

Honesty notes:
- A **qualitative Boolean threshold** model over SIGNED edges only — not a kinetic/ODE simulation.
- Unsigned edges among the genes are **excluded** and reported via `signed_coverage`; low
  coverage means the simulation reflects only the signed portion.
- Synchronous updates; attractor type/period can depend on the update scheme.
