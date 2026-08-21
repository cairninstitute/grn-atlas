---
name: grn-sirna-pool
description: "Score all siRNAs in a dsRNA window for efficacy using Reynolds/Ui-Tei heuristic rules. Reports GC content, thermodynamic asymmetry, repeat penalties, and ranked efficacy scores."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-sirna-pool/scripts/run.py --sequence <value> --k <value>
```

### Parameters
- `--sequence` — dsRNA sequence
- `--k` — siRNA length (default 21)
- `--top` — Number of top siRNAs to return (default 10)
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-sirna-pool/scripts/run.py --sequence <value> --k <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
