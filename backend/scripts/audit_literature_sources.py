#!/usr/bin/env python3
"""Record machine-ingestion decisions for literature aggregation sources."""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

SOURCES = [
    {
        "source": "funRiceGenes", "url": "https://funricegenes.github.io/net.pdf",
        "decision": "not_ingested", "reason": "Interaction networks are distributed as a PDF rather than a row-level machine-readable edge table with provenance.",
    },
    {
        "source": "funPlantGenes", "url": "https://funplantgenes.henau.edu.cn/",
        "decision": "not_ingested", "reason": "No documented bulk interaction-edge export with direction, sign, and publication provenance was identified.",
    },
    {
        "source": "TFLink small-scale", "url": "https://tflink.net/download/",
        "decision": "ingest_direct_unsigned", "reason": "Stable TSV exports include TF and target identifiers, methods, PubMed IDs, and small-scale evidence labels; they do not encode activation/repression sign.",
    },
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for source in SOURCES:
        try:
            request = urllib.request.Request(source["url"], method="HEAD", headers={"User-Agent": "grn-atlas/1.0"})
            with urllib.request.urlopen(request, timeout=30) as response:
                source["reachable"] = response.status == 200
                source["content_type"] = response.headers.get("Content-Type")
        except Exception as exc:
            source["reachable"] = False
            source["access_error"] = str(exc)
    payload = {"sources": SOURCES, "policy": "Only row-level records with traceable provenance are eligible for atlas evidence storage."}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
