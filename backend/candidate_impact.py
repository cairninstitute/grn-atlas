"""Rank regulatory candidates by their marginal effect on feedback structure."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict

import networkx as nx


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS regulatory_candidate_impacts (
            species TEXT NOT NULL, source_id TEXT NOT NULL, target_id TEXT NOT NULL,
            relation_type TEXT NOT NULL, evidence_tier TEXT NOT NULL,
            closes_cycle INTEGER NOT NULL, shortest_return_path INTEGER,
            feedback_nodes_added INTEGER NOT NULL, existing_cores_merged INTEGER NOT NULL,
            impact_score REAL NOT NULL, rank INTEGER,
            path_genes TEXT NOT NULL DEFAULT '[]',
            PRIMARY KEY(species,source_id,target_id,relation_type)
        );
        CREATE INDEX IF NOT EXISTS idx_rci_species_rank
            ON regulatory_candidate_impacts(species,rank);
    """)


def rank_candidates(conn: sqlite3.Connection, species_filter: str | None = None) -> dict:
    ensure_schema(conn)
    where = "WHERE species=?" if species_filter else ""
    args = (species_filter,) if species_filter else ()
    species_rows = conn.execute(
        f"SELECT DISTINCT species FROM regulatory_edge_candidates {where} ORDER BY species", args
    ).fetchall()
    summaries = {}
    for (species,) in species_rows:
        graph = nx.DiGraph()
        graph.add_nodes_from(row[0] for row in conn.execute(
            "SELECT id FROM genes WHERE species=?", (species,)
        ))
        graph.add_edges_from(conn.execute(
            "SELECT i.source_id,i.target_id FROM interactions i "
            "JOIN genes s ON s.id=i.source_id JOIN genes t ON t.id=i.target_id "
            "WHERE s.species=? AND t.species=? AND i.sign IN ('activation','repression') "
            "AND i.sign_evidence IN ('measured','perturbation') AND i.confidence>=0.5",
            (species, species),
        ))
        components = list(nx.strongly_connected_components(graph))
        component_of = {gene: index for index, members in enumerate(components) for gene in members}
        condensation = nx.condensation(graph, components)
        cyclic = {
            index for index, members in enumerate(components)
            if len(members) > 1 or any(graph.has_edge(gene, gene) for gene in members)
        }
        rows = []
        for source, target, relation, confidence, tier in conn.execute(
            "SELECT source_id,target_id,relation_type,confidence,evidence_tier "
            "FROM regulatory_edge_candidates WHERE species=? AND status='candidate'",
            (species,),
        ):
            source_component = component_of.get(source)
            target_component = component_of.get(target)
            closes = False
            path_components: list[int] = []
            path_genes: list[str] = []
            if source_component is not None and target_component is not None:
                if source_component == target_component:
                    closes = source == target or source_component in cyclic
                    path_components = [source_component]
                else:
                    try:
                        path_components = nx.shortest_path(
                            condensation, target_component, source_component,
                        )
                        closes = True
                    except nx.NetworkXNoPath:
                        pass
            if closes:
                path_genes = [
                    sorted(condensation.nodes[index]["members"])[0]
                    for index in path_components
                ]
            added = sum(
                len(condensation.nodes[index]["members"])
                for index in path_components if index not in cyclic
            ) if closes else 0
            merged = sum(index in cyclic for index in path_components) if closes else 0
            score = float(confidence) * (
                1.0 + min(added, 25) / 10.0 + min(merged, 5) * 0.35
            ) if closes else float(confidence) * 0.1
            rows.append((species, source, target, relation, tier, int(closes),
                         max(0, len(path_components) - 1) if closes else None,
                         added, merged, round(score, 6), None, json.dumps(path_genes)))
        rows.sort(key=lambda row: (-row[9], -row[7], row[1], row[2], row[3]))
        rows = [row[:10] + (rank, row[11]) for rank, row in enumerate(rows, start=1)]
        conn.execute("DELETE FROM regulatory_candidate_impacts WHERE species=?", (species,))
        conn.executemany(
            "INSERT INTO regulatory_candidate_impacts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows,
        )
        summaries[species] = {
            "candidates": len(rows),
            "cycle_closing": sum(row[5] for row in rows),
            "potential_feedback_nodes": sum(row[7] for row in rows if row[5]),
        }
    conn.commit()
    return summaries


def top_impacts(conn: sqlite3.Connection, species: str, limit: int = 50) -> list[dict]:
    ensure_schema(conn)
    rows = conn.execute(
        "SELECT i.source_id,i.target_id,i.relation_type,i.evidence_tier,i.closes_cycle,"
        "i.shortest_return_path,i.feedback_nodes_added,i.existing_cores_merged,i.impact_score,"
        "i.rank,i.path_genes,c.support_class,c.confidence,c.evidence_sources "
        "FROM regulatory_candidate_impacts i JOIN regulatory_edge_candidates c USING "
        "(species,source_id,target_id,relation_type) WHERE i.species=? ORDER BY i.rank LIMIT ?",
        (species, limit),
    ).fetchall()
    keys = ("source_id", "target_id", "relation_type", "evidence_tier", "closes_cycle",
            "shortest_return_path", "feedback_nodes_added", "existing_cores_merged",
            "impact_score", "rank", "path_genes", "support_class", "confidence", "sources")
    result = []
    for row in rows:
        item = dict(zip(keys, row))
        item["closes_cycle"] = bool(item["closes_cycle"])
        item["path_genes"] = json.loads(item["path_genes"])
        item["sources"] = json.loads(item["sources"])
        result.append(item)
    return result
