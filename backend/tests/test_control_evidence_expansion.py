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


def test_transfer_resolves_duplicate_ids_to_native_evidence_anchored_gene():
    conn = base_db()
    conn.executemany("INSERT INTO genes VALUES (?,?,?,?)", [
        ("A", "A", "one", 1), ("B", "B", "one", 0),
        ("OMA_A", "Tf", "two", 1), ("OMA_B", "Target", "two", 0),
        ("two:Tf", "TF", "two", 0), ("two:Target", "target", "two", 0),
        ("two:Other", "Other", "two", 0),
    ])
    conn.executemany("INSERT INTO interactions VALUES (?,?,?,?,?,?,?,?)", [
        ("A", "B", "activation", .9, '["donor"]', "[]", "activation", "measured"),
        ("two:Tf", "two:Target", "activation", .9, '["recipient"]', "[]",
         "activation", "measured"),
        ("two:Tf", "two:Other", "activation", .9, '["recipient"]', "[]",
         "activation", "measured"),
    ])
    conn.executemany("INSERT INTO orthologs VALUES (?,?,?,?,?,?)", [
        ("A", "OMA_A", "one", "two", "1:1", 100),
        ("B", "OMA_B", "one", "two", "1:1", 100),
    ])

    build_conserved_regulatory_evidence.build(conn)

    assert conn.execute(
        "SELECT source_id,target_id FROM orthology_transfer_candidates WHERE species='two'"
    ).fetchone() == ("two:Tf", "two:Target")
    assert conn.execute(
        "SELECT reason FROM orthology_transfer_mappings "
        "WHERE source_gene='A' AND target_species='two'"
    ).fetchone()[0].endswith("canonical_alias_resolution")


def test_alias_resolution_learns_unambiguous_species_namespace():
    conn = base_db()
    conn.execute("INSERT INTO genes VALUES ('two:Anchor','Anchor','two',0)")
    for index in range(10):
        conn.executemany("INSERT INTO genes VALUES (?,?,?,?)", [
            (f"OMA_{index}", f"Gene{index}", "two", 0),
            (f"two:Gene{index}", f"gene{index}", "two", 0),
        ])
        conn.execute(
            "INSERT INTO interactions VALUES (?,?,?,?,?,?,?,?)",
            (f"two:Gene{index}", "two:Anchor", "activation", .9, '["native"]', "[]",
             "activation", "measured"),
        )
    conn.executemany("INSERT INTO genes VALUES (?,?,?,?)", [
        ("OMA_U", "Unobserved", "two", 0),
        ("two:Unobserved", "unobserved", "two", 0),
    ])

    aliases = build_conserved_regulatory_evidence._canonical_gene_ids(conn)

    assert aliases["OMA_U"] == "two:Unobserved"


def test_supported_direct_evidence_can_seed_transfer_without_interaction_row():
    conn = base_db()
    conn.executemany("INSERT INTO genes VALUES (?,?,?,?)", [
        ("A", "A", "one", 1), ("B", "B", "one", 0),
        ("OA", "OA", "two", 1), ("OB", "OB", "two", 0),
    ])
    conn.executemany("INSERT INTO orthologs VALUES (?,?,?,?,?,?)", [
        ("A", "OA", "one", "two", "1:1", 1),
        ("B", "OB", "one", "two", "1:1", 1),
    ])
    conn.execute(
        "INSERT INTO regulatory_evidence "
        "(species,source_id,target_id,relation_type,evidence_layer,directness,source_name,"
        "source_version,record_key,confidence,pmids,imported_at) "
        "VALUES ('one','A','B','activation','direct_signed','direct','curated','v1','A|B',"
        ".9,'[\"1\"]',datetime('now'))"
    )

    result = build_conserved_regulatory_evidence.build(conn)
    metadata = json.loads(conn.execute(
        "SELECT metadata FROM orthology_transfer_candidates"
    ).fetchone()[0])

    assert result["projected"] == 1
    assert metadata["donor_evidence_tier"] == "supported"
    assert metadata["supported_donor_count"] == 1


def test_uncalibrated_perturbation_transfer_stays_exploratory():
    conn = base_db()
    conn.executemany("INSERT INTO genes VALUES (?,?,?,?)", [
        ("A", "A", "one", 1), ("B", "B", "one", 0),
        ("OA", "OA", "two", 1), ("OB", "OB", "two", 0),
    ])
    conn.executemany("INSERT INTO orthologs VALUES (?,?,?,?,?,?)", [
        ("A", "OA", "one", "two", "1:1", 1),
        ("B", "OB", "one", "two", "1:1", 1),
    ])
    conn.execute(
        "CREATE TABLE perturbation_sign_consensus "
        "(species TEXT,source_id TEXT,target_id TEXT,relation_type TEXT,confidence REAL,"
        "datasets TEXT,status TEXT)"
    )
    conn.execute(
        "INSERT INTO perturbation_sign_consensus VALUES "
        "('one','A','B','activation',.8,'[\"experiment-1\"]','accepted')"
    )

    build_conserved_regulatory_evidence.build(conn)
    status, metadata_json = conn.execute(
        "SELECT status,metadata FROM orthology_transfer_candidates"
    ).fetchone()
    metadata = json.loads(metadata_json)

    assert status == "unvalidated"
    assert metadata["donor_evidence_tier"] == "exploratory"
    assert metadata["supported_donor_count"] == 0


def test_bounded_paralog_mapping_creates_penalized_exploratory_hypotheses():
    conn = base_db()
    conn.executemany("INSERT INTO genes VALUES (?,?,?,?)", [
        ("A", "A", "one", 1), ("B", "B", "one", 0),
        ("OA1", "OA1", "two", 1), ("OA2", "OA2", "two", 1),
        ("OB", "OB", "two", 0),
    ])
    conn.execute("INSERT INTO interactions VALUES (?,?,?,?,?,?,?,?)",
                 ("A", "B", "activation", .9, '["curated"]', "[]",
                  "activation", "measured"))
    conn.executemany("INSERT INTO orthologs VALUES (?,?,?,?,?,?)", [
        ("A", "OA1", "one", "two", "synteny", .5),
        ("A", "OA2", "one", "two", "synteny", .5),
        ("B", "OB", "one", "two", "synteny", .5),
    ])

    result = build_conserved_regulatory_evidence.build(conn)
    rows = conn.execute(
        "SELECT mapping_class,status,mapping_score FROM orthology_transfer_candidates "
        "ORDER BY source_id"
    ).fetchall()

    assert result["projected"] == 2
    assert all(row[0] == "paralog_aware_synteny" for row in rows)
    assert all(row[1] == "unvalidated" for row in rows)
    assert all(row[2] < .5 for row in rows)


def test_multilayer_edges_retain_their_mechanism():
    conn = base_db()
    stored = multilayer_control.replace_source(conn, "reviewed", [{
        "species": "one", "source_id": "A", "target_id": "B",
        "relation_type": "repression", "regulatory_layer": "protein_degradation",
        "confidence": 0.9,
    }])
    assert stored == 1
    assert conn.execute("SELECT regulatory_layer FROM regulatory_layer_edges").fetchone()[0] == "protein_degradation"
