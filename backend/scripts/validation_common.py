"""Shared helpers for roadmap validation benchmarks."""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
RUNS_DIR = DATA_DIR / "validation_runs"
DB_PATH = DATA_DIR / "grn.sqlite3"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from starlette.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_runs_dir() -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)


def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def rank_of(items: Iterable[Dict[str, Any]], predicate: Callable[[Dict[str, Any]], bool]) -> Optional[int]:
    for idx, item in enumerate(items, start=1):
        if predicate(item):
            return idx
    return None


def case_result(
    case_id: str,
    title: str,
    status: str,
    metrics: Optional[Dict[str, Any]] = None,
    details: Optional[Dict[str, Any]] = None,
    notes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "case_id": case_id,
        "title": title,
        "status": status,
        "metrics": metrics or {},
        "details": details or {},
        "notes": notes or [],
    }


def benchmark_payload(
    name: str,
    milestone: str,
    description: str,
    cases: List[Dict[str, Any]],
    notes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    status_counts = {"pass": 0, "partial": 0, "fail": 0}
    for case in cases:
        status_counts[case["status"]] = status_counts.get(case["status"], 0) + 1
    overall = "pass"
    if status_counts["fail"]:
        overall = "fail"
    elif status_counts["partial"]:
        overall = "partial"
    return {
        "benchmark": name,
        "milestone": milestone,
        "description": description,
        "run_at_utc": utc_now(),
        "status": overall,
        "summary": {
            "cases_total": len(cases),
            "cases_pass": status_counts["pass"],
            "cases_partial": status_counts["partial"],
            "cases_fail": status_counts["fail"],
        },
        "cases": cases,
        "notes": notes or [],
    }


def save_benchmark(name: str, payload: Dict[str, Any]) -> Path:
    ensure_runs_dir()
    out = RUNS_DIR / f"{name}.json"
    write_json(out, payload)
    return out


def response_json(resp) -> Dict[str, Any]:
    try:
        return resp.json()
    except Exception:
        return {"raw_text": resp.text}


def top_symbols(items: Iterable[Dict[str, Any]], limit: int = 5) -> List[str]:
    out = []
    for item in items:
        symbol = item.get("symbol") or item.get("pathway_name") or item.get("gene_id") or item.get("pathway_id")
        out.append(symbol)
        if len(out) >= limit:
            break
    return out


def load_gene_symbol_map(species: Optional[str] = None) -> Dict[str, str]:
    conn = db_conn()
    try:
        query = "SELECT id, symbol FROM genes"
        params: List[Any] = []
        if species:
            query += " WHERE species = ?"
            params.append(species)
        return {row["id"]: row["symbol"] or row["id"] for row in conn.execute(query, params)}
    finally:
        conn.close()


def find_tf_with_targets(species: str, min_targets: int = 8) -> Optional[Dict[str, Any]]:
    conn = db_conn()
    try:
        row = conn.execute(
            """
            SELECT g.id, g.symbol, COUNT(*) AS n_targets
            FROM interactions i
            JOIN genes g ON g.id = i.source_id
            WHERE g.species = ? AND g.is_tf = 1
            GROUP BY g.id, g.symbol
            HAVING COUNT(*) >= ?
            ORDER BY COUNT(*) DESC
            LIMIT 1
            """,
            (species, min_targets),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def load_regulon(tf_id: str, limit: int = 16) -> List[Dict[str, Any]]:
    conn = db_conn()
    try:
        rows = conn.execute(
            """
            SELECT i.target_id, g.symbol, i.regulation_type, i.confidence
            FROM interactions i
            LEFT JOIN genes g ON g.id = i.target_id
            WHERE i.source_id = ?
            ORDER BY i.confidence DESC
            LIMIT ?
            """,
            (tf_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def synthetic_regulon_values(tf_id: str, limit: int = 12) -> Dict[str, float]:
    values: Dict[str, float] = {}
    for row in load_regulon(tf_id, limit=limit):
        reg = row["regulation_type"]
        if reg == "activation":
            values[row["target_id"]] = 2.0
        elif reg == "repression":
            values[row["target_id"]] = -2.0
        else:
            values[row["target_id"]] = 1.0
    return values


def find_pathway_by_name(name_like: str) -> Optional[Dict[str, Any]]:
    conn = db_conn()
    try:
        row = conn.execute(
            """
            SELECT p.pathway_id, p.name, COUNT(*) AS n_members
            FROM pathways p
            JOIN pathway_annotations pa ON pa.pathway_id = p.pathway_id
            WHERE LOWER(p.name) LIKE ?
            GROUP BY p.pathway_id, p.name
            ORDER BY COUNT(*) DESC
            LIMIT 1
            """,
            (f"%{name_like.lower()}%",),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def pathway_members(pathway_id: str, limit: int = 20) -> List[str]:
    conn = db_conn()
    try:
        rows = conn.execute(
            "SELECT gene_id FROM pathway_annotations WHERE pathway_id = ? LIMIT ?",
            (pathway_id, limit),
        ).fetchall()
        return [row["gene_id"] for row in rows]
    finally:
        conn.close()


def find_non_tf_to_tf_edges(species: str, min_confidence: float = 0.4, limit: int = 10) -> List[Dict[str, Any]]:
    conn = db_conn()
    try:
        rows = conn.execute(
            """
            SELECT gs.id AS source_id, gs.symbol AS source_symbol,
                   gt.id AS target_id, gt.symbol AS target_symbol,
                   i.confidence
            FROM interactions i
            JOIN genes gs ON gs.id = i.source_id
            JOIN genes gt ON gt.id = i.target_id
            WHERE gs.species = ?
              AND gs.is_tf = 0
              AND gt.is_tf = 1
              AND i.confidence >= ?
            ORDER BY i.confidence DESC
            LIMIT ?
            """,
            (species, min_confidence, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
