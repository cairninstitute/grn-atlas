---
name: grn-network-control
description: "Use when the user wants the minimal set of TFs to perturb to steer a whole gene program, not the effect of one perturbation. Good for prompts like 'what's the smallest set of regulators to knock down to shut off these 12 genes?', 'which TFs should I target to push this program up?', or 'find the driver set that controls this module'. Returns a greedy minimal driver set (set-cover over regulatory reachability), which targets each driver covers, and — where the TF→target sign is known (curated or experiment-derived) — the recommended perturbation (overexpress vs knock down) to move each target in the desired direction. Prefer this over grn-perturbation (single gene) and grn-combinatorial-perturbation (fixed pairs/triples) when the task is to CONTROL a target set with the fewest interventions. It is reachability + known signs, not a dynamical control guarantee."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## grn-network-control

Inputs:
- `--target-genes` comma-separated atlas gene ids/symbols (the program to steer)
- optional `--species`, `--desired-direction` (`up`/`down`), `--max-drivers` (default 10), `--min-confidence` (default 0.4)

Output:
- `driver_set` — the greedy minimal set of TFs, each with the targets it covers, the edge sign +
  evidence tier, and a recommended perturbation (`overexpress`/`knockdown`/`perturb`)
- `n_targets_covered` / `uncovered_targets` — how much of the program the driver set reaches
- `method` + `caveats`

Honesty notes:
- This is directed-network reachability plus known edge signs — **not** a dynamical control
  guarantee or an attractor calculation.
- A perturbation direction is only recommended when the edge carries a curated (`measured`) or
  experiment-derived (`perturbation`) sign; unsigned edges return `direction unresolved`.
- Coverage is limited to TFs with atlas edges to the targets at the chosen confidence.
