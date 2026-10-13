#!/usr/bin/env python3
"""Fetch and ingest source-level signed regulatory evidence without auto-promotion."""

from __future__ import annotations

import argparse
import csv
import io
import json
import shutil
import sqlite3
import sys
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from external_evidence import (  # noqa: E402
    begin_import, benchmark_source, file_sha256, finish_import, gene_resolver,
    replace_source_evidence,
)

DATA_DIR = BACKEND / "data" / "external_sources"
DEFAULT_DB = BACKEND / "data" / "grn.sqlite3"
SOURCES = {
    "collectri": {
        "name": "CollecTRI", "version": "OmniPath current",
        "url": "https://omnipathdb.org/interactions?datasets=collectri&organisms=9606&format=tsv&genesymbols=1&fields=sources%2Creferences%2Ccuration_effort",
        "file": "collectri_human.tsv",
    },
    "signor": {
        "name": "SIGNOR", "version": "October 2026",
        "url": "https://signor.uniroma2.it/scripts/downloadTranscriptional.php",
        "file": "signor_transcriptional.tsv",
    },
    "agris": {
        "name": "AGRIS AtRegNet", "version": "2019-03-11",
        "url": "https://agris-knowledgebase.org/Downloads/AtRegNet.zip",
        "file": "AtRegNet.zip",
    },
}


def download(url: str, destination: Path, force: bool = False) -> None:
    if destination.exists() and not force:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "grn-atlas/1.0"})
    partial = destination.with_suffix(destination.suffix + ".part")
    with urllib.request.urlopen(request, timeout=180) as response, partial.open("wb") as output:
        shutil.copyfileobj(response, output)
    partial.replace(destination)


def parse_pmids(raw: str) -> list[str]:
    values = []
    for item in (raw or "").replace(";", " ").split():
        token = item.rsplit(":", 1)[-1]
        if token.isdigit():
            values.append(token)
    return values


def collectri_rows(path: Path, conn: sqlite3.Connection):
    resolve = gene_resolver(conn, "human")
    stats = Counter()
    rows = []
    with path.open(newline="") as handle:
        for record in csv.DictReader(handle, delimiter="\t"):
            stats["input"] += 1
            stimulation = record.get("consensus_stimulation") == "True"
            inhibition = record.get("consensus_inhibition") == "True"
            if stimulation == inhibition:
                stats["not_unambiguously_signed"] += 1
                continue
            source_id = resolve(record.get("source_genesymbol"))
            target_id = resolve(record.get("target_genesymbol"))
            if not source_id or not target_id or source_id == target_id:
                stats["unmapped_or_self"] += 1
                continue
            relation = "activation" if stimulation else "repression"
            rows.append({
                "species": "human", "source_id": source_id, "target_id": target_id,
                "relation_type": relation, "evidence_layer": "direct_signed",
                "directness": "direct", "record_key": f"{record['source']}|{record['target']}",
                "pmids": parse_pmids(record.get("references", "")),
                "metadata": {
                    "upstream_sources": record.get("sources", "").split(";"),
                    "curation_effort": int(record.get("curation_effort") or 0),
                    "source_uniprot": record.get("source"), "target_uniprot": record.get("target"),
                },
            })
    stats["mapped"] = len(rows)
    return rows, dict(stats)


def signor_rows(path: Path, conn: sqlite3.Connection):
    resolvers = {"9606": ("human", gene_resolver(conn, "human")),
                 "10090": ("mouse", gene_resolver(conn, "mouse"))}
    stats = Counter()
    rows = []
    with path.open(newline="") as handle:
        for record in csv.reader(handle, delimiter="\t"):
            stats["input"] += 1
            if len(record) < 27 or record[12] not in resolvers:
                stats["unsupported_species"] += 1
                continue
            effect = record[8].lower()
            if effect.startswith("up-regulates"):
                relation = "activation"
            elif effect.startswith("down-regulates"):
                relation = "repression"
            else:
                stats["not_unambiguously_signed"] += 1
                continue
            species, resolve = resolvers[record[12]]
            source_id, target_id = resolve(record[0]), resolve(record[4])
            if not source_id or not target_id or source_id == target_id:
                stats["unmapped_or_self"] += 1
                continue
            rows.append({
                "species": species, "source_id": source_id, "target_id": target_id,
                "relation_type": relation, "evidence_layer": "direct_signed",
                "directness": "direct", "record_key": record[26],
                "pmids": parse_pmids(record[21]),
                "context": {"tissue": record[13] or None},
                "metadata": {"effect": record[8], "mechanism": record[9],
                             "source_uniprot": record[2], "target_uniprot": record[6]},
            })
    stats["mapped"] = len(rows)
    return rows, dict(stats)


def agris_rows(path: Path, conn: sqlite3.Connection):
    resolve = gene_resolver(conn, "arabidopsis")
    stats = Counter()
    rows_by_key = {}
    with zipfile.ZipFile(path) as archive, archive.open("AtRegNet.csv") as raw:
        handle = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="")
        for record in csv.DictReader(handle):
            stats["input"] += 1
            if record.get("TargetType") != "Direct" or record.get("Confirmation") != "Confirmed":
                stats["not_confirmed_direct"] += 1
                continue
            interaction = (record.get("InteractionType") or "").lower()
            if interaction == "activation":
                relation = "activation"
            elif interaction == "repression":
                relation = "repression"
            else:
                stats["not_unambiguously_signed"] += 1
                continue
            source_id = resolve(record.get("TFLocus"))
            target_id = resolve(record.get("TargetLocus"))
            if not source_id or not target_id or source_id == target_id:
                stats["unmapped_or_self"] += 1
                continue
            key = f"{source_id}|{target_id}|{relation}"
            row = rows_by_key.setdefault(key, {
                "species": "arabidopsis", "source_id": source_id, "target_id": target_id,
                "relation_type": relation, "evidence_layer": "direct_signed",
                "directness": "direct", "record_key": key, "pmids": [],
                "metadata": {"confirmation": "Confirmed", "target_type": "Direct",
                             "tf_family": record.get("TFFamily")},
            })
            row["pmids"].extend(parse_pmids(record.get("PubMedID", "")))
    rows = list(rows_by_key.values())
    stats["mapped"] = len(rows)
    return rows, dict(stats)


PARSERS = {"collectri": collectri_rows, "signor": signor_rows, "agris": agris_rows}


def ingest(source_key: str, conn: sqlite3.Connection, force_download: bool = False) -> dict:
    config = SOURCES[source_key]
    path = DATA_DIR / config["file"]
    download(config["url"], path, force_download)
    digest = file_sha256(path)
    run_id = begin_import(conn, config["name"], config["version"], config["url"], digest)
    conn.commit()
    try:
        rows, counts = PARSERS[source_key](path, conn)
        conn.execute("SAVEPOINT evidence_replace")
        counts["stored"] = replace_source_evidence(
            conn, config["name"], config["version"], run_id, rows
        )
        conn.execute("RELEASE evidence_replace")
        finish_import(conn, run_id, counts)
    except Exception:
        try:
            conn.execute("ROLLBACK TO evidence_replace")
            conn.execute("RELEASE evidence_replace")
        except sqlite3.OperationalError:
            pass
        finish_import(conn, run_id, {}, "failed")
        raise
    result = benchmark_source(conn, config["name"])
    result["parse_counts"] = counts
    result["sha256"] = digest
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", nargs="+", choices=[*SOURCES, "all"])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    keys = list(SOURCES) if "all" in args.sources else args.sources
    with sqlite3.connect(args.db) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        report = [ingest(key, conn, args.force_download) for key in keys]
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
