#!/usr/bin/env python3
"""Rank candidate edges by their marginal feedback-core impact."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from candidate_impact import rank_candidates  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=BACKEND / "data" / "grn.sqlite3")
    parser.add_argument("--species")
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        result = rank_candidates(conn, args.species)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
