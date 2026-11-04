#!/usr/bin/env python3
"""Fetch AlphaFold structural disorder features for atlas TFs.

Downloads per-residue pLDDT scores from AlphaFold DB for each TF with a UniProt
accession. Computes:
  - disorder_fraction: fraction of residues with pLDDT < 50 (intrinsically disordered)
  - mean_plddt: overall structure quality/confidence
  - dbd_plddt: mean pLDDT over the DNA-binding domain region (if annotatable)

Stores results in the esm2_embeddings table as additional metadata columns,
or in a new alphafold_features table.

Usage:
    python backend/scripts/fetch_alphafold_features.py [--db backend/data/grn.sqlite3]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DB = BACKEND / "data" / "grn.sqlite3"

ALPHAFOLD_API = "https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}"
ALPHAFOLD_CIF = "https://alphafold.ebi.ac.uk/files/AF-{uniprot_id}-F1-model_v4.cif"
ALPHAFOLD_PAE = "https://alphafold.ebi.ac.uk/files/AF-{uniprot_id}-F1-predicted_aligned_error_v4.json"

DISORDER_THRESHOLD = 50


def ensure_table(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS alphafold_features (
            gene_id TEXT NOT NULL,
            species TEXT NOT NULL,
            uniprot_acc TEXT,
            protein_length INTEGER,
            mean_plddt REAL,
            disorder_fraction REAL,
            low_confidence_fraction REAL,
            high_confidence_fraction REAL,
            fetch_status TEXT NOT NULL DEFAULT 'pending',
            fetched_at TEXT,
            PRIMARY KEY (gene_id, species)
        );
    """)
    conn.commit()


def get_tfs_with_uniprot(conn: sqlite3.Connection) -> list[dict]:
    return [
        {"gene_id": r[0], "species": r[1], "uniprot_acc": r[2]}
        for r in conn.execute("""
            SELECT ps.gene_id, ps.species, ps.uniprot_acc
            FROM protein_sequences ps
            WHERE ps.fetch_status = 'found'
              AND ps.uniprot_acc IS NOT NULL
              AND ps.uniprot_acc != ''
              AND NOT EXISTS (
                  SELECT 1 FROM alphafold_features af
                  WHERE af.gene_id = ps.gene_id AND af.species = ps.species
              )
            ORDER BY ps.species, ps.gene_id
        """).fetchall()
    ]


def fetch_plddt_from_api(uniprot_acc: str) -> list[float] | None:
    url = ALPHAFOLD_API.format(uniprot_id=uniprot_acc)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (grn-atlas-build)"})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        if isinstance(data, list) and data:
            cif_url = data[0].get("cifUrl", "")
            plddt_url = data[0].get("paeImageUrl", "")
            pdb_url = data[0].get("pdbUrl", "")
            if pdb_url:
                return fetch_plddt_from_pdb(pdb_url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except Exception:
        pass
    return None


def fetch_plddt_from_pdb(pdb_url: str) -> list[float] | None:
    req = urllib.request.Request(pdb_url, headers={"User-Agent": "Mozilla/5.0 (grn-atlas-build)"})
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        text = resp.read().decode("utf-8")
    except Exception:
        return None

    plddts = []
    seen_residues = set()
    for line in text.splitlines():
        if line.startswith("ATOM") and line[12:16].strip() == "CA":
            res_seq = line[22:26].strip()
            if res_seq not in seen_residues:
                seen_residues.add(res_seq)
                try:
                    bfactor = float(line[60:66].strip())
                    plddts.append(bfactor)
                except (ValueError, IndexError):
                    pass
    return plddts if plddts else None


def compute_features(plddts: list[float]) -> dict:
    n = len(plddts)
    if n == 0:
        return {}
    mean_plddt = sum(plddts) / n
    disordered = sum(1 for p in plddts if p < DISORDER_THRESHOLD)
    low_conf = sum(1 for p in plddts if p < 70)
    high_conf = sum(1 for p in plddts if p >= 90)
    return {
        "protein_length": n,
        "mean_plddt": round(mean_plddt, 2),
        "disorder_fraction": round(disordered / n, 4),
        "low_confidence_fraction": round(low_conf / n, 4),
        "high_confidence_fraction": round(high_conf / n, 4),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--max-tfs", type=int, default=0, help="0 = all")
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.db), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    ensure_table(conn)

    tfs = get_tfs_with_uniprot(conn)
    if args.max_tfs > 0:
        tfs = tfs[:args.max_tfs]

    print(f"Fetching AlphaFold features for {len(tfs)} TFs...", flush=True)

    stats = {"fetched": 0, "not_found": 0, "error": 0}
    for i, tf in enumerate(tfs):
        try:
            plddts = fetch_plddt_from_api(tf["uniprot_acc"])
        except Exception as e:
            print(f"  [{i+1}/{len(tfs)}] {tf['gene_id']} ERROR: {e}")
            conn.execute(
                "INSERT OR REPLACE INTO alphafold_features (gene_id, species, uniprot_acc, fetch_status, fetched_at) "
                "VALUES (?, ?, ?, 'error', datetime('now'))",
                (tf["gene_id"], tf["species"], tf["uniprot_acc"])
            )
            stats["error"] += 1
            time.sleep(args.delay)
            continue

        if plddts is None:
            conn.execute(
                "INSERT OR REPLACE INTO alphafold_features (gene_id, species, uniprot_acc, fetch_status, fetched_at) "
                "VALUES (?, ?, ?, 'not_found', datetime('now'))",
                (tf["gene_id"], tf["species"], tf["uniprot_acc"])
            )
            stats["not_found"] += 1
        else:
            features = compute_features(plddts)
            conn.execute(
                "INSERT OR REPLACE INTO alphafold_features "
                "(gene_id, species, uniprot_acc, protein_length, mean_plddt, "
                "disorder_fraction, low_confidence_fraction, high_confidence_fraction, "
                "fetch_status, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'found', datetime('now'))",
                (tf["gene_id"], tf["species"], tf["uniprot_acc"],
                 features.get("protein_length"), features.get("mean_plddt"),
                 features.get("disorder_fraction"), features.get("low_confidence_fraction"),
                 features.get("high_confidence_fraction"))
            )
            stats["fetched"] += 1

        if (i + 1) % args.batch_size == 0:
            conn.commit()
            print(f"  [{i+1}/{len(tfs)}] fetched={stats['fetched']} not_found={stats['not_found']} error={stats['error']}", flush=True)

        time.sleep(args.delay)

    conn.commit()

    # Summary by species
    print(f"\n=== AlphaFold Feature Summary ===")
    for r in conn.execute(
        "SELECT species, fetch_status, COUNT(*) FROM alphafold_features GROUP BY species, fetch_status ORDER BY species"
    ):
        print(f"  {r[0]}: {r[1]} = {r[2]}")

    disorder_stats = conn.execute("""
        SELECT species,
               COUNT(*) as n,
               ROUND(AVG(mean_plddt), 1) as avg_plddt,
               ROUND(AVG(disorder_fraction), 3) as avg_disorder
        FROM alphafold_features
        WHERE fetch_status = 'found'
        GROUP BY species
    """).fetchall()
    print(f"\nDisorder analysis:")
    for r in disorder_stats:
        print(f"  {r[0]}: n={r[1]}, avg_pLDDT={r[2]}, avg_disorder={r[3]}")

    print(json.dumps(stats, indent=2))
    conn.close()


if __name__ == "__main__":
    main()
