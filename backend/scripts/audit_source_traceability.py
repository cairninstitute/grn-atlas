#!/usr/bin/env python3
"""Can every edge be traced back to the source file it names?

The SIGNOR migration turned up 1,812 human edges labelled SIGNOR that are not
in SIGNOR's current content. That was found only because SIGNOR happened to be
instrumented; the same question was unanswered for every other source.

This answers it for the sources whose inputs are cached on disk. For each, it
parses the file, resolves identifiers with the project's own gene_resolver, and
compares against the edges in `interactions` that claim that source.

Three outcomes per source:

  traceable        the edge is in the file it names - as it should be
  untraceable      the edge claims the source but is not in the cached file
  not_loaded       the file has it, the database does not

This measures the database against the files the build actually used, not
against upstream. An edge the cached file does not contain cannot have come
from that file, whatever upstream says today. Drift between the cached files
and upstream is a separate question, and the one source_import_runs.sha256
exists to answer.

Read-only, no network.

Usage:
    venv/bin/python backend/scripts/audit_source_traceability.py
    venv/bin/python backend/scripts/audit_source_traceability.py --source TRRUST
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

DB = BACKEND / "data" / "grn.sqlite3"
DATA = BACKEND / "data"
REPORT = DATA / "source_traceability_audit.json"

# label in interactions.sources -> the cached file it was built from.
# cols are (source, target) zero-indexed; header says whether to skip row 1.
SOURCES = [
    {"label": "TRRUST", "species": "human",
     "file": "trrust_rawdata.human.tsv", "cols": (0, 1), "header": False},
    {"label": "TRRUST", "species": "mouse",
     "file": "trrust_rawdata.mouse.tsv", "cols": (0, 1), "header": False},
    {"label": "DoRothEA", "species": "human",
     "file": "dorothea_human.tsv", "cols": (0, 1), "header": False},
    {"label": "DoRothEA", "species": "mouse",
     "file": "dorothea_mouse.tsv", "cols": (0, 1), "header": False},
    {"label": "CollecTRI", "species": "human",
     "file": "external_sources/collectri_human.tsv", "cols": (2, 3), "header": True},
    {"label": "SIGNOR", "species": "human",
     "file": "external_sources/signor_transcriptional.tsv", "cols": (0, 4), "header": False},
    {"label": "ATRM", "species": "arabidopsis",
     "file": "atrm_regulations.tsv", "cols": (0, 1), "header": True},
    {"label": "PlantRegMap", "species": "arabidopsis",
     "file": "regulation_arabidopsis.tsv", "cols": (0, 1), "header": False},
    {"label": "PlantRegMap", "species": "tomato",
     "file": "regulation_tomato.tsv", "cols": (0, 1), "header": False},
    {"label": "PlantRegMap", "species": "petunia",
     "file": "regulation_petunia.tsv", "cols": (0, 1), "header": False},
    {"label": "PlantRegMap", "species": "potato",
     "file": "regulation_potato.tsv", "cols": (0, 1), "header": False},
]


def file_pairs(path: Path, cols, header: bool, resolve) -> tuple[set, int, int]:
    """Resolved (source_id, target_id) pairs, rows read, rows that would not resolve."""
    pairs, rows, unresolved = set(), 0, 0
    a, b = cols
    with path.open(newline="") as fh:
        reader = csv.reader(fh, delimiter="\t")
        if header:
            next(reader, None)
        for row in reader:
            if len(row) <= max(a, b):
                continue
            rows += 1
            sid, tid = resolve(row[a].strip()), resolve(row[b].strip())
            if sid and tid:
                pairs.add((sid, tid))
            else:
                unresolved += 1
    return pairs, rows, unresolved


def db_pairs(conn, label: str, species: str) -> set:
    return {(s, t) for s, t in conn.execute(
        "SELECT i.source_id, i.target_id FROM interactions i, genes g "
        "WHERE g.id = i.source_id AND g.species = ? "
        "AND i.sources LIKE ?", (species, f"%{label}%"))}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=DB)
    ap.add_argument("--data", type=Path, default=DATA)
    ap.add_argument("--report", type=Path, default=REPORT)
    ap.add_argument("--source", default=None, help="audit one label only")
    ap.add_argument("--examples", type=int, default=8)
    ap.add_argument("--min-resolution", type=float, default=0.80,
                    help="below this share of file rows resolving to gene ids, "
                         "the untraceable count is reported as indeterminate")
    args = ap.parse_args()

    if not args.db.exists():
        print(f"database missing: {args.db}", file=sys.stderr)
        return 1
    from external_evidence import gene_resolver

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    report = {"generated_at": datetime.now(timezone.utc).isoformat(),
              "database": str(args.db.resolve()), "sources": [], "skipped": []}
    resolvers = {}

    print(f"\n{'source':<14}{'species':<13}{'db edges':>10}{'traceable':>11}"
          f"{'untraceable':>13}{'not loaded':>12}")
    print("-" * 73)

    for spec in SOURCES:
        if args.source and spec["label"] != args.source:
            continue
        path = args.data / spec["file"]
        if not path.exists():
            report["skipped"].append({**spec, "reason": "file not cached"})
            continue
        species = spec["species"]
        if species not in resolvers:
            resolvers[species] = gene_resolver(conn, species)
        resolve = resolvers[species]

        fpairs, rows, unresolved = file_pairs(path, spec["cols"], spec["header"], resolve)
        dpairs = db_pairs(conn, spec["label"], species)
        traceable = dpairs & fpairs
        untraceable = dpairs - fpairs
        not_loaded = fpairs - dpairs
        frac = len(untraceable) / len(dpairs) if dpairs else None

        # If most of the file will not resolve to gene ids, the comparison is
        # resolver-limited and says nothing about provenance. Say so rather
        # than reporting a number that reads as missing data.
        resolution = (rows - unresolved) / rows if rows else 0.0
        # A low resolution rate inflates `untraceable`, because the auditor
        # cannot find database edges in a file whose identifiers it failed to
        # parse. If nothing is untraceable, that cannot have happened: the
        # loader and the auditor agree, whatever the rate.
        determinate = resolution >= args.min_resolution or not untraceable

        entry = {
            "label": spec["label"], "species": species, "file": spec["file"],
            "file_rows": rows, "file_pairs_resolved": len(fpairs),
            "file_rows_unresolved": unresolved,
            "db_edges": len(dpairs), "traceable": len(traceable),
            "untraceable": len(untraceable), "not_loaded": len(not_loaded),
            "untraceable_fraction": round(frac, 4) if frac is not None else None,
            "file_resolution_rate": round(resolution, 4),
            "determinate": determinate,
            "caveat": (None if determinate else
                       "resolver mapped only "
                       f"{resolution:.0%} of file rows to gene ids; the "
                       "untraceable count reflects identifier mismatch, not "
                       "missing provenance"),
            "untraceable_examples": [f"{s}>{t}" for s, t in
                                     sorted(untraceable)[:args.examples]],
        }
        report["sources"].append(entry)
        flag = "" if determinate else "  ? id mismatch"
        shown = f"{len(untraceable):,}" if determinate else "indet."
        print(f"{spec['label']:<14}{species:<13}{len(dpairs):>10,}{len(traceable):>11,}"
              f"{shown:>13}{len(not_loaded):>12,}"
              f"{'  ' + format(frac, '.1%') if (frac is not None and determinate) else ''}"
              f"{flag}")

    conn.close()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")

    worst = sorted((e for e in report["sources"]
                    if e["untraceable_fraction"] and e["determinate"]),
                   key=lambda e: -e["untraceable_fraction"])[:3]
    if worst:
        print("\nleast traceable:")
        for e in worst:
            print(f"  {e['label']} / {e['species']}: {e['untraceable']:,} of "
                  f"{e['db_edges']:,} ({e['untraceable_fraction']:.1%}) not in "
                  f"{e['file']}")
            if e["untraceable_examples"]:
                print(f"    e.g. {', '.join(e['untraceable_examples'][:4])}")
    indet = [e for e in report["sources"] if not e["determinate"]]
    if indet:
        print("\nindeterminate - identifier spaces differ between file and database,"
              "\nso these say nothing about provenance until the mapping is fixed:")
        for e in indet:
            print(f"  {e['label']} / {e['species']}: resolver mapped "
                  f"{e['file_resolution_rate']:.0%} of {e['file_rows']:,} file rows")

    dropped = [e for e in report["sources"]
               if e["determinate"] and e["not_loaded"] > 0.1 * max(e["db_edges"], 1)]
    if dropped:
        print("\nfile content not in the database (the loader dropped it):")
        for e in dropped:
            print(f"  {e['label']} / {e['species']}: {e['not_loaded']:,} resolvable "
                  f"pairs absent, against {e['db_edges']:,} loaded")

    if report["skipped"]:
        print(f"\nskipped {len(report['skipped'])} source(s) with no cached file: "
              + ", ".join(f"{s['label']}/{s['species']}" for s in report["skipped"]))
    print(f"\nReport: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
