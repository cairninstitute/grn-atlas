"""Versioned SQLite persistence for CloneLab projects and sequence records."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from .sequence import canonical_sequence, molecule_sha256, normalize_topology, sequence_sha256

SCHEMA_VERSION = 2


class CloneLabStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def ensure_schema(self) -> None:
        with closing(self.connect()) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    darwin_context TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sequences (
                    sequence_id TEXT PRIMARY KEY,
                    project_id TEXT,
                    name TEXT NOT NULL,
                    description TEXT,
                    bases TEXT NOT NULL,
                    topology TEXT NOT NULL CHECK(topology IN ('linear', 'circular')),
                    length INTEGER NOT NULL,
                    sequence_sha256 TEXT NOT NULL,
                    molecule_sha256 TEXT NOT NULL,
                    accession TEXT,
                    source TEXT,
                    annotations TEXT NOT NULL DEFAULT '{}',
                    imported_format TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_clonelab_sequences_project
                    ON sequences(project_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_clonelab_sequences_molecule_hash
                    ON sequences(molecule_sha256);
                CREATE TABLE IF NOT EXISTS features (
                    feature_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sequence_id TEXT NOT NULL,
                    feature_type TEXT NOT NULL,
                    start_pos INTEGER NOT NULL,
                    end_pos INTEGER NOT NULL,
                    strand INTEGER,
                    parts TEXT NOT NULL DEFAULT '[]',
                    qualifiers TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(sequence_id) REFERENCES sequences(sequence_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT,
                    event_type TEXT NOT NULL,
                    object_type TEXT,
                    object_id TEXT,
                    details TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS constructs (
                    construct_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    sequence TEXT NOT NULL,
                    topology TEXT NOT NULL,
                    sequence_sha256 TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS assays (
                    assay_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    assay_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS reports (
                    report_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    output_format TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                );
            """)
            current = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
            if current is None:
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (SCHEMA_VERSION, _now()),
                )
            elif current < SCHEMA_VERSION:
                for version in range(current + 1, SCHEMA_VERSION + 1):
                    conn.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                        (version, _now()),
                    )
            elif current > SCHEMA_VERSION:
                raise RuntimeError(f"unsupported CloneLab schema version {current}; expected at most {SCHEMA_VERSION}")
            conn.commit()

    def create_project(self, name: str, description: str | None = None,
                       darwin_context: dict | None = None) -> dict:
        project_id = f"clp_{uuid.uuid4().hex[:16]}"
        now = _now()
        with closing(self.connect()) as conn:
            conn.execute(
                "INSERT INTO projects VALUES (?,?,?,?,?,?)",
                (project_id, name, description, json.dumps(darwin_context or {}, sort_keys=True), now, now),
            )
            conn.execute(
                "INSERT INTO audit_events(project_id,event_type,object_type,object_id,details,created_at) "
                "VALUES (?,?,?,?,?,?)",
                (project_id, "project_created", "project", project_id, "{}", now),
            )
            conn.commit()
        return self.get_project(project_id)

    def get_project(self, project_id: str) -> dict | None:
        with closing(self.connect()) as conn:
            row = conn.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
            if not row:
                return None
            result = dict(row)
            result["darwin_context"] = json.loads(result["darwin_context"])
            result["sequences"] = [
                self._sequence_row(record, include_bases=False, conn=conn)
                for record in conn.execute(
                    "SELECT * FROM sequences WHERE project_id=? ORDER BY created_at", (project_id,)
                ).fetchall()
            ]
            result["construct_ids"] = [row[0] for row in conn.execute(
                "SELECT construct_id FROM constructs WHERE project_id=? ORDER BY created_at", (project_id,)
            )]
            result["assay_ids"] = [row[0] for row in conn.execute(
                "SELECT assay_id FROM assays WHERE project_id=? ORDER BY created_at", (project_id,)
            )]
            result["report_ids"] = [row[0] for row in conn.execute(
                "SELECT report_id FROM reports WHERE project_id=? ORDER BY created_at", (project_id,)
            )]
            return result

    def save_sequence(self, record: dict, project_id: str | None = None) -> dict:
        sequence = canonical_sequence(record["sequence"])
        topology = normalize_topology(record.get("topology", "linear"))
        raw_hash = sequence_sha256(sequence)
        identity_hash = molecule_sha256(sequence, topology)
        sequence_id = f"cls_{uuid.uuid4().hex[:16]}"
        now = _now()
        with closing(self.connect()) as conn:
            if project_id and not conn.execute(
                "SELECT 1 FROM projects WHERE project_id=?", (project_id,)
            ).fetchone():
                raise KeyError(f"project not found: {project_id}")
            conn.execute(
                """INSERT INTO sequences
                   (sequence_id,project_id,name,description,bases,topology,length,sequence_sha256,
                    molecule_sha256,accession,source,annotations,imported_format,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    sequence_id, project_id, record.get("name") or sequence_id,
                    record.get("description"), sequence, topology, len(sequence), raw_hash,
                    identity_hash, record.get("accession"), record.get("source"),
                    json.dumps(record.get("annotations") or {}, sort_keys=True),
                    record.get("format"), now,
                ),
            )
            conn.execute("DELETE FROM features WHERE sequence_id=?", (sequence_id,))
            for feature in record.get("features", []):
                _validate_feature(feature, len(sequence))
                conn.execute(
                    """INSERT INTO features
                       (sequence_id,feature_type,start_pos,end_pos,strand,parts,qualifiers)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        sequence_id, feature.get("type", "misc_feature"), feature["start"],
                        feature["end"], feature.get("strand"),
                        json.dumps(feature.get("parts") or [], sort_keys=True),
                        json.dumps(feature.get("qualifiers") or {}, sort_keys=True),
                    ),
                )
            conn.execute(
                "INSERT INTO audit_events(project_id,event_type,object_type,object_id,details,created_at) "
                "VALUES (?,?,?,?,?,?)",
                (project_id, "sequence_imported", "sequence", sequence_id,
                 json.dumps({"sha256": raw_hash, "topology": topology}, sort_keys=True), now),
            )
            conn.commit()
        return self.get_sequence(sequence_id)

    def get_sequence(self, sequence_id: str, *, include_bases: bool = True) -> dict | None:
        with closing(self.connect()) as conn:
            row = conn.execute("SELECT * FROM sequences WHERE sequence_id=?", (sequence_id,)).fetchone()
            return self._sequence_row(row, include_bases=include_bases, conn=conn) if row else None

    def _sequence_row(self, row, *, include_bases: bool, conn: sqlite3.Connection) -> dict:
        result = dict(row)
        if not include_bases:
            result.pop("bases", None)
        else:
            result["sequence"] = result.pop("bases")
        result["annotations"] = json.loads(result["annotations"])
        features = conn.execute(
            "SELECT * FROM features WHERE sequence_id=? ORDER BY start_pos, end_pos", (result["sequence_id"],)
        ).fetchall()
        result["features"] = [
            {
                "feature_id": feature["feature_id"],
                "type": feature["feature_type"],
                "start": feature["start_pos"],
                "end": feature["end_pos"],
                "strand": feature["strand"],
                "parts": json.loads(feature["parts"]),
                "qualifiers": json.loads(feature["qualifiers"]),
            }
            for feature in features
        ]
        return result

    def save_construct(self, project_id: str, construct: dict) -> dict:
        self._require_project(project_id)
        sequence = canonical_sequence(construct["sequence"])
        topology = normalize_topology(construct.get("topology", "circular"))
        construct_id = f"clc_{uuid.uuid4().hex[:16]}"
        payload = {**construct, "sequence": sequence}
        with closing(self.connect()) as conn:
            conn.execute(
                "INSERT INTO constructs VALUES (?,?,?,?,?,?,?,?)",
                (construct_id, project_id, construct.get("label") or construct_id, sequence, topology,
                 sequence_sha256(sequence), json.dumps(payload, sort_keys=True), _now()),
            )
            conn.commit()
        return {"construct_id": construct_id, "project_id": project_id, **payload}

    def save_assay(self, project_id: str, assay: dict) -> dict:
        self._require_project(project_id)
        assay_id = f"cla_{uuid.uuid4().hex[:16]}"
        with closing(self.connect()) as conn:
            conn.execute(
                "INSERT INTO assays VALUES (?,?,?,?,?)",
                (assay_id, project_id, assay.get("assay_type", "diagnostic_digest"),
                 json.dumps(assay, sort_keys=True), _now()),
            )
            conn.commit()
        return {"assay_id": assay_id, "project_id": project_id, **assay}

    def save_report(self, project_id: str, report: dict) -> dict:
        self._require_project(project_id)
        report_id = f"clr_{uuid.uuid4().hex[:16]}"
        with closing(self.connect()) as conn:
            conn.execute(
                "INSERT INTO reports VALUES (?,?,?,?,?,?)",
                (report_id, project_id, report["format"], report["sha256"],
                 json.dumps(report, sort_keys=True), _now()),
            )
            conn.commit()
        return {"report_id": report_id, "project_id": project_id, **report}

    def _require_project(self, project_id: str) -> None:
        with closing(self.connect()) as conn:
            if not conn.execute("SELECT 1 FROM projects WHERE project_id=?", (project_id,)).fetchone():
                raise KeyError(f"project not found: {project_id}")


def _validate_feature(feature: dict, sequence_length: int) -> None:
    start, end = int(feature["start"]), int(feature["end"])
    if start < 0 or end <= start or end > sequence_length:
        raise ValueError(f"feature coordinates [{start}, {end}) are outside sequence length {sequence_length}")
    if feature.get("strand") not in (None, -1, 1):
        raise ValueError("feature strand must be -1, 1, or null")


def _now() -> str:
    return datetime.now(UTC).isoformat()
