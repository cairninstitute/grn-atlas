import json
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SCRIPTS = BACKEND / "scripts"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(SCRIPTS))

import build_conserved_regulatory_evidence  # noqa: E402
import load_connectf_evidence  # noqa: E402
import multilayer_control  # noqa: E402
from external_evidence import ensure_schema  # noqa: E402


def base_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE genes (id TEXT PRIMARY KEY, symbol TEXT, species TEXT, is_tf INTEGER);
        CREATE TABLE gene_aliases (gene_id TEXT, alias TEXT);
        CREATE TABLE interactions (
          source_id TEXT, target_id TEXT, regulation_type TEXT, confidence REAL,
          sources TEXT, pmids TEXT, sign TEXT, sign_evidence TEXT
        );
        CREATE TABLE orthologs (
          gene_a TEXT, gene_b TEXT, species_a TEXT, species_b TEXT, rel_type TEXT, score REAL
        );
        CREATE TABLE cis_support_edges (source_id TEXT,target_id TEXT,score REAL);
    """)
    ensure_schema(conn)
    return conn


def test_connectf_preserves_experiment_context_and_statistics(tmp_path):
    conn = base_db()
    conn.executemany("INSERT INTO genes VALUES (?,?,?,?)", [
        ("AT1G00010", "TF", "arabidopsis", 1),
        ("AT1G00020", "TARGET", "arabidopsis", 0),
    ])
    data = tmp_path / "arabidopsis" / "data"
    metadata = tmp_path / "arabidopsis" / "metadata"
    data.mkdir(parents=True)
    metadata.mkdir(parents=True)
    (data / "AT1G00010_DESeq2.csv").write_text('gene,log2FC,padj\nAT1G00020,1.2,0.01\n')
    (metadata / "AT1G00010_DESeq2.txt").write_text(
        "*Transcription_Factor_ID: AT1G00010\n*Experiment_Type: Expression\n"
        "*Technology/Method: RNASeq\n*Edge_Type: Cells:Regulated:TARGET\n"
        "*Tissue/Sample: root\nTreatment_Time: 30 min\n"
    )
    result = load_connectf_evidence.load(conn, tmp_path)
    assert result["perturbation_signed"] == 1
    relation, context, meta = conn.execute(
        "SELECT relation_type,context,metadata FROM regulatory_evidence"
    ).fetchone()
    assert relation == "activation"
    assert json.loads(context)["tissue_sample"] == "root"
    assert json.loads(meta)["log2fc"] == 1.2


def test_connectf_loss_of_function_inverts_observed_fold_change():
    assert load_connectf_evidence.perturbation_mode(Path("TF_lof_DESeq2.csv"), {}) == "loss"
    assert load_connectf_evidence.perturbation_mode(
        Path("TF.csv"), {"genotype": "tf knockout mutant"}
    ) == "loss"


def test_conserved_transfer_requires_cis_support_for_one_donor():
    conn = base_db()
    conn.executemany("INSERT INTO genes VALUES (?,?,?,?)", [
        ("A", "A", "one", 1), ("B", "B", "one", 0),
        ("OA", "OA", "two", 1), ("OB", "OB", "two", 0),
    ])
    conn.execute("INSERT INTO interactions VALUES (?,?,?,?,?,?,?,?)",
                 ("A", "B", "activation", .9, '["curated"]', "[]", "activation", "measured"))
    conn.executemany("INSERT INTO orthologs VALUES (?,?,?,?,?,?)", [
        ("A", "OA", "one", "two", "1:1", 100),
        ("B", "OB", "one", "two", "1:1", 100),
    ])
    conn.execute("INSERT INTO cis_support_edges VALUES ('OA','OB',.8)")
    result = build_conserved_regulatory_evidence.build(conn)
    assert result["stored"] == 1
    assert conn.execute("SELECT relation_type FROM regulatory_evidence").fetchone()[0] == "activation"


def test_reciprocal_unique_synteny_is_exploratory_and_inferred_donors_are_excluded():
    conn = base_db()
    conn.executemany("INSERT INTO genes VALUES (?,?,?,?)", [
        ("A", "A", "one", 1), ("B", "B", "one", 0),
        ("OA", "OA", "two", 1), ("OB", "OB", "two", 0),
        ("C", "C", "one", 1), ("D", "D", "one", 0),
        ("OC", "OC", "two", 1), ("OD", "OD", "two", 0),
    ])
    conn.executemany("INSERT INTO interactions VALUES (?,?,?,?,?,?,?,?)", [
        ("A", "B", "activation", .9, '["curated"]', "[]", "activation", "measured"),
        ("C", "D", "activation", .9, '["Inferred:one"]', "[]", "activation", "measured"),
    ])
    conn.executemany("INSERT INTO orthologs VALUES (?,?,?,?,?,?)", [
        ("A", "OA", "one", "two", "synteny", .8),
        ("B", "OB", "one", "two", "synteny", .8),
        ("C", "OC", "one", "two", "synteny", .8),
        ("D", "OD", "one", "two", "synteny", .8),
    ])
    result = build_conserved_regulatory_evidence.build(conn)
    assert result["projected"] == 1
    assert result["unvalidated"] == 1
    assert conn.execute(
        "SELECT mapping_class,status FROM orthology_transfer_candidates"
    ).fetchone() == ("reciprocal_unique_synteny", "unvalidated")
    assert conn.execute(
        "SELECT directness FROM regulatory_evidence"
    ).fetchone()[0] == "conserved_unvalidated"


def test_multilayer_edges_retain_their_mechanism():
    conn = base_db()
    stored = multilayer_control.replace_source(conn, "reviewed", [{
        "species": "one", "source_id": "A", "target_id": "B",
        "relation_type": "repression", "regulatory_layer": "protein_degradation",
        "confidence": 0.9,
    }])
    assert stored == 1
    assert conn.execute("SELECT regulatory_layer FROM regulatory_layer_edges").fetchone()[0] == "protein_degradation"
