#!/usr/bin/env python3
"""Fetch signed TF-target edges from CollecTRI and SIGNOR via OmniPath.

These provide additional signed edges for human/mouse to expand sign coverage
beyond the existing KnockTF perturbation data and ortholog transfer.

CollecTRI: expanded signed TF-target prior knowledge with literature references
SIGNOR: causal signaling relations (transcriptional subset only)

Output: TSVs loaded directly into regulatory_evidence + interactions tables.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from external_evidence import begin_import, finish_import, gene_resolver, replace_source_evidence  # noqa: E402

DB = BACKEND / "data" / "grn.sqlite3"

OMNIPATH_BASE = "https://omnipathdb.org/interactions?"
SOURCES = {
    "collectri": {
        "url_params": "datasets=collectri&genesymbols=yes&fields=collectri_tf,extra_attrs&organisms={taxid}",
        "species": {"human": 9606, "mouse": 10090},
        "source_name": "CollecTRI",
        "source_version": "OmniPath 2026",
        "evidence_layer": "direct_signed",
    },
    "signor": {
        "url_params": "datasets=signor&genesymbols=yes&fields=extra_attrs&organisms={taxid}&types=stimulation,inhibition",
        "species": {"human": 9606, "mouse": 10090},
        "source_name": "SIGNOR",
        "source_version": "October 2026",
        "evidence_layer": "direct_signed",
    },
}


def fetch_omnipath(dataset: str, species: str) -> list[dict]:
    cfg = SOURCES[dataset]
    taxid = cfg["species"].get(species)
    if not taxid:
        return []

    url = OMNIPATH_BASE + cfg["url_params"].format(taxid=taxid) + "&license=academic"
    print(f"  Fetching {dataset} {species} from OmniPath...", flush=True)

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (grn-atlas-build)"})
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        text = resp.read().decode("utf-8")
    except Exception as e:
        print(f"  ERROR fetching {dataset} {species}: {e}")
        return []

    rows = []
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    for record in reader:
        tf = record.get("source_genesymbol", "").strip()
        target = record.get("target_genesymbol", "").strip()
        if not tf or not target:
            continue

        is_stim = record.get("is_stimulation", "0") == "1"
        is_inhib = record.get("is_inhibition", "0") == "1"

        if is_stim and not is_inhib:
            sign = "activation"
        elif is_inhib and not is_stim:
            sign = "repression"
        else:
            sign = "regulation"

        pmids = record.get("references", "")
        pmid_list = [p.strip() for p in pmids.split(";") if p.strip().isdigit()] if pmids else []

        rows.append({
            "tf_symbol": tf,
            "target_symbol": target,
            "sign": sign,
            "pmids": pmid_list,
            "record_key": f"{dataset}:{tf}:{target}:{species}",
        })

    print(f"  Got {len(rows)} edges from {dataset} {species}", flush=True)
    return rows


def load_into_db(rows: list[dict], dataset: str, species: str, conn: sqlite3.Connection) -> Counter:
    cfg = SOURCES[dataset]
    stats = Counter()
    resolve = gene_resolver(conn, species)

    run_id = begin_import(conn, cfg["source_name"], cfg["source_version"],
                          f"https://omnipathdb.org ({dataset})")

    for row in rows:
        stats["input"] += 1
        source_id = resolve(row["tf_symbol"])
        target_id = resolve(row["target_symbol"])
        if not source_id or not target_id:
            stats["unresolved"] += 1
            continue
        if source_id == target_id:
            stats["self_loop"] += 1
            continue

        stats["resolved"] += 1
        replace_source_evidence(
            conn,
            species=species,
            source_id=source_id,
            target_id=target_id,
            relation_type=row["sign"],
            evidence_layer=cfg["evidence_layer"],
            source_name=cfg["source_name"],
            source_version=cfg["source_version"],
            record_key=row["record_key"],
            confidence=0.80 if row["sign"] != "regulation" else 0.60,
            pmids=row["pmids"],
            import_run_id=run_id,
        )

        # Also promote to interactions table
        existing = conn.execute(
            "SELECT sign, sign_evidence FROM interactions WHERE source_id=? AND target_id=?",
            (source_id, target_id)
        ).fetchone()

        if existing is None:
            conn.execute(
                "INSERT OR IGNORE INTO interactions (source_id, target_id, regulation_type, confidence, sources, pmids, sign, sign_evidence) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (source_id, target_id, row["sign"], 0.80 if row["sign"] != "regulation" else 0.60,
                 cfg["source_name"], json.dumps(row["pmids"]),
                 row["sign"] if row["sign"] != "regulation" else None,
                 "measured" if row["sign"] != "regulation" else "unknown")
            )
            stats["new_edges"] += 1
        elif existing[0] is None and row["sign"] != "regulation":
            conn.execute(
                "UPDATE interactions SET sign=?, sign_evidence='measured' "
                "WHERE source_id=? AND target_id=?",
                (row["sign"], source_id, target_id)
            )
            stats["sign_added"] += 1
        else:
            stats["already_present"] += 1

    finish_import(conn, run_id, dict(stats))
    conn.commit()
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--datasets", nargs="*", default=["collectri", "signor"])
    parser.add_argument("--species", nargs="*", default=["human", "mouse"])
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.db), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    all_stats = {}
    for dataset in args.datasets:
        if dataset not in SOURCES:
            print(f"Unknown dataset: {dataset}")
            continue
        for species in args.species:
            rows = fetch_omnipath(dataset, species)
            if rows:
                stats = load_into_db(rows, dataset, species, conn)
                all_stats[f"{dataset}_{species}"] = dict(stats)
                print(f"  {dataset} {species}: {dict(stats)}", flush=True)
            else:
                all_stats[f"{dataset}_{species}"] = {"status": "no_data"}
            time.sleep(2)

    conn.close()
    print(f"\n=== Sign Expansion Results ===")
    print(json.dumps(all_stats, indent=2))


if __name__ == "__main__":
    main()
