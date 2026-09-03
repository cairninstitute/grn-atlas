#!/usr/bin/env python3
"""
Load TF-target interactions from ConnecTF into the GRN Atlas database.

ConnecTF (Brooks et al., Plant Physiology, 2021) aggregates experimentally
validated TF-target interactions from TARGET, ChIP-seq, and other assays.

Data source: https://connectf.s3.amazonaws.com/connectf_data_release_v1.tar.gz
Publication: PMID 33631799

This script loads:
  - Arabidopsis TARGET/DESeq2/ChIP experiments (~295K new edges from 64 TFs)
  - Rice ChIP-seq and expression experiments (~3.5K new edges from 7 TFs)

DAP-seq edges are NOT loaded here — they're already in the database via the
DAP-seq pipeline. Only non-DAP experimental edges are imported.

Usage:
    # Download the data first:
    curl -L -o /tmp/connectf_data.tar.gz \\
        https://connectf.s3.amazonaws.com/connectf_data_release_v1.tar.gz
    tar xzf /tmp/connectf_data.tar.gz -C /tmp

    cd backend
    source venv/bin/activate
    python scripts/load_connectf.py /tmp/connectf_data_release_v1

Idempotent: existing edges gain "ConnecTF" in their sources list; new edges
are inserted. Safe to re-run.
"""
import sqlite3
import csv
import json
import os
import re
import sys
from pathlib import Path
from collections import defaultdict

DB_PATH = "data/grn.sqlite3"

CONNECTF_SOURCE = "ConnecTF"
DEFAULT_CONFIDENCE = 0.70
REGULATION_TYPE = "regulation"


def parse_metadata(meta_dir):
    """Read metadata files to map data files to TF IDs and experiment types."""
    tf_map = {}
    for f in Path(meta_dir).glob("*.txt"):
        tf_id = None
        edge_type = None
        method = None
        with open(f, errors="replace") as fh:
            for line in fh:
                if line.startswith("*Transcription_Factor_ID:"):
                    tf_id = line.split(":", 1)[1].strip()
                elif line.startswith("*Edge_Type:"):
                    edge_type = line.split(":", 1)[1].strip()
                elif line.startswith("*Technology/Method:"):
                    method = line.split(":", 1)[1].strip()
        if tf_id:
            data_name = f.stem
            tf_map[data_name] = {
                "tf_id": tf_id,
                "edge_type": edge_type or "unknown",
                "method": method or "unknown",
            }
    return tf_map


def load_species_edges(data_dir, meta_dir, gene_ids, species_label):
    """Load edges from ConnecTF data files for a species."""
    tf_map = parse_metadata(meta_dir)
    edges = defaultdict(set)

    for f in sorted(Path(data_dir).glob("*.csv")):
        stem = f.stem

        # Skip DAP-seq files (already in DB)
        if "DAP" in stem.upper():
            continue

        # Find TF ID from metadata or filename
        tf_id = None
        if stem in tf_map:
            tf_id = tf_map[stem]["tf_id"]
        else:
            m = re.match(r"((?:AT[1-5CM]G\d{5})|(?:LOC_Os\d+g\d+))", stem)
            if m:
                tf_id = m.group(1)

        if not tf_id or tf_id not in gene_ids:
            continue

        with open(f) as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
            if not header:
                continue

            has_fc = len(header) > 1 and "log2fc" in header[1].lower() if len(header) > 1 else False

            for row in reader:
                if not row:
                    continue
                target = row[0].strip().strip('"')

                if species_label == "arabidopsis" and not target.startswith("AT"):
                    continue
                if species_label == "rice" and not target.startswith("LOC_Os"):
                    continue
                if target not in gene_ids:
                    continue
                if target == tf_id:
                    continue

                reg_type = REGULATION_TYPE
                if has_fc:
                    try:
                        fc = float(row[1])
                        if fc > 0:
                            reg_type = "activation"
                        elif fc < 0:
                            reg_type = "repression"
                    except (ValueError, IndexError):
                        pass

                edges[(tf_id, target)].add(reg_type)

    result = []
    for (tf, tgt), reg_types in edges.items():
        if "activation" in reg_types and "repression" in reg_types:
            reg = "regulation"
        elif "activation" in reg_types:
            reg = "activation"
        elif "repression" in reg_types:
            reg = "repression"
        else:
            reg = REGULATION_TYPE
        result.append((tf, tgt, reg))

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/load_connectf.py /path/to/connectf_data_release_v1")
        sys.exit(1)

    data_root = Path(sys.argv[1])
    if not data_root.exists():
        print(f"Error: {data_root} does not exist")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")

    # Load gene ID sets
    arab_genes = set()
    for (gid,) in conn.execute(
        "SELECT id FROM genes WHERE species = 'arabidopsis'"
    ):
        arab_genes.add(gid)

    rice_genes = set()
    for (gid,) in conn.execute(
        "SELECT id FROM genes WHERE species = 'rice'"
    ):
        rice_genes.add(gid)

    print(f"DB genes: arabidopsis={len(arab_genes):,}, rice={len(rice_genes):,}")

    # Load existing edges for duplicate detection
    existing = {}
    for row in conn.execute(
        "SELECT source_id, target_id, sources FROM interactions"
    ):
        existing[(row[0], row[1])] = json.loads(row[2])

    print(f"Existing edges: {len(existing):,}")

    total_new = 0
    total_updated = 0

    # === Arabidopsis ===
    arab_data = data_root / "arabidopsis" / "data"
    arab_meta = data_root / "arabidopsis" / "metadata"
    if arab_data.exists():
        print("\nLoading Arabidopsis ConnecTF edges...")
        arab_edges = load_species_edges(arab_data, arab_meta, arab_genes, "arabidopsis")
        print(f"  Parsed {len(arab_edges):,} unique TF-target pairs")

        new_rows = []
        update_rows = []
        for tf, tgt, reg in arab_edges:
            pair = (tf, tgt)
            if pair in existing:
                sources = existing[pair]
                if CONNECTF_SOURCE not in sources:
                    sources.append(CONNECTF_SOURCE)
                    update_rows.append((json.dumps(sources), tf, tgt))
            else:
                new_rows.append((
                    tf, tgt, reg, DEFAULT_CONFIDENCE,
                    json.dumps([CONNECTF_SOURCE]), "[]",
                ))

        if update_rows:
            conn.executemany(
                "UPDATE interactions SET sources = ? "
                "WHERE source_id = ? AND target_id = ?",
                update_rows,
            )
            total_updated += len(update_rows)

        if new_rows:
            conn.executemany(
                "INSERT INTO interactions "
                "(source_id, target_id, regulation_type, confidence, sources, pmids) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                new_rows,
            )
            total_new += len(new_rows)

        print(f"  Arabidopsis: {len(new_rows):,} new, {len(update_rows):,} updated")
    else:
        print("  Arabidopsis data not found, skipping")

    # === Rice ===
    rice_data = data_root / "rice" / "data"
    rice_meta = data_root / "rice" / "metadata"
    if rice_data.exists():
        print("\nLoading Rice ConnecTF edges...")
        rice_edges = load_species_edges(rice_data, rice_meta, rice_genes, "rice")
        print(f"  Parsed {len(rice_edges):,} unique TF-target pairs")

        new_rows = []
        update_rows = []
        for tf, tgt, reg in rice_edges:
            pair = (tf, tgt)
            if pair in existing:
                sources = existing[pair]
                if CONNECTF_SOURCE not in sources:
                    sources.append(CONNECTF_SOURCE)
                    update_rows.append((json.dumps(sources), tf, tgt))
            else:
                new_rows.append((
                    tf, tgt, reg, DEFAULT_CONFIDENCE,
                    json.dumps([CONNECTF_SOURCE]), "[]",
                ))

        if update_rows:
            conn.executemany(
                "UPDATE interactions SET sources = ? "
                "WHERE source_id = ? AND target_id = ?",
                update_rows,
            )
            total_updated += len(update_rows)

        if new_rows:
            conn.executemany(
                "INSERT INTO interactions "
                "(source_id, target_id, regulation_type, confidence, sources, pmids) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                new_rows,
            )
            total_new += len(new_rows)

        print(f"  Rice: {len(new_rows):,} new, {len(update_rows):,} updated")
    else:
        print("  Rice data not found, skipping")

    conn.commit()

    # Summary
    print(f"\n=== Summary ===")
    print(f"  New edges inserted: {total_new:,}")
    print(f"  Existing edges updated with ConnecTF source: {total_updated:,}")

    # Show new edge counts by species
    for sp in ["arabidopsis", "rice"]:
        count = conn.execute(
            "SELECT COUNT(*) FROM interactions i "
            "JOIN genes g ON g.id = i.source_id "
            "WHERE g.species = ? AND i.sources LIKE '%ConnecTF%'",
            (sp,),
        ).fetchone()[0]
        print(f"  {sp} edges with ConnecTF source: {count:,}")

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
