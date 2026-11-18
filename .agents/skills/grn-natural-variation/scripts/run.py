#!/usr/bin/env python3
"""Query promoter variant impact on TF binding sites across accessions.

Currently reports readiness and existing motif infrastructure.
Full natural-variation analysis requires a variant panel to be loaded.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[4] / "backend"
DB = BACKEND / "data" / "grn.sqlite3"


def output(data):
    print(json.dumps(data, indent=2, default=str))


def check_table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row[0] > 0


def check_readiness(conn: sqlite3.Connection) -> dict:
    tables = {
        "motifs": "JASPAR TF-motif mappings",
        "motif_hits": "Motif hits in promoter regions",
        "gene_locations": "Gene coordinates and promoter windows",
        "cis_support_scores": "Per-edge cis-regulatory support scores",
    }

    infrastructure = {}
    for table, desc in tables.items():
        exists = check_table_exists(conn, table)
        count = 0
        if exists:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        infrastructure[table] = {
            "exists": exists,
            "rows": count,
            "description": desc,
        }

    variant_tables = ["accession_variants", "variant_panel", "promoter_variants"]
    variant_status = {}
    for table in variant_tables:
        variant_status[table] = check_table_exists(conn, table)

    has_variants = any(variant_status.values())

    species_motifs = {}
    if infrastructure["motif_hits"]["exists"] and infrastructure["motif_hits"]["rows"] > 0:
        for species, count in conn.execute(
            """SELECT g.species, COUNT(DISTINCT mh.ext_gene_id)
               FROM motif_hits mh
               JOIN gene_id_crosswalk c ON c.ext_gene_id = mh.ext_gene_id
               JOIN genes g ON g.id = c.atlas_gene_id
               GROUP BY g.species"""
        ):
            species_motifs[species] = count

    return {
        "readiness": "partial" if not has_variants else "ready",
        "infrastructure": infrastructure,
        "variant_tables": variant_status,
        "has_variant_panel": has_variants,
        "species_with_motif_scans": species_motifs,
        "missing_for_full_analysis": [
            "Multi-accession variant panel (e.g. 1001 Genomes for Arabidopsis, "
            "3000 Rice Genomes for rice)",
            "Variant-to-promoter intersection pipeline",
            "Per-accession motif rescoring",
        ] if not has_variants else [],
        "workaround": (
            "Use grn-allele-affinity for single-variant rescoring against the "
            "reference. Use grn-variant-effect to check if a known variant "
            "overlaps a motif-supported site."
        ),
    }


def gene_motif_sites(conn: sqlite3.Connection, gene_id: str, species: str | None) -> dict:
    if species is None:
        row = conn.execute("SELECT species FROM genes WHERE id=?", (gene_id,)).fetchone()
        species = row[0] if row else None

    if species is None:
        return {"error": f"Gene {gene_id} not found."}

    ext_id = conn.execute(
        "SELECT ext_gene_id FROM gene_id_crosswalk WHERE atlas_gene_id=? AND species=?",
        (gene_id, species),
    ).fetchone()
    ext_gene_id = ext_id[0] if ext_id else gene_id

    hits = conn.execute(
        """SELECT motif_id, score, p_value, start, \"end\", strand
           FROM motif_hits WHERE ext_gene_id=?
           ORDER BY score DESC""",
        (ext_gene_id,),
    ).fetchall()

    motif_sites = []
    for motif_id, score, pvalue, start, end, strand in hits:
        tf_name = conn.execute(
            "SELECT tf_gene_id FROM motifs WHERE motif_id=?", (motif_id,)
        ).fetchone()
        motif_sites.append({
            "motif_id": motif_id,
            "tf_gene_id": tf_name[0] if tf_name else None,
            "score": score,
            "p_value": pvalue,
            "start": start,
            "end": end,
            "strand": strand,
        })

    loc = conn.execute(
        "SELECT chromosome, start, \"end\", strand FROM gene_locations WHERE gene_id=?",
        (gene_id,),
    ).fetchone()

    loc_dict = None
    if loc:
        chrom, gstart, gend, strand = loc
        prom_start = gstart - 2500 if strand == 1 else gend
        prom_end = gstart if strand == 1 else gend + 2500
        loc_dict = {
            "chromosome": chrom,
            "start": gstart,
            "end": gend,
            "strand": strand,
            "promoter_start": prom_start,
            "promoter_end": prom_end,
        }

    return {
        "gene_id": gene_id,
        "species": species,
        "motif_hits": len(motif_sites),
        "sites": motif_sites[:50],
        "gene_location": loc_dict,
        "note": (
            "These motif sites are potential variant impact points. When a "
            "variant panel is loaded, variants overlapping these sites will "
            "be scored for gain/loss of TF binding."
        ),
    }


def edge_motif_sites(conn: sqlite3.Connection, source_id: str, target_id: str) -> dict:
    tf_motifs = conn.execute(
        "SELECT motif_id FROM motifs WHERE tf_gene_id=?", (source_id,)
    ).fetchall()

    if not tf_motifs:
        return {
            "source_id": source_id,
            "target_id": target_id,
            "error": f"No JASPAR motifs found for TF {source_id}.",
        }

    motif_ids = [m[0] for m in tf_motifs]

    target_species = conn.execute(
        "SELECT species FROM genes WHERE id=?", (target_id,)
    ).fetchone()
    species = target_species[0] if target_species else None

    ext_id = conn.execute(
        "SELECT ext_gene_id FROM gene_id_crosswalk WHERE atlas_gene_id=? AND species=?",
        (target_id, species),
    ).fetchone() if species else None
    ext_target = ext_id[0] if ext_id else target_id

    hits = []
    for mid in motif_ids:
        for row in conn.execute(
            """SELECT score, p_value, start, "end", strand
               FROM motif_hits WHERE ext_gene_id=? AND motif_id=?""",
            (ext_target, mid),
        ):
            hits.append({
                "motif_id": mid,
                "score": row[0],
                "p_value": row[1],
                "start": row[2],
                "end": row[3],
                "strand": row[4],
            })

    cis = conn.execute(
        "SELECT cis_score, hit_count FROM cis_support_scores WHERE source_id=? AND target_id=?",
        (source_id, target_id),
    ).fetchone()

    return {
        "source_id": source_id,
        "target_id": target_id,
        "species": species,
        "tf_motifs": motif_ids,
        "motif_hits_in_target_promoter": len(hits),
        "hits": hits[:20],
        "cis_support": {"score": cis[0], "hit_count": cis[1]} if cis else None,
        "note": (
            "Each motif hit marks a site where a variant could gain or lose "
            f"binding of {source_id} to {target_id}'s promoter."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--gene-id", default=None)
    parser.add_argument("--source-id", default=None)
    parser.add_argument("--target-id", default=None)
    parser.add_argument("--species", default=None)
    parser.add_argument("--db", type=Path, default=DB)
    args = parser.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)

    if args.status:
        output(check_readiness(conn))
    elif args.source_id and args.target_id:
        output(edge_motif_sites(conn, args.source_id, args.target_id))
    elif args.gene_id:
        output(gene_motif_sites(conn, args.gene_id, args.species))
    else:
        output({"error": "Provide --status, --gene-id, or --source-id/--target-id."})

    conn.close()


if __name__ == "__main__":
    main()
