import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import calibrate_cross_species_transfer  # noqa: E402


def test_calibration_holds_out_shared_sources_and_gates_independent_class():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE genes (id TEXT PRIMARY KEY, species TEXT);
        CREATE TABLE interactions (
            source_id TEXT,target_id TEXT,regulation_type TEXT,confidence REAL,
            sources TEXT,pmids TEXT,sign TEXT,sign_evidence TEXT
        );
        CREATE TABLE orthology_transfer_candidates (
            species TEXT,source_id TEXT,target_id TEXT,relation_type TEXT,mapping_class TEXT,
                donor_sources TEXT,donor_pmids TEXT,recipient_binding_sources TEXT,
                recipient_cis_support INTEGER,status TEXT,donor_species TEXT
        );
    """)
    for index in range(60):
        source, target = f"S{index}", f"T{index}"
        conn.executemany("INSERT INTO genes VALUES (?,?)", [(source, "recipient"), (target, "recipient")])
        conn.execute(
            "INSERT INTO interactions VALUES (?,?,?,?,?,?,?,?)",
            (source, target, "activation", .9, '["truth"]', "[]", "activation", "measured"),
        )
        conn.execute(
            "INSERT INTO orthology_transfer_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("recipient", source, target, "activation", "reciprocal_unique_synteny",
             '["donor"]', "[]", '["binding"]', 0, "qualified", '["donor_species"]'),
        )
    for index in range(20):
        source, target = f"RS{index}", f"RT{index}"
        conn.executemany("INSERT INTO genes VALUES (?,?)", [(source, "recipient"), (target, "recipient")])
        conn.execute(
            "INSERT INTO interactions VALUES (?,?,?,?,?,?,?,?)",
            (source, target, "repression", .9, '["truth"]', "[]", "repression", "measured"),
        )
    conn.execute(
        "UPDATE orthology_transfer_candidates SET donor_sources='[\"truth\"]' WHERE source_id='S0'"
    )
    result = calibrate_cross_species_transfer.calibrate(conn)
    row = result["classes"][0]
    assert row["cases"] == 59
    assert row["precision"] == 1.0
    assert row["gate_pass"] is True
    assert result["excluded_overlaps"]["shared_source"] == 1
