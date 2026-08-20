"""Fetch protein-coding gene lists for human and mouse from mygene.info.

Uses the scroll API (fetch_all) to retrieve all genes, not just the first 10k.

Usage:
    python backend/scripts/fetch_gene_lists.py          # both species
    python backend/scripts/fetch_gene_lists.py human     # one species
"""
import json
import sys
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

SPECIES = {
    "human": {"taxid": 9606, "out": "gene_list_human.json"},
    "mouse": {"taxid": 10090, "out": "gene_list_mouse.json"},
}

BASE_URL = "https://mygene.info/v3/query"


def fetch_species(name, cfg):
    taxid = cfg["taxid"]
    url = f"{BASE_URL}?q=type_of_gene:protein-coding&species={taxid}&fields=symbol,name&size=1000&fetch_all=TRUE"
    print(f"Fetching {name} protein-coding genes from mygene.info...")

    genes = {}
    page = 0
    while url:
        req = urllib.request.Request(url, headers={"User-Agent": "grn-atlas-build/1.0"})
        resp = urllib.request.urlopen(req, timeout=60)
        data = json.loads(resp.read().decode("utf-8"))

        for hit in data.get("hits", []):
            symbol = hit.get("symbol")
            if symbol:
                genes[symbol] = hit.get("name", "")

        page += 1
        scroll_id = data.get("_scroll_id")
        if scroll_id and len(data.get("hits", [])) > 0:
            url = f"{BASE_URL}?scroll_id={scroll_id}&size=1000"
        else:
            url = None

    out_path = DATA_DIR / cfg["out"]
    with open(out_path, "w") as f:
        json.dump(genes, f, indent=1)
    print(f"  Wrote {out_path}: {len(genes):,} genes")


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(SPECIES.keys())
    for name in targets:
        if name not in SPECIES:
            print(f"Unknown species: {name}")
            continue
        fetch_species(name, SPECIES[name])


if __name__ == "__main__":
    main()
