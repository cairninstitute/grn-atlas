#!/usr/bin/env python3
"""
Load sequence-based (family) orthologs from ortholog_map_plaza.json into the
orthologs table, supplementing the existing synteny-only mappings.

Also builds a gene_aliases table so users can search by common enzyme names
(CHS, CHI, ANS, etc.) in addition to the TAIR symbol (TT4, TT5, LDOX).
"""
import json
import sqlite3
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"

KNOWN_ALIASES = {
    "chalcone synthase": "CHS",
    "chalcone-flavanone isomerase": "CHI",
    "chalcone and stilbene synthase": "CHS",
    "dihydroflavonol 4-reductase": "DFR",
    "dihydroflavonol reductase": "DFR",
    "leucoanthocyanidin dioxygenase": "ANS",
    "anthocyanidin synthase": "ANS",
    "flavanone 3-hydroxylase": "F3H",
    "flavonoid 3'-hydroxylase": "F3'H",
    "flavonoid 3',5'-hydroxylase": "F3'5'H",
    "flavonol synthase": "FLS",
    "phenylalanine ammonia-lyase": "PAL",
    "4-coumarate:coa ligase": "4CL",
    "cinnamate 4-hydroxylase": "C4H",
    "udp-glucose:flavonoid 3-o-glucosyltransferase": "UFGT",
    "glutathione s-transferase phi 12": "GST",
    "production of anthocyanin pigment 1": "MYB75",
    "production of anthocyanin pigment 2": "MYB90",
    "transparent testa 2": "WRKY44",
    "transparent testa 8": "bHLH42",
    "transparent testa glabra 1": "TTG1",
    "transparent testa glabra 2": "WRKY44",
    "myb domain protein 75": "MYB75",
    "myb domain protein 90": "MYB90",
    "myb domain protein 113": "MYB113",
    "myb domain protein 114": "MYB114",
    "basic helix-loop-helix (bhlh) dna-binding superfamily protein": None,
    "wrky dna-binding protein": None,
}

SYMBOL_ALIASES = {
    "TT8": "bHLH42",
    "TT1": "WIP1",
    "TT2": "MYB123",
    "TT16": "ABS",
    "TTG1": "WD40",
    "TTG2": "WRKY44",
    "GL1": "MYB0",
    "GL3": "bHLH1",
    "EGL3": "bHLH2",
    "PAP1": "MYB75",
    "PAP2": "MYB90",
    "MYB111": "PFG3",
    "MYB12": "PFG1",
    "MYB11": "PFG2",
    "HY5": "bZIP56",
    "PIF3": "bHLH8",
    "PIF4": "bHLH9",
    "PIF5": "bHLH15",
    "AN2": "MYB",
    "AN1": "bHLH",
    "AN11": "WD40",
    "JAF13": "bHLH",
    "DPL": "MYB",
    "PHZ": "MYB",
}

ENZYME_PATTERNS = [
    (re.compile(r"chalcone synthase", re.I), "CHS"),
    (re.compile(r"chalcone.*isomerase", re.I), "CHI"),
    (re.compile(r"dihydroflavonol.*reductase", re.I), "DFR"),
    (re.compile(r"leucoanthocyanidin.*dioxygenase", re.I), "ANS"),
    (re.compile(r"anthocyanidin synthase", re.I), "ANS"),
    (re.compile(r"flavanone 3-hydroxylase", re.I), "F3H"),
    (re.compile(r"flavonoid 3.*5.*hydroxylase", re.I), "F3'5'H"),
    (re.compile(r"flavonoid 3.*hydroxylase", re.I), "F3'H"),
    (re.compile(r"flavonol synthase", re.I), "FLS"),
    (re.compile(r"phenylalanine ammonia.lyase", re.I), "PAL"),
    (re.compile(r"cinnamate 4-hydroxylase", re.I), "C4H"),
    (re.compile(r"4-coumarate.*ligase", re.I), "4CL"),
    (re.compile(r"udp.*glucose.*flavonoid.*glucosyltransferase", re.I), "UFGT"),
    (re.compile(r"glutathione s-transferase", re.I), "GST"),
    (re.compile(r"anthocyanin\s*\d", re.I), None),
]


def load_family_orthologs(conn):
    """Load ortholog_map_plaza.json family-based orthologs."""
    map_path = DATA_DIR / "ortholog_map_plaza.json"
    if not map_path.exists():
        print(f"  SKIP: {map_path} not found")
        return 0

    with open(map_path) as f:
        ortho_map = json.load(f)

    existing = set()
    for row in conn.execute("SELECT gene_a, gene_b FROM orthologs"):
        existing.add((row[0], row[1]))

    inserted = 0
    for arab_gene, species_map in ortho_map.items():
        for species, targets in species_map.items():
            for target_id in targets:
                pair = (arab_gene, target_id)
                reverse = (target_id, arab_gene)
                if pair in existing or reverse in existing:
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO orthologs (gene_a, gene_b, species_a, species_b, rel_type, score) "
                    "VALUES (?, ?, 'arabidopsis', ?, 'family', NULL)",
                    (arab_gene, target_id, species),
                )
                existing.add(pair)
                inserted += 1

    conn.commit()
    return inserted


def build_alias_table(conn):
    """Create gene_aliases table with common enzyme/protein names."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gene_aliases (
            gene_id   TEXT NOT NULL,
            alias     TEXT NOT NULL,
            source    TEXT NOT NULL DEFAULT 'auto',
            PRIMARY KEY (gene_id, alias)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_alias_name ON gene_aliases(alias COLLATE NOCASE)")

    rows = conn.execute("SELECT id, symbol, name FROM genes WHERE name IS NOT NULL AND name != ''").fetchall()

    inserted = 0
    for row in rows:
        gene_id, symbol, name = row
        name_lower = name.lower().strip()

        alias = None
        for key, val in KNOWN_ALIASES.items():
            if key in name_lower and val:
                alias = val
                break

        if not alias:
            for pattern, val in ENZYME_PATTERNS:
                if pattern.search(name) and val:
                    alias = val
                    break

        if not alias and symbol in SYMBOL_ALIASES:
            alias = SYMBOL_ALIASES[symbol]

        if alias and alias.upper() != symbol.upper():
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO gene_aliases (gene_id, alias, source) VALUES (?, ?, 'name_match')",
                    (gene_id, alias),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                pass

    conn.commit()
    return inserted


def update_gene_synonyms(conn):
    """Add aliases to the genes.synonyms field so they appear in search."""
    aliases = conn.execute("SELECT gene_id, alias FROM gene_aliases").fetchall()

    updated = 0
    for gene_id, alias in aliases:
        row = conn.execute("SELECT synonyms FROM genes WHERE id = ?", (gene_id,)).fetchone()
        if not row:
            continue
        current = row[0] or ""
        current_list = [s.strip() for s in current.split(";") if s.strip()] if current else []
        if alias not in current_list:
            current_list.append(alias)
            conn.execute("UPDATE genes SET synonyms = ? WHERE id = ?",
                         ("; ".join(current_list), gene_id))
            updated += 1

    conn.commit()
    return updated


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")

    before = conn.execute("SELECT COUNT(*) FROM orthologs").fetchone()[0]
    print(f"Orthologs before: {before}")

    print("Loading family-based orthologs from ortholog_map_plaza.json...")
    n = load_family_orthologs(conn)
    print(f"  Inserted {n} new family-based ortholog pairs")

    after = conn.execute("SELECT COUNT(*) FROM orthologs").fetchone()[0]
    print(f"Orthologs after: {after} (+{after - before})")

    # Verify PAP1 mapping
    pap1 = conn.execute(
        "SELECT gene_b, species_b, rel_type FROM orthologs WHERE gene_a = 'AT1G56650'"
    ).fetchall()
    print(f"\nPAP1 (AT1G56650) orthologs: {len(pap1)}")
    for row in pap1:
        print(f"  → {row[0]} ({row[1]}) [{row[2]}]")

    print("\nBuilding gene_aliases table...")
    n = build_alias_table(conn)
    print(f"  Created {n} aliases")

    print("\nUpdating gene synonyms for search...")
    n = update_gene_synonyms(conn)
    print(f"  Updated {n} genes with alias synonyms")

    # Show some examples
    print("\nSample aliases:")
    for row in conn.execute(
        "SELECT g.symbol, g.species, a.alias FROM gene_aliases a "
        "JOIN genes g ON g.id = a.gene_id ORDER BY a.alias LIMIT 20"
    ):
        print(f"  {row[0]:15} ({row[1]:12}) → {row[2]}")

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
