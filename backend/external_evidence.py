"""Normalized, source-level regulatory evidence storage and import helpers."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

VALID_LAYERS = {
    "direct_signed", "direct_unsigned", "perturbation_signed",
    "causal_signaling", "orthology_transferred",
}
VALID_RELATIONS = {"activation", "repression", "regulation"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS source_import_runs (
            import_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            source_version TEXT NOT NULL,
            source_url TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            sha256 TEXT,
            status TEXT NOT NULL,
            counts TEXT NOT NULL DEFAULT '{}',
            UNIQUE(source_name, source_version, sha256)
        );
        CREATE TABLE IF NOT EXISTS regulatory_evidence (
            evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
            species TEXT NOT NULL,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            evidence_layer TEXT NOT NULL,
            directness TEXT NOT NULL DEFAULT 'unknown',
            source_name TEXT NOT NULL,
            source_version TEXT NOT NULL,
            record_key TEXT NOT NULL,
            confidence REAL,
            context TEXT NOT NULL DEFAULT '{}',
            pmids TEXT NOT NULL DEFAULT '[]',
            metadata TEXT NOT NULL DEFAULT '{}',
            import_run_id INTEGER,
            imported_at TEXT NOT NULL,
            UNIQUE(source_name, species, record_key),
            FOREIGN KEY(source_id) REFERENCES genes(id),
            FOREIGN KEY(target_id) REFERENCES genes(id),
            FOREIGN KEY(import_run_id) REFERENCES source_import_runs(import_run_id)
        );
        CREATE INDEX IF NOT EXISTS idx_re_species_layer
            ON regulatory_evidence(species, evidence_layer);
        CREATE INDEX IF NOT EXISTS idx_re_pair
            ON regulatory_evidence(source_id, target_id);
        CREATE INDEX IF NOT EXISTS idx_re_source
            ON regulatory_evidence(source_name);
    """)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def gene_resolver(conn: sqlite3.Connection, species: str):
    """Return a strict case-insensitive symbol/ID resolver for one species."""
    exact: dict[str, str | None] = {}

    def add(label: str | None, gene_id: str) -> None:
        key = (label or "").strip().upper()
        if not key:
            return
        if key in exact and exact[key] != gene_id:
            exact[key] = None
        else:
            exact[key] = gene_id

    for gene_id, symbol in conn.execute(
        "SELECT id, symbol FROM genes WHERE species = ?", (species,)
    ):
        add(gene_id, gene_id)
        add(symbol, gene_id)
    if "gene_aliases" in {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }:
        for gene_id, alias in conn.execute(
            "SELECT ga.gene_id, ga.alias FROM gene_aliases ga "
            "JOIN genes g ON g.id = ga.gene_id WHERE g.species = ?", (species,)
        ):
            add(alias, gene_id)
    return lambda label: exact.get((label or "").strip().upper())


def begin_import(
    conn: sqlite3.Connection,
    source_name: str,
    source_version: str,
    source_url: str,
    sha256: str | None,
) -> int:
    ensure_schema(conn)
    if sha256 is None:
        existing = conn.execute(
            "SELECT import_run_id FROM source_import_runs WHERE source_name=? "
            "AND source_version=? AND sha256 IS NULL ORDER BY import_run_id DESC",
            (source_name, source_version),
        ).fetchall()
        if existing:
            import_run_id = int(existing[0][0])
            conn.execute(
                "UPDATE source_import_runs SET status='superseded' WHERE source_name=? "
                "AND source_version=? AND sha256 IS NULL AND import_run_id<>?",
                (source_name, source_version, import_run_id),
            )
            conn.execute(
                "UPDATE source_import_runs SET source_url=?,fetched_at=?,status='running',counts='{}' "
                "WHERE import_run_id=?", (source_url, utc_now(), import_run_id),
            )
            return import_run_id
    conn.execute(
        "INSERT INTO source_import_runs "
        "(source_name, source_version, source_url, fetched_at, sha256, status, counts) "
        "VALUES (?, ?, ?, ?, ?, 'running', '{}') "
        "ON CONFLICT(source_name, source_version, sha256) DO UPDATE SET "
        "source_url=excluded.source_url, fetched_at=excluded.fetched_at, status='running', counts='{}'",
        (source_name, source_version, source_url, utc_now(), sha256),
    )
    row = conn.execute(
        "SELECT import_run_id FROM source_import_runs WHERE source_name=? AND source_version=? "
        "AND sha256 IS ?", (source_name, source_version, sha256),
    ).fetchone()
    return int(row[0])


def replace_source_evidence(
    conn: sqlite3.Connection,
    source_name: str,
    source_version: str,
    import_run_id: int,
    rows: Iterable[dict],
) -> int:
    conn.execute("DELETE FROM regulatory_evidence WHERE source_name = ?", (source_name,))
    values = []
    for row in rows:
        relation = row["relation_type"]
        layer = row["evidence_layer"]
        if relation not in VALID_RELATIONS or layer not in VALID_LAYERS:
            raise ValueError(f"Invalid evidence row: relation={relation}, layer={layer}")
        values.append((
            row["species"], row["source_id"], row["target_id"], relation, layer,
            row.get("directness", "unknown"), source_name, source_version,
            row["record_key"], row.get("confidence"),
            json.dumps(row.get("context", {}), sort_keys=True),
            json.dumps(sorted(set(row.get("pmids", [])))),
            json.dumps(row.get("metadata", {}), sort_keys=True),
            import_run_id, utc_now(),
        ))
    conn.executemany(
        "INSERT INTO regulatory_evidence "
        "(species, source_id, target_id, relation_type, evidence_layer, directness, "
        "source_name, source_version, record_key, confidence, context, pmids, metadata, "
        "import_run_id, imported_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        values,
    )
    return len(values)


def finish_import(conn: sqlite3.Connection, import_run_id: int, counts: dict, status: str = "complete") -> None:
    conn.execute(
        "UPDATE source_import_runs SET status=?, counts=? WHERE import_run_id=?",
        (status, json.dumps(counts, sort_keys=True), import_run_id),
    )
    conn.commit()


def benchmark_source(conn: sqlite3.Connection, source_name: str) -> dict:
    ensure_schema(conn)
    rows = conn.execute(
        "SELECT species, source_id, target_id, relation_type FROM regulatory_evidence "
        "WHERE source_name=?", (source_name,),
    ).fetchall()
    existing = {
        (row[0], row[1]): row[2]
        for row in conn.execute("SELECT source_id, target_id, regulation_type FROM interactions")
    }
    pairs: dict[tuple[str, str, str], set[str]] = {}
    records_by_species: dict[str, int] = {}
    for species, source_id, target_id, relation in rows:
        pairs.setdefault((species, source_id, target_id), set()).add(relation)
        records_by_species[species] = records_by_species.get(species, 0) + 1
    result = {
        "source": source_name,
        "mapped_records": len(rows),
        "unique_pairs": len(pairs),
        "new_pairs": 0,
        "overlapping_pairs": 0,
        "signed_agreements": 0,
        "signed_conflicts": 0,
        "source_internal_sign_conflicts": 0,
        "existing_unsigned": 0,
        "by_species": {},
    }
    for (species, source_id, target_id), relations in pairs.items():
        bucket = result["by_species"].setdefault(
            species, {"records": records_by_species[species], "unique_pairs": 0,
                      "new_pairs": 0, "conflicts": 0, "internal_conflicts": 0}
        )
        bucket["unique_pairs"] += 1
        old = existing.get((source_id, target_id))
        if old is None:
            result["new_pairs"] += 1
            bucket["new_pairs"] += 1
        else:
            result["overlapping_pairs"] += 1
        if len(relations) != 1:
            result["source_internal_sign_conflicts"] += 1
            bucket["internal_conflicts"] += 1
            continue
        relation = next(iter(relations))
        if old is not None:
            if old not in ("activation", "repression"):
                result["existing_unsigned"] += 1
            elif old == relation:
                result["signed_agreements"] += 1
            else:
                result["signed_conflicts"] += 1
                bucket["conflicts"] += 1
    return result
