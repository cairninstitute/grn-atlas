import sqlite3

import planning
import pytest


@pytest.fixture()
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE genes (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            species TEXT NOT NULL,
            is_tf INTEGER NOT NULL,
            gene_type TEXT,
            synonyms TEXT,
            symbol_source TEXT
        );
        CREATE TABLE interactions (
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            regulation_type TEXT NOT NULL,
            confidence REAL NOT NULL,
            sources TEXT NOT NULL,
            pmids TEXT NOT NULL DEFAULT '[]',
            PRIMARY KEY (source_id, target_id)
        );
        CREATE TABLE inferred_edges (
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            method TEXT NOT NULL DEFAULT 'GRNBoost2',
            importance REAL NOT NULL,
            species TEXT NOT NULL,
            PRIMARY KEY (source_id, target_id, method)
        );
        CREATE TABLE motifs (
            motif_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            jaspar_id TEXT,
            tf_gene_id TEXT,
            tf_symbol TEXT
        );
        CREATE TABLE motif_hits (
            ext_gene_id TEXT NOT NULL,
            motif_id TEXT NOT NULL,
            assembly TEXT NOT NULL,
            window_type TEXT NOT NULL,
            chromosome TEXT NOT NULL,
            start INTEGER NOT NULL,
            end INTEGER NOT NULL,
            strand INTEGER NOT NULL,
            score REAL,
            p_value REAL,
            tier TEXT,
            site_confidence REAL
        );
        CREATE TABLE gene_id_crosswalk (
            species TEXT NOT NULL,
            atlas_gene_id TEXT NOT NULL,
            ext_gene_id TEXT NOT NULL,
            ext_assembly TEXT NOT NULL,
            relation TEXT NOT NULL DEFAULT '1:1',
            PRIMARY KEY (atlas_gene_id, ext_gene_id)
        );
        CREATE TABLE pathway_annotations (
            gene_id TEXT NOT NULL,
            pathway_id TEXT NOT NULL,
            PRIMARY KEY (gene_id, pathway_id)
        );
        CREATE TABLE trait_associations (
            gene_id TEXT NOT NULL,
            trait TEXT NOT NULL,
            pubmed_id TEXT,
            source TEXT NOT NULL DEFAULT 'GWAS Catalog',
            PRIMARY KEY (gene_id, trait)
        );
        CREATE TABLE orthologs (
            gene_a TEXT NOT NULL,
            gene_b TEXT NOT NULL,
            species_a TEXT NOT NULL,
            species_b TEXT NOT NULL,
            rel_type TEXT,
            score REAL,
            PRIMARY KEY (gene_a, gene_b)
        );
    """)
    conn.executemany(
        "INSERT INTO genes (id,symbol,name,species,is_tf,gene_type,synonyms,symbol_source) VALUES (?,?,?,?,?,?,?,?)",
        [
            ("TF1", "TF1", "TF one", "human", 1, "protein_coding", None, None),
            ("TG1", "TG1", "Target one", "human", 0, "protein_coding", None, None),
            ("AT1", "AN2", "Anthocyanin 2", "petunia", 1, "protein_coding", None, None),
        ],
    )
    conn.executemany(
        "INSERT INTO interactions VALUES (?,?,?,?,?,?)",
        [
            ("TF1", "TG1", "activation", 0.9, '["TRRUST"]', '["12345"]'),
            ("TF1", "TF1", "activation", 0.7, '["TRRUST"]', '[]'),
            ("AT1", "AT1", "activation", 0.6, '["Inferred:Arabidopsis"]', '[]'),
        ],
    )
    conn.execute("INSERT INTO inferred_edges VALUES (?,?,?,?,?)", ("TF1", "TG1", "GRNBoost2", 1.7, "human"))
    conn.execute("INSERT INTO motifs VALUES (?,?,?,?,?)", ("M1|TF1", "JASPAR2024", "MA1", "TF1", "TF1"))
    conn.execute("INSERT INTO gene_id_crosswalk VALUES (?,?,?,?,?)", ("human", "TG1", "TG1.1", "GRCh38", "1:1"))
    conn.execute(
        "INSERT INTO motif_hits VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("TG1.1", "M1|TF1", "GRCh38", "promoter", "1", 100, 110, 1, 10.0, 1e-6, "JASPAR_scan", 0.9),
    )
    conn.execute("INSERT INTO pathway_annotations VALUES (?,?)", ("TG1", "P1"))
    conn.execute("INSERT INTO trait_associations VALUES (?,?,?,?)", ("TG1", "Trait A", "111", "GWAS Catalog"))
    conn.execute("INSERT INTO orthologs VALUES (?,?,?,?,?,?)", ("AT1", "TF1", "petunia", "human", "ortholog", 0.8))
    conn.commit()
    yield conn
    conn.close()


def test_triage_candidates_ranks_tf_first(db):
    out = planning.triage_candidates(db, ["TG1", "TF1"], intent="network")
    assert out["ranked_candidates"][0]["gene_id"] == "TF1"
    assert out["ranked_candidates"][0]["priority_score"] >= out["ranked_candidates"][1]["priority_score"]


def test_triage_candidates_excludes_missing(db):
    out = planning.triage_candidates(db, ["TF1", "NOPE"], intent="experiment")
    assert any(item["gene_id"] == "NOPE" for item in out["excluded_genes"])


def test_prioritize_experiments_returns_recommendations(db):
    out = planning.prioritize_experiments(db, ["TF1"], intent="experiment")
    assert out["plans"][0]["gene_id"] == "TF1"
    assert len(out["plans"][0]["recommended_experiments"]) > 0
    assert out["plans"][0]["recommended_experiments"][0]["priority_score"] > 0
