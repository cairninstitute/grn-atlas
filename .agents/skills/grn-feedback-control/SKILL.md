---
name: grn-feedback-control
description: "Discover signed feedback cores, representative regulatory loops, and candidate structural controller genes across a species GRN. Use for questions about positive or negative feedback, toggle switches, repressilators, control loops, or feedback-vertex intervention points."
compatibility: Requires the GRN Atlas backend virtualenv or a running GRN Atlas server.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
venv/bin/python .agents/skills/grn-feedback-control/scripts/run.py --species arabidopsis
venv/bin/python .agents/skills/grn-feedback-control/scripts/run.py --species human --min-confidence 0.7 --max-loop-length 5
```

### Parameters

- `--species` — required species name.
- `--min-confidence` — minimum edge confidence; default `0.5`.
- `--evidence-tiers` — comma-separated `measured,perturbation` selection.
- `--max-loop-length` — longest representative circuit; default `6`, maximum `10`.
- `--max-cores` — maximum feedback cores returned.
- `--max-circuits` — total representative-circuit limit.
- `--circuits-per-core` — representative-circuit limit for one core.
- `--max-search-states` — hard search-work budget per core.
- `--max-controllers` — control candidates retained per core.
- `--refresh` — recompute and replace an identical cached run.
- `--http URL` — optional running backend URL.

### Output interpretation

- `feedback_cores` are strongly connected signed regions and are exhaustively identified for the filtered graph.
- Self-loops and reciprocal loops are exhaustively detected within returned cores.
- Longer loops are bounded representatives, not an exhaustive cycle list. Always inspect `truncation` and each core's `circuit_search`.
- Positive-loop polarity suggests switch or memory behavior; negative-loop polarity suggests homeostasis, adaptation, or oscillation. These are hypotheses, not demonstrated dynamics.
- A feedback vertex set identifies structural intervention points. It does not establish perturbation direction or guarantee attractor control.
- Exact controller sets are used only for small cores. Large cores use a bounded greedy approximation and report whether all detected feedback was broken.

### Routing notes

- Use this skill for species-wide feedback discovery or control-loop questions.
- Use `grn-network-patterns` for feed-forward loops and bi-fans without feedback-control analysis.
- Follow with `grn-dynamics` for qualitative behavior of one selected, fully signed small circuit.
- Follow with evidence or multiome audits before presenting a circuit as a biological mechanism.
