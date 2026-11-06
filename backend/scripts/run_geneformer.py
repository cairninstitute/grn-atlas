#!/usr/bin/env python3
"""Generate Geneformer embeddings from scRNA-seq data.

Tokenizes cell-level expression into rank-ordered gene tokens and runs
the pre-trained Geneformer BERT model to produce per-cell embeddings.
These embeddings enable gene function prediction and cell-type-specific
regulatory inference.

Geneformer tokenization:
  1. For each cell, rank genes by expression level (descending)
  2. Map gene names to Geneformer token IDs (Ensembl-based vocabulary)
  3. Truncate to model max length (2048 tokens)
  4. Run forward pass to get [CLS] embedding per cell

Requires: torch, transformers, anndata (install via requirements-gpu.txt)

Usage:
    python backend/scripts/run_geneformer.py --species human
    python backend/scripts/run_geneformer.py --species all
"""
from __future__ import annotations

import argparse
import json
import pickle
import sqlite3
from pathlib import Path

import anndata as ad
import numpy as np

REPO = Path(__file__).resolve().parents[1]
DATA_DIR = REPO / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"
CACHE_DIR = DATA_DIR / "scrna_cache"

MODEL_NAME = "ctheodoris/Geneformer"
MAX_INPUT_SIZE = 2048
BATCH_SIZE = 8

SPECIES_ENSEMBL_PREFIX = {
    "human": "ENSG",
    "mouse": "ENSMUSG",
    "arabidopsis": "AT",
}


def _get_token_dict() -> dict[str, int]:
    """Load Geneformer's gene-to-token mapping from the pickle dictionary."""
    try:
        from huggingface_hub import hf_hub_download
        path = hf_hub_download(MODEL_NAME, "geneformer/token_dictionary_gc104M.pkl")
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        print(f"  Warning: could not load Geneformer token dictionary: {e}")
        return {}


def _get_gene_name_to_ensembl() -> dict[str, str]:
    """Load Geneformer's gene name → Ensembl ID mapping."""
    try:
        from huggingface_hub import hf_hub_download
        path = hf_hub_download(MODEL_NAME, "geneformer/gene_name_id_dict_gc104M.pkl")
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        print(f"  Warning: could not load gene name dict: {e}")
        return {}


def tokenize_cells(
    adata: ad.AnnData,
    conn: sqlite3.Connection,
    species: str,
    token_dict: dict[str, int] | None = None,
    name_to_ensembl: dict[str, str] | None = None,
) -> tuple[list[list[int]], list[str]]:
    """Tokenize scRNA-seq cells into Geneformer format.

    For each cell: rank genes by expression, map to token IDs, truncate.
    """
    if token_dict is None:
        token_dict = _get_token_dict()
    if name_to_ensembl is None:
        name_to_ensembl = _get_gene_name_to_ensembl()

    gene_to_token = {}
    for gene_name in adata.var_names:
        gn = str(gene_name)
        ensembl = None
        if gn.startswith("ENSG"):
            ensembl = gn
        elif gn in name_to_ensembl:
            ensembl = name_to_ensembl[gn]
        elif gn.upper() in name_to_ensembl:
            ensembl = name_to_ensembl[gn.upper()]
        if ensembl and ensembl in token_dict:
            gene_to_token[gene_name] = token_dict[ensembl]

    print(f"  Mapped {len(gene_to_token)}/{adata.n_vars} genes to Geneformer tokens")

    if len(gene_to_token) < 100:
        print(f"  Warning: very few genes mapped. Embeddings may be low quality.")

    tokenized_cells = []
    cell_ids = []
    mappable_genes = [g for g in adata.var_names if g in gene_to_token]
    mappable_indices = [list(adata.var_names).index(g) for g in mappable_genes]

    for i in range(adata.n_obs):
        if hasattr(adata.X[i], "toarray"):
            expr = np.array(adata.X[i].toarray()).flatten()
        else:
            expr = np.array(adata.X[i]).flatten()

        mapped_expr = [(mappable_genes[j], expr[mappable_indices[j]])
                       for j in range(len(mappable_genes)) if expr[mappable_indices[j]] > 0]
        mapped_expr.sort(key=lambda x: -x[1])
        tokens = [gene_to_token[g] for g, _ in mapped_expr[:MAX_INPUT_SIZE]]

        if tokens:
            tokenized_cells.append(tokens)
            cell_ids.append(adata.obs_names[i])

    return tokenized_cells, cell_ids


def embed_cells(
    tokenized_cells: list[list[int]],
    device: str = "cuda",
) -> np.ndarray:
    """Run Geneformer forward pass to get per-cell embeddings."""
    import torch
    from transformers import AutoModel

    model = AutoModel.from_pretrained(MODEL_NAME, trust_remote_code=True)
    model = model.to(device)
    model.eval()

    hidden_size = model.config.hidden_size
    all_embeddings = np.zeros((len(tokenized_cells), hidden_size), dtype=np.float32)

    for batch_start in range(0, len(tokenized_cells), BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, len(tokenized_cells))
        batch_tokens = tokenized_cells[batch_start:batch_end]

        max_len = max(len(t) for t in batch_tokens)
        padded = np.zeros((len(batch_tokens), max_len), dtype=np.int64)
        attention_mask = np.zeros((len(batch_tokens), max_len), dtype=np.int64)
        for i, tokens in enumerate(batch_tokens):
            padded[i, :len(tokens)] = tokens
            attention_mask[i, :len(tokens)] = 1

        input_ids = torch.tensor(padded, device=device)
        attn = torch.tensor(attention_mask, device=device)

        with torch.no_grad():
            outputs = model(input_ids=input_ids, attention_mask=attn)
            mask = attn.unsqueeze(-1).float()
            cls_embeddings = (outputs.last_hidden_state * mask).sum(dim=1) / mask.sum(dim=1)
            cls_embeddings = cls_embeddings.cpu().numpy()
            all_embeddings[batch_start:batch_end] = cls_embeddings

        if (batch_start // BATCH_SIZE) % 50 == 0:
            print(f"  Embedded {batch_end}/{len(tokenized_cells)} cells", flush=True)

    return all_embeddings


def compute_cluster_embeddings(
    cell_embeddings: np.ndarray,
    cell_ids: list[str],
    adata: ad.AnnData,
    cluster_col: str = "cell_type",
) -> dict[str, np.ndarray]:
    """Average cell embeddings per cluster."""
    cell_to_idx = {cid: i for i, cid in enumerate(cell_ids)}
    cluster_embs = {}
    for cluster in adata.obs[cluster_col].unique():
        mask = adata.obs[cluster_col] == cluster
        indices = [cell_to_idx[cid] for cid in adata.obs_names[mask] if cid in cell_to_idx]
        if indices:
            cluster_embs[str(cluster)] = cell_embeddings[indices].mean(axis=0)
    return cluster_embs


def store_geneformer_embeddings(
    conn: sqlite3.Connection,
    species: str,
    cell_embeddings: np.ndarray,
    cell_ids: list[str],
    cluster_embeddings: dict[str, np.ndarray],
) -> dict:
    """Store Geneformer embeddings in the database."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS geneformer_cell_embeddings (
            species        TEXT NOT NULL,
            cell_id        TEXT NOT NULL,
            embedding      BLOB NOT NULL,
            model_version  TEXT,
            computed_at    TEXT,
            PRIMARY KEY (species, cell_id)
        );
        CREATE TABLE IF NOT EXISTS geneformer_cluster_embeddings (
            species        TEXT NOT NULL,
            cluster_id     TEXT NOT NULL,
            embedding      BLOB NOT NULL,
            embedding_dim  INTEGER NOT NULL,
            model_version  TEXT,
            computed_at    TEXT,
            PRIMARY KEY (species, cluster_id)
        );
    """)
    for table in ("geneformer_cell_embeddings", "geneformer_cluster_embeddings"):
        existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if "model_version" not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN model_version TEXT")
        if "computed_at" not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN computed_at TEXT")

    conn.execute("DELETE FROM geneformer_cell_embeddings WHERE species = ?", (species,))
    conn.execute("DELETE FROM geneformer_cluster_embeddings WHERE species = ?", (species,))

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        "INSERT INTO geneformer_cell_embeddings "
        "(species, cell_id, embedding, model_version, computed_at) "
        "VALUES (?, ?, ?, ?, ?)",
        [(species, cid, cell_embeddings[i].tobytes(), MODEL_NAME, now)
         for i, cid in enumerate(cell_ids)],
    )

    embedding_dim = cell_embeddings.shape[1] if cell_embeddings.size > 0 else 0
    conn.executemany(
        "INSERT INTO geneformer_cluster_embeddings "
        "(species, cluster_id, embedding, embedding_dim, model_version, computed_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(species, cid, emb.tobytes(), embedding_dim, MODEL_NAME, now)
         for cid, emb in cluster_embeddings.items()],
    )

    conn.commit()
    return {
        "n_cells_embedded": len(cell_ids),
        "n_clusters": len(cluster_embeddings),
        "embedding_dim": embedding_dim,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--species", required=True)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--device", default="cuda",
                        help="torch device (cuda or cpu)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    import torch
    if args.device == "cuda" and not torch.cuda.is_available():
        print("CUDA not available, falling back to CPU")
        args.device = "cpu"

    species_list = list(SPECIES_ENSEMBL_PREFIX.keys()) if args.species == "all" else [args.species]

    conn = sqlite3.connect(str(args.db), timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")

    token_dict = _get_token_dict()
    name_to_ensembl = _get_gene_name_to_ensembl()
    print(f"Geneformer vocabulary: {len(token_dict)} tokens, "
          f"gene name mapping: {len(name_to_ensembl)} entries")

    results = {}
    for species in species_list:
        print(f"\n{'='*60}")
        print(f"Geneformer embeddings for {species}")
        print(f"{'='*60}")

        h5ad_lookup = {
            "arabidopsis": CACHE_DIR / "arabidopsis_root.h5ad",
            "human": CACHE_DIR / "pbmc3k_processed.h5ad",
            "mouse": CACHE_DIR / "paul15.h5ad",
        }
        h5ad_path = h5ad_lookup.get(species, CACHE_DIR / f"{species}.h5ad")

        if not h5ad_path.exists():
            print(f"  No cached h5ad found at {h5ad_path}. Run fetch_scrna_data.py first.")
            continue

        adata = ad.read_h5ad(h5ad_path)
        print(f"  Loaded: {adata.n_obs} cells, {adata.n_vars} genes")

        tokenized, cell_ids = tokenize_cells(
            adata, conn, species, token_dict, name_to_ensembl)
        print(f"  Tokenized: {len(tokenized)} cells")

        if not tokenized:
            print(f"  No cells tokenized — skipping")
            continue

        if args.dry_run:
            results[species] = {"tokenized_cells": len(tokenized)}
            continue

        print(f"  Running Geneformer forward pass on {args.device}...")
        embeddings = embed_cells(tokenized, device=args.device)
        print(f"  Embeddings shape: {embeddings.shape}")

        cluster_col = "cell_type" if "cell_type" in adata.obs.columns else "louvain"
        if cluster_col not in adata.obs.columns:
            cluster_col = "leiden"
        cluster_embs = compute_cluster_embeddings(embeddings, cell_ids, adata, cluster_col)

        result = store_geneformer_embeddings(conn, species, embeddings, cell_ids, cluster_embs)
        print(f"  Stored: {result['n_cells_embedded']} cell embeddings, "
              f"{result['n_clusters']} cluster embeddings ({result['embedding_dim']}d)")
        results[species] = result

    conn.close()
    print(f"\n{json.dumps(results, indent=2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
