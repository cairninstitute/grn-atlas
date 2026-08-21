"""Fetch DAP-seq TF-target gene mappings from Plant Cistrome (O'Malley et al. 2016).

Downloads bulk target gene files from the Salk Plant Cistrome database and
consolidates them into a single TSV of TF-target pairs with AGI locus IDs.

Source: https://neomorph.salk.edu/dap_web/pages/browse_table_aj.php
Paper: O'Malley et al. 2016, Cell 166(5):1598 (PMID 27203113)

Usage:
    python backend/scripts/fetch_dapseq.py
"""
import io
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_TSV = DATA_DIR / "dapseq_arabidopsis.tsv"

GENES_ZIP_URL = ("https://neomorph.salk.edu/dap_web/pages/"
                 "dap_data_v4/fullset/dap_download_may2016_genes.zip")


def normalize_agi(agi):
    """Normalize AGI locus ID to uppercase without isoform suffix."""
    return agi.strip().upper().split(".")[0]


def main():
    print("Downloading DAP-seq target genes from Plant Cistrome (~10 MB)...")
    req = urllib.request.Request(GENES_ZIP_URL,
                                headers={"User-Agent": "Mozilla/5.0 (grn-atlas-build)"})
    resp = urllib.request.urlopen(req, timeout=120)
    data = resp.read()
    print(f"  Downloaded {len(data):,} bytes")

    edges = defaultdict(set)
    tf_count = 0

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            if not name.endswith("_targets.txt"):
                continue
            tf_count += 1
            with zf.open(name) as f:
                for line in io.TextIOWrapper(f, encoding="utf-8"):
                    line = line.strip()
                    if not line or line.startswith("tf.at_id"):
                        continue
                    parts = line.split("\t")
                    if len(parts) < 2:
                        continue
                    tf = normalize_agi(parts[0])
                    target = normalize_agi(parts[1])
                    if tf.startswith("AT") and target.startswith("AT"):
                        edges[(tf, target)].add(name)

    kept = 0
    with open(OUT_TSV, "w") as f:
        for (tf, target), experiments in sorted(edges.items()):
            n_exp = len(experiments)
            if n_exp < 2:
                continue
            conf = min(0.65 + 0.10 * (n_exp - 2), 0.95)
            f.write(f"{tf}\t{target}\tregulation\t{conf:.2f}\tDAP-seq\t27203113\n")
            kept += 1

    print(f"  {tf_count} TF experiments")
    print(f"  {len(edges):,} unique TF-target pairs (all)")
    print(f"  {kept:,} kept (supported by 2+ experiments)")
    print(f"  Written to {OUT_TSV}")


if __name__ == "__main__":
    main()
