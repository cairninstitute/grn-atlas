#!/usr/bin/env python3
"""Benchmark bounded feedback analysis at increasing signed-edge volumes."""

from __future__ import annotations

import argparse
import csv
import json
import math
import resource
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from feedback_control import FeedbackParameters, analyze_feedback  # noqa: E402


def _schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        PRAGMA temp_store=MEMORY;
        CREATE TABLE genes (
            id TEXT PRIMARY KEY, symbol TEXT, name TEXT, species TEXT, is_tf INTEGER
        );
        CREATE TABLE interactions (
            source_id TEXT, target_id TEXT, regulation_type TEXT, confidence REAL,
            sources TEXT, pmids TEXT, sign TEXT, sign_evidence TEXT, sign_r REAL,
            PRIMARY KEY (source_id, target_id)
        );
    """)


def _insert_edges(conn: sqlite3.Connection, node_count: int, edge_count: int) -> None:
    core_size = min(500, node_count // 4)
    inserted = 0
    batch: list[tuple[object, ...]] = []

    def add(source: int, target: int, ordinal: int) -> None:
        nonlocal inserted
        sign = "repression" if ordinal % 3 == 0 else "activation"
        batch.append((
            f"G{source:06d}", f"G{target:06d}", sign, 0.75 + (ordinal % 20) / 100,
            '["synthetic-benchmark"]', "[]", sign, "measured", None,
        ))
        inserted += 1
        if len(batch) >= 50_000:
            conn.executemany("INSERT INTO interactions VALUES (?,?,?,?,?,?,?,?,?)", batch)
            batch.clear()

    # Seed short circuits, then add a bounded strongly connected core to exercise
    # classification, circuit search, and controller analysis at every scale.
    for source in range(min(12, core_size)):
        if inserted >= edge_count:
            break
        add(source, source, inserted)
    for source in range(core_size):
        for step in (1, 7, 31):
            if inserted >= edge_count:
                break
            add(source, (source + step) % core_size, inserted)

    # Remaining edges form a DAG. This stresses loading/SCC scale without creating
    # an unrealistically enormous feedback core that dominates the volume test.
    dag_start = core_size
    distance = 1
    while inserted < edge_count:
        added_this_distance = 0
        for source in range(dag_start, node_count - distance):
            if inserted >= edge_count:
                break
            add(source, source + distance, inserted)
            added_this_distance += 1
        if added_this_distance == 0:
            raise RuntimeError("node_count is too small for the requested unique edge count")
        distance += 1
    if batch:
        conn.executemany("INSERT INTO interactions VALUES (?,?,?,?,?,?,?,?,?)", batch)


def run_worker(edge_count: int, node_count: int) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="grn-feedback-benchmark-") as directory:
        database = Path(directory) / "benchmark.sqlite3"
        conn = sqlite3.connect(database)
        _schema(conn)
        conn.executemany(
            "INSERT INTO genes VALUES (?,?,?,?,?)",
            ((f"G{i:06d}", f"G{i:06d}", f"Synthetic gene {i}", "benchmark", int(i < 500))
             for i in range(node_count)),
        )
        build_start = time.perf_counter()
        _insert_edges(conn, node_count, edge_count)
        conn.commit()
        build_seconds = time.perf_counter() - build_start
        analysis_start = time.perf_counter()
        result = analyze_feedback(
            conn,
            "benchmark",
            FeedbackParameters(
                max_cores=20,
                max_circuits=50,
                circuits_per_core=12,
                max_search_states=100_000,
                max_controllers=30,
            ),
        )
        analysis_seconds = time.perf_counter() - analysis_start
        peak_rss_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return {
            "nodes": node_count,
            "edges": edge_count,
            "build_seconds": round(build_seconds, 3),
            "analysis_seconds": round(analysis_seconds, 3),
            "peak_rss_mib": round(peak_rss_kib / 1024, 1),
            "feedback_cores": result["summary"]["feedback_cores"],
            "feedback_genes": result["summary"]["feedback_genes"],
            "circuits_returned": result["summary"]["circuits_returned"],
            "search_truncated": result["truncation"]["search"],
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-edges", type=int, default=25_000)
    parser.add_argument("--scales", type=int, nargs="+", default=[1, 10, 100])
    parser.add_argument("--nodes", type=int, default=50_000)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--edges", type=int)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(run_worker(args.edges, args.nodes)))
        return

    rows = []
    for scale in args.scales:
        edge_count = args.base_edges * scale
        minimum_nodes = math.ceil(math.sqrt(2 * edge_count)) + 500
        node_count = max(args.nodes, minimum_nodes)
        completed = subprocess.run(
            [sys.executable, __file__, "--worker", "--edges", str(edge_count),
             "--nodes", str(node_count)],
            check=True,
            capture_output=True,
            text=True,
        )
        row = json.loads(completed.stdout)
        row["scale"] = scale
        rows.append(row)
        print(json.dumps(row, sort_keys=True), flush=True)

    payload = {"algorithm": "bounded-feedback-control", "results": rows}
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2) + "\n")
    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["scale", *[key for key in rows[0] if key != "scale"]],
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    main()
