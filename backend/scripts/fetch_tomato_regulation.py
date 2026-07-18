"""
One-time enrichment: fetch the real tomato (Solanum lycopersicum) TF-target
regulatory network from PlantRegMap and write it as regulation_tomato.tsv, in
the same format build_db already uses for Arabidopsis.

We use PlantRegMap's FunTFBS network (functional TF binding sites) -- its
higher-confidence predicted regulation set. PlantRegMap Solyc ids carry a
version suffix that may differ from our gene set's, so genes are matched on the
version-less base id (Solyc..g......).

Usage: python backend/scripts/fetch_tomato_regulation.py
"""
import json
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
PLAZA_GENES_JSON = DATA_DIR / "genome_genes_plaza.json"
OUTPUT_TSV = DATA_DIR / "regulation_tomato.tsv"

FUNTFBS_URL = ("https://plantregmap.gao-lab.org/download_ftp.php?filepath="
               "08-download/Solanum_lycopersicum/binding/regulation_from_FunTFBS_Sly.txt")
CONFIDENCE = 0.65  # matches Arabidopsis motif/FunTFBS-based confidence
UA = {"User-Agent": "Mozilla/5.0 (grn-atlas-build)"}


def base_id(gene_id):
    return gene_id.split(".")[0]


def load_tomato_base_map():
    """base Solyc id -> our tomato gene id (with version), from PLAZA gene set."""
    genes = json.loads(PLAZA_GENES_JSON.read_text())
    return {base_id(gid): gid for gid, g in genes.items() if g.get("species") == "tomato"}


def main():
    base_map = load_tomato_base_map()
    print(f"Tomato genes in our set: {len(base_map)}")

    print("Downloading PlantRegMap FunTFBS tomato network…")
    req = urllib.request.Request(FUNTFBS_URL, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as resp:
        lines = resp.read().decode("utf-8", "replace").splitlines()

    edges = []
    seen = set()
    unmapped = 0
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        tf = base_map.get(base_id(parts[0]))
        target = base_map.get(base_id(parts[2]))
        if not tf or not target or tf == target:
            if not (tf and target):
                unmapped += 1
            continue
        key = (tf, target)
        if key in seen:
            continue
        seen.add(key)
        edges.append((tf, target))

    with open(OUTPUT_TSV, "w") as f:
        for tf, target in edges:
            f.write(f"{tf}\t{target}\tregulation\t{CONFIDENCE}\tFunTFBS\n")
    print(f"Wrote {OUTPUT_TSV}: {len(edges)} edges "
          f"({unmapped} raw edges had an endpoint outside our gene set)")


if __name__ == "__main__":
    main()
