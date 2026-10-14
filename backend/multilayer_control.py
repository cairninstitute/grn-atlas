"""Storage helpers for non-transcriptional regulatory control edges."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

VALID_LAYERS = {"protein_activity", "protein_degradation", "post_transcriptional", "complex_formation"}
VALID_SIGNS = {"activation", "repression"}


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS regulatory_layer_edges (
            species TEXT NOT NULL, source_id TEXT NOT NULL, target_id TEXT NOT NULL,
            relation_type TEXT NOT NULL, regulatory_layer TEXT NOT NULL,
            confidence REAL NOT NULL, evidence_source TEXT NOT NULL,
            pmids TEXT NOT NULL DEFAULT '[]', context TEXT NOT NULL DEFAULT '{}',
            metadata TEXT NOT NULL DEFAULT '{}', imported_at TEXT NOT NULL,
            PRIMARY KEY(species,source_id,target_id,relation_type,regulatory_layer,evidence_source)
        );
        CREATE INDEX IF NOT EXISTS idx_rle_species_layer
            ON regulatory_layer_edges(species,regulatory_layer,confidence);
    """)


def replace_source(conn: sqlite3.Connection, source_name: str, rows: list[dict]) -> int:
    ensure_schema(conn)
    conn.execute("DELETE FROM regulatory_layer_edges WHERE evidence_source=?", (source_name,))
    now = datetime.now(timezone.utc).isoformat()
    values = []
    for row in rows:
        layer = row["regulatory_layer"]
        relation = row["relation_type"]
        if layer not in VALID_LAYERS or relation not in VALID_SIGNS:
            raise ValueError(f"Unsupported multilayer edge: {layer}/{relation}")
        values.append((row["species"], row["source_id"], row["target_id"], relation,
                       layer, row["confidence"], source_name,
                       json.dumps(row.get("pmids", [])), json.dumps(row.get("context", {}), sort_keys=True),
                       json.dumps(row.get("metadata", {}), sort_keys=True), now))
    conn.executemany("INSERT INTO regulatory_layer_edges VALUES (?,?,?,?,?,?,?,?,?,?,?)", values)
    conn.commit()
    return len(values)
