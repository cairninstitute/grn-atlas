"""Schema and direction helpers for context-aware perturbation evidence."""

from __future__ import annotations

import sqlite3


OBSERVATION_COLUMNS = {
    "experiment_id": "TEXT",
    "replicate_id": "TEXT",
    "tissue": "TEXT",
    "treatment": "TEXT",
    "timepoint": "TEXT",
    "genotype": "TEXT",
    "p_value": "REAL",
    "adjusted_p": "REAL",
    "source_version": "TEXT",
    "pmids": "TEXT NOT NULL DEFAULT '[]'",
    "mapping_status": "TEXT NOT NULL DEFAULT 'mapped'",
}


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS perturbation_observations (
            obs_id INTEGER PRIMARY KEY AUTOINCREMENT,
            species TEXT NOT NULL,
            perturbed_gene TEXT NOT NULL,
            perturbation_type TEXT NOT NULL,
            affected_gene TEXT NOT NULL,
            observed_log2fc REAL,
            observed_significant INTEGER DEFAULT 0,
            dataset_label TEXT,
            metadata TEXT
        )
    """)
    existing = {
        row[1] for row in conn.execute("PRAGMA table_info(perturbation_observations)")
    }
    for name, declaration in OBSERVATION_COLUMNS.items():
        if name not in existing:
            conn.execute(
                f"ALTER TABLE perturbation_observations ADD COLUMN {name} {declaration}"
            )
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_po_species ON perturbation_observations(species);
        CREATE INDEX IF NOT EXISTS idx_po_gene ON perturbation_observations(perturbed_gene);
        CREATE INDEX IF NOT EXISTS idx_po_pair
            ON perturbation_observations(species, perturbed_gene, affected_gene);
        CREATE TABLE IF NOT EXISTS perturbation_sign_consensus (
            species TEXT NOT NULL,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            relation_type TEXT,
            mean_activation_score REAL NOT NULL,
            mean_abs_effect REAL NOT NULL,
            sign_consistency REAL NOT NULL,
            observation_count INTEGER NOT NULL,
            experiment_count INTEGER NOT NULL,
            dataset_count INTEGER NOT NULL,
            datasets TEXT NOT NULL,
            experiment_ids TEXT NOT NULL,
            contexts TEXT NOT NULL,
            direct_binding_sources TEXT NOT NULL,
            status TEXT NOT NULL,
            confidence REAL NOT NULL,
            model_version TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            PRIMARY KEY (species, source_id, target_id)
        );
        CREATE INDEX IF NOT EXISTS idx_psc_species_status
            ON perturbation_sign_consensus(species, status, confidence);
    """)
    conn.commit()


def perturbation_orientation(perturbation_type: str | None) -> int | None:
    """Return +1 for gain-of-function and -1 for loss-of-function."""
    value = (perturbation_type or "").strip().lower().replace("-", "_")
    gain_tokens = (
        "induc", "overexpress", "gain", "activation", "agonist", "crispr_a", "gof",
    )
    loss_tokens = (
        "knock", "loss", "deplet", "silenc", "inhibit", "crispr_ko", "crispr_i",
        "lof", "mutant",
    )
    if any(token in value for token in gain_tokens):
        return 1
    if any(token in value for token in loss_tokens):
        return -1
    return None
