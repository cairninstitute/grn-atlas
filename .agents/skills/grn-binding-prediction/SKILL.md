---
name: grn-binding-prediction
description: Query or trigger structural binding predictions — scores whether a TF protein can physically bind a target gene's promoter DNA using Boltz-2. Use for validating candidate regulatory edges or prioritizing wet-lab experiments.
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

### Query stored predictions

```bash
# Top predictions for a species
python .agents/skills/grn-binding-prediction/scripts/run.py --species arabidopsis --top 20

# Filter by binding class
python .agents/skills/grn-binding-prediction/scripts/run.py --species human --binding-class likely

# Lookup a specific edge
python .agents/skills/grn-binding-prediction/scripts/run.py --species arabidopsis --source-id AT1G01060 --target-id AT5G61850
```

### Run batch predictions

```bash
# Fetch sequences only (no API key needed)
python backend/scripts/predict_structural_binding.py --fetch-sequences-only --species arabidopsis --tier cycle_closing

# Predict cycle-closing candidates
python backend/scripts/predict_structural_binding.py --species arabidopsis --tier cycle_closing --max-edges 50
```

### Parameters

| Parameter | Description |
|-----------|-------------|
| `--species` | Filter by species name |
| `--source-id` | TF gene ID |
| `--target-id` | Target gene ID |
| `--binding-class` | Filter: `likely`, `uncertain`, `unlikely`, `no_sequence`, `error` |
| `--top` | Max results to return (default: 50) |
| `--min-confidence` | Minimum confidence score filter (0.0-1.0) |

### Output interpretation

Each prediction includes:
- **confidence_score** (0.0-1.0): Boltz-2 structural confidence for the TF-DNA complex
- **binding_class**: `likely` (≥0.7), `uncertain` (0.4-0.7), `unlikely` (<0.4), `no_sequence`, `error`
- **protein_length**: TF protein sequence length (amino acids)
- **dna_length**: Promoter DNA window length (base pairs)

### Verification boundary

These are **computational structure predictions**, not experimental binding measurements. A high confidence score means the model predicts the TF protein *can* fold into a complex with the DNA sequence — it does not prove the TF binds that promoter *in vivo*. Always label as predicted_structural evidence, never as measured.

Confidence thresholds (0.7/0.4) are preliminary and have not been calibrated against gold-standard ChIP-seq data. Use for prioritization, not as definitive evidence.

### API key

Requires `NVIDIA_NIM_API_KEY` environment variable. Get a free-tier key at https://build.nvidia.com (search for Boltz-2).

### Routing notes

- Use this skill to check if structural binding predictions exist for a candidate edge
- Use `grn-candidate-triage` for broader candidate ranking (not just structural)
- Use `grn-evidence-audit` to see all evidence layers for an edge including structural predictions
- Use `grn-feedback-control` to find which candidates are cycle-closing (highest priority for prediction)
