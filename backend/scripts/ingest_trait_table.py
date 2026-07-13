"""Generic gene-trait ingestion — species-agnostic (#5 trait linkage, generalized).

Loads any gene->trait table into trait_associations, keyed by gene ids that already
exist in the atlas for the given species. This is how a plant GWAS (e.g. Zach's ~400
Dahlia cultivar runs -> gene->flower-colour-trait mappings) is onboarded alongside the
human GWAS Catalog.

Input TSV (header row; tab-separated). Recognised columns (case-insensitive):
  gene_id / gene / locus   (required)  -- must match atlas gene ids for <species>
  trait / phenotype        (required)
  pubmed / pmid            (optional)
  source                   (optional; default from --source)

Associations whose gene_id is not in the atlas for <species> are skipped (reported).
Existing rows for the same source+species are replaced (idempotent per source).

Usage:
  python backend/scripts/ingest_trait_table.py <species> <table.tsv> --source "Dahlia GWAS (Zach 2026)"
"""
import argparse
import csv
import sqlite3
from pathlib import Path

DB = Path(__file__).parent.parent / "data" / "grn.sqlite3"
_GENE = ("gene_id", "gene", "locus")
_TRAIT = ("trait", "phenotype")
_PMID = ("pubmed", "pmid", "pubmedid")


def _col(fieldnames, names):
    low = {f.lower(): f for f in fieldnames}
    for n in names:
        if n in low:
            return low[n]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("species")
    ap.add_argument("tsv")
    ap.add_argument("--source", default="external GWAS")
    args = ap.parse_args()

    conn = sqlite3.connect(DB)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS trait_associations (
            gene_id TEXT NOT NULL, trait TEXT NOT NULL, pubmed_id TEXT,
            source TEXT NOT NULL DEFAULT 'GWAS Catalog', PRIMARY KEY (gene_id, trait));
        CREATE INDEX IF NOT EXISTS idx_trait_gene ON trait_associations(gene_id);
    """)
    atlas = {r[0] for r in conn.execute("SELECT id FROM genes WHERE species=?", (args.species,))}
    if not atlas:
        raise SystemExit(f"no atlas genes for species '{args.species}'")

    with open(args.tsv, newline="", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        gcol = _col(reader.fieldnames, _GENE)
        tcol = _col(reader.fieldnames, _TRAIT)
        pcol = _col(reader.fieldnames, _PMID)
        scol = _col(reader.fieldnames, ("source",))
        if not (gcol and tcol):
            raise SystemExit(f"need gene + trait columns; got {reader.fieldnames}")
        rows, skipped, seen = [], 0, set()
        for r in reader:
            g, t = (r.get(gcol) or "").strip(), (r.get(tcol) or "").strip()
            if not g or not t:
                continue
            if g not in atlas:
                skipped += 1
                continue
            key = (g, t)
            if key in seen:
                continue
            seen.add(key)
            rows.append((g, t, (r.get(pcol) or "").strip() if pcol else None,
                         (r.get(scol) or args.source) if scol else args.source))

    # replace existing rows for this source (idempotent re-ingest)
    conn.execute("DELETE FROM trait_associations WHERE source=?", (args.source,))
    conn.executemany(
        "INSERT OR IGNORE INTO trait_associations (gene_id, trait, pubmed_id, source) "
        "VALUES (?,?,?,?)", rows)
    conn.commit()
    conn.close()
    print(f"ingested {len(rows)} associations for {args.species} "
          f"(source='{args.source}'), skipped {skipped} non-atlas genes")


if __name__ == "__main__":
    main()
