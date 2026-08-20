"""
Post-build validation: compare the atlas regulatory edges against literature
gold-standard edges, sample random edges for plausibility, check pathway
coherence, and estimate false positive rates.

Usage:
    python backend/scripts/validate_regulation_quality.py          # all species
    python backend/scripts/validate_regulation_quality.py petunia  # one species
"""
import json
import random
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"

# GO term sets for pathway coherence checks.
# Each entry: (pathway_label, set of GO IDs, expected TF GO IDs).
PATHWAY_GO = {
    "anthocyanin": {
        "target_go": {
            "GO:0009718",  # anthocyanin-containing compound biosynthetic process
            "GO:0009813",  # flavonoid biosynthetic process
            "GO:0009699",  # phenylpropanoid biosynthetic process
        },
        "tf_go": {
            "GO:0031540",  # regulation of anthocyanin biosynthetic process
            "GO:0031542",  # positive regulation of anthocyanin biosynthetic process
            "GO:0009962",  # regulation of flavonoid biosynthetic process
            "GO:0009963",  # positive regulation of flavonoid biosynthetic process
        },
    },
    "ethylene": {
        "target_go": {
            "GO:0009693",  # ethylene biosynthetic process
            "GO:0009692",  # ethylene metabolic process
        },
        "tf_go": {
            "GO:0009873",  # ethylene-activated signaling pathway
            "GO:0010104",  # regulation of ethylene-activated signaling pathway
            "GO:0010364",  # regulation of ethylene biosynthetic process
        },
    },
    "carotenoid": {
        "target_go": {
            "GO:0016117",  # carotenoid biosynthetic process
            "GO:0016116",  # carotenoid metabolic process
        },
        "tf_go": {
            "GO:1904143",  # positive regulation of carotenoid biosynthetic process
        },
    },
    "flavonol": {
        "target_go": {
            "GO:0051555",  # flavonol biosynthetic process
            "GO:0051553",  # flavone biosynthetic process
        },
        "tf_go": {
            "GO:0009962",  # regulation of flavonoid biosynthetic process
            "GO:1900384",  # regulation of flavonol biosynthetic process
        },
    },
    "terpene": {
        "target_go": {
            "GO:0046246",  # terpene biosynthetic process
            "GO:0051762",  # sesquiterpene biosynthetic process
            "GO:0043693",  # monoterpene biosynthetic process
        },
        "tf_go": set(),
    },
}


def load_gold_standard(species):
    path = DATA_DIR / f"gold_standard_{species}.tsv"
    if not path.exists():
        return []
    entries = []
    with open(path) as f:
        header = f.readline()
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5:
                continue
            entries.append({
                "tf_symbol": parts[0],
                "target_symbol": parts[1],
                "regulation_type": parts[2],
                "evidence": parts[3],
                "pubmed_id": parts[4],
                "notes": parts[5] if len(parts) > 5 else "",
            })
    return entries


def resolve_symbol(db, species, symbol):
    """Resolve a gene symbol to atlas gene ID(s) for a species."""
    candidates = set()

    rows = db.execute(
        "SELECT id FROM genes WHERE species=? AND symbol=? COLLATE NOCASE",
        (species, symbol)).fetchall()
    candidates.update(r[0] for r in rows)

    rows = db.execute(
        "SELECT id, synonyms FROM genes WHERE species=? AND synonyms LIKE ? COLLATE NOCASE",
        (species, f"%{symbol}%")).fetchall()
    sym_lower = symbol.lower()
    for gid, synonyms in rows:
        for s in synonyms.split(";"):
            if s.strip().lower() == sym_lower:
                candidates.add(gid)
                break

    reg_path = DATA_DIR / f"regulator_map_{species}.json"
    if reg_path.exists():
        regs = json.loads(reg_path.read_text())
        for reg in regs:
            if reg["name"].lower() == symbol.lower():
                candidates.add(reg["gene_id"])

    sym_path = DATA_DIR / f"curated_symbols_{species}.json"
    if sym_path.exists():
        syms = json.loads(sym_path.read_text())
        for gid, info in syms.items():
            if info.get("symbol", "").lower() == symbol.lower():
                candidates.add(gid)

    return list(candidates)


def check_edge(db, tf_ids, target_ids):
    """Check if any TF->target edge exists in interactions or inferred_edges."""
    for tf_id in tf_ids:
        for tgt_id in target_ids:
            row = db.execute(
                "SELECT sources, confidence FROM interactions WHERE source_id=? AND target_id=?",
                (tf_id, tgt_id)).fetchone()
            if row:
                sources = json.loads(row[0])
                if "Inferred:Arabidopsis" in sources:
                    source_type = "Inferred:Arabidopsis"
                elif "Inferred:Potato" in sources:
                    source_type = "Inferred:Potato"
                elif "Literature" in sources:
                    source_type = "Literature"
                else:
                    source_type = "PlantRegMap"
                return {"found": True, "source": source_type, "confidence": row[1],
                        "tf_id": tf_id, "target_id": tgt_id}

            row = db.execute(
                "SELECT importance FROM inferred_edges WHERE source_id=? AND target_id=?",
                (tf_id, tgt_id)).fetchone()
            if row:
                return {"found": True, "source": "GRNBoost2", "confidence": row[0],
                        "tf_id": tf_id, "target_id": tgt_id}
    return {"found": False, "source": None, "confidence": None,
            "tf_id": tf_ids[0] if tf_ids else None,
            "target_id": target_ids[0] if target_ids else None}


def check_ortholog_gaps(species):
    """Identify master regulators with no Arabidopsis ortholog."""
    reg_path = DATA_DIR / f"regulator_map_{species}.json"
    orth_path = DATA_DIR / "ortholog_map_plaza.json"
    if not reg_path.exists() or not orth_path.exists():
        return []

    regs = json.loads(reg_path.read_text())
    ortho = json.loads(orth_path.read_text())

    pet_to_ath = {}
    for at_id, mapping in ortho.items():
        for pet_id in mapping.get(species, []):
            pet_to_ath.setdefault(pet_id, []).append(at_id)

    gaps = []
    for reg in regs:
        gid = reg["gene_id"]
        ath_orths = pet_to_ath.get(gid, [])
        gaps.append({
            "symbol": reg["name"],
            "gene_id": gid,
            "has_ath_ortholog": len(ath_orths) > 0,
            "ath_orthologs": ath_orths,
        })
    return gaps


# ---------------------------------------------------------------------------
# Section 2: Random edge sampling
# ---------------------------------------------------------------------------

def _gene_go_terms(db, gene_id):
    """Return set of GO IDs annotated to a gene."""
    rows = db.execute("SELECT go_id FROM go_annotations WHERE gene_id=?",
                      (gene_id,)).fetchall()
    return {r[0] for r in rows}


def _gene_info(db, gene_id):
    row = db.execute("SELECT symbol, synonyms, name FROM genes WHERE id=?",
                     (gene_id,)).fetchone()
    if not row:
        return {"symbol": gene_id, "synonyms": "", "name": ""}
    return {"symbol": row[0], "synonyms": row[1] or "", "name": row[2] or ""}


def _go_overlap(go_a, go_b):
    """Jaccard similarity between two GO term sets."""
    if not go_a or not go_b:
        return 0.0
    return len(go_a & go_b) / len(go_a | go_b)


def sample_random_edges(db, species, n=100, seed=42):
    """Sample n random edges from the interactions table for a species and
    score each for plausibility using GO term overlap between TF and target."""
    rng = random.Random(seed)

    rows = db.execute("""
        SELECT i.source_id, i.target_id, i.sources, i.confidence
        FROM interactions i
        JOIN genes g ON i.source_id = g.id
        WHERE g.species = ?
    """, (species,)).fetchall()

    if not rows:
        return []

    sample = rng.sample(rows, min(n, len(rows)))
    results = []
    for src_id, tgt_id, sources, confidence in sample:
        src_go = _gene_go_terms(db, src_id)
        tgt_go = _gene_go_terms(db, tgt_id)
        overlap = _go_overlap(src_go, tgt_go)
        src_info = _gene_info(db, src_id)
        tgt_info = _gene_info(db, tgt_id)
        source_type = json.loads(sources)[0] if sources else "unknown"

        results.append({
            "tf_id": src_id,
            "tf_symbol": src_info["symbol"],
            "target_id": tgt_id,
            "target_symbol": tgt_info["symbol"],
            "source": source_type,
            "confidence": confidence,
            "tf_go_count": len(src_go),
            "target_go_count": len(tgt_go),
            "go_overlap": round(overlap, 4),
            "shared_go_count": len(src_go & tgt_go),
        })

    return results


# ---------------------------------------------------------------------------
# Section 3: Pathway coherence
# ---------------------------------------------------------------------------

def check_pathway_coherence(db, species):
    """For each known pathway, check whether TFs annotated to regulatory GO
    terms preferentially regulate genes annotated to the pathway's biosynthetic
    GO terms (vs random targets)."""
    results = {}

    for pathway, config in PATHWAY_GO.items():
        target_go = config["target_go"]
        tf_go = config["tf_go"]

        # Find pathway target genes for this species
        pathway_targets = set()
        for go_id in target_go:
            rows = db.execute("""
                SELECT ga.gene_id FROM go_annotations ga
                JOIN genes g ON ga.gene_id = g.id
                WHERE ga.go_id = ? AND g.species = ?
            """, (go_id, species)).fetchall()
            pathway_targets.update(r[0] for r in rows)

        if not pathway_targets:
            continue

        # Find pathway TFs
        pathway_tfs = set()
        for go_id in tf_go:
            rows = db.execute("""
                SELECT ga.gene_id FROM go_annotations ga
                JOIN genes g ON ga.gene_id = g.id
                WHERE ga.go_id = ? AND g.species = ?
            """, (go_id, species)).fetchall()
            pathway_tfs.update(r[0] for r in rows)

        # Count edges from pathway TFs to pathway targets vs all targets
        if not pathway_tfs:
            results[pathway] = {
                "pathway_targets": len(pathway_targets),
                "pathway_tfs": 0,
                "note": "no TFs annotated to regulatory GO terms",
            }
            continue

        tf_list = list(pathway_tfs)
        placeholders = ",".join(["?"] * len(tf_list))

        edges_to_pathway = db.execute(f"""
            SELECT COUNT(*) FROM interactions
            WHERE source_id IN ({placeholders})
            AND target_id IN ({",".join(["?"] * len(pathway_targets))})
        """, tf_list + list(pathway_targets)).fetchone()[0]

        edges_total = db.execute(f"""
            SELECT COUNT(*) FROM interactions
            WHERE source_id IN ({placeholders})
        """, tf_list).fetchone()[0]

        # Also check inferred_edges
        ie_to_pathway = db.execute(f"""
            SELECT COUNT(*) FROM inferred_edges
            WHERE source_id IN ({placeholders})
            AND target_id IN ({",".join(["?"] * len(pathway_targets))})
        """, tf_list + list(pathway_targets)).fetchone()[0]

        ie_total = db.execute(f"""
            SELECT COUNT(*) FROM inferred_edges
            WHERE source_id IN ({placeholders})
        """, tf_list).fetchone()[0]

        # Expected fraction if edges were random
        total_genes = db.execute(
            "SELECT COUNT(*) FROM genes WHERE species=?",
            (species,)).fetchone()[0]
        expected_frac = len(pathway_targets) / total_genes if total_genes else 0

        actual_frac_interactions = (edges_to_pathway / edges_total) if edges_total else 0
        actual_frac_inferred = (ie_to_pathway / ie_total) if ie_total else 0

        enrichment_interactions = (actual_frac_interactions / expected_frac) if expected_frac else 0
        enrichment_inferred = (actual_frac_inferred / expected_frac) if expected_frac else 0

        results[pathway] = {
            "pathway_targets": len(pathway_targets),
            "pathway_tfs": len(pathway_tfs),
            "edges_to_pathway": edges_to_pathway,
            "edges_total": edges_total,
            "ie_to_pathway": ie_to_pathway,
            "ie_total": ie_total,
            "expected_fraction": round(expected_frac, 6),
            "actual_fraction_interactions": round(actual_frac_interactions, 6),
            "actual_fraction_inferred": round(actual_frac_inferred, 6),
            "enrichment_interactions": round(enrichment_interactions, 2),
            "enrichment_inferred": round(enrichment_inferred, 2),
        }

    return results


# ---------------------------------------------------------------------------
# Section 4: False positive estimation
# ---------------------------------------------------------------------------

def estimate_false_positives(db, species, n_negative=200, seed=42):
    """Estimate false positive rate by checking how often edges exist between
    gene pairs that should NOT be connected: TFs paired with random genes from
    unrelated GO categories."""
    rng = random.Random(seed)

    # Get all TFs for this species
    tf_rows = db.execute("""
        SELECT DISTINCT source_id FROM interactions i
        JOIN genes g ON i.source_id = g.id WHERE g.species = ?
    """, (species,)).fetchall()
    tf_ids = [r[0] for r in tf_rows]

    # Get all genes for this species
    gene_rows = db.execute(
        "SELECT id FROM genes WHERE species=?", (species,)).fetchall()
    all_genes = [r[0] for r in gene_rows]

    if not tf_ids or not all_genes:
        return {}

    # Generate random TF-gene pairs
    pairs = set()
    attempts = 0
    while len(pairs) < n_negative and attempts < n_negative * 10:
        tf = rng.choice(tf_ids)
        target = rng.choice(all_genes)
        if tf != target:
            pairs.add((tf, target))
        attempts += 1

    # Check how many random pairs have edges
    found_interactions = 0
    found_inferred = 0
    found_by_source = defaultdict(int)
    for tf, target in pairs:
        row = db.execute(
            "SELECT sources FROM interactions WHERE source_id=? AND target_id=?",
            (tf, target)).fetchone()
        if row:
            found_interactions += 1
            src = json.loads(row[0])[0]
            found_by_source[src] += 1

        row = db.execute(
            "SELECT importance FROM inferred_edges WHERE source_id=? AND target_id=?",
            (tf, target)).fetchone()
        if row:
            found_inferred += 1

    n = len(pairs)
    return {
        "random_pairs_tested": n,
        "found_in_interactions": found_interactions,
        "found_in_inferred_edges": found_inferred,
        "interaction_hit_rate": round(found_interactions / n, 4) if n else 0,
        "inferred_hit_rate": round(found_inferred / n, 4) if n else 0,
        "combined_hit_rate": round((found_interactions + found_inferred) / n, 4) if n else 0,
        "by_source": dict(found_by_source),
    }


# ---------------------------------------------------------------------------
# Section 5: Gold standard (original + negative control awareness)
# ---------------------------------------------------------------------------

def validate_species(species):
    gold = load_gold_standard(species)
    if not gold:
        print(f"\n{species.upper()}: no gold standard file — skipping")
        return None

    db = sqlite3.connect(DB_PATH)
    edge_details = []
    unresolved = []
    source_counts = defaultdict(int)

    # Separate positive and negative controls
    positive_edges = [e for e in gold if e["regulation_type"] != "negative_control"
                      and "negative_control" not in e.get("notes", "")
                      and "negative_control" not in e.get("evidence", "")]
    negative_edges = [e for e in gold if e["regulation_type"] == "negative_control"
                      or "negative_control" in e.get("notes", "")
                      or "negative_control" in e.get("evidence", "")]

    # --- Evaluate positive edges (should be found) ---
    for entry in positive_edges:
        tf_ids = resolve_symbol(db, species, entry["tf_symbol"])
        tgt_ids = resolve_symbol(db, species, entry["target_symbol"])

        if not tf_ids or not tgt_ids:
            unresolved_syms = []
            if not tf_ids:
                unresolved_syms.append(entry["tf_symbol"])
            if not tgt_ids:
                unresolved_syms.append(entry["target_symbol"])
            unresolved.extend(unresolved_syms)
            edge_details.append({
                "tf": entry["tf_symbol"], "target": entry["target_symbol"],
                "resolved": False, "found": False, "source": None,
                "expected": "positive", "correct": False,
                "unresolved_symbols": unresolved_syms,
                "evidence": entry["evidence"], "pubmed_id": entry["pubmed_id"],
            })
            continue

        result = check_edge(db, tf_ids, tgt_ids)
        if result["found"]:
            source_counts[result["source"]] += 1

        edge_details.append({
            "tf": entry["tf_symbol"], "target": entry["target_symbol"],
            "resolved": True, "found": result["found"],
            "expected": "positive", "correct": result["found"],
            "source": result["source"], "confidence": result["confidence"],
            "tf_id": result["tf_id"], "target_id": result["target_id"],
            "evidence": entry["evidence"], "pubmed_id": entry["pubmed_id"],
        })

    # --- Evaluate negative controls (should NOT be found) ---
    for entry in negative_edges:
        tf_ids = resolve_symbol(db, species, entry["tf_symbol"])
        tgt_ids = resolve_symbol(db, species, entry["target_symbol"])

        if not tf_ids or not tgt_ids:
            edge_details.append({
                "tf": entry["tf_symbol"], "target": entry["target_symbol"],
                "resolved": False, "found": False,
                "expected": "negative", "correct": True,
                "source": None, "evidence": entry["evidence"],
                "pubmed_id": entry["pubmed_id"],
            })
            continue

        result = check_edge(db, tf_ids, tgt_ids)
        is_correct = not result["found"]

        edge_details.append({
            "tf": entry["tf_symbol"], "target": entry["target_symbol"],
            "resolved": True, "found": result["found"],
            "expected": "negative", "correct": is_correct,
            "source": result["source"], "confidence": result.get("confidence"),
            "tf_id": result.get("tf_id"), "target_id": result.get("target_id"),
            "evidence": entry["evidence"], "pubmed_id": entry["pubmed_id"],
        })

    gaps = check_ortholog_gaps(species)

    # --- Metrics ---
    pos_resolved = [e for e in edge_details if e["resolved"] and e["expected"] == "positive"]
    neg_resolved = [e for e in edge_details if e["resolved"] and e["expected"] == "negative"]

    true_pos = sum(1 for e in pos_resolved if e["found"])
    false_neg = sum(1 for e in pos_resolved if not e["found"])
    true_neg = sum(1 for e in neg_resolved if not e["found"])
    false_pos = sum(1 for e in neg_resolved if e["found"])

    recall = true_pos / len(pos_resolved) if pos_resolved else 0.0
    specificity = true_neg / len(neg_resolved) if neg_resolved else None
    precision_gold = (true_pos / (true_pos + false_pos)
                      if (true_pos + false_pos) > 0 else None)

    # --- Random sampling ---
    print(f"\n{'=' * 60}")
    print(f"  {species.upper()} QUALITY REPORT")
    print(f"{'=' * 60}")

    print(f"\n--- Gold Standard ---")
    total_pos = len([e for e in gold if e not in negative_edges])
    total_neg = len(negative_edges)
    print(f"Positive edges: {len(pos_resolved)} resolved of {total_pos} "
          f"({len(positive_edges) - len(pos_resolved)} unresolved)")
    if unresolved:
        print(f"  Unresolved symbols: {', '.join(sorted(set(unresolved)))}")
    print(f"Negative controls: {len(neg_resolved)} resolved of {total_neg}")

    print(f"\nRecall (true positives): {true_pos}/{len(pos_resolved)} = {recall:.1%}")
    for src, cnt in sorted(source_counts.items()):
        print(f"  via {src}: {cnt}")
    print(f"  MISSING: {false_neg}")

    if neg_resolved:
        print(f"Specificity (true negatives): {true_neg}/{len(neg_resolved)} = "
              f"{specificity:.1%}")
        if false_pos:
            fps = [e for e in neg_resolved if e["found"]]
            for e in fps:
                print(f"  FALSE POSITIVE: {e['tf']} -> {e['target']} "
                      f"[{e['source']}] (should be absent)")

    if precision_gold is not None and neg_resolved:
        print(f"Precision (gold standard): {precision_gold:.1%}")

    print(f"\nPer-edge detail:")
    for e in edge_details:
        if e["expected"] == "positive":
            status = "FOUND" if e["found"] else (
                "UNRESOLVED" if not e["resolved"] else "MISSING")
        else:
            status = "FALSE_POS" if e["found"] else "TRUE_NEG"
        src = f" [{e['source']}]" if e.get("source") else ""
        marker = " *" if not e.get("correct", True) else ""
        print(f"  {e['tf']:12s} -> {e['target']:16s}  {status}{src}"
              f"  ({e['evidence']}){marker}")

    gapped = [g for g in gaps if not g["has_ath_ortholog"]]
    if gapped:
        print(f"\nOrtholog gaps: {len(gapped)} master regulators without "
              f"Arabidopsis ortholog:")
        for g in gapped:
            print(f"  {g['symbol']} ({g['gene_id']})")

    # --- Random edge sampling ---
    print(f"\n--- Random Edge Sampling (100 edges) ---")
    sampled = sample_random_edges(db, species, n=100)
    if sampled:
        overlaps = [e["go_overlap"] for e in sampled]
        mean_overlap = sum(overlaps) / len(overlaps)
        nonzero = sum(1 for o in overlaps if o > 0)
        by_source = defaultdict(list)
        for e in sampled:
            by_source[e["source"]].append(e["go_overlap"])

        print(f"Mean GO overlap (Jaccard): {mean_overlap:.4f}")
        print(f"Edges with any GO overlap: {nonzero}/{len(sampled)} "
              f"({nonzero/len(sampled):.0%})")
        print(f"By source:")
        for src, overlaps_src in sorted(by_source.items()):
            mean_src = sum(overlaps_src) / len(overlaps_src)
            nz = sum(1 for o in overlaps_src if o > 0)
            print(f"  {src}: n={len(overlaps_src)}, mean_overlap={mean_src:.4f}, "
                  f"any_overlap={nz}/{len(overlaps_src)}")

    # --- Pathway coherence ---
    print(f"\n--- Pathway Coherence ---")
    coherence = check_pathway_coherence(db, species)
    for pathway, stats in sorted(coherence.items()):
        if "note" in stats:
            print(f"  {pathway}: {stats['pathway_targets']} targets, {stats['note']}")
            continue
        print(f"  {pathway}: {stats['pathway_tfs']} TFs, "
              f"{stats['pathway_targets']} targets")
        if stats["edges_total"] > 0:
            print(f"    interactions: {stats['edges_to_pathway']}/{stats['edges_total']} "
                  f"to pathway ({stats['actual_fraction_interactions']:.4f} vs "
                  f"expected {stats['expected_fraction']:.4f}, "
                  f"enrichment={stats['enrichment_interactions']:.1f}x)")
        if stats["ie_total"] > 0:
            print(f"    GRNBoost2: {stats['ie_to_pathway']}/{stats['ie_total']} "
                  f"to pathway ({stats['actual_fraction_inferred']:.4f} vs "
                  f"expected {stats['expected_fraction']:.4f}, "
                  f"enrichment={stats['enrichment_inferred']:.1f}x)")

    # --- False positive estimation ---
    print(f"\n--- False Positive Estimation (200 random TF-gene pairs) ---")
    fp_est = estimate_false_positives(db, species, n_negative=200)
    if fp_est:
        print(f"Random pairs tested: {fp_est['random_pairs_tested']}")
        print(f"Found in interactions: {fp_est['found_in_interactions']} "
              f"({fp_est['interaction_hit_rate']:.1%})")
        print(f"Found in GRNBoost2: {fp_est['found_in_inferred_edges']} "
              f"({fp_est['inferred_hit_rate']:.1%})")
        print(f"Combined hit rate: {fp_est['combined_hit_rate']:.1%}")
        if fp_est["by_source"]:
            print(f"  By source: {dict(fp_est['by_source'])}")

    # --- Build report ---
    report = {
        "species": species,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gold_standard": {
            "positive_total": total_pos,
            "positive_resolved": len(pos_resolved),
            "negative_total": total_neg,
            "negative_resolved": len(neg_resolved),
            "unresolved_symbols": sorted(set(unresolved)),
            "true_positives": true_pos,
            "false_negatives": false_neg,
            "true_negatives": true_neg,
            "false_positives": false_pos,
            "recall": round(recall, 4),
            "specificity": round(specificity, 4) if specificity is not None else None,
            "precision": round(precision_gold, 4) if precision_gold is not None else None,
            "by_source": dict(source_counts),
            "edge_details": edge_details,
        },
        "random_sample": {
            "n": len(sampled) if sampled else 0,
            "mean_go_overlap": round(mean_overlap, 4) if sampled else None,
            "edges": sampled,
        },
        "pathway_coherence": coherence,
        "false_positive_estimation": fp_est,
        "ortholog_gaps": gaps,
    }

    report_path = DATA_DIR / f"quality_report_{species}.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\nReport written to {report_path}")
    db.close()
    return report


def main():
    if not DB_PATH.exists():
        sys.exit(f"Database not found at {DB_PATH} — run build_db.py first")

    if len(sys.argv) > 1:
        species_list = [sys.argv[1]]
    else:
        species_list = [p.stem.replace("gold_standard_", "")
                        for p in DATA_DIR.glob("gold_standard_*.tsv")]

    if not species_list:
        print("No gold standard files found in", DATA_DIR)
        return

    for sp in sorted(species_list):
        validate_species(sp)


if __name__ == "__main__":
    main()
