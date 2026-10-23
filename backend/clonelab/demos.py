"""Reproducible Darwin-to-CloneLab scientific demonstrations."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from Bio import SeqIO

from .promoter import retrieve_promoter
from .reference import ReferenceRegistry
from .restriction import restriction_map
from .sequence import sequence_sha256
from .workflow import optimize_construct_design

DEMO_DIR = Path(__file__).with_name("demonstrations")


def list_demonstrations() -> list[dict]:
    return [json.loads(path.read_text()) for path in sorted(DEMO_DIR.glob("*.json"))]


def _network_context(database_path: Path, species: str, gene_id: str) -> dict:
    connection = sqlite3.connect(database_path)
    outbound = connection.execute(
        "SELECT COUNT(*) FROM interactions i JOIN genes g ON g.id=i.source_id WHERE g.species=? AND i.source_id=?",
        (species, gene_id),
    ).fetchone()[0]
    inbound = connection.execute(
        "SELECT COUNT(*) FROM interactions i JOIN genes g ON g.id=i.target_id WHERE g.species=? AND i.target_id=?",
        (species, gene_id),
    ).fetchone()[0]
    evidence = connection.execute(
        "SELECT COUNT(DISTINCT source_name) FROM regulatory_evidence WHERE species=? AND (source_id=? OR target_id=?)",
        (species, gene_id, gene_id),
    ).fetchone()[0]
    connection.close()
    return {"incoming_edges": inbound, "outgoing_edges": outbound, "distinct_evidence_sources": evidence}


def run_demonstration(
    demonstration_id: str,
    *,
    registry: ReferenceRegistry,
    database_path: str | Path,
    plasmid_path: str | Path,
) -> dict:
    config_path = DEMO_DIR / f"{demonstration_id}.json"
    if not config_path.exists():
        raise ValueError(f"unknown CloneLab demonstration: {demonstration_id}")
    config = json.loads(config_path.read_text())
    database_path = Path(database_path)
    promoter = retrieve_promoter(
        registry, database_path, species=config["species"], gene_id=config["gene_id"],
        upstream=config["upstream"], downstream=config["downstream"],
    )
    plasmid_record = SeqIO.read(plasmid_path, "genbank")
    vector = str(plasmid_record.seq).upper()
    eco_sites = restriction_map(vector, ["EcoRI"], topology="circular")["sites"]
    if len(eco_sites) != 1:
        raise ValueError("the authenticated pUC19 fixture must have exactly one EcoRI site")
    insertion_start = eco_sites[0]["top_cut"]
    analysis = optimize_construct_design(
        vector, promoter["sequence"], insertion_start=insertion_start,
        candidate_enzymes=config["candidate_enzymes"], include_tandem=True,
        min_fragment_bp=50, max_fragment_bp=20_000,
    )
    return {
        "demonstration": config,
        "darwin_target": {
            "species": config["species"], "gene_id": config["gene_id"],
            "gene_symbol": config["gene_symbol"],
            "network_context": _network_context(database_path, config["species"], config["gene_id"]),
        },
        "promoter": promoter,
        "vector": {
            "name": "pUC19", "accession": plasmid_record.id, "length": len(vector),
            "sequence": vector, "sequence_sha256": sequence_sha256(vector), "topology": "circular",
        },
        "insertion_start": insertion_start,
        "analysis": analysis,
        "release_gate": "pass" if analysis["optimization"]["best_digest"]["fully_discriminatory"] else "fail",
    }


def demonstration_summary(result: dict) -> dict:
    best = result["analysis"]["optimization"]["best_digest"]
    return {
        "schema": "clonelab-demonstration-result-v1",
        "demonstration": result["demonstration"],
        "darwin_target": result["darwin_target"],
        "promoter": {key: value for key, value in result["promoter"].items() if key != "sequence"},
        "vector": {key: value for key, value in result["vector"].items() if key != "sequence"},
        "insertion_start": result["insertion_start"],
        "constructs": [{key: value for key, value in item.items() if key != "sequence"}
                       for item in result["analysis"]["hypotheses"]],
        "best_digest": best,
        "gel": result["analysis"]["gel"],
        "verification_scope": result["analysis"]["verification_scope"],
        "release_gate": result["release_gate"],
    }
