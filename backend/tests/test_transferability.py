import sqlite3

import pytest
import transferability


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
            ("H1", "H1", "Human one", "human", 1, "protein_coding", None, None),
            ("H2", "H2", "Human two", "human", 0, "protein_coding", None, None),
            ("M1", "M1", "Mouse one", "mouse", 1, "protein_coding", None, None),
        ],
    )
    conn.executemany(
        "INSERT INTO interactions VALUES (?,?,?,?,?,?)",
        [
            ("H1", "H2", "activation", 0.9, '["TRRUST"]', '["12345"]'),
            ("M1", "M1", "activation", 0.7, '["TRRUST"]', '[]'),
        ],
    )
    conn.execute("INSERT INTO orthologs VALUES (?,?,?,?,?,?)", ("H1", "M1", "human", "mouse", "1:1", 0.95))
    conn.commit()
    yield conn
    conn.close()


def test_transferability_returns_best_ortholog(db):
    out = transferability.assess_transferability(db, "H1", "mouse", intent="network")
    assert out["best_target_ortholog"]["gene_id"] == "M1"
    assert out["transferability_label"] in {"high", "moderate", "low"}
    assert out["supported_transfer_claims"]
