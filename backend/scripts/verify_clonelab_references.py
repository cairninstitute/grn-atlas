#!/usr/bin/env python3
"""Verify CloneLab reference files against their recorded hashes."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from clonelab.reference import ReferenceRegistry

manifest = Path(__file__).resolve().parents[1] / "data" / "clonelab_references.json"
results = ReferenceRegistry(manifest).verify()
print(json.dumps(results, indent=2))
raise SystemExit(0 if results and all(row["valid"] for row in results) else 1)
