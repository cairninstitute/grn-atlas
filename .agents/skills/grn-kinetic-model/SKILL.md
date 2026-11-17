---
name: grn-kinetic-model
description: "Simulate a signed regulatory circuit as a Hill-function ODE system to test whether it oscillates, switches, or is monostable. Give it a list of gene IDs forming a feedback loop and it constructs the ODE from atlas edge signs, sweeps Hill coefficients and degradation rates, and classifies the dynamics. Use after grn-feedback to test whether a discovered circuit has the topology to produce oscillations or bistability."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python). Needs numpy (included). Direct database access only; no HTTP endpoint.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-kinetic-model/scripts/run.py \
  --genes AT2G46830,AT1G01060,AT5G61380

backend/venv/bin/python .agents/skills/grn-kinetic-model/scripts/run.py \
  --genes AT2G46830,AT1G01060,AT5G61380 --hill-range 2,4,8 --time 200

backend/venv/bin/python .agents/skills/grn-kinetic-model/scripts/run.py --help
```

### Parameters
- `--genes` (required) — comma-separated gene IDs forming the circuit.
- `--species` — omit and it is inferred from the first gene.
- `--hill-range` (default `1,2,4,8`) — Hill coefficients to sweep.
- `--deg-range` (default `0.1,0.5,1.0,2.0`) — degradation rates to sweep.
- `--time` (default `100`) — simulation time in arbitrary units.
- `--dt` (default `0.1`) — integration time step.
- `--db` — path to the SQLite database (default `backend/data/grn.sqlite3`).

### Output
JSON with:
- `circuit` — genes and signed edges found between them.
- `parameter_sweep` — classification per (hill, degradation) pair:
  `oscillatory`, `bistable`, or `monostable`.
- `summary` — overall classification and oscillatory fraction.
- `best_oscillation` — parameter set with strongest oscillation (if any),
  including estimated period and amplitude.

### How it works
For each gene, the model builds a production term from its activators and
repressors using Hill functions. Activation:
`alpha * x^n / (K^n + x^n)`. Repression: `alpha * K^n / (K^n + x^n)`.
The full ODE for gene i is:
`dx_i/dt = basal + sum(activation_terms) * prod(repression_terms) - deg * x_i`.

The parameter sweep tests multiple Hill coefficients (steepness of switching)
and degradation rates. For each, 4 random initial conditions are simulated.
The last 30% of each trajectory is classified by FFT analysis as oscillatory
(dominant frequency above noise) or steady-state. If different initial
conditions converge to different steady states, the system is classified as
bistable.

### Limitations
This is a qualitative screen, not a quantitative prediction. The model uses
symmetric parameters (same alpha, K, degradation for all genes) and does not
account for delays, cooperative binding, or post-translational regulation.
A circuit classified as `monostable` here may still oscillate under more
realistic parameterizations. Use as a first filter, not a final answer.
