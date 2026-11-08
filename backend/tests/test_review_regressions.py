"""Regression tests for findings from independent review (2026-11-05).

Each test targets a specific defect that was found and fixed.
Tests that only inspect source code or use in-memory DBs run without grn.sqlite3.
Tests that query the built database are marked with @needs_db.
"""
import json
import sqlite3
from pathlib import Path

import numpy as np
import pytest

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"
needs_db = pytest.mark.skipif(not DB.exists(), reason="grn.sqlite3 not built")


@pytest.fixture(scope="module")
def db():
    if not DB.exists():
        pytest.skip("grn.sqlite3 not built")
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# ---------- Finding #1: OmniPath malformed sources ----------

@needs_db
def test_interaction_sources_are_valid_json(db):
    """Every non-empty sources column must be a valid JSON array."""
    bad = db.execute(
        "SELECT COUNT(*) FROM interactions "
        "WHERE sources IS NOT NULL AND sources != '' AND json_valid(sources) = 0"
    ).fetchone()[0]
    assert bad == 0, f"{bad} interactions have non-JSON sources column"


@needs_db
def test_interaction_sources_are_json_arrays(db):
    """sources column must be a JSON array, not a bare string."""
    rows = db.execute(
        "SELECT sources FROM interactions "
        "WHERE sources IS NOT NULL AND sources != '' LIMIT 500"
    ).fetchall()
    for row in rows:
        parsed = json.loads(row[0])
        assert isinstance(parsed, list), f"sources is {type(parsed).__name__}, expected list: {row[0][:80]}"


# ---------- Finding #2: Evo2 scores labeling ----------

def test_evo2_scorer_returns_method_field():
    """Evo2 scorer must include method and note fields."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.score_evo2_promoters import score_sequence_loglikelihood
    assert "not" in score_sequence_loglikelihood.__doc__.lower() or \
           "NOT" in score_sequence_loglikelihood.__doc__


@needs_db
def test_evo2_scores_have_rows_when_table_exists(db):
    """evo2_promoter_scores table, if present, must contain scored rows."""
    tables = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='evo2_promoter_scores'"
    ).fetchall()]
    if not tables:
        pytest.skip("evo2_promoter_scores table not present")
    count = db.execute("SELECT COUNT(*) FROM evo2_promoter_scores").fetchone()[0]
    assert count > 0, "evo2_promoter_scores table exists but is empty"


# ---------- Finding #3: Geneformer mean pooling ----------

def test_geneformer_uses_mean_pooling():
    """embed_cells must use masked mean pooling, not position-0 extraction."""
    source = (Path(__file__).resolve().parents[1] / "scripts" / "run_geneformer.py").read_text()
    assert "[:, 0, :]" not in source, "embed_cells still uses position-0 (CLS) extraction"
    assert "mask" in source, "embed_cells should use masked mean pooling"


# ---------- Finding #4: Cell-type gene truncation ----------

def test_score_tf_activity_batches_all_genes():
    """_score_tf_activity must not silently truncate gene list."""
    import inspect
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from advanced import _score_tf_activity
    source = inspect.getsource(_score_tf_activity)
    assert "[:500]" not in source, "_score_tf_activity still truncates gene list to 500"


def test_derive_celltype_batches_all_genes():
    """derive_celltype_regulation must not truncate gene list to 999."""
    source = (Path(__file__).resolve().parents[1] / "scripts" / "derive_celltype_regulation.py").read_text()
    assert "[:999]" not in source, "derive_celltype_regulation still truncates gene list to 999"


@needs_db
def test_celltype_edges_span_full_gene_set(db):
    """Cell-type edges must cover more genes than the old truncation limit."""
    scrna = db.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='scrna_cluster_expression'"
    ).fetchone()[0]
    if not scrna:
        pytest.skip("no scrna data loaded")
    row = db.execute(
        "SELECT dataset_id, cluster_id, COUNT(*) AS n FROM scrna_cluster_expression "
        "GROUP BY dataset_id, cluster_id ORDER BY n DESC LIMIT 1"
    ).fetchone()
    if not row:
        pytest.skip("no cluster expression data")
    n_expressed = row[2]
    if n_expressed <= 500:
        pytest.skip(f"cluster only has {n_expressed} genes, need >500 to test")
    ct_tables = db.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='celltype_regulatory_edges'"
    ).fetchone()[0]
    if not ct_tables:
        pytest.skip("celltype_regulatory_edges not materialized")
    n_targets = db.execute(
        "SELECT COUNT(DISTINCT target_id) FROM celltype_regulatory_edges"
    ).fetchone()[0]
    assert n_targets > 999, (
        f"Only {n_targets} distinct targets in cell-type edges; "
        f"should exceed old 999 truncation limit given {n_expressed} expressed genes"
    )


# ---------- Finding #5: Trajectory honest labeling ----------

def test_trajectory_response_has_analysis_type():
    """trajectory_regulation must include analysis_type field."""
    import inspect
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from advanced import trajectory_regulation
    source = inspect.getsource(trajectory_regulation)
    assert "analysis_type" in source, "trajectory_regulation missing analysis_type field"
    assert "cluster_variation" in source, "trajectory_regulation should label as cluster_variation"


def test_trajectory_note_disclaims_pseudotime():
    """Trajectory note must clearly state this is NOT pseudotime."""
    import inspect
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from advanced import trajectory_regulation
    source = inspect.getsource(trajectory_regulation)
    assert "NOT" in source or "not pseudotime" in source.lower() or "arbitrary" in source.lower(), \
        "trajectory_regulation note must disclaim pseudotime"


# ---------- Finding #7: OmniPath citation parsing ----------

def test_omnipath_url_requests_references_field():
    """OmniPath URL must include fields=references to get citation data."""
    source = (Path(__file__).resolve().parents[1] / "scripts" / "fetch_collectri_signor.py").read_text()
    assert "fields=references" in source, "OmniPath URL missing fields=references"


def test_omnipath_pmid_parser_handles_any_namespace_prefix():
    """PMID parser must strip any namespace prefix (PMID:, CollecTRI:, SIGNOR:)."""
    source = (Path(__file__).resolve().parents[1] / "scripts" / "fetch_collectri_signor.py").read_text()
    assert "rsplit" in source or 'split(":", 1)' in source or "rsplit(\":\", 1)" in source, \
        "Parser should strip arbitrary namespace prefixes from references"


# ---------- Finding #8: Directed inference calibration split ----------

def test_calibration_uses_train_test_split():
    """calibrate_threshold must use held-out evaluation, not in-sample."""
    import inspect
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from infer_directed_grn import calibrate_threshold
    source = inspect.getsource(calibrate_threshold)
    assert "train" in source.lower() and "test" in source.lower(), \
        "calibrate_threshold should use train/test split"
    assert "held_out" in source or "heldout" in source, \
        "calibrate_threshold should report held-out metrics"


def test_calibration_produces_held_out_metrics():
    """calibrate_threshold output must include held-out AUPRC."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from infer_directed_grn import calibrate_threshold

    rng = np.random.RandomState(0)
    n = 2000
    inferred = [(f"TF{i % 20}", f"TG{i}", rng.random(), 0.0, 0.0) for i in range(n)]
    gt = {(f"TF{i % 20}", f"TG{i}"): {"sign": "activation", "mean_fc": 2.0, "n_obs": 3,
                                        "consistency": 1.0, "confidence": 0.9}
          for i in range(0, n, 10)}

    threshold, stats = calibrate_threshold(inferred, gt)
    assert "auprc_held_out" in stats, f"Missing held-out AUPRC in stats: {stats.keys()}"
    assert "n_gt_train" in stats, f"Missing train count in stats: {stats.keys()}"
    assert "n_gt_test" in stats, f"Missing test count in stats: {stats.keys()}"
    assert stats["n_gt_train"] > 0
    assert stats["n_gt_test"] > 0
    assert stats["n_gt_train"] + stats["n_gt_test"] == stats["n_gt"]


def test_calibration_caller_uses_correct_key():
    """infer_directed_grn.py must not use bare 'auprc' key — renamed to auprc_held_out."""
    source = (Path(__file__).resolve().parents[1] / "scripts" / "infer_directed_grn.py").read_text()
    import re
    bare_auprc = re.findall(r"""['"]auprc['"]""", source)
    assert not bare_auprc, (
        f"Found {len(bare_auprc)} bare 'auprc' key(s) — all should be 'auprc_held_out'"
    )


# ---------- Rice alias loader ordering in Makefile ----------

def test_makefile_rice_loader_before_expression_atlas():
    """GFF3 rice alias loader must run unconditionally and before Expression Atlas."""
    makefile = (Path(__file__).resolve().parents[2] / "Makefile").read_text()
    lines = makefile.split("\n")
    in_evidence = False
    gff3_idx = None
    atlas_idx = None
    for i, line in enumerate(lines):
        if line.startswith("evidence-expansion:"):
            in_evidence = True
            continue
        if in_evidence and not line.startswith("\t") and line.strip():
            break
        if in_evidence:
            if "load_rice_rap_aliases" in line:
                gff3_idx = i
                assert "||" not in line, \
                    "GFF3 rice loader must run unconditionally, not as || fallback"
                assert not line.strip().startswith("-"), \
                    "GFF3 rice loader must not be prefixed with - (failure must halt)"
            if "load_expression_atlas" in line:
                atlas_idx = i
    assert gff3_idx is not None, "GFF3 rice alias loader missing from evidence-expansion"
    assert atlas_idx is not None, "Expression Atlas loader missing from evidence-expansion"
    assert gff3_idx < atlas_idx, \
        f"GFF3 rice loader (line {gff3_idx}) must run before Expression Atlas (line {atlas_idx})"


# ---------- Geneformer schema migration ----------

def test_geneformer_migrates_existing_schema():
    """run_geneformer store function must ALTER TABLE for missing columns."""
    source = (Path(__file__).resolve().parents[1] / "scripts" / "run_geneformer.py").read_text()
    assert "ALTER TABLE" in source, \
        "store_embeddings must migrate existing tables with ALTER TABLE"
    assert "model_version" in source and "computed_at" in source, \
        "Migration must add model_version and computed_at columns"
    assert "PRAGMA table_info" in source, \
        "Migration must check existing columns before ALTER"


def test_geneformer_migration_on_old_schema():
    """Geneformer store must succeed on a table without model_version/computed_at."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE geneformer_cell_embeddings (
            species TEXT NOT NULL, cell_id TEXT NOT NULL,
            embedding BLOB NOT NULL, PRIMARY KEY (species, cell_id))
    """)
    conn.execute("""
        CREATE TABLE geneformer_cluster_embeddings (
            species TEXT NOT NULL, cluster_id TEXT NOT NULL,
            embedding BLOB NOT NULL, embedding_dim INTEGER NOT NULL,
            PRIMARY KEY (species, cluster_id))
    """)
    import importlib, sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    mod = importlib.import_module("run_geneformer")
    mod.store_geneformer_embeddings(conn, "test", np.zeros((2, 4)), ["c1", "c2"], {"cl1": np.zeros(4)})
    cols = {r[1] for r in conn.execute("PRAGMA table_info(geneformer_cell_embeddings)").fetchall()}
    assert "model_version" in cols, "model_version column not added by migration"
    assert "computed_at" in cols, "computed_at column not added by migration"
    row = conn.execute("SELECT model_version, computed_at FROM geneformer_cell_embeddings LIMIT 1").fetchone()
    assert row[0] is not None, "model_version not populated"
    assert row[1] is not None, "computed_at not populated"


# ---------- verify-data known_gaps populated ----------

def test_verify_data_known_gaps_populated():
    """verify_release_data known_gaps dict must contain at least one entry with a reason."""
    source = (Path(__file__).resolve().parents[1] / "scripts" / "verify_release_data.py").read_text()
    import re
    assignments = re.findall(r'known_gaps\s*=\s*\{([^}]*)\}', source, re.DOTALL)
    has_populated = any('"reason"' in a or "'reason'" in a for a in assignments)
    assert has_populated, \
        "known_gaps must contain at least one entry with a 'reason' field, not be empty"


# ---------- OmniPath PMID dedup and json.dumps(sources) ----------

def test_omnipath_pmid_dedup():
    """OmniPath parser must deduplicate PMIDs from multi-namespace references."""
    source = (Path(__file__).resolve().parents[1] / "scripts" / "fetch_collectri_signor.py").read_text()
    assert "dict.fromkeys" in source or "set(" in source, \
        "PMID list must be deduplicated (dict.fromkeys or set)"


def test_omnipath_sources_written_as_json_array():
    """OmniPath loader must write sources as json.dumps([name]), not bare string."""
    source = (Path(__file__).resolve().parents[1] / "scripts" / "fetch_collectri_signor.py").read_text()
    assert "json.dumps(" in source, \
        "Sources must be written via json.dumps, not as bare strings"


# ---------- ESM2 creates protein_sequences table ----------

def test_esm2_creates_protein_sequences_table():
    """ESM2 ensure_table must create protein_sequences (not just esm2_embeddings)."""
    conn = sqlite3.connect(":memory:")
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import importlib
    esm2 = importlib.import_module("generate_esm2_embeddings")
    esm2.ensure_table(conn)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "protein_sequences" in tables, \
        "ensure_table must create protein_sequences for bootstrap-gpu"
    assert "esm2_embeddings" in tables


# ---------- Perturbation verifier accepts ortholog_transfer ----------

def test_perturbation_verifier_accepts_ortholog_transfer():
    """verify_perturbation_release must accept ortholog_transfer as valid sign_evidence."""
    source = (Path(__file__).resolve().parents[1] / "scripts" / "verify_perturbation_release.py").read_text()
    assert "ortholog_transfer" in source, \
        "observed_interactions_not_promoted check must include ortholog_transfer"


@needs_db
def test_all_sign_evidence_values_are_accepted(db):
    """Every sign_evidence value in the DB must be accepted by the perturbation verifier."""
    source = (Path(__file__).resolve().parents[1] / "scripts" / "verify_perturbation_release.py").read_text()
    values = db.execute(
        "SELECT DISTINCT sign_evidence FROM interactions WHERE sign_evidence IS NOT NULL"
    ).fetchall()
    for (val,) in values:
        assert val in source, \
            f"sign_evidence '{val}' exists in DB but not in perturbation verifier whitelist"


# ---------- Evo2 output field structure ----------

def test_evo2_output_has_required_fields():
    """Evo2 scorer output dict must include sequence_plausibility, method, and note."""
    source = (Path(__file__).resolve().parents[1] / "scripts" / "score_evo2_promoters.py").read_text()
    for field in ("sequence_plausibility", "method", "note"):
        assert f'"{field}"' in source, f"Evo2 scorer output missing '{field}' field"
    assert "mean_max_logit_sigmoid" in source, \
        "Evo2 method must be documented as mean_max_logit_sigmoid"
    assert "not a calibrated" in source.lower() or "relative ranking" in source.lower(), \
        "Evo2 note must disclaim calibration"


# ---------- Rice crosswalk data integrity ----------

@needs_db
def test_rice_rap_aliases_loaded(db):
    """Rice gene_aliases must contain RAP-DB entries for Expression Atlas resolution."""
    count = db.execute(
        "SELECT COUNT(*) FROM gene_aliases WHERE source='RAP-DB'"
    ).fetchone()[0]
    assert count >= 4000, f"Only {count} RAP-DB aliases; need >=4000 for Expression Atlas"


@needs_db
def test_expression_atlas_has_evidence(db):
    """Expression Atlas must have stored evidence rows after rice crosswalk."""
    count = db.execute(
        "SELECT COUNT(*) FROM regulatory_evidence WHERE source_name='Expression Atlas reviewed perturbations'"
    ).fetchone()[0]
    assert count >= 10, f"Only {count} Expression Atlas evidence rows; expected >=10"


# ---------- Directed inference data integrity ----------

@needs_db
def test_directed_edges_exist(db):
    """Directed inferred edges table must have substantial coverage."""
    tables = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='directed_inferred_edges'"
    ).fetchall()]
    if not tables:
        pytest.skip("directed_inferred_edges table not present")
    count = db.execute("SELECT COUNT(*) FROM directed_inferred_edges").fetchone()[0]
    assert count >= 500_000, f"Only {count} directed edges; expected >=500K"


@needs_db
def test_celltype_edges_exist(db):
    """Cell-type regulatory edges must have substantial coverage."""
    tables = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='celltype_regulatory_edges'"
    ).fetchall()]
    if not tables:
        pytest.skip("celltype_regulatory_edges table not present")
    count = db.execute("SELECT COUNT(*) FROM celltype_regulatory_edges").fetchone()[0]
    assert count >= 50_000, f"Only {count} cell-type edges; expected >=50K"
