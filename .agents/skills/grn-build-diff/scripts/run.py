#!/usr/bin/env python3
"""Compare two atlas builds: what changed, and which source caused it.

Pure file-based comparison of content_digest.py reports and, optionally,
export_source_lock.py lock files. No database or server access.
"""
import argparse
import json
import sys
from pathlib import Path


def output(data):
    print(json.dumps(data, indent=2, default=str))


def load_json(path: Path, label: str) -> dict | None:
    if not path.exists():
        output({"error": f"{label} not found: {path}"})
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        output({"error": f"{label} is not valid JSON: {path} ({e})"})
        return None


def diff_digests(before: dict, after: dict) -> dict:
    tables_before = before.get("tables", {}) or {}
    tables_after = after.get("tables", {}) or {}

    names_before = set(tables_before)
    names_after = set(tables_after)

    tables_added = sorted(names_after - names_before)
    tables_removed = sorted(names_before - names_after)
    tables_in_both = names_before & names_after

    tables_changed = sorted(
        name for name in tables_in_both
        if tables_before[name].get("digest") != tables_after[name].get("digest")
    )

    row_changes = {}
    for name in sorted(names_before | names_after):
        rb = tables_before.get(name, {}).get("rows")
        ra = tables_after.get(name, {}).get("rows")
        if name in tables_changed or name in tables_added or name in tables_removed:
            delta = None
            if isinstance(rb, (int, float)) and isinstance(ra, (int, float)):
                delta = ra - rb
            row_changes[name] = {"before": rb, "after": ra, "delta": delta}

    return {
        "tables_changed": tables_changed,
        "tables_added": tables_added,
        "tables_removed": tables_removed,
        "row_changes": row_changes,
    }


def diff_locks(lock_before: dict, lock_after: dict) -> dict:
    sources_before = lock_before.get("sources", {}) or {}
    sources_after = lock_after.get("sources", {}) or {}

    keys_before = set(sources_before)
    keys_after = set(sources_after)

    sources_added = sorted(keys_after - keys_before)
    sources_removed = sorted(keys_before - keys_after)
    sources_drifted = sorted(
        key for key in (keys_before & keys_after)
        if sources_before[key].get("sha256") != sources_after[key].get("sha256")
    )

    return {
        "sources_drifted": sources_drifted,
        "sources_added": sources_added,
        "sources_removed": sources_removed,
    }


def build_summary(result: dict, lock_checked: bool) -> str:
    parts = []
    n_changed = len(result["tables_changed"])
    n_added = len(result["tables_added"])
    n_removed = len(result["tables_removed"])
    if n_changed or n_added or n_removed:
        bits = []
        if n_changed:
            bits.append(f"{n_changed} table(s) changed")
        if n_added:
            bits.append(f"{n_added} table(s) added")
        if n_removed:
            bits.append(f"{n_removed} table(s) removed")
        parts.append(", ".join(bits))
    else:
        parts.append("no table content changes")

    if lock_checked:
        n_drift = len(result["sources_drifted"])
        n_src_added = len(result["sources_added"])
        n_src_removed = len(result["sources_removed"])
        if n_drift or n_src_added or n_src_removed:
            bits = []
            if n_drift:
                bits.append(f"{n_drift} source(s) drifted: {', '.join(result['sources_drifted'])}")
            if n_src_added:
                bits.append(f"{n_src_added} source(s) added")
            if n_src_removed:
                bits.append(f"{n_src_removed} source(s) removed")
            parts.append("; ".join(bits))
        else:
            parts.append("no source drift")
    else:
        parts.append("source drift not checked (no --lock-before/--lock-after given)")

    return "; ".join(parts) + "."


def main():
    parser = argparse.ArgumentParser(
        description="Compare two atlas builds to find what changed and which source caused it")
    parser.add_argument("--before", required=True, type=Path,
                        help="older content_digest.py JSON report")
    parser.add_argument("--after", required=True, type=Path,
                        help="newer content_digest.py JSON report")
    parser.add_argument("--lock-before", type=Path, default=None,
                        help="older export_source_lock.py sources.lock.json")
    parser.add_argument("--lock-after", type=Path, default=None,
                        help="newer export_source_lock.py sources.lock.json")
    args = parser.parse_args()

    before = load_json(args.before, "--before")
    after = load_json(args.after, "--after")

    result = diff_digests(before, after)

    lock_checked = bool(args.lock_before and args.lock_after)
    if args.lock_before and not args.lock_after:
        output({"error": "--lock-before given without --lock-after; provide both or neither"})
        sys.exit(1)
    if args.lock_after and not args.lock_before:
        output({"error": "--lock-after given without --lock-before; provide both or neither"})
        sys.exit(1)

    if lock_checked:
        lock_before = load_json(args.lock_before, "--lock-before")
        lock_after = load_json(args.lock_after, "--lock-after")
        result.update(diff_locks(lock_before, lock_after))
    else:
        result["sources_drifted"] = []
        result["sources_added"] = []
        result["sources_removed"] = []

    result["summary"] = build_summary(result, lock_checked)

    output(result)


if __name__ == "__main__":
    main()
