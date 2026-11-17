#!/usr/bin/env python3
"""Content digest of the atlas database, for reproducibility checking.

Two builds of the same atlas are never byte-identical: timestamps are stored
in the data, surrogate ids depend on insertion order, and SQLite page layout
varies. This computes a digest of what the database *asserts* instead, so two
builds can be compared for content rather than bytes.

Method
    Each row is reduced to a canonical string over its non-volatile columns,
    hashed, and the row hashes are summed modulo 2**128. Summation is
    order-independent, so no ORDER BY and no large temp sort is needed - which
    matters on a database this size. Duplicate rows add rather than cancel.
    Floats are normalised to %.9g, so differences below that precision do not
    register; this is a declared tolerance, not an accident.

Volatile columns (timestamps, surrogate ids) are excluded by default and the
exclusions are listed in the report, so the digest is auditable rather than
magic.

Read-only: opens the database with mode=ro and runs only SELECTs.

Usage:
    venv/bin/python backend/scripts/content_digest.py
    venv/bin/python backend/scripts/content_digest.py --tables interactions genes
    venv/bin/python backend/scripts/content_digest.py --check backend/data/content_digest.expected.json
    venv/bin/python backend/scripts/content_digest.py --compare before.json after.json
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DB = BACKEND / "data" / "grn.sqlite3"
REPORT = BACKEND / "data" / "content_digest.json"

DIGEST_VERSION = "content-digest-v1"
FLOAT_FORMAT = ".9g"
MODULUS = 1 << 128
HASH_BYTES = 16
SEP = b"\x1f"
NULL = b"\x00NULL"

# Tables grouped by what it takes to reproduce them. A clone without a GPU or
# API keys cannot rebuild the accelerated layer, and session tables hold data a
# user imported at runtime, not atlas content - neither belongs in a
# reproducibility check of the atlas itself.
LAYERS = {
    "session": ("imported_*", "scrna_*"),
    "accelerated": ("geneformer_*", "esm2_*", "evo2_*", "alphafold_*",
                    "structural_binding_predictions", "protein_sequences",
                    "promoter_dna_sequences"),
}

# Columns whose value depends on when or in what order the build ran, not on
# what the data says. Matched case-insensitively against the column name.
VOLATILE_PATTERNS = (
    "*_at", "generated_*", "imported_*", "fetched_*", "created_*", "updated_*",
    "timestamp", "*_timestamp", "obs_id", "evidence_id", "import_run_id",
)


def layer_of(table: str) -> str:
    for layer, patterns in LAYERS.items():
        if any(fnmatch.fnmatch(table, p) for p in patterns):
            return layer
    return "core"


def is_volatile(column: str) -> bool:
    low = column.lower()
    return any(fnmatch.fnmatch(low, pat) for pat in VOLATILE_PATTERNS)


def canon(value) -> bytes:
    if value is None:
        return NULL
    if isinstance(value, float):
        return format(value, FLOAT_FORMAT).encode()
    if isinstance(value, (int,)):
        return str(value).encode()
    if isinstance(value, bytes):
        return value.hex().encode()
    return str(value).encode()


def digest_table(conn: sqlite3.Connection, table: str, columns: list[str],
                 batch: int = 50_000) -> tuple[int, str]:
    quoted = ", ".join(f'"{c}"' for c in columns)
    cur = conn.execute(f'SELECT {quoted} FROM "{table}"')
    total = 0
    acc = 0
    prefix = table.encode() + SEP
    new = hashlib.blake2b
    while True:
        chunk = cur.fetchmany(batch)
        if not chunk:
            break
        for row in chunk:
            h = new(prefix + SEP.join(canon(v) for v in row),
                    digest_size=HASH_BYTES).digest()
            acc = (acc + int.from_bytes(h, "big")) % MODULUS
        total += len(chunk)
    return total, f"{acc:032x}"


def build_report(db: Path, only: list[str] | None, exclude: list[str]) -> dict:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    if only:
        tables = [t for t in tables if t in set(only)]
    tables = [t for t in tables if not any(fnmatch.fnmatch(t, p) for p in exclude)]

    report = {
        "digest_version": DIGEST_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": str(db.resolve()),
        "sqlite_version": sqlite3.sqlite_version,
        "float_format": FLOAT_FORMAT,
        "volatile_patterns": list(VOLATILE_PATTERNS),
        "excluded_tables": exclude,
        "tables": {},
    }

    for t in tables:
        cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{t}")')]
        hashed = [c for c in cols if not is_volatile(c)]
        skipped = [c for c in cols if is_volatile(c)]
        if not hashed:
            report["tables"][t] = {"rows": None, "digest": None,
                                   "layer": layer_of(t),
                                   "note": "every column volatile; not hashed"}
            continue
        t0 = time.time()
        n, d = digest_table(conn, t, hashed)
        report["tables"][t] = {
            "rows": n, "digest": d,
            "layer": layer_of(t),
            "columns_hashed": hashed,
            "columns_excluded": skipped,
            "seconds": round(time.time() - t0, 1),
        }
        print(f"  [{layer_of(t)[:4]}] {t:<32} {n:>12,}  {d[:16]}...  "
              f"({report['tables'][t]['seconds']}s)", flush=True)

    conn.close()

    # A digest per layer, plus one over everything. The core digest is the one
    # a fresh clone should be able to match.
    report["layer_digests"] = {}
    report["layer_rows"] = {}
    for layer in sorted({m.get("layer", "core") for m in report["tables"].values()}):
        roll = hashlib.blake2b(digest_size=32)
        n = 0
        for name in sorted(report["tables"]):
            meta = report["tables"][name]
            if meta.get("layer", "core") != layer:
                continue
            roll.update(f"{name}|{meta['rows']}|{meta['digest']}".encode())
            n += meta["rows"] or 0
        report["layer_digests"][layer] = roll.hexdigest()
        report["layer_rows"][layer] = n

    roll = hashlib.blake2b(digest_size=32)
    for name in sorted(report["tables"]):
        meta = report["tables"][name]
        roll.update(f"{name}|{meta['rows']}|{meta['digest']}".encode())
    report["atlas_digest"] = roll.hexdigest()
    report["core_digest"] = report["layer_digests"].get("core")
    return report


def compare(a: dict, b: dict, layer: str | None = None) -> list[str]:
    diffs = []
    if a.get("digest_version") != b.get("digest_version"):
        diffs.append(f"digest_version: {a.get('digest_version')} -> {b.get('digest_version')}")
    ta, tb = a.get("tables", {}), b.get("tables", {})
    if layer:
        ta = {k: v for k, v in ta.items() if v.get("layer", "core") == layer}
        tb = {k: v for k, v in tb.items() if v.get("layer", "core") == layer}
    for name in sorted(set(ta) | set(tb)):
        if name not in ta:
            diffs.append(f"{name}: table added ({tb[name].get('rows'):,} rows)")
        elif name not in tb:
            diffs.append(f"{name}: table removed (was {ta[name].get('rows'):,} rows)")
        elif ta[name].get("digest") != tb[name].get("digest"):
            ra, rb = ta[name].get("rows"), tb[name].get("rows")
            if ra == rb:
                diffs.append(f"{name}: same row count ({ra:,}) but content differs")
            else:
                delta = (rb or 0) - (ra or 0)
                diffs.append(f"{name}: {ra:,} -> {rb:,} rows ({delta:+,})")
            ca = set(ta[name].get("columns_hashed") or [])
            cb = set(tb[name].get("columns_hashed") or [])
            if ca != cb:
                diffs.append(f"    schema changed: +{sorted(cb - ca)} -{sorted(ca - cb)}")
    return diffs


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=DB)
    ap.add_argument("--report", type=Path, default=REPORT)
    ap.add_argument("--tables", nargs="*", default=None,
                    help="digest only these tables")
    ap.add_argument("--exclude-table", nargs="*", default=[],
                    help="glob patterns of tables to skip")
    ap.add_argument("--check", type=Path, default=None,
                    help="compare against a committed digest; exit 1 on mismatch")
    ap.add_argument("--layer", default="core",
                    choices=["core", "accelerated", "session", "all"],
                    help="which layer --check and --compare judge (default: core)")
    ap.add_argument("--compare", nargs=2, type=Path, default=None,
                    metavar=("BEFORE", "AFTER"),
                    help="diff two existing reports and exit")
    args = ap.parse_args()

    if args.compare:
        before = json.loads(args.compare[0].read_text())
        after = json.loads(args.compare[1].read_text())
        diffs = compare(before, after, None if args.layer == "all" else args.layer)
        if not diffs:
            print("identical content: "
                  f"{before.get('atlas_digest', '')[:16]}...")
            return 0
        print(f"{len(diffs)} difference(s):\n")
        for d in diffs:
            print(f"  {d}")
        return 1

    if not args.db.exists():
        print(f"database missing: {args.db}", file=sys.stderr)
        return 1

    print(f"Digesting {args.db} ...\n")
    t0 = time.time()
    report = build_report(args.db, args.tables, args.exclude_table)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")

    rows = sum(m["rows"] or 0 for m in report["tables"].values())
    print(f"\n{len(report['tables'])} tables, {rows:,} rows, "
          f"{time.time() - t0:.0f}s")
    for layer in sorted(report["layer_digests"]):
        print(f"  {layer:<12} {report['layer_rows'][layer]:>12,} rows  "
              f"{report['layer_digests'][layer]}")
    print(f"atlas_digest: {report['atlas_digest']}")
    print(f"Report: {args.report}")

    if args.check:
        if not args.check.exists():
            print(f"\nno expected digest at {args.check}; "
                  f"commit this report there to establish the baseline")
            return 0
        expected = json.loads(args.check.read_text())
        diffs = compare(expected, report, None if args.layer == "all" else args.layer)
        if not diffs:
            print(f"\nMATCH: {args.layer} layer is identical to the expected digest")
            return 0
        print(f"\nMISMATCH ({args.layer} layer): {len(diffs)} "
              f"difference(s) from {args.check}\n")
        for d in diffs:
            print(f"  {d}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
