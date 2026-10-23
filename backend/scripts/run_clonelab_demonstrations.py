#!/usr/bin/env python3
"""Run both release demonstrations and write compact reproducibility records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clonelab.demos import demonstration_summary, list_demonstrations, run_demonstration  # noqa: E402
from clonelab.reference import ReferenceRegistry  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", default="all")
    parser.add_argument("--output-dir", default=ROOT.parent / "docs/clonelab/demos", type=Path)
    args = parser.parse_args()
    registry = ReferenceRegistry(ROOT / "data/clonelab_references.json")
    plasmid = ROOT / "data/clonelab/pUC19_L09137.2.gb"
    selected = [row["demonstration_id"] for row in list_demonstrations()]
    if args.demo != "all":
        selected = [args.demo]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    passed = 0
    for demonstration_id in selected:
        result = run_demonstration(
            demonstration_id, registry=registry,
            database_path=ROOT / "data/grn.sqlite3", plasmid_path=plasmid,
        )
        summary = demonstration_summary(result)
        (args.output_dir / f"{demonstration_id}.json").write_text(json.dumps(summary, indent=2) + "\n")
        passed += summary["release_gate"] == "pass"
        print(f"{demonstration_id}: {summary['release_gate']} ({summary['best_digest']['enzymes']})")
    print(f"Release demonstrations: {passed}/{len(selected)} passed")
    return 0 if passed == len(selected) else 1


if __name__ == "__main__":
    raise SystemExit(main())
