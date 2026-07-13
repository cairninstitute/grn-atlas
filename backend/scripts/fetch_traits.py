"""Gene–trait associations for human (#5 trait linkage), from the EBI GWAS Catalog.

Links regulators/targets to organism-level phenotypes ("which traits sit downstream
of this gene / which regulators underlie a trait"). Matches the catalog's MAPPED_GENE
symbols to the atlas's human gene IDs (which are HGNC symbols).

These are statistical GWAS associations (SNP→nearest/mapped gene→trait), NOT mechanistic
regulation — labelled source 'GWAS Catalog' and surfaced as associations, with PubMed IDs.

Input : a local GWAS Catalog associations TSV (downloaded to /tmp; see module doc).
Output: trait_associations.json.gz = [{gene_id, trait, pubmed_id}]  (loaded by load_traits.py)

Usage: python backend/scripts/fetch_traits.py /tmp/gwas-catalog-download-associations-alt-full.tsv
"""
import csv
import gzip
import json
import re
import sqlite3
import sys
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"
DB = DATA / "grn.sqlite3"
OUT = DATA / "trait_associations.json.gz"
_SPLIT = re.compile(r"\s*(?:,|;|/|\bx\b|\s-\s)\s*")


def human_symbols():
    conn = sqlite3.connect(DB)
    ids, sym2id = set(), {}
    for gid, sym in conn.execute("SELECT id, symbol FROM genes WHERE species='human'"):
        ids.add(gid)
        if sym:
            sym2id[sym.upper()] = gid
    conn.close()
    return ids, sym2id


def main(tsv_path):
    ids, sym2id = human_symbols()
    print(f"atlas human genes: {len(ids)}")
    seen = set()          # (gene_id, trait)
    out = []
    with open(tsv_path, newline="", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            trait = (row.get("DISEASE/TRAIT") or "").strip()
            mapped = row.get("MAPPED_GENE") or ""
            pmid = (row.get("PUBMEDID") or "").strip()
            if not trait or not mapped:
                continue
            for tok in _SPLIT.split(mapped):
                tok = tok.strip().upper()
                gid = tok if tok in ids else sym2id.get(tok)
                if not gid:
                    continue
                key = (gid, trait)
                if key in seen:
                    continue
                seen.add(key)
                out.append({"gene_id": gid, "trait": trait, "pubmed_id": pmid})
    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        json.dump(out, f)
    genes = {a["gene_id"] for a in out}
    traits = {a["trait"] for a in out}
    print(f"associations: {len(out)}  genes: {len(genes)}  distinct traits: {len(traits)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else
         "/tmp/gwas-catalog-download-associations-alt-full.tsv")
