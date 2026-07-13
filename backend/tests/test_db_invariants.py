"""Tier 2 — build-DB integrity & sanity invariants against the built database."""
import sqlite3
from pathlib import Path

import pytest

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"
pytestmark = pytest.mark.skipif(not DB.exists(), reason="grn.sqlite3 not built")


@pytest.fixture(scope="module")
def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def one(db, sql, *p):
    return db.execute(sql, p).fetchone()[0]


# ---------- referential integrity ----------

def test_interaction_endpoints_exist(db):
    assert one(db, "SELECT COUNT(*) FROM interactions WHERE source_id NOT IN (SELECT id FROM genes)") == 0
    assert one(db, "SELECT COUNT(*) FROM interactions WHERE target_id NOT IN (SELECT id FROM genes)") == 0


def test_locations_reference_genes(db):
    assert one(db, "SELECT COUNT(*) FROM gene_locations WHERE gene_id NOT IN (SELECT id FROM genes)") == 0


def test_orthologs_reference_genes(db):
    assert one(db, "SELECT COUNT(*) FROM orthologs WHERE gene_a NOT IN (SELECT id FROM genes) "
                   "OR gene_b NOT IN (SELECT id FROM genes)") == 0


def test_go_annotations_reference_genes_and_terms(db):
    assert one(db, "SELECT COUNT(*) FROM go_annotations WHERE gene_id NOT IN (SELECT id FROM genes)") == 0


def test_arabidopsis_motif_layer_wellformed(db):
    """#4: if the TAIR10 binding layer is loaded, it must be sane and well-joined."""
    n = one(db, "SELECT COUNT(*) FROM motif_hits WHERE assembly='TAIR10'")
    if n == 0:
        pytest.skip("arabidopsis motif layer not loaded")
    # every hit joins to a motif and is a significant predicted site
    assert one(db, "SELECT COUNT(*) FROM motif_hits h WHERE h.assembly='TAIR10' "
                   "AND h.motif_id NOT IN (SELECT motif_id FROM motifs)") == 0
    assert one(db, "SELECT COUNT(*) FROM motif_hits WHERE assembly='TAIR10' AND p_value > 1e-4") == 0
    assert one(db, "SELECT COUNT(*) FROM motif_hits WHERE assembly='TAIR10' AND tier != 'JASPAR_scan'") == 0
    # promoters are reachable via an identity crosswalk to arabidopsis genes
    assert one(db, "SELECT COUNT(*) FROM gene_id_crosswalk WHERE species='arabidopsis' "
                   "AND atlas_gene_id NOT IN (SELECT id FROM genes)") == 0
    assert one(db, "SELECT COUNT(*) FROM go_annotations WHERE go_id NOT IN (SELECT go_id FROM go_terms)") == 0


def test_crosswalk_atlas_ids_exist(db):
    assert one(db, "SELECT COUNT(*) FROM gene_id_crosswalk WHERE atlas_gene_id NOT IN (SELECT id FROM genes)") == 0


def test_motif_hits_reference_motifs(db):
    assert one(db, "SELECT COUNT(*) FROM motif_hits WHERE motif_id NOT IN (SELECT motif_id FROM motifs)") == 0


def test_motif_tf_genes_exist(db):
    # tf_gene_id may be NULL, but non-null must resolve to a gene
    assert one(db, "SELECT COUNT(*) FROM motifs WHERE tf_gene_id IS NOT NULL "
                   "AND tf_gene_id NOT IN (SELECT id FROM genes)") == 0


def test_every_located_chromosome_has_a_length(db):
    assert one(db, "SELECT COUNT(*) FROM (SELECT DISTINCT species, chromosome FROM gene_locations) l "
                   "WHERE NOT EXISTS (SELECT 1 FROM chromosomes c "
                   "WHERE c.species=l.species AND c.chromosome=l.chromosome)") == 0


# ---------- coordinate sanity ----------

def test_location_coords_wellformed(db):
    assert one(db, "SELECT COUNT(*) FROM gene_locations WHERE start < 0 OR end < start") == 0


def test_locations_within_chromosome_bounds(db):
    assert one(db, "SELECT COUNT(*) FROM gene_locations l JOIN chromosomes c "
                   "ON c.species=l.species AND c.chromosome=l.chromosome WHERE l.end > c.length") == 0


def test_window_coords_wellformed(db):
    assert one(db, "SELECT COUNT(*) FROM gene_windows WHERE start < 0 OR end <= start") == 0


def test_motif_hits_lie_within_a_promoter_window(db):
    total = one(db, "SELECT COUNT(*) FROM motif_hits")
    if total == 0:
        pytest.skip("no motif hits loaded")
    contained = one(db,
        "SELECT COUNT(*) FROM motif_hits h WHERE EXISTS ("
        "  SELECT 1 FROM gene_windows w WHERE w.ext_gene_id=h.ext_gene_id "
        "  AND w.window_type='promoter' AND w.assembly=h.assembly "
        "  AND w.chromosome=h.chromosome AND h.start >= w.start AND h.end <= w.end)")
    assert contained == total


# ---------- content sanity ----------

def test_inferred_edges_are_labelled(db):
    # petunia is 100% inferred; every such edge must carry the Inferred source
    n_pet = one(db, "SELECT COUNT(*) FROM interactions i JOIN genes g ON g.id=i.source_id "
                    "WHERE g.species='petunia'")
    n_lab = one(db, "SELECT COUNT(*) FROM interactions i JOIN genes g ON g.id=i.source_id "
                    "WHERE g.species='petunia' AND i.sources LIKE '%Inferred%'")
    assert n_pet > 0 and n_pet == n_lab


def test_blast_curated_symbols_applied(db):
    # a few known BLAST-curated regulator symbols should resolve
    for sym, sp in [("AN2", "petunia"), ("ANT1", "tomato")]:
        assert one(db, "SELECT COUNT(*) FROM genes WHERE symbol=? AND species=?", sym, sp) >= 1


def test_no_empty_symbols(db):
    assert one(db, "SELECT COUNT(*) FROM genes WHERE symbol IS NULL OR symbol=''") == 0
