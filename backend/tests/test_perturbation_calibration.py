import sqlite3
import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import calibrate_perturbation_signs  # noqa: E402


def test_calibration_gates_species_and_sign_separately():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE perturbation_sign_consensus (
            species TEXT, source_id TEXT, target_id TEXT, relation_type TEXT,
            confidence REAL, status TEXT
        );
        CREATE TABLE interactions (
            source_id TEXT, target_id TEXT, regulation_type TEXT,
            sign TEXT, sign_evidence TEXT
        );
    """)
    consensus = []
    interactions = []
    for index in range(60):
        target = f"A{index}"
        observed = "activation" if index < 54 else "repression"
        consensus.append(("test", "TF", target, "activation", 0.8, "accepted"))
        interactions.append(("TF", target, observed, observed, "measured"))
    for index in range(60):
        target = f"R{index}"
        observed = "repression" if index < 30 else "activation"
        consensus.append(("test", "TF", target, "repression", 0.8, "accepted"))
        interactions.append(("TF", target, observed, observed, "measured"))
    conn.executemany("INSERT INTO perturbation_sign_consensus VALUES (?,?,?,?,?,?)", consensus)
    conn.executemany("INSERT INTO interactions VALUES (?,?,?,?,?)", interactions)

    report = calibrate_perturbation_signs.calibrate(conn)

    classes = {
        row["relation_type"]: row for row in report["classes"]
    }
    assert classes["activation"]["gate_pass"] is True
    assert classes["repression"]["gate_pass"] is False
    assert conn.execute(
        "SELECT gate_pass FROM perturbation_sign_calibration "
        "WHERE species='test' AND relation_type='activation'"
    ).fetchone()[0] == 1
