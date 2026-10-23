"""Atlas-to-genome promoter retrieval with explicit coordinate provenance."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .reference import ReferenceRegistry


def retrieve_promoter(
    registry: ReferenceRegistry,
    database_path: str | Path,
    *,
    species: str,
    gene_id: str,
    upstream: int = 2000,
    downstream: int = 500,
) -> dict:
    if upstream < 0 or downstream < 0 or upstream + downstream <= 0:
        raise ValueError("promoter window lengths must be non-negative and non-empty")
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        """SELECT c.atlas_gene_id, c.ext_gene_id, c.ext_assembly,
                  w.chromosome, w.start, w.end, w.strand
           FROM gene_id_crosswalk c
           JOIN gene_windows w ON w.ext_gene_id = c.ext_gene_id
                              AND w.assembly = c.ext_assembly
          WHERE c.species = ? AND c.atlas_gene_id = ? AND w.window_type = 'gene_body'
          LIMIT 1""",
        (species, gene_id),
    ).fetchone()
    connection.close()
    if row is None:
        raise ValueError(f"no genome crosswalk and gene body are available for {species} {gene_id}")
    if row["strand"] == 1:
        tss = row["start"]
        start, end = max(0, tss - upstream), tss + downstream
    elif row["strand"] == -1:
        tss = row["end"]
        start, end = max(0, tss - downstream), tss + upstream
    else:
        raise ValueError(f"gene {gene_id} has an unknown strand")
    result = registry.retrieve(
        species=species, assembly=row["ext_assembly"], record_id=row["chromosome"],
        start=start, end=end, strand=row["strand"], molecule_type="genome",
    )
    return {
        **result,
        "gene_id": row["atlas_gene_id"],
        "external_gene_id": row["ext_gene_id"],
        "region_type": "promoter",
        "tss_zero_based": tss,
        "upstream_bp": upstream,
        "downstream_bp": downstream,
        "orientation": "transcriptional_5_to_3",
        "coordinate_source": "atlas gene_id_crosswalk + gene_windows",
    }
