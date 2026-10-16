#!/usr/bin/env python3
"""Promote high-confidence regulatory evidence into the interactions table.

Scans regulatory_evidence for direct binding and signed evidence that isn't
yet in the interactions table, and inserts or updates interactions accordingly.

Sources promoted:
  - ChIP-Atlas: direct unsigned binding (confidence ≥ 0.45)
  - TFLink small-scale: direct unsigned binding
  - CollecTRI: direct signed evidence (sign populated)
  - SIGNOR: direct signed evidence (sign populated)

DirectBinding edges are NOT promoted here — load_direct_binding.py handles
those directly to avoid double-promotion and confidence inflation.

For edges that already exist in interactions, the source label is appended
and confidence is boosted. For new edges, they're inserted with the evidence
source as their source label. Signed sources (CollecTRI, SIGNOR) populate
the sign and sign_evidence columns.

Usage:
    python backend/scripts/promote_evidence_to_interactions.py [--db backend/data/grn.sqlite3]
    python backend/scripts/promote_evidence_to_interactions.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"

PROMOTABLE_SOURCES = {
    "ChIP-Atlas": {"label": "ChIP-Atlas", "min_confidence": 0.45},
    "TFLink small-scale": {"label": "TFLink small-scale", "min_confidence": 0.50},
    "CollecTRI": {"label": "CollecTRI", "min_confidence": 0.50},
    "SIGNOR": {"label": "SIGNOR", "min_confidence": 0.50},
}

MULTI_EVIDENCE_BOOST = 0.05
SOURCE_ALIASES = {"TFLink": "TFLink small-scale"}


def _canonical_sources(raw_sources: list[str]) -> set[str]:
    return {SOURCE_ALIASES.get(source, source) for source in raw_sources}


def promote(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    stats = Counter()

    null_evidence = conn.execute(
        "SELECT COUNT(*) FROM interactions WHERE sign_evidence IS NULL"
    ).fetchone()[0]
    stats["null_sign_evidence_repaired"] = null_evidence
    if null_evidence and not dry_run:
        conn.execute(
            "UPDATE interactions SET sign_evidence = 'unknown' "
            "WHERE sign_evidence IS NULL"
        )

    pairs: dict[tuple[str, str], dict] = {}
    for source_name, cfg in PROMOTABLE_SOURCES.items():
        min_conf = cfg["min_confidence"]
        label = cfg["label"]
        rows = conn.execute(
            "SELECT source_id, target_id, relation_type, confidence "
            "FROM regulatory_evidence "
            "WHERE source_name = ? AND COALESCE(confidence, 0.60) >= ?",
            (source_name, min_conf),
        ).fetchall()
        stats[f"evidence_{source_name}"] = len(rows)

        for source_id, target_id, relation, confidence in rows:
            if source_id == target_id:
                continue
            key = (source_id, target_id)
            if key not in pairs:
                pairs[key] = {
                    "confidence": confidence or 0.50,
                    "sources": set(),
                    "signs": set(),
                }
            entry = pairs[key]
            entry["sources"].add(label)
            entry["confidence"] = max(entry["confidence"], confidence or 0.50)
            if relation in ("activation", "repression"):
                entry["signs"].add(relation)

    print(f"Candidate pairs from evidence: {len(pairs):,}")
    stats["candidate_pairs"] = len(pairs)

    new_edges = 0
    updated_edges = 0
    unchanged_edges = 0
    conflicted_pairs = 0
    signs_repaired = 0
    source_labels_normalized = 0

    for (src_id, tgt_id), entry in pairs.items():
        desired_sign = next(iter(entry["signs"])) if len(entry["signs"]) == 1 else None
        if len(entry["signs"]) > 1:
            conflicted_pairs += 1
        existing = conn.execute(
            "SELECT sources, confidence, regulation_type, sign, sign_evidence "
            "FROM interactions "
            "WHERE source_id = ? AND target_id = ?",
            (src_id, tgt_id),
        ).fetchone()

        if existing:
            raw_sources = json.loads(existing[0])
            old_sources = _canonical_sources(raw_sources)
            new_labels = entry["sources"] - old_sources
            merged = sorted(old_sources | entry["sources"])
            normalized = set(raw_sources) != old_sources
            repair_sign = desired_sign is not None and existing[3] is None
            repaired_relation = desired_sign if repair_sign else None
            clear_conflicted_type = (
                desired_sign is None
                and len(entry["signs"]) > 1
                and existing[3] is None
                and existing[2] in ("activation", "repression")
            )
            changed = bool(new_labels or normalized or repair_sign or clear_conflicted_type)
            if changed:
                new_conf = min(existing[1] + MULTI_EVIDENCE_BOOST * len(new_labels), 0.95)
                if not dry_run:
                    conn.execute(
                        "UPDATE interactions SET sources = ?, confidence = ?, "
                        "regulation_type = CASE WHEN ? IS NOT NULL THEN ? "
                        "  WHEN ? THEN 'regulation' ELSE regulation_type END, "
                        "sign = CASE WHEN sign IS NULL THEN ? ELSE sign END, "
                        "sign_evidence = CASE WHEN sign IS NULL AND ? IS NOT NULL "
                        "  THEN 'measured' ELSE COALESCE(sign_evidence, 'unknown') END "
                        "WHERE source_id = ? AND target_id = ?",
                        (
                            json.dumps(merged), round(new_conf, 4),
                            repaired_relation, repaired_relation, clear_conflicted_type,
                            desired_sign, desired_sign, src_id, tgt_id,
                        ),
                    )
                source_labels_normalized += int(normalized)
                signs_repaired += int(repair_sign)
                updated_edges += 1
            else:
                unchanged_edges += 1
        else:
            relation = desired_sign or "regulation"
            sign_evidence = "measured" if desired_sign else "unknown"
            if not dry_run:
                conn.execute(
                    "INSERT OR IGNORE INTO interactions "
                    "(source_id, target_id, regulation_type, confidence, sources, pmids, "
                    " sign, sign_evidence) "
                    "VALUES (?, ?, ?, ?, ?, '[]', ?, ?)",
                    (src_id, tgt_id, relation,
                     round(entry["confidence"], 4),
                     json.dumps(sorted(entry["sources"])),
                     desired_sign, sign_evidence),
                )
            new_edges += 1

    if not dry_run:
        conn.commit()

    stats["new_edges"] = new_edges
    stats["updated_edges"] = updated_edges
    stats["unchanged_edges"] = unchanged_edges
    stats["conflicted_pairs"] = conflicted_pairs
    stats["signs_repaired"] = signs_repaired
    stats["source_labels_normalized"] = source_labels_normalized
    return dict(stats)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would change without modifying the DB")
    args = parser.parse_args()

    with sqlite3.connect(args.db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        result = promote(conn, dry_run=args.dry_run)

    prefix = "[DRY RUN] " if args.dry_run else ""
    print(f"\n{prefix}Evidence promotion results:")
    print(f"  New edges inserted:    {result['new_edges']:,}")
    print(f"  Existing edges updated: {result['updated_edges']:,}")
    print(f"  Already present:       {result['unchanged_edges']:,}")
    for key, val in sorted(result.items()):
        if key.startswith("evidence_"):
            print(f"  {key}: {val:,}")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
