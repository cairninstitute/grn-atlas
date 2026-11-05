#!/usr/bin/env python3
"""Fetch and process public scRNA-seq datasets for cell-type regulation analysis.

Downloads well-annotated scRNA-seq datasets and stores them in the atlas
as cell-type-resolved expression profiles with TF activity scores.

Datasets:
  - Human PBMC 3K (10x Genomics via scanpy)
  - Mouse Tabula Muris (Figshare per-tissue h5ad)
  - Arabidopsis root (Denyer et al. 2019 from GEO)

Usage:
    python backend/scripts/fetch_scrna_data.py --species all
    python backend/scripts/fetch_scrna_data.py --species human
    python backend/scripts/fetch_scrna_data.py --species arabidopsis --db backend/data/grn.sqlite3
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import sqlite3
import tempfile
import urllib.request
from pathlib import Path

import anndata as ad
import numpy as np
import scanpy as sc

REPO = Path(__file__).resolve().parents[1]
DATA_DIR = REPO / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"
CACHE_DIR = DATA_DIR / "scrna_cache"

DATASETS = {
    "human": {
        "name": "PBMC 3K (10x Genomics)",
        "species": "human",
        "tissue": "peripheral blood",
        "source": "scanpy_builtin",
        "citation": "Zheng et al. 2017, Nature Communications",
    },
    "mouse": {
        "name": "Paul15 Mouse Hematopoiesis",
        "species": "mouse",
        "tissue": "bone marrow",
        "source": "scanpy_builtin",
        "citation": "Paul et al. 2015, Cell",
    },
    "arabidopsis": {
        "name": "Root Atlas (Denyer et al. 2019)",
        "species": "arabidopsis",
        "tissue": "root",
        "source": "geo_csv",
        "geo_accession": "GSE123818",
        "counts_url": "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE123nnn/GSE123818/suppl/GSE123818_Root_single_cell_wt_datamatrix.csv.gz",
        "citation": "Denyer et al. 2019, Developmental Cell",
    },
}


def _ensure_cache():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _download(url: str, dest: Path, label: str = "") -> Path:
    if dest.exists():
        print(f"  Using cached {dest.name}")
        return dest
    print(f"  Downloading {label or url}...")
    urllib.request.urlretrieve(url, str(dest))
    size_mb = dest.stat().st_size / 1024 / 1024
    print(f"  Downloaded {size_mb:.1f} MB")
    return dest


def fetch_human() -> ad.AnnData:
    """Fetch PBMC 3K processed dataset via scanpy."""
    print("[human] Fetching PBMC 3K...")
    cache_path = CACHE_DIR / "pbmc3k_processed.h5ad"
    if cache_path.exists():
        print("  Using cached pbmc3k_processed.h5ad")
        return ad.read_h5ad(cache_path)

    adata = sc.datasets.pbmc3k_processed()
    adata.write_h5ad(cache_path)
    print(f"  {adata.n_obs} cells, {adata.n_vars} genes")
    return adata


def fetch_mouse() -> ad.AnnData:
    """Fetch Paul15 mouse hematopoiesis dataset via scanpy."""
    print("[mouse] Fetching Paul15 hematopoiesis...")
    cache_path = CACHE_DIR / "paul15.h5ad"
    if cache_path.exists():
        print("  Using cached paul15.h5ad")
        return ad.read_h5ad(cache_path)

    adata = sc.datasets.paul15()
    if "paul15_clusters" in adata.obs.columns:
        adata.obs["cell_type"] = adata.obs["paul15_clusters"]
    elif "louvain" not in adata.obs.columns:
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)
        sc.pp.highly_variable_genes(adata, n_top_genes=2000)
        sc.pp.pca(adata)
        sc.pp.neighbors(adata)
        sc.tl.leiden(adata, resolution=0.6)
        adata.obs["cell_type"] = adata.obs["leiden"]
    adata.write_h5ad(cache_path)
    print(f"  {adata.n_obs} cells, {adata.n_vars} genes")
    return adata


def fetch_arabidopsis() -> ad.AnnData:
    """Fetch Denyer et al. 2019 root atlas from GEO."""
    cfg = DATASETS["arabidopsis"]
    print(f"[arabidopsis] Fetching {cfg['name']}...")
    cache_path = CACHE_DIR / "GSE123818_Root_wt.csv.gz"
    _download(cfg["counts_url"], cache_path, "GEO counts matrix")

    h5ad_cache = CACHE_DIR / "arabidopsis_root.h5ad"
    if h5ad_cache.exists():
        print("  Using cached arabidopsis_root.h5ad")
        return ad.read_h5ad(h5ad_cache)

    print("  Parsing count matrix (streaming)...")
    import csv
    from scipy import sparse

    with gzip.open(cache_path, "rt") as f:
        reader = csv.reader(f)
        header = next(reader)
        cell_ids = header[1:] if header[0] == "" or header[0].lower() in ("gene", "gene_id", "") else header

        genes = []
        row_indices = []
        col_indices = []
        values = []
        for gene_idx, row in enumerate(reader):
            if not row:
                continue
            genes.append(row[0])
            for cell_idx, val_str in enumerate(row[1:]):
                val = float(val_str)
                if val > 0:
                    row_indices.append(cell_idx)
                    col_indices.append(gene_idx)
                    values.append(val)
            if gene_idx % 5000 == 0:
                print(f"    Parsed {gene_idx} genes...", flush=True)

    n_cells = len(cell_ids)
    n_genes = len(genes)
    X = sparse.csr_matrix(
        (values, (row_indices, col_indices)),
        shape=(n_cells, n_genes), dtype=np.float32,
    )
    adata = ad.AnnData(
        X=X,
        obs={"cell_id": cell_ids},
        var={"gene_id": genes},
    )
    adata.obs_names = cell_ids
    adata.var_names = genes

    print(f"  {adata.n_obs} cells, {adata.n_vars} genes")
    print("  Running basic QC and clustering...")
    sc.pp.filter_cells(adata, min_genes=200)
    sc.pp.filter_genes(adata, min_cells=10)
    adata.layers["counts"] = adata.X.copy()
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    sc.pp.highly_variable_genes(adata, n_top_genes=2000)
    hvg_mask = adata.var["highly_variable"].values
    from sklearn.decomposition import TruncatedSVD
    from sklearn.cluster import MiniBatchKMeans
    svd = TruncatedSVD(n_components=20, random_state=42)
    X_pca = svd.fit_transform(adata.X[:, hvg_mask])
    km = MiniBatchKMeans(n_clusters=12, random_state=42, batch_size=500)
    adata.obs["leiden"] = km.fit_predict(X_pca).astype(str)

    ROOT_MARKERS = {
        "epidermis": ["AT1G79840", "AT3G54220"],
        "cortex": ["AT5G44610", "AT3G22120"],
        "endodermis": ["AT4G37490", "AT3G54220"],
        "stele": ["AT1G62500", "AT5G12870"],
        "meristem": ["AT4G37490", "AT5G17300"],
    }

    cluster_labels = {}
    for cluster in adata.obs["leiden"].unique():
        mask = adata.obs["leiden"] == cluster
        cluster_data = adata[mask]
        best_score = -1
        best_type = f"cluster_{cluster}"
        for cell_type, markers in ROOT_MARKERS.items():
            present = [m for m in markers if m in adata.var_names]
            if present:
                if hasattr(cluster_data.X, "toarray"):
                    expr = cluster_data[:, present].X.toarray().mean()
                else:
                    expr = cluster_data[:, present].X.mean()
                if expr > best_score:
                    best_score = expr
                    best_type = cell_type
        cluster_labels[cluster] = best_type

    adata.obs["cell_type"] = adata.obs["leiden"].map(cluster_labels)
    adata.write_h5ad(h5ad_cache)
    return adata


FETCHERS = {
    "human": fetch_human,
    "mouse": fetch_mouse,
    "arabidopsis": fetch_arabidopsis,
}


def get_gene_id_mapping(conn: sqlite3.Connection, species: str) -> dict[str, str]:
    """Map gene symbols to gene IDs in the atlas."""
    rows = conn.execute(
        "SELECT id, symbol FROM genes WHERE species = ?", (species,)
    ).fetchall()
    mapping = {}
    for gid, symbol in rows:
        mapping[gid] = gid
        if symbol:
            mapping[symbol.upper()] = gid
            mapping[symbol] = gid
    return mapping


def compute_cluster_profiles(
    adata: ad.AnnData, species: str, gene_mapping: dict[str, str],
    cluster_col: str = "cell_type",
) -> tuple[list[dict], list[dict]]:
    """Compute per-cluster mean expression profiles for atlas genes."""
    if cluster_col not in adata.obs.columns:
        for fallback in ["leiden", "louvain", "cluster"]:
            if fallback in adata.obs.columns:
                cluster_col = fallback
                break

    clusters = adata.obs[cluster_col].unique()
    cluster_info = []
    expression_profiles = []

    for cluster in sorted(clusters, key=str):
        mask = adata.obs[cluster_col] == cluster
        n_cells = int(mask.sum())
        cluster_data = adata[mask]

        if hasattr(cluster_data.X, "toarray"):
            mean_expr = np.array(cluster_data.X.toarray().mean(axis=0)).flatten()
        else:
            mean_expr = np.array(cluster_data.X.mean(axis=0)).flatten()

        cluster_info.append({
            "cluster_id": str(cluster),
            "cluster_name": str(cluster),
            "n_cells": n_cells,
        })

        seen_in_cluster: dict[str, float] = {}
        for i, gene_name in enumerate(adata.var_names):
            gene_id = gene_mapping.get(gene_name) or gene_mapping.get(str(gene_name).upper())
            if gene_id and mean_expr[i] > 0.01:
                seen_in_cluster[gene_id] = max(
                    seen_in_cluster.get(gene_id, 0.0), float(mean_expr[i]))
        for gene_id, expr_val in seen_in_cluster.items():
            expression_profiles.append({
                "gene_id": gene_id,
                "cluster_id": str(cluster),
                "mean_expression": round(expr_val, 4),
            })

    return cluster_info, expression_profiles


def store_scrna_data(
    conn: sqlite3.Connection, species: str, dataset_cfg: dict,
    adata: ad.AnnData, cluster_info: list[dict],
    expression_profiles: list[dict],
) -> dict:
    """Store scRNA-seq data in the atlas database."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scrna_datasets (
            dataset_id    TEXT PRIMARY KEY,
            name          TEXT NOT NULL,
            species       TEXT NOT NULL,
            tissue        TEXT,
            n_cells       INTEGER NOT NULL,
            n_genes       INTEGER NOT NULL,
            n_clusters    INTEGER NOT NULL,
            citation      TEXT,
            source        TEXT,
            metadata      TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS scrna_clusters (
            dataset_id   TEXT NOT NULL,
            cluster_id   TEXT NOT NULL,
            cluster_name TEXT,
            n_cells      INTEGER NOT NULL DEFAULT 0,
            metadata     TEXT,
            PRIMARY KEY (dataset_id, cluster_id),
            FOREIGN KEY (dataset_id) REFERENCES scrna_datasets(dataset_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS scrna_cluster_expression (
            dataset_id   TEXT NOT NULL,
            cluster_id   TEXT NOT NULL,
            gene_id      TEXT NOT NULL,
            mean_expression REAL NOT NULL,
            PRIMARY KEY (dataset_id, cluster_id, gene_id),
            FOREIGN KEY (dataset_id) REFERENCES scrna_datasets(dataset_id)
        )
    """)

    dataset_id = f"scrna_{species}"
    conn.execute("DELETE FROM scrna_cluster_expression WHERE dataset_id = ?", (dataset_id,))
    conn.execute("DELETE FROM scrna_clusters WHERE dataset_id = ?", (dataset_id,))
    conn.execute("DELETE FROM scrna_datasets WHERE dataset_id = ?", (dataset_id,))

    conn.execute(
        "INSERT INTO scrna_datasets "
        "(dataset_id, name, species, tissue, n_cells, n_genes, n_clusters, citation, source) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (dataset_id, dataset_cfg["name"], species, dataset_cfg.get("tissue"),
         adata.n_obs, adata.n_vars, len(cluster_info),
         dataset_cfg.get("citation"), dataset_cfg.get("source")),
    )

    conn.executemany(
        "INSERT INTO scrna_clusters (dataset_id, cluster_id, cluster_name, n_cells) "
        "VALUES (?, ?, ?, ?)",
        [(dataset_id, c["cluster_id"], c["cluster_name"], c["n_cells"])
         for c in cluster_info],
    )

    conn.executemany(
        "INSERT INTO scrna_cluster_expression "
        "(dataset_id, cluster_id, gene_id, mean_expression) "
        "VALUES (?, ?, ?, ?)",
        [(dataset_id, p["cluster_id"], p["gene_id"], p["mean_expression"])
         for p in expression_profiles],
    )

    conn.commit()
    return {
        "dataset_id": dataset_id,
        "n_cells": adata.n_obs,
        "n_genes": adata.n_vars,
        "n_clusters": len(cluster_info),
        "n_expression_profiles": len(expression_profiles),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--species", required=True,
                        help="Species to fetch (human, mouse, arabidopsis, or 'all')")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    _ensure_cache()
    species_list = list(FETCHERS.keys()) if args.species == "all" else [args.species]

    conn = sqlite3.connect(str(args.db), timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")

    results = {}
    for species in species_list:
        if species not in FETCHERS:
            print(f"Unknown species: {species}")
            continue

        print(f"\n{'='*60}")
        print(f"Fetching scRNA-seq data for {species}")
        print(f"{'='*60}")

        adata = FETCHERS[species]()
        print(f"  Loaded: {adata.n_obs} cells, {adata.n_vars} genes")

        gene_mapping = get_gene_id_mapping(conn, species)
        print(f"  Gene mapping: {len(gene_mapping)} entries")

        cluster_col = "cell_type" if "cell_type" in adata.obs.columns else None
        if cluster_col is None:
            for col in ["louvain", "leiden", "cluster", "celltype"]:
                if col in adata.obs.columns:
                    cluster_col = col
                    break

        if cluster_col is None:
            print(f"  No cluster column found. Running leiden clustering...")
            if "neighbors" not in adata.uns:
                sc.pp.neighbors(adata)
            sc.tl.leiden(adata, resolution=0.6)
            cluster_col = "leiden"

        print(f"  Using cluster column: {cluster_col}")
        cluster_info, expr_profiles = compute_cluster_profiles(
            adata, species, gene_mapping, cluster_col)
        print(f"  Clusters: {len(cluster_info)}")
        print(f"  Expression profiles (gene × cluster): {len(expr_profiles):,}")

        if not args.dry_run:
            result = store_scrna_data(
                conn, species, DATASETS[species], adata, cluster_info, expr_profiles)
            print(f"  Stored: {result['n_expression_profiles']:,} profiles")
            results[species] = result
        else:
            results[species] = {
                "n_cells": adata.n_obs, "n_clusters": len(cluster_info),
                "n_profiles": len(expr_profiles),
            }

    conn.close()
    print(f"\n{'='*60}")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
