#!/usr/bin/env python3
"""Consensus candidate ranking."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="GRN Atlas consensus ranking")
    common.add_common_args(parser)
    parser.add_argument("--gene-ids", required=True)
    parser.add_argument("--intent", default="experiment")
    parser.add_argument("--species")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--include-external", action="store_true")
    parser.add_argument("--years-back", type=int, default=5)
    args = parser.parse_args()

    payload = {
        "gene_ids": [g.strip() for g in args.gene_ids.split(",") if g.strip()],
        "intent": args.intent,
        "species": args.species,
        "top_n": args.top_n,
        "include_external": args.include_external,
        "years_back": args.years_back,
    }
    if args.http:
        data = common.http_post(args.http, "/api/v1/research/consensus-ranking", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.consensus_ranking(backend.ConsensusRankingRequest(**payload)))
    common.output(data)


if __name__ == "__main__":
    main()
