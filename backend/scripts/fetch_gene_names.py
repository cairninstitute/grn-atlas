"""
One-time enrichment step: fetch real gene full-names for every symbol in
trrust_rawdata.human.tsv from MyGene.info (https://mygene.info), and cache
the result to gene_names.json so the app never needs network access to
serve gene data.

Usage: python fetch_gene_names.py
"""
import json
import urllib.request
import urllib.parse
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
TRRUST_TSV = DATA_DIR / "trrust_rawdata.human.tsv"
OUTPUT_JSON = DATA_DIR / "gene_names.json"
BATCH_SIZE = 900


def load_symbols():
    symbols = set()
    with open(TRRUST_TSV) as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 4:
                continue
            tf, target, _, _ = parts
            symbols.add(tf)
            symbols.add(target)
    return sorted(symbols)


def fetch_batch(symbols):
    body = urllib.parse.urlencode({
        "q": ",".join(symbols),
        "scopes": "symbol",
        "species": "human",
        "fields": "symbol,name",
    }).encode()
    req = urllib.request.Request(
        "https://mygene.info/v3/query",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main():
    symbols = load_symbols()
    print(f"Fetching names for {len(symbols)} genes from mygene.info...")

    names = {}
    for i in range(0, len(symbols), BATCH_SIZE):
        chunk = symbols[i:i + BATCH_SIZE]
        results = fetch_batch(chunk)
        for hit in results:
            symbol = hit.get("query")
            name = hit.get("name")
            if symbol and name and symbol not in names:
                names[symbol] = name
        print(f"  batch {i // BATCH_SIZE + 1}: {len(results)} results, {len(names)} names so far")

    missing = [s for s in symbols if s not in names]
    print(f"Resolved {len(names)}/{len(symbols)} gene names ({len(missing)} not found)")

    with open(OUTPUT_JSON, "w") as f:
        json.dump(names, f, indent=1, sort_keys=True)
    print(f"Wrote {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
