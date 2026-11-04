#!/usr/bin/env python3
"""Transfer regulatory signs from signed edges to orthologous unsigned edges.

For each unsigned edge (TF→target) in species B, look for signed edges
(TF_ortholog→target_ortholog) in species A. If found, transfer the sign
with appropriate evidence labeling.

Only transfers when:
  - Both TF and target have orthologs in the donor species
  - The donor edge has a sign from measured or perturbation evidence
  - No conflicting signs exist across donors

Usage:
    python backend/scripts/transfer_ortholog_signs.py [--db PATH] [--min-score 0.5]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DB = BACKEND / "data" / "grn.sqlite3"
SIGN_EVIDENCE_LABEL = "ortholog_transfer"
MIN_ORTHOLOG_SCORE = 0.5


def get_signed_edges(conn: sqlite3.Connection) -> dict[tuple[str, str], tuple[str, str]]:
    """Return {(source_id, target_id): (sign, sign_evidence)} for all signed edges."""
    rows = conn.execute("""
        SELECT source_id, target_id, sign, sign_evidence
        FROM interactions
        WHERE sign IN ('activation', 'repression')
          AND sign_evidence IN ('measured', 'perturbation')
    """).fetchall()
    return {(r[0], r[1]): (r[2], r[3]) for r in rows}


def get_orthologs(conn: sqlite3.Connection, min_score: float) -> dict[str, list[tuple[str, str]]]:
    """Return {gene_id: [(ortholog_id, species)]} mapping."""
    ortho: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for a, b, sp_a, sp_b, score in conn.execute(
        "SELECT gene_a, gene_b, species_a, species_b, COALESCE(score, 0.5) FROM orthologs WHERE COALESCE(score, 0.5) >= ?",
        (min_score,)
    ):
        ortho[a].append((b, sp_b))
        ortho[b].append((a, sp_a))
    return ortho


def get_gene_species(conn: sqlite3.Connection) -> dict[str, str]:
    return dict(conn.execute("SELECT id, species FROM genes").fetchall())


def main():
    parser = argparse.ArgumentParser(description="Transfer signs via ortholog edges")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--min-score", type=float, default=MIN_ORTHOLOG_SCORE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.db))
    stats = Counter()

    print("Loading signed edges...")
    signed = get_signed_edges(conn)
    print(f"  {len(signed)} signed edges (measured + perturbation)")

    print("Loading orthologs...")
    orthologs = get_orthologs(conn, args.min_score)
    print(f"  {len(orthologs)} genes with ortholog mappings")

    print("Loading gene species...")
    gene_species = get_gene_species(conn)

    print("Loading unsigned edges...")
    unsigned = conn.execute("""
        SELECT source_id, target_id, rowid
        FROM interactions
        WHERE (sign IS NULL OR sign = '')
    """).fetchall()
    print(f"  {len(unsigned)} unsigned edges to check")

    print("\nTransferring signs...")
    updates = []

    for source_id, target_id, rowid in unsigned:
        stats["checked"] += 1

        source_orthologs = orthologs.get(source_id, [])
        target_orthologs = orthologs.get(target_id, [])

        if not source_orthologs or not target_orthologs:
            stats["no_orthologs"] += 1
            continue

        donor_signs: dict[str, list[str]] = defaultdict(list)

        for src_orth, src_sp in source_orthologs:
            for tgt_orth, tgt_sp in target_orthologs:
                if src_sp != tgt_sp:
                    continue
                key = (src_orth, tgt_orth)
                if key in signed:
                    sign, evidence = signed[key]
                    donor_signs[sign].append(f"{src_sp}:{src_orth}->{tgt_orth}")

        if not donor_signs:
            stats["no_signed_donor"] += 1
            continue

        if len(donor_signs) > 1:
            stats["conflicting"] += 1
            continue

        sign = list(donor_signs.keys())[0]
        donors = donor_signs[sign]
        n_donors = len(donors)

        updates.append((sign, SIGN_EVIDENCE_LABEL, json.dumps(donors[:5]), rowid))
        stats[f"transferred_{sign}"] += 1
        stats["transferred_total"] += 1

        if stats["checked"] % 200000 == 0:
            print(f"  [{stats['checked']}/{len(unsigned)}] transferred: {stats['transferred_total']}")

    print(f"\n  Checked: {stats['checked']}")
    print(f"  No orthologs: {stats['no_orthologs']}")
    print(f"  No signed donor: {stats['no_signed_donor']}")
    print(f"  Conflicting: {stats['conflicting']}")
    print(f"  Transferred activation: {stats.get('transferred_activation', 0)}")
    print(f"  Transferred repression: {stats.get('transferred_repression', 0)}")
    print(f"  Total transferred: {stats['transferred_total']}")

    if args.dry_run:
        print("\n  DRY RUN — no changes applied")
    else:
        print(f"\n  Applying {len(updates)} sign transfers...")
        conn.executemany(
            "UPDATE interactions SET sign = ?, sign_evidence = ?, sign_r = NULL WHERE rowid = ?",
            [(sign, ev, rowid) for sign, ev, _donors, rowid in updates]
        )
        conn.commit()
        print("  Done.")

    # Final sign distribution
    print("\nFinal sign distribution:")
    for sign, ev, count in conn.execute("""
        SELECT sign, sign_evidence, COUNT(*)
        FROM interactions
        WHERE sign IS NOT NULL AND sign != ''
        GROUP BY sign, sign_evidence
        ORDER BY COUNT(*) DESC
    """):
        print(f"  {sign} ({ev}): {count:,}")

    unsigned_remaining = conn.execute(
        "SELECT COUNT(*) FROM interactions WHERE sign IS NULL OR sign = ''"
    ).fetchone()[0]
    print(f"\n  Unsigned remaining: {unsigned_remaining:,}")

    conn.close()
    print(json.dumps(dict(stats), indent=2))


if __name__ == "__main__":
    main()
