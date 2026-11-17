#!/usr/bin/env python3
"""Score projected edges with per-edge cis-regulatory support.

For each orthology-transferred edge TF→target in a plant species, checks
whether the TF's JASPAR motif appears in the target's promoter (via the
motif_hits table). Edges with a motif hit get a cis_support score; those
without stay at zero. The score is stored alongside the edge, not merged
into its confidence — the two stay separable.

This is the core of Phase 2B: giving projected edges independent evidence
in the recipient species.

Usage:
    venv/bin/python backend/scripts/score_cis_support.py
    venv/bin/python backend/scripts/score_cis_support.py --species tomato
    venv/bin/python backend/scripts/score_cis_support.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

DB = BACKEND / "data" / "grn.sqlite3"

PLANT_SPECIES = ["arabidopsis", "tomato", "petunia", "rice", "pepper", "potato"]


def ensure_cis_support_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cis_support_scores (
            species TEXT NOT NULL,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            has_motif_hit INTEGER NOT NULL DEFAULT 0,
            best_motif_score REAL,
            best_motif_pvalue REAL,
            motif_id TEXT,
            hit_count INTEGER NOT NULL DEFAULT 0,
            cis_score REAL NOT NULL DEFAULT 0.0,
            PRIMARY KEY (species, source_id, target_id),
            FOREIGN KEY(source_id) REFERENCES genes(id),
            FOREIGN KEY(target_id) REFERENCES genes(id)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_cis_species_score
            ON cis_support_scores(species, cis_score DESC)
    """)


def build_tf_motif_map(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Map gene_id → list of JASPAR motif_ids for that TF."""
    tf_motifs: dict[str, list[str]] = {}
    for tf_gene_id, motif_id in conn.execute(
        "SELECT tf_gene_id, motif_id FROM motifs WHERE tf_gene_id IS NOT NULL"
    ):
        tf_motifs.setdefault(tf_gene_id, []).append(motif_id)
    return tf_motifs


def build_crosswalk(conn: sqlite3.Connection, species: str) -> dict[str, str]:
    """Map atlas gene_id → ext_gene_id used in motif_hits."""
    crosswalk: dict[str, str] = {}
    for atlas_id, ext_id in conn.execute(
        "SELECT atlas_gene_id, ext_gene_id FROM gene_id_crosswalk WHERE species=?",
        (species,),
    ):
        crosswalk[atlas_id] = ext_id
    for gene_id, in conn.execute(
        "SELECT id FROM genes WHERE species=?", (species,),
    ):
        if gene_id not in crosswalk:
            crosswalk[gene_id] = gene_id
    return crosswalk


def build_motif_hit_index(conn: sqlite3.Connection) -> dict[tuple[str, str], tuple[float, float, int]]:
    """Index (ext_gene_id, motif_id) → (best_score, best_pvalue, hit_count)."""
    index: dict[tuple[str, str], tuple[float, float, int]] = {}
    for ext_gene_id, motif_id, score, pvalue in conn.execute(
        "SELECT ext_gene_id, motif_id, score, p_value FROM motif_hits"
    ):
        key = (ext_gene_id, motif_id)
        if key in index:
            old_score, old_pvalue, old_count = index[key]
            index[key] = (
                max(old_score, score or 0.0),
                min(old_pvalue, pvalue or 1.0),
                old_count + 1,
            )
        else:
            index[key] = (score or 0.0, pvalue or 1.0, 1)
    return index


def score_species(
    conn: sqlite3.Connection,
    species: str,
    tf_motifs: dict[str, list[str]],
    hit_index: dict[tuple[str, str], tuple[float, float, int]],
    dry_run: bool = False,
) -> dict:
    stats = Counter()
    crosswalk = build_crosswalk(conn, species)

    projected_edges = conn.execute(
        """SELECT i.source_id, i.target_id, i.sources
           FROM interactions i
           JOIN genes s ON s.id = i.source_id
           WHERE s.species = ? AND i.sources LIKE '%Inferred:%'""",
        (species,),
    ).fetchall()
    stats["projected_edges"] = len(projected_edges)

    rows = []
    for source_id, target_id, sources_json in projected_edges:
        try:
            sources = json.loads(sources_json)
        except (json.JSONDecodeError, TypeError):
            sources = []
        if not any("Inferred:" in s for s in sources):
            continue

        donor_tfs = set()
        for src in sources:
            if src.startswith("Inferred:"):
                parts = src.split(":")
                if len(parts) >= 2:
                    donor_species = parts[1]
                    donor_edges = conn.execute(
                        """SELECT i2.source_id FROM interactions i2
                           JOIN genes s2 ON s2.id = i2.source_id
                           WHERE i2.target_id = ? AND s2.species = ?""",
                        (target_id, donor_species),
                    ).fetchall()
                    for (did,) in donor_edges:
                        donor_tfs.add(did)
        donor_tfs.add(source_id)

        motif_ids = set()
        for tf in donor_tfs:
            motif_ids.update(tf_motifs.get(tf, []))

        if not motif_ids:
            stats["no_motif_for_tf"] += 1
            rows.append((species, source_id, target_id, 0, None, None, None, 0, 0.0))
            continue

        target_ext = crosswalk.get(target_id, target_id)
        best_score = None
        best_pvalue = None
        best_motif = None
        total_hits = 0

        for mid in motif_ids:
            hit = hit_index.get((target_ext, mid))
            if hit:
                score, pvalue, count = hit
                total_hits += count
                if best_score is None or score > best_score:
                    best_score = score
                    best_pvalue = pvalue
                    best_motif = mid

        if total_hits > 0:
            stats["has_motif_hit"] += 1
            cis_score = min(0.95, 0.3 + 0.1 * min(total_hits, 5) + min(best_score or 0, 20) / 100)
            rows.append((species, source_id, target_id, 1, best_score, best_pvalue, best_motif, total_hits, round(cis_score, 4)))
        else:
            stats["no_motif_hit"] += 1
            rows.append((species, source_id, target_id, 0, None, None, None, 0, 0.0))

    if rows and not dry_run:
        conn.execute("DELETE FROM cis_support_scores WHERE species=?", (species,))
        conn.executemany(
            "INSERT INTO cis_support_scores "
            "(species, source_id, target_id, has_motif_hit, best_motif_score, "
            "best_motif_pvalue, motif_id, hit_count, cis_score) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            rows,
        )
        conn.commit()

    stats["scored"] = len(rows)
    return dict(stats)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--species", nargs="*", default=PLANT_SPECIES)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.db), timeout=30)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")

    ensure_cis_support_table(conn)

    print("Building TF-motif map...", flush=True)
    tf_motifs = build_tf_motif_map(conn)
    print(f"  {len(tf_motifs)} TFs with JASPAR motifs")

    print("Building motif hit index...", flush=True)
    hit_index = build_motif_hit_index(conn)
    print(f"  {len(hit_index)} (gene, motif) pairs with hits")

    all_stats = {}
    for species in args.species:
        print(f"\n[{species}] Scoring cis-support...", flush=True)
        stats = score_species(conn, species, tf_motifs, hit_index, dry_run=args.dry_run)
        all_stats[species] = stats
        if stats.get("projected_edges", 0) > 0:
            hit_rate = stats.get("has_motif_hit", 0) / max(stats.get("scored", 1), 1)
            print(f"  {stats['projected_edges']} projected edges, "
                  f"{stats.get('has_motif_hit', 0)} with motif hits ({hit_rate:.1%})")

    conn.close()
    print(f"\n{json.dumps(all_stats, indent=2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
