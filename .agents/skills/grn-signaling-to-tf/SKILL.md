---
name: grn-signaling-to-tf
description: "Trace a receptor or ligand through the regulatory network to identify downstream TF targets. Reports direct TF targets and secondary cascade TFs (2-hop)."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-signaling-to-tf/scripts/run.py --species <value> --receptor <value>
```

### Parameters
- `--species` — Species
- `--receptor` — Receptor gene ID
- `--ligand` — Ligand gene ID
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-signaling-to-tf/scripts/run.py --species <value> --receptor <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
