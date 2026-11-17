"""Queries over the non-transcriptional regulatory layer.

`regulatory_layer_edges` holds curated causal relations that are not
transcription: a kinase changing a substrate's activity, a ligase driving
degradation, a complex forming. They are deliberately excluded from the
observed signed graph, because labelling them transcriptional was the defect
that the November 2026 SIGNOR migration fixed.

Excluded is not the same as unavailable, and until this module they were
reachable only through feedback_control.py's `--include-multilayer` flag.
That matters: in the human graph the layer contributes 25 cross-core
macro-circuits that the transcriptional view cannot see, because it is how
separate transcriptional cores actually communicate.

Everything here is read-only.
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict

EVIDENCE_BOUNDARY = (
    "These are curated causal relations at the protein level, not transcription. "
    "They are excluded from the observed signed graph by design. A path through "
    "this layer establishes a documented mechanism, not a measured rate, and says "
    "nothing about timing or magnitude."
)


def _table_exists(conn: sqlite3.Connection) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' "
        "AND name='regulatory_layer_edges'").fetchone() is not None


def _tf_flags(conn: sqlite3.Connection, gene_ids) -> dict[str, bool]:
    if not gene_ids:
        return {}
    out = {}
    ids = list(gene_ids)
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        q = ",".join("?" for _ in chunk)
        for gid, is_tf in conn.execute(
                f"SELECT id, is_tf FROM genes WHERE id IN ({q})", chunk):
            out[gid] = bool(is_tf)
    return out


def _symbols(conn: sqlite3.Connection, gene_ids) -> dict[str, str]:
    if not gene_ids:
        return {}
    out = {}
    ids = list(gene_ids)
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        q = ",".join("?" for _ in chunk)
        for gid, sym in conn.execute(
                f"SELECT id, symbol FROM genes WHERE id IN ({q})", chunk):
            out[gid] = sym
    return out


def summary(conn: sqlite3.Connection, species: str | None = None) -> dict:
    """What the layer holds, by species, layer and source."""
    if not _table_exists(conn):
        return {"available": False, "reason": "regulatory_layer_edges not present",
                "evidence_boundary": EVIDENCE_BOUNDARY}
    where, params = ("WHERE species = ?", [species]) if species else ("", [])
    rows = [
        {"species": s, "regulatory_layer": lay, "relation_type": rel,
         "evidence_source": src, "edges": n}
        for s, lay, rel, src, n in conn.execute(
            f"SELECT species, regulatory_layer, relation_type, evidence_source, "
            f"COUNT(*) FROM regulatory_layer_edges {where} "
            f"GROUP BY species, regulatory_layer, relation_type, evidence_source "
            f"ORDER BY COUNT(*) DESC", params)]
    return {
        "available": True,
        "species_filter": species,
        "total_edges": sum(r["edges"] for r in rows),
        "breakdown": rows,
        "evidence_boundary": EVIDENCE_BOUNDARY,
    }


def _gene_known(conn: sqlite3.Connection, gene_id: str) -> bool:
    return conn.execute("SELECT 1 FROM genes WHERE id = ?",
                        (gene_id,)).fetchone() is not None


def _unknown_gene(gene_id: str) -> dict:
    return {
        "available": True, "gene_id": gene_id, "gene_known": False,
        "upstream_count": 0, "downstream_count": 0, "reached_count": 0,
        "error": f"{gene_id!r} is not an id in the genes table; this is an "
                 "unresolved identifier, not an absence of curated signalling. "
                 "Check the species' id convention before reporting zero.",
        "evidence_boundary": EVIDENCE_BOUNDARY,
    }


def layer_species(conn: sqlite3.Connection, gene_id: str) -> list[str]:
    """Which species' layer this gene appears in. Ids can collide across species."""
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT species FROM regulatory_layer_edges "
        "WHERE source_id = ? OR target_id = ? ORDER BY species",
        (gene_id, gene_id))]


def _layer_gene_count(conn: sqlite3.Connection, species: str | None) -> int:
    where, params = ("WHERE species = ?", [species]) if species else ("", [])
    return conn.execute(
        f"SELECT COUNT(*) FROM (SELECT source_id AS g FROM regulatory_layer_edges "
        f"{where} UNION SELECT target_id FROM regulatory_layer_edges {where})",
        params + params).fetchone()[0]


def _edge_rows(conn, gene_id, direction, species, layers, min_confidence):
    clauses, params = [], []
    if direction == "downstream":
        clauses.append("source_id = ?")
    elif direction == "upstream":
        clauses.append("target_id = ?")
    else:
        clauses.append("(source_id = ? OR target_id = ?)")
    params.extend([gene_id] if direction != "both" else [gene_id, gene_id])
    if species:
        clauses.append("species = ?")
        params.append(species)
    if layers:
        clauses.append("regulatory_layer IN (%s)" % ",".join("?" for _ in layers))
        params.extend(layers)
    clauses.append("confidence >= ?")
    params.append(min_confidence)
    return conn.execute(
        "SELECT source_id, target_id, relation_type, regulatory_layer, confidence, "
        "evidence_source, pmids, metadata FROM regulatory_layer_edges "
        "WHERE " + " AND ".join(clauses) + " ORDER BY confidence DESC, source_id",
        params).fetchall()


def neighborhood(conn: sqlite3.Connection, gene_id: str, *, species: str | None = None,
                 layers: list[str] | None = None, min_confidence: float = 0.0,
                 direction: str = "both", limit: int = 200) -> dict:
    """Signalling edges touching one gene, annotated with TF status."""
    if not _table_exists(conn):
        return {"available": False, "reason": "regulatory_layer_edges not present",
                "evidence_boundary": EVIDENCE_BOUNDARY}
    if not _gene_known(conn, gene_id):
        return _unknown_gene(gene_id)
    resolved, ambiguous = species, []
    if resolved is None:
        found = layer_species(conn, gene_id)
        ambiguous = found if len(found) > 1 else []
        if len(found) == 1:
            resolved = found[0]
    rows = _edge_rows(conn, gene_id, direction, resolved, layers, min_confidence)
    partners = {r[0] for r in rows} | {r[1] for r in rows}
    tf, sym = _tf_flags(conn, partners), _symbols(conn, partners)

    def shape(r):
        src, tgt, rel, lay, conf, source, pmids, meta = r
        try:
            m = json.loads(meta or "{}")
        except (TypeError, ValueError):
            m = {}
        return {
            "source_id": src, "source_symbol": sym.get(src),
            "target_id": tgt, "target_symbol": sym.get(tgt),
            "relation_type": rel, "regulatory_layer": lay,
            "confidence": conf, "evidence_source": source,
            "pmids": json.loads(pmids or "[]"),
            "target_is_tf": tf.get(tgt, False),
            "source_is_tf": tf.get(src, False),
            "original_type": m.get("omnipath_type"),
        }

    up_all = [shape(r) for r in rows if r[1] == gene_id]
    down_all = [shape(r) for r in rows if r[0] == gene_id]
    # Counts are over everything found, never over the truncated payload: an
    # agent quotes these as fact.
    return {
        "available": True,
        "gene_id": gene_id, "symbol": sym.get(gene_id), "gene_known": True,
        "is_tf": tf.get(gene_id, False),
        "species": resolved,
        "upstream": up_all[:limit], "downstream": down_all[:limit],
        "upstream_count": len(up_all), "downstream_count": len(down_all),
        "upstream_returned": min(len(up_all), limit),
        "downstream_returned": min(len(down_all), limit),
        "upstream_truncated": len(up_all) > limit,
        "downstream_truncated": len(down_all) > limit,
        "tf_targets_in_layer": sum(1 for e in down_all if e["target_is_tf"]),
        "tf_regulators_in_layer": sum(1 for e in up_all if e["source_is_tf"]),
        "evidence_boundary": EVIDENCE_BOUNDARY,
        **({"species_ambiguous": ambiguous,
            "warning": "gene appears in more than one species' layer and no "
                       "--species was given; edges from both are mixed"}
           if ambiguous else {}),
    }


MAX_TRACE_EDGES = 500
SATURATION_FRACTION = 0.10


def trace_to_tf(conn: sqlite3.Connection, gene_id: str, *, depth: int = 2,
                species: str | None = None, min_confidence: float = 0.0,
                max_nodes: int = 2000) -> dict:
    """Walk the layer upstream from a gene, reporting which hops are TFs.

    The question this answers is which signalling proteins reach a given
    transcription factor, and by what documented mechanism. Breadth-first and
    bounded; a hit is a documented chain, not a demonstrated cascade.

    Measured on the November 2026 layer, reach past two hops becomes a property
    of the network rather than of the seed: hub kinases reach roughly an eighth
    of all layer genes at depth 3, and three unrelated hubs land within 1.3% of
    each other. Reach is still seed-dependent -- a gene with one upstream edge
    reaches 88 where a hub reaches 919 -- but a result of that size does not
    answer "what is upstream of X". `reached_fraction` and `saturated` say which
    regime a given answer is in; read them before quoting `reached_count`.
    """
    if not _table_exists(conn):
        return {"available": False, "reason": "regulatory_layer_edges not present",
                "evidence_boundary": EVIDENCE_BOUNDARY}
    if not _gene_known(conn, gene_id):
        return _unknown_gene(gene_id)
    resolved = species
    ambiguous = []
    if resolved is None:
        found = layer_species(conn, gene_id)
        ambiguous = found if len(found) > 1 else []
        if len(found) == 1:
            resolved = found[0]

    seen = {gene_id: 0}
    frontier, paths = [gene_id], defaultdict(list)
    truncated_nodes = False
    for level in range(1, depth + 1):
        if not frontier:
            break
        nxt = []
        for node in frontier:
            for src, tgt, rel, lay, conf, source, _p, _m in _edge_rows(
                    conn, node, "upstream", resolved, None, min_confidence):
                paths[node].append({"from": src, "relation_type": rel,
                                    "regulatory_layer": lay, "confidence": conf,
                                    "evidence_source": source, "hop": level})
                if src not in seen:
                    seen[src] = level
                    nxt.append(src)
                if len(seen) >= max_nodes:
                    truncated_nodes = True
                    break
            if truncated_nodes:
                break
        if truncated_nodes:
            break
        frontier = nxt

    tf, sym = _tf_flags(conn, seen), _symbols(conn, seen)
    reached = [{"gene_id": g, "symbol": sym.get(g), "hops": h, "is_tf": tf.get(g, False)}
               for g, h in sorted(seen.items(), key=lambda kv: (kv[1], kv[0]))
               if g != gene_id]
    layer_genes = _layer_gene_count(conn, resolved)
    fraction = (len(reached) / layer_genes) if layer_genes else 0.0

    # The edge detail is the bulk of this payload and it goes into an agent's
    # context. Keep the hop structure, cap the volume.
    kept, budget, edges_truncated = {}, MAX_TRACE_EDGES, False
    for node, es in paths.items():
        if budget <= 0:
            edges_truncated = True
            break
        kept[node] = es[:budget]
        if len(es) > budget:
            edges_truncated = True
        budget -= len(kept[node])

    out = {
        "available": True,
        "gene_id": gene_id, "symbol": sym.get(gene_id), "gene_known": True,
        "is_tf": tf.get(gene_id, False),
        "species": resolved, "depth": depth,
        "reached": reached, "reached_count": len(reached),
        "tf_count": sum(1 for r in reached if r["is_tf"]),
        "layer_genes_in_species": layer_genes,
        "reached_fraction": round(fraction, 4),
        "saturated": fraction > SATURATION_FRACTION,
        "edges_by_node": kept,
        "edges_truncated": edges_truncated,
        "truncated": truncated_nodes,
        "evidence_boundary": EVIDENCE_BOUNDARY,
    }
    if ambiguous:
        out["species_ambiguous"] = ambiguous
        out["warning"] = ("gene appears in more than one species' layer and no "
                          "--species was given; the walk crossed species")
    if out["saturated"]:
        out["saturation_warning"] = (
            f"reached {len(reached):,} genes, {fraction:.1%} of this species' layer. "
            "At this size the result reflects the network's hub structure more than "
            "the seed gene. Report it as reachability, not as the gene's regulators, "
            "or re-run at a lower --depth.")
    return out
