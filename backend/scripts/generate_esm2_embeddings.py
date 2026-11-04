#!/usr/bin/env python3
"""Generate ESM2 protein embeddings for all TFs with cached sequences.

Uses facebook/esm2_t33_650M_UR50D (locally cached) to compute per-protein
mean-pooled embeddings. Stores results in esm2_embeddings table.

Usage:
    python backend/scripts/generate_esm2_embeddings.py [--db PATH] [--batch-size 8]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DB = BACKEND / "data" / "grn.sqlite3"
MODEL_NAME = "facebook/esm2_t33_650M_UR50D"
EMBEDDING_DIM = 1280
MAX_SEQ_LEN = 1022


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS esm2_embeddings (
            gene_id TEXT NOT NULL,
            species TEXT NOT NULL,
            embedding BLOB NOT NULL,
            embedding_dim INTEGER NOT NULL,
            sequence_len INTEGER NOT NULL,
            model_version TEXT NOT NULL,
            computed_at TEXT NOT NULL,
            PRIMARY KEY (gene_id, species)
        )
    """)
    conn.commit()


def load_sequences(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("""
        SELECT ps.gene_id, ps.species, ps.sequence, ps.sequence_len
        FROM protein_sequences ps
        JOIN genes g ON g.id = ps.gene_id AND g.is_tf = 1
        WHERE ps.fetch_status = 'found'
          AND ps.sequence IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM esm2_embeddings e
            WHERE e.gene_id = ps.gene_id AND e.species = ps.species
          )
        ORDER BY ps.sequence_len ASC
    """).fetchall()
    return [{"gene_id": r[0], "species": r[1], "sequence": r[2], "seq_len": r[3]} for r in rows]


def fetch_all_tf_sequences(conn: sqlite3.Connection) -> None:
    """Fetch protein sequences for TFs that don't have them yet."""
    UA = {"User-Agent": "grn-atlas/1.0 (ken.janik@gmail.com)"}
    SPECIES_TAXON = {
        "human": 9606, "mouse": 10090, "arabidopsis": 3702,
        "tomato": 4081, "rice": 39947, "potato": 4113, "pepper": 4072, "petunia": 4102,
    }

    tfs = conn.execute("""
        SELECT g.id, g.symbol, g.species
        FROM genes g
        WHERE g.is_tf = 1
          AND NOT EXISTS (
            SELECT 1 FROM protein_sequences ps WHERE ps.gene_id = g.id AND ps.species = g.species
          )
    """).fetchall()

    if not tfs:
        print(f"  All TF protein sequences already cached.")
        return

    print(f"  Fetching protein sequences for {len(tfs)} TFs...")
    found = 0
    for i, (gene_id, symbol, species) in enumerate(tfs, 1):
        taxon = SPECIES_TAXON.get(species)
        if not taxon or not symbol:
            conn.execute(
                "INSERT OR IGNORE INTO protein_sequences (gene_id, species, fetch_status, fetched_at) "
                "VALUES (?, ?, 'not_found', datetime('now'))", (gene_id, species))
            continue

        query = f"gene_exact:{symbol} AND taxonomy_id:{taxon}"
        url = f"https://rest.uniprot.org/uniprotkb/search?query={urllib.parse.quote(query)}&format=fasta&size=1"
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=15) as resp:
                fasta = resp.read().decode()
            lines = [l for l in fasta.strip().split("\n") if not l.startswith(">")]
            seq = "".join(lines).strip()
            if seq and len(seq) >= 20:
                acc_line = fasta.split("\n")[0]
                acc = acc_line.split("|")[1] if "|" in acc_line else ""
                conn.execute(
                    "INSERT OR REPLACE INTO protein_sequences "
                    "(gene_id, species, uniprot_acc, sequence, sequence_len, fetch_status, fetched_at) "
                    "VALUES (?, ?, ?, ?, ?, 'found', datetime('now'))",
                    (gene_id, species, acc, seq, len(seq)))
                found += 1
            else:
                conn.execute(
                    "INSERT OR IGNORE INTO protein_sequences (gene_id, species, fetch_status, fetched_at) "
                    "VALUES (?, ?, 'not_found', datetime('now'))", (gene_id, species))
        except Exception:
            conn.execute(
                "INSERT OR IGNORE INTO protein_sequences (gene_id, species, fetch_status, fetched_at) "
                "VALUES (?, ?, 'not_found', datetime('now'))", (gene_id, species))

        if i % 50 == 0:
            conn.commit()
            print(f"    [{i}/{len(tfs)}] {found} found so far")
            time.sleep(0.3)

    conn.commit()
    print(f"  Fetched {found}/{len(tfs)} new protein sequences")


def main():
    parser = argparse.ArgumentParser(description="Generate ESM2 embeddings for TF proteins")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--fetch-only", action="store_true", help="Only fetch sequences, skip embeddings")
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.db))
    ensure_table(conn)

    print("Phase 1: Fetch missing TF protein sequences...")
    fetch_all_tf_sequences(conn)

    if args.fetch_only:
        print("Fetch-only mode. Done.")
        conn.close()
        return

    sequences = load_sequences(conn)
    if not sequences:
        print("No new sequences to embed. Done.")
        conn.close()
        return

    print(f"\nPhase 2: Generating ESM2 embeddings for {len(sequences)} proteins...")

    import torch
    from transformers import AutoModel, AutoTokenizer

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"  Device: {device}")

    print(f"  Loading {MODEL_NAME}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME).to(device).eval()

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    total = len(sequences)
    batch_size = args.batch_size

    for batch_start in range(0, total, batch_size):
        batch = sequences[batch_start:batch_start + batch_size]
        seqs = [s["sequence"][:MAX_SEQ_LEN] for s in batch]

        with torch.no_grad():
            inputs = tokenizer(seqs, return_tensors="pt", padding=True, truncation=True,
                               max_length=MAX_SEQ_LEN + 2).to(device)
            outputs = model(**inputs)
            hidden = outputs.last_hidden_state

            for j, s in enumerate(batch):
                seq_len = min(len(s["sequence"]), MAX_SEQ_LEN)
                emb = hidden[j, 1:seq_len + 1, :].mean(dim=0).cpu().numpy()
                emb_bytes = emb.tobytes()

                conn.execute(
                    "INSERT OR REPLACE INTO esm2_embeddings "
                    "(gene_id, species, embedding, embedding_dim, sequence_len, model_version, computed_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (s["gene_id"], s["species"], emb_bytes, EMBEDDING_DIM, seq_len, MODEL_NAME, now))

        conn.commit()
        done = min(batch_start + batch_size, total)
        if done % 20 == 0 or done == total:
            print(f"  [{done}/{total}] embedded")

    conn.close()

    print(f"\nSummary:")
    conn2 = sqlite3.connect(str(args.db))
    stats = conn2.execute(
        "SELECT species, COUNT(*) FROM esm2_embeddings GROUP BY species ORDER BY COUNT(*) DESC"
    ).fetchall()
    for species, count in stats:
        print(f"  {species}: {count} embeddings")
    print(f"  Total: {sum(c for _, c in stats)}")
    conn2.close()


if __name__ == "__main__":
    main()
