#!/usr/bin/env python3
"""Move SIGNOR's non-transcriptional records out of the transcriptional graph.

Why this exists
    fetch_collectri_signor.py requests SIGNOR with no interaction-type filter,
    although its docstring says "transcriptional subset only". Protein-level
    causal relations - GNA11 -> PLCB1, NLGN2 -> NRXN1 - are therefore loaded
    into `interactions`, where feedback_control.py labels every edge
    `transcriptional` by construction. They are real curated biology in the
    wrong table.

    Fixing the fetcher is necessary but not sufficient: replace_source_evidence
    replaces `regulatory_evidence` rows on re-fetch, but nothing deletes stale
    rows from `interactions`. The existing records have to be migrated.

Three phases, each separately verifiable:

  --classify   Query OmniPath twice (all SIGNOR records, then the
               transcriptional subset), check the two results are consistent,
               and write a classification file. Network required.

  (default)    Dry run. Read the classification, report exactly what would
               change in each table. Touches nothing.

  --apply      Perform the migration inside one transaction.

What --apply does
    regulatory_evidence     SIGNOR rows for non-transcriptional pairs removed
    regulatory_layer_edges  those pairs inserted, layer from the OmniPath type
    interactions            SIGNOR dropped from `sources`; the row is deleted
                            only when SIGNOR was its only source. If the sign
                            can no longer be supported by a remaining signed
                            evidence record, sign is cleared to 'unknown'
                            rather than left asserted.

Take a content digest before and after: this changes what the atlas asserts.

Usage:
    venv/bin/python backend/scripts/migrate_signor_layers.py --classify
    venv/bin/python backend/scripts/migrate_signor_layers.py
    venv/bin/python backend/scripts/migrate_signor_layers.py --apply
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sqlite3
import sys
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

DB = BACKEND / "data" / "grn.sqlite3"
CLASSIFICATION = BACKEND / "data" / "signor_type_classification.json"
REPORT = BACKEND / "data" / "signor_migration_report.json"

OMNIPATH_BASE = "https://omnipathdb.org/interactions?"
# multilayer_control.replace_source accepts these only; an unsigned record has
# no place in a signed table, so by default it is reported and not written.
VALID_SIGNS = {"activation", "repression"}
SOURCE_NAME = "SIGNOR"
TAXIDS = {"human": 9606, "mouse": 10090}

# OmniPath interaction type -> regulatory_layer_edges layer.
# multilayer_control.VALID_LAYERS does not currently include post_translational;
# see the note printed by --apply.
TYPE_TO_LAYER = {
    "post_translational": "protein_activity",
    "post_transcriptional": "post_transcriptional",
    "mirna_transcriptional": "post_transcriptional",
    "lncrna_post_transcriptional": "post_transcriptional",
}


# --------------------------------------------------------------------------
# Phase 1: classify
# --------------------------------------------------------------------------

def fetch(species: str, types: str | None) -> list[dict]:
    url = (f"{OMNIPATH_BASE}resources={SOURCE_NAME}&genesymbols=yes"
           f"&organisms={TAXIDS[species]}&fields=references&license=academic")
    if types:
        url += f"&types={types}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (grn-atlas-build)"})
    print(f"  GET types={types or '(all)'} {species} ...", flush=True)
    with urllib.request.urlopen(req, timeout=180) as resp:
        text = resp.read().decode("utf-8")
    out = []
    for rec in csv.DictReader(io.StringIO(text), delimiter="\t"):
        tf = (rec.get("source_genesymbol") or "").strip()
        tgt = (rec.get("target_genesymbol") or "").strip()
        if not tf or not tgt:
            continue
        stim = (rec.get("is_stimulation") or "").strip() in ("1", "True", "true")
        inhib = (rec.get("is_inhibition") or "").strip() in ("1", "True", "true")
        if stim and not inhib:
            sign = "activation"
        elif inhib and not stim:
            sign = "repression"
        else:
            sign = "regulation"
        out.append({"tf": tf, "target": tgt, "sign": sign,
                    "type": (rec.get("type") or "").strip()})
    print(f"    {len(out)} records", flush=True)
    return out


def classify(path: Path, species_list: list[str]) -> int:
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE_NAME,
        "species": {},
        "warnings": [],
    }
    for species in species_list:
        all_rows = fetch(species, None)
        time.sleep(2)
        tx_rows = fetch(species, "transcriptional")
        time.sleep(2)

        all_pairs = {(r["tf"], r["target"]) for r in all_rows}
        tx_pairs = {(r["tf"], r["target"]) for r in tx_rows}

        # Sanity: the type filter must actually narrow the result, and the
        # transcriptional set must be a subset. If not, the parameter was
        # ignored and the whole classification is meaningless.
        if not tx_pairs:
            result["warnings"].append(
                f"{species}: transcriptional query returned nothing; "
                f"either SIGNOR has no transcriptional records for this "
                f"organism, or the types filter is unsupported")
        if tx_pairs and not tx_pairs <= all_pairs:
            result["warnings"].append(
                f"{species}: transcriptional set is not a subset of the full "
                f"set ({len(tx_pairs - all_pairs)} extra); refusing to trust it")
            tx_pairs = set()
        if tx_pairs and len(tx_pairs) == len(all_pairs):
            result["warnings"].append(
                f"{species}: the types filter did not narrow the result "
                f"({len(all_pairs)} both ways); it was probably ignored")

        types_seen = Counter(r["type"] for r in all_rows if r["type"])
        non_tx = sorted(all_pairs - tx_pairs)
        non_tx_set = all_pairs - tx_pairs
        pair_type, pair_sign = {}, {}
        for r in all_rows:
            key = (r["tf"], r["target"])
            if key not in non_tx_set:
                continue
            label = f"{r['tf']}>{r['target']}"
            if r["type"]:
                pair_type.setdefault(label, r["type"])
            # A pair with conflicting signs across records keeps no sign.
            if label in pair_sign and pair_sign[label] != r["sign"]:
                pair_sign[label] = "regulation"
            else:
                pair_sign.setdefault(label, r["sign"])
        signs_seen = Counter(pair_sign.values())

        result["species"][species] = {
            "all_pairs": len(all_pairs),
            "transcriptional_pairs": len(tx_pairs),
            "non_transcriptional_pairs": len(non_tx),
            "types_seen": dict(types_seen),
            "transcriptional": [f"{a}>{b}" for a, b in sorted(tx_pairs)],
            "non_transcriptional": [f"{a}>{b}" for a, b in non_tx],
            "non_transcriptional_type": pair_type,
            "non_transcriptional_sign": pair_sign,
            "signs_seen": dict(signs_seen),
        }
        print(f"  {species}: {len(all_pairs)} total, {len(tx_pairs)} transcriptional, "
              f"{len(non_tx)} to migrate  signs={dict(signs_seen)}", flush=True)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(f"\nClassification written to {path}")
    if result["warnings"]:
        print("\nWARNINGS - do not run --apply until these are understood:")
        for w in result["warnings"]:
            print(f"  - {w}")
        return 1
    return 0


# --------------------------------------------------------------------------
# Phases 2 and 3: plan, then optionally apply
# --------------------------------------------------------------------------

def resolved_pairs(conn, species: str, labels: list[str]) -> dict[str, tuple[str, str]]:
    """Map 'TF>TARGET' symbol pairs onto atlas gene ids for one species."""
    from external_evidence import gene_resolver
    resolve = gene_resolver(conn, species)
    out = {}
    for label in labels:
        tf, _, target = label.partition(">")
        sid, tid = resolve(tf), resolve(target)
        if sid and tid and sid != tid:
            out[label] = (sid, tid)
    return out


def plan(conn: sqlite3.Connection, classification: dict) -> dict:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classification_generated_at": classification.get("generated_at"),
        "species": {},
        "totals": Counter(),
    }
    for species, data in classification["species"].items():
        pairs = resolved_pairs(conn, species, data["non_transcriptional"])
        delete_rows, strip_rows, clear_sign, layer_rows = [], [], [], []
        for label, (sid, tid) in pairs.items():
            row = conn.execute(
                "SELECT sources, sign, sign_evidence FROM interactions "
                "WHERE source_id=? AND target_id=?", (sid, tid)).fetchone()
            otype = data["non_transcriptional_type"].get(label, "post_translational")
            osign = data.get("non_transcriptional_sign", {}).get(label, "regulation")
            layer_rows.append({"species": species, "source_id": sid, "target_id": tid,
                               "omnipath_type": otype, "relation_type": osign,
                               "layer": TYPE_TO_LAYER.get(otype, "protein_activity")})
            if row is None:
                continue
            try:
                sources = json.loads(row[0] or "[]")
            except (TypeError, ValueError):
                sources = []
            if SOURCE_NAME not in sources:
                continue
            remaining = [s for s in sources if s != SOURCE_NAME]
            if not remaining:
                delete_rows.append({"source_id": sid, "target_id": tid,
                                    "sign": row[1], "sign_evidence": row[2]})
                continue
            strip_rows.append({"source_id": sid, "target_id": tid,
                               "remaining_sources": remaining})
            # Can the sign still be supported without SIGNOR?
            if row[1]:
                supported = conn.execute(
                    "SELECT COUNT(*) FROM regulatory_evidence "
                    "WHERE source_id=? AND target_id=? AND source_name<>? "
                    "AND relation_type IN ('activation','repression')",
                    (sid, tid, SOURCE_NAME)).fetchone()[0]
                if not supported:
                    clear_sign.append({"source_id": sid, "target_id": tid, "sign": row[1]})
        report["species"][species] = {
            "non_transcriptional_pairs": len(data["non_transcriptional"]),
            "resolved_to_atlas_genes": len(pairs),
            "interactions_to_delete": delete_rows,
            "interactions_to_strip_source": strip_rows,
            "signs_to_clear": clear_sign,
            "layer_edges_to_insert": layer_rows,
        }
        report["totals"]["interactions_deleted"] += len(delete_rows)
        report["totals"]["sources_stripped"] += len(strip_rows)
        report["totals"]["signs_cleared"] += len(clear_sign)
        signed = [r for r in layer_rows if r["relation_type"] in VALID_SIGNS]
        report["species"][species]["layer_edges_signed"] = len(signed)
        report["species"][species]["layer_edges_unsigned"] = len(layer_rows) - len(signed)
        report["totals"]["layer_edges_signed"] += len(signed)
        report["totals"]["layer_edges_unsigned"] += len(layer_rows) - len(signed)
    report["totals"] = dict(report["totals"])
    return report


def apply_plan(conn: sqlite3.Connection, report: dict,
               include_unsigned: bool = False) -> None:
    from multilayer_control import ensure_schema
    ensure_schema(conn)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("BEGIN")
    try:
        for species, data in report["species"].items():
            for r in data["interactions_to_delete"]:
                conn.execute("DELETE FROM interactions WHERE source_id=? AND target_id=?",
                             (r["source_id"], r["target_id"]))
            for r in data["interactions_to_strip_source"]:
                conn.execute("UPDATE interactions SET sources=? "
                             "WHERE source_id=? AND target_id=?",
                             (json.dumps(r["remaining_sources"]),
                              r["source_id"], r["target_id"]))
            for r in data["signs_to_clear"]:
                conn.execute("UPDATE interactions SET sign=NULL, sign_evidence='unknown' "
                             "WHERE source_id=? AND target_id=?",
                             (r["source_id"], r["target_id"]))
            conn.execute("DELETE FROM regulatory_layer_edges WHERE evidence_source=? "
                         "AND species=?", (SOURCE_NAME, species))
            for r in data["layer_edges_to_insert"]:
                if r["relation_type"] not in VALID_SIGNS and not include_unsigned:
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO regulatory_layer_edges "
                    "(species,source_id,target_id,relation_type,regulatory_layer,"
                    " confidence,evidence_source,pmids,context,metadata,imported_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (r["species"], r["source_id"], r["target_id"], r["relation_type"],
                     r["layer"], 0.80, SOURCE_NAME, "[]", "{}",
                     json.dumps({"omnipath_type": r["omnipath_type"],
                                 "migrated_by": "migrate_signor_layers"},
                                sort_keys=True), now))
            # Remove the migrated pairs from regulatory_evidence under SIGNOR.
            for r in data["layer_edges_to_insert"]:
                conn.execute("DELETE FROM regulatory_evidence WHERE source_name=? "
                             "AND source_id=? AND target_id=?",
                             (SOURCE_NAME, r["source_id"], r["target_id"]))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def verify(conn: sqlite3.Connection, classification: dict) -> dict:
    """Classify the SIGNOR rows still in `interactions` against the fetch.

    A row left behind is one of three things, and they need different fixes:
      transcriptional            - correct, it belongs there
      non_transcriptional        - the migration missed it, usually because the
                                   symbol no longer resolves to a gene id
      absent_from_omnipath       - the pair is in neither of today's result
                                   sets, so it was loaded by an earlier fetch
                                   that upstream no longer returns
    """
    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "species": {}}
    for species, data in classification["species"].items():
        tx = set(resolved_pairs(conn, species, data["transcriptional"]).values())
        non_tx = set(resolved_pairs(conn, species, data["non_transcriptional"]).values())
        buckets = Counter()
        examples = {"non_transcriptional": [], "absent_from_omnipath": []}
        for sid, tid in conn.execute(
                "SELECT i.source_id, i.target_id FROM interactions i, genes g "
                "WHERE g.id = i.source_id AND g.species = ? "
                "AND i.sources LIKE '%SIGNOR%'", (species,)):
            if (sid, tid) in tx:
                buckets["transcriptional"] += 1
            elif (sid, tid) in non_tx:
                buckets["non_transcriptional"] += 1
                if len(examples["non_transcriptional"]) < 10:
                    examples["non_transcriptional"].append(f"{sid}>{tid}")
            else:
                buckets["absent_from_omnipath"] += 1
                if len(examples["absent_from_omnipath"]) < 10:
                    examples["absent_from_omnipath"].append(f"{sid}>{tid}")
        out["species"][species] = {
            "signor_rows_remaining": sum(buckets.values()),
            "transcriptional_pairs_resolved": len(tx),
            **dict(buckets), "examples": examples,
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=DB)
    ap.add_argument("--classification", type=Path, default=CLASSIFICATION)
    ap.add_argument("--report", type=Path, default=REPORT)
    ap.add_argument("--species", nargs="*", default=["human", "mouse"])
    ap.add_argument("--verify", action="store_true",
                    help="classify the SIGNOR rows still in interactions; "
                         "read-only, run after --apply")
    ap.add_argument("--classify", action="store_true",
                    help="query OmniPath and write the classification file")
    ap.add_argument("--apply", action="store_true",
                    help="perform the migration (default is a dry run)")
    ap.add_argument("--include-unsigned", action="store_true",
                    help="also write records SIGNOR does not sign; these exceed "
                         "multilayer_control.VALID_SIGNS and replace_source would "
                         "reject them, so only use this once that contract is widened")
    args = ap.parse_args()

    if args.classify:
        print("Classifying SIGNOR records by interaction type...\n")
        return classify(args.classification, args.species)

    if not args.classification.exists():
        print(f"no classification at {args.classification}\n"
              f"run with --classify first (needs network access to omnipathdb.org)",
              file=sys.stderr)
        return 1
    if not args.db.exists():
        print(f"database missing: {args.db}", file=sys.stderr)
        return 1

    classification = json.loads(args.classification.read_text())

    if args.verify:
        conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
        res = verify(conn, classification)
        conn.close()
        for species, d in res["species"].items():
            print(f"\n{species}: {d['signor_rows_remaining']:,} SIGNOR rows still in interactions")
            print(f"  transcriptional (correct)        {d.get('transcriptional', 0):,}")
            print(f"  non-transcriptional (missed)     {d.get('non_transcriptional', 0):,}")
            print(f"  absent from today's OmniPath     {d.get('absent_from_omnipath', 0):,}")
            for k, v in d["examples"].items():
                if v:
                    print(f"    {k}: {', '.join(v[:5])}")
        args.report.with_name("signor_verify_report.json").write_text(
            json.dumps(res, indent=2) + "\n")
        print(f"\nReport: {args.report.with_name('signor_verify_report.json')}")
        return 0

    if classification.get("warnings"):
        print("the classification carries warnings; resolve them first:")
        for w in classification["warnings"]:
            print(f"  - {w}")
        return 1

    mode = "ro" if not args.apply else "rw"
    conn = sqlite3.connect(f"file:{args.db}?mode={mode}", uri=True)
    report = plan(conn, classification)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")

    t = report["totals"]
    print(f"\n{'APPLYING' if args.apply else 'DRY RUN - nothing written'}\n")
    for species, d in report["species"].items():
        print(f"  {species}: {d['non_transcriptional_pairs']:,} non-transcriptional pairs, "
              f"{d['resolved_to_atlas_genes']:,} resolve to atlas genes")
    print(f"\n  interactions to delete (SIGNOR was the only source): "
          f"{t.get('interactions_deleted', 0):,}")
    print(f"  interactions to strip SIGNOR from:                     "
          f"{t.get('sources_stripped', 0):,}")
    print(f"  signs to clear (unsupported without SIGNOR):           "
          f"{t.get('signs_cleared', 0):,}")
    print(f"  regulatory_layer_edges to insert (signed):             "
          f"{t.get('layer_edges_signed', 0):,}")
    print(f"  non-transcriptional pairs with no usable sign:         "
          f"{t.get('layer_edges_unsigned', 0):,}"
          f"{'  (will be written)' if args.include_unsigned else '  (not written)'}")
    print(f"\n  Report: {args.report}")

    if args.apply:
        apply_plan(conn, report, include_unsigned=args.include_unsigned)
        print("\nApplied. Re-run the content digest and compare against the baseline.")
        print("Note: the regulatory_layer is mapped from the OmniPath interaction "
              "type, which is coarse - SIGNOR's own mechanism annotation would "
              "place these more precisely. The original type is kept in metadata.")
    else:
        print("\nRe-run with --apply to perform it. Take a content digest first.")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
