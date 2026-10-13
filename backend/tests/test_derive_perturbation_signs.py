import sqlite3
import sys

from scripts import derive_perturbation_signs


def test_species_scope_does_not_reset_other_species(tmp_path, monkeypatch):
    path = tmp_path / "signs.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE genes (id TEXT PRIMARY KEY, species TEXT);
            CREATE TABLE interactions (
                source_id TEXT, target_id TEXT, sign TEXT, sign_evidence TEXT
            );
            CREATE TABLE perturbation_observations (
                species TEXT, perturbed_gene TEXT, affected_gene TEXT,
                observed_log2fc REAL, dataset_label TEXT, observed_significant INTEGER
            );
            INSERT INTO genes VALUES ('ATTF','arabidopsis'), ('ATTG','arabidopsis'),
                                     ('HTF','human'), ('HTG','human');
            INSERT INTO interactions VALUES ('ATTF','ATTG',NULL,'perturbation'),
                                             ('HTF','HTG','repression','perturbation');
            INSERT INTO perturbation_observations VALUES
                ('arabidopsis','ATTF','ATTG',-2.0,'knocktf',1);
        """)
    monkeypatch.setattr(sys, "argv", ["derive_perturbation_signs.py", "--species", "arabidopsis",
                                       "--db", str(path)])
    derive_perturbation_signs.main()
    with sqlite3.connect(path) as conn:
        assert conn.execute(
            "SELECT sign, sign_evidence FROM interactions WHERE source_id='ATTF'"
        ).fetchone() == ("activation", "perturbation")
        assert conn.execute(
            "SELECT sign, sign_evidence FROM interactions WHERE source_id='HTF'"
        ).fetchone() == ("repression", "perturbation")
