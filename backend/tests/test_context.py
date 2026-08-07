import sqlite3

import context


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE genes (id TEXT PRIMARY KEY, symbol TEXT, name TEXT, species TEXT, is_tf INTEGER, gene_type TEXT, synonyms TEXT, symbol_source TEXT);
        CREATE TABLE interactions (source_id TEXT, target_id TEXT, regulation_type TEXT, confidence REAL, sources TEXT, pmids TEXT);
        CREATE TABLE orthologs (gene_a TEXT, gene_b TEXT, species_a TEXT, species_b TEXT, rel_type TEXT, score REAL);
        CREATE TABLE motif_hits (ext_gene_id TEXT, motif_id TEXT, assembly TEXT, window_type TEXT, chromosome TEXT, start INTEGER, end INTEGER, strand INTEGER, score REAL, p_value REAL, tier TEXT, site_confidence REAL);
        CREATE TABLE pathway_annotations (gene_id TEXT, pathway_id TEXT);
        CREATE TABLE trait_associations (gene_id TEXT, trait TEXT, pubmed_id TEXT, source TEXT);
    """)
    conn.executemany(
        "INSERT INTO genes VALUES (?,?,?,?,?,?,?,?)",
        [
            ("H1", "TP53", "human gene", "human", 1, "protein_coding", None, None),
            ("A1", "HY5", "arabidopsis gene", "arabidopsis", 1, "protein_coding", None, None),
        ],
    )
    conn.execute("INSERT INTO interactions VALUES (?,?,?,?,?,?)", ("H1", "H1", "activation", 0.9, '["TRRUST"]', '[]'))
    conn.execute("INSERT INTO orthologs VALUES (?,?,?,?,?,?)", ("A1", "H1", "arabidopsis", "human", "ortholog", 0.7))
    conn.execute("INSERT INTO pathway_annotations VALUES (?,?)", ("H1", "P1"))
    conn.execute("INSERT INTO trait_associations VALUES (?,?,?,?)", ("H1", "Trait A", "111", "GWAS Catalog"))
    conn.commit()
    return conn


def test_network_readiness_for_human():
    conn = _db()
    report = context.build_readiness_report(conn, "human", "network")
    assert report["readiness_score"] > 0.5
    assert report["recommended_skills"]
    conn.close()


def test_traits_gap_for_arabidopsis():
    conn = _db()
    report = context.build_readiness_report(conn, "arabidopsis", "traits")
    assert any(g["layer"] == "trait_associations" for g in report["coverage_gaps"])
    conn.close()


def test_unknown_intent_is_reported():
    conn = _db()
    report = context.build_readiness_report(conn, "human", "unknown")
    assert report["readiness_score"] == 0.0
    assert report["coverage_gaps"][0]["status"] == "unsupported"
    conn.close()
