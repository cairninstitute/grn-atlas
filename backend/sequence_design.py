"""Variant, promoter-edit, CRISPR, and primer-design helpers."""

from __future__ import annotations

from typing import Any


def variant_effect(db, gene_id: str, position: int, assembly: str | None = None,
                   window_type: str = "promoter", ref: str | None = None,
                   alt: str | None = None) -> dict[str, Any]:
    gene = db.get_gene(gene_id)
    if not gene:
        return {"gene_id": gene_id, "results": [], "warnings": ["gene not found"]}
    rows = db.conn.execute(
        "SELECT x.ext_gene_id, x.ext_assembly AS assembly, h.chromosome, h.start, h.end, h.motif_id, h.score, h.p_value, "
        "m.tf_gene_id, m.tf_symbol "
        "FROM gene_id_crosswalk x "
        "JOIN motif_hits h ON h.ext_gene_id = x.ext_gene_id AND h.assembly = x.ext_assembly "
        "JOIN motifs m ON m.motif_id = h.motif_id "
        "WHERE x.atlas_gene_id = ? AND h.window_type = ?",
        (gene_id, window_type),
    ).fetchall()
    if assembly:
        rows = [r for r in rows if r["assembly"] == assembly]
    hits = []
    for r in rows:
        if r["start"] <= position <= r["end"]:
            width = max(r["end"] - r["start"], 1)
            center = (r["start"] + r["end"]) / 2.0
            dist = abs(position - center)
            centrality = max(0.0, 1.0 - (dist / width))
            hits.append({
                "motif_id": r["motif_id"],
                "tf_gene_id": r["tf_gene_id"],
                "tf_symbol": r["tf_symbol"],
                "assembly": r["assembly"],
                "chromosome": r["chromosome"],
                "site_start": r["start"],
                "site_end": r["end"],
                "position": position,
                "predicted_effect": "disrupt_candidate" if alt else "site_overlap_candidate",
                "effect_confidence": round(0.4 + 0.5 * centrality, 3),
                "site_score": r["score"],
                "p_value": r["p_value"],
                "note": "Sequence-level allele scoring is not yet implemented; this is overlap-based.",
            })
    hits.sort(key=lambda h: (-(h["effect_confidence"]), h["p_value"]))
    return {
        "gene_id": gene_id,
        "symbol": gene.symbol,
        "species": gene.species,
        "position": position,
        "assembly": assembly,
        "ref": ref,
        "alt": alt,
        "results": hits,
        "warnings": [] if hits else ["no motif-supported promoter sites overlapped the requested position"],
    }


def promoter_edit_prioritization(db, gene_id: str, top: int = 10) -> dict[str, Any]:
    gene = db.get_gene(gene_id)
    if not gene:
        return {"gene_id": gene_id, "results": [], "warnings": ["gene not found"]}
    rows = db.conn.execute(
        "SELECT x.ext_gene_id, x.ext_assembly AS assembly, h.chromosome, h.start, h.end, h.motif_id, h.score, h.p_value, "
        "m.tf_gene_id, m.tf_symbol, i.confidence AS edge_confidence "
        "FROM gene_id_crosswalk x "
        "JOIN motif_hits h ON h.ext_gene_id = x.ext_gene_id AND h.assembly = x.ext_assembly "
        "JOIN motifs m ON m.motif_id = h.motif_id "
        "LEFT JOIN interactions i ON i.source_id = m.tf_gene_id AND i.target_id = x.atlas_gene_id "
        "WHERE x.atlas_gene_id = ? AND h.window_type = 'promoter'",
        (gene_id,),
    ).fetchall()
    out = []
    for r in rows:
        edge_conf = r["edge_confidence"] or 0.0
        score = min((r["score"] / 10.0), 1.0) * 0.6 + min(edge_conf, 1.0) * 0.4
        out.append({
            "tf_gene_id": r["tf_gene_id"],
            "tf_symbol": r["tf_symbol"],
            "motif_id": r["motif_id"],
            "assembly": r["assembly"],
            "chromosome": r["chromosome"],
            "edit_window_start": max(r["start"] - 3, 0),
            "edit_window_end": r["end"] + 3,
            "site_start": r["start"],
            "site_end": r["end"],
            "priority_score": round(score, 3),
            "edge_confidence": edge_conf,
            "note": "Prioritized from motif evidence and any matching atlas edge support; not a sequence-edit efficacy prediction.",
        })
    out.sort(key=lambda r: (-r["priority_score"], r["edit_window_start"]))
    return {
        "gene_id": gene_id,
        "symbol": gene.symbol,
        "species": gene.species,
        "results": out[:top],
        "warnings": [] if out else ["no promoter motif sites were available for this gene"],
    }


def crispr_design(sequence: str | None = None, gene_id: str | None = None, pam: str = "NGG",
                  top: int = 10) -> dict[str, Any]:
    if not sequence:
        return {
            "gene_id": gene_id,
            "guides": [],
            "warnings": ["sequence input is required for guide design in the current implementation"],
        }
    seq = sequence.upper().replace(" ", "").replace("\n", "")
    guides = []
    for i in range(20, len(seq) - 2):
        pam_seq = seq[i:i+3]
        if len(pam_seq) < 3 or pam_seq[1:] != "GG":
            continue
        guide = seq[i-20:i]
        if len(guide) != 20:
            continue
        gc = sum(1 for b in guide if b in "GC") / len(guide)
        penalty = 0.1 if "TTTT" in guide else 0.0
        score = max(0.0, 0.7 - abs(gc - 0.5) - penalty)
        guides.append({
            "guide_sequence": guide,
            "pam": pam_seq,
            "start": i - 20,
            "end": i - 1,
            "gc_fraction": round(gc, 3),
            "priority_score": round(score, 3),
            "notes": ["heuristic sequence-only ranking; off-target search is not yet implemented"],
        })
    guides.sort(key=lambda g: (-g["priority_score"], g["start"]))
    return {"gene_id": gene_id, "pam": pam, "guides": guides[:top], "warnings": [] if guides else ["no compatible guides found"]}


def _tm(seq: str) -> int:
    seq = seq.upper()
    return 2 * sum(1 for b in seq if b in "AT") + 4 * sum(1 for b in seq if b in "GC")


def primer_design(sequence: str | None = None, gene_id: str | None = None,
                  product_min: int = 80, product_max: int = 250, top: int = 10) -> dict[str, Any]:
    if not sequence:
        return {
            "gene_id": gene_id,
            "primer_pairs": [],
            "warnings": ["sequence input is required for primer design in the current implementation"],
        }
    seq = sequence.upper().replace(" ", "").replace("\n", "")
    pairs = []
    for i in range(0, max(len(seq) - 18, 1)):
        left = seq[i:i+20]
        if len(left) < 18:
            continue
        if not (0.35 <= sum(1 for b in left if b in "GC") / len(left) <= 0.65):
            continue
        for j in range(i + product_min, min(i + product_max, len(seq) - 20)):
            right_template = seq[j:j+20]
            if len(right_template) < 18:
                continue
            right = right_template[::-1].translate(str.maketrans("ATGC", "TACG"))
            tm_left = _tm(left)
            tm_right = _tm(right)
            delta = abs(tm_left - tm_right)
            score = max(0.0, 1.0 - delta / 20.0)
            pairs.append({
                "left_primer": left,
                "right_primer": right,
                "left_start": i,
                "right_start": j,
                "product_size": j + len(right_template) - i,
                "tm_left": tm_left,
                "tm_right": tm_right,
                "priority_score": round(score, 3),
                "notes": ["heuristic sequence-only primer ranking; secondary-structure/off-target checks are not yet implemented"],
            })
            if len(pairs) >= top * 5:
                break
        if len(pairs) >= top * 5:
            break
    pairs.sort(key=lambda p: (-p["priority_score"], p["product_size"]))
    return {"gene_id": gene_id, "primer_pairs": pairs[:top], "warnings": [] if pairs else ["no primer pairs met the simple heuristic filters"]}
