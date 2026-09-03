#!/usr/bin/env python3
"""
Load literature-curated regulatory edges for key plant pathways:

  1. Petunia anthocyanin/flavonoid pathway (MBW complex → structural genes)
  2. Petunia vacuolar acidification (AN1-AN11-PH4-PH3 → PH1, PH5)
  3. Tomato fruit ripening (RIN, NOR, FUL1/FUL2 → structural/signaling genes)
  4. Display name fixes for petunia structural genes

Sources (all experimentally validated — ChIP, EMSA, transactivation, genetics):
  - Albert et al. 2014, Plant Cell 26:962-80 (PMID 24642943)
  - Verweij/Spelt et al. 2016, Plant Cell 28:786-803 (PMID 26977085)
  - Quattrocchio et al. 1999, Plant Cell 11:1433-44 (PMID 10449578)
  - Spelt et al. 2000, Plant Cell 12:1619-32 (PMID 11006337)
  - Fujisawa et al. 2013, Plant Cell 25:371-86 (PMID 23386264)
  - Fujisawa et al. 2014, Plant Cell 26:89-101 (PMID 24415769)
  - Jiang et al. 2024, Plant Physiol 194:2322-37 (PMID 37995308)
  - Gao et al. 2018, Hort Res 5:75 (PMID 30588320)

Usage:
    cd backend
    source venv/bin/activate
    python scripts/load_curated_pathway_edges.py

Idempotent: existing edges gain the literature source tag; new edges inserted.
"""
import sqlite3
import json
import re
import sys
from collections import defaultdict

DB_PATH = "data/grn.sqlite3"


# ──────────────────────────────────────────────────────────────────────
# Display name fixes for petunia genes
# ──────────────────────────────────────────────────────────────────────

PETUNIA_DISPLAY_NAMES = {
    # Anthocyanin structural genes
    "Peaxi162Scf00047g01225": "CHS-A",
    "Peaxi162Scf00164g00313": "CHS-B",
    "Peaxi162Scf00536g00092": "CHS-J",
    "Peaxi162Scf00180g00126": "CHI-A",
    "Peaxi162Scf00904g00048": "CHI-A",
    "Peaxi162Scf00080g01317": "CHI-B",
    "Peaxi162Scf00032g00067": "DFR-A",
    "Peaxi162Scf00329g00024": "DFR-B",
    "Peaxi162Scf00150g00218": "F3'5'H-A",
    "Peaxi162Scf00201g00243": "F3'5'H-B",
    "Peaxi162Scf00274g00747": "FLS",

    # MBW complex TFs
    "Peaxi162Scf00118g00310": "AN2",
    "Peaxi162Scf01210g00002": "DPL",
    "Peaxi162Scf00119g00942": "JAF13",
    "Peaxi162Scf00349g00057": "PH4",
    "Peaxi162Scf00912g00146": "AN11",

    # Vacuolar acidification
    "Peaxi162Scf00540g00515": "PH1",
    "Peaxi162Scf00021g00922": "ANL2",
    "Peaxi162Scf00040g00320": "ANL2-like",
}

TOMATO_DISPLAY_NAMES = {
    "Solyc05g012020": "RIN",
    "Solyc06g069430.2": "FUL1",
    "Solyc03g114830.2": "FUL2",
    "Solyc07g055920.2": "TAGL1",
    "Solyc02g077920.2": "CNR",
    "Solyc08g080090.2": "SGR1",
    "Solyc12g008840.1": "TBG4",
    "Solyc09g010210.2": "CEL2",
    "Solyc03g111690.2": "PL",
    "Solyc03g044300.2": "AP2a",
    "Solyc03g031860.2": "PSY1",
    "Solyc06g051800.2": "EXP1",
    "Solyc02g082670.2": "WOX13",
}


# ──────────────────────────────────────────────────────────────────────
# Petunia anthocyanin pathway edges
# From Albert et al. 2014; Spelt et al. 2000; Quattrocchio et al. 1999;
# Verweij et al. 2016
# ──────────────────────────────────────────────────────────────────────

PETUNIA_EDGES = [
    # MBW activator complex: AN2 + AN1 + AN11 → anthocyanin structural genes
    # AN2 (MYB) activates:
    ("AN2", "CHS-A", "activation", "Albert2014,Spelt2000"),
    ("AN2", "CHI-A", "activation", "Albert2014"),
    ("AN2", "DFR-A", "activation", "Albert2014,Spelt2000"),
    ("AN2", "F3'5'H-A", "activation", "Albert2014"),
    ("AN2", "AN1", "activation", "Albert2014"),     # MBW activates AN1

    # AN1 (bHLH) required for:
    ("AN1", "CHS-A", "activation", "Spelt2000,Quattrocchio1999"),
    ("AN1", "CHI-A", "activation", "Spelt2000"),
    ("AN1", "DFR-A", "activation", "Spelt2000,Quattrocchio1999"),
    ("AN1", "F3'5'H-A", "activation", "Spelt2000"),

    # DPL (deep purple) — paralog of AN2, same targets in lip tissue
    ("DPL", "CHS-A", "activation", "Albert2014"),
    ("DPL", "DFR-A", "activation", "Albert2014"),
    ("DPL", "AN1", "activation", "Albert2014"),

    # MYB27 — repressor of anthocyanin pathway (Albert et al. 2014)
    # MYB27 represses AN1 and itself is activated by MBW
    ("AN2", "MYB27", "activation", "Albert2014"),   # MBW activates its own repressor

    # PH4 pathway (vacuolar acidification) — Verweij et al. 2016
    # AN1 + AN11 + PH4 → PH3, PH5, PH1
    ("PH4", "PH1", "activation", "Verweij2016"),
    ("PH4", "PH5", "activation", "Verweij2016"),
    ("PH4", "PH3", "activation", "Verweij2016"),     # PH3 is target of MBW-PH4
    # PH3 (WRKY) feed-forward: PH3 + AN1-AN11-PH4 → PH5
    ("PH3", "PH5", "activation", "Verweij2016"),

    # JAF13 (bHLH) — second bHLH in MBW, partially redundant with AN1
    ("JAF13", "DFR-A", "activation", "Quattrocchio1999"),
    ("JAF13", "CHS-A", "activation", "Quattrocchio1999"),
]


# ──────────────────────────────────────────────────────────────────────
# Tomato ripening edges
# From Fujisawa et al. 2013 (RIN ChIP-chip); Fujisawa et al. 2014
# (FUL1/FUL2 ChIP-chip); Gao et al. 2018 (NOR-like1); Jiang et al. 2024
# ──────────────────────────────────────────────────────────────────────

TOMATO_EDGES = [
    # RIN direct targets (Fujisawa 2013, ChIP-chip validated, PMID 23386264)
    # Using Solyc IDs where display_name resolution might fail
    # Ethylene biosynthesis
    ("Solyc05g012020", "Solyc01g095080.2", "activation", "Fujisawa2013"),  # RIN → ACS2
    ("Solyc05g012020", "Solyc05g050010.2", "activation", "Fujisawa2013"),  # RIN → ACS4
    ("Solyc05g012020", "Solyc07g049530.2", "activation", "Fujisawa2013"),  # RIN → ACO1
    # Carotenoid / lycopene
    ("Solyc05g012020", "Solyc03g031860.2", "activation", "Fujisawa2013"),  # RIN → PSY1
    ("Solyc05g012020", "Solyc03g123760.2", "activation", "Fujisawa2013"),  # RIN → PDS
    # Cell wall
    ("Solyc05g012020", "Solyc06g051800.2", "activation", "Fujisawa2013"),  # RIN → EXP1
    ("Solyc05g012020", "Solyc10g080210.1", "activation", "Fujisawa2013"),  # RIN → PG2a
    ("Solyc05g012020", "Solyc09g010210.2", "activation", "Fujisawa2013"),  # RIN → CEL2
    ("Solyc05g012020", "Solyc12g008840.1", "activation", "Fujisawa2013"),  # RIN → TBG4
    # Chlorophyll degradation
    ("Solyc05g012020", "Solyc08g080090.2", "activation", "Fujisawa2013"),  # RIN → SGR1
    # TFs (RIN regulates other ripening TFs)
    ("Solyc05g012020", "Solyc10g006880.2", "activation", "Fujisawa2013"),  # RIN → NOR
    ("Solyc05g012020", "Solyc02g077920.2", "activation", "Fujisawa2013"),  # RIN → CNR
    ("Solyc05g012020", "Solyc03g044300.2", "activation", "Fujisawa2013"),  # RIN → AP2a
    ("Solyc05g012020", "Solyc06g069430.2", "activation", "Fujisawa2013"),  # RIN → FUL1
    ("Solyc05g012020", "Solyc03g114830.2", "activation", "Fujisawa2013"),  # RIN → FUL2
    ("Solyc05g012020", "Solyc07g055920.2", "activation", "Fujisawa2013"),  # RIN → TAGL1

    # FUL1/FUL2 direct targets (Fujisawa 2014, ChIP-chip, PMID 24415769)
    ("Solyc06g069430.2", "Solyc01g095080.2", "activation", "Fujisawa2014"),  # FUL1 → ACS2
    ("Solyc06g069430.2", "Solyc03g031860.2", "activation", "Fujisawa2014"),  # FUL1 → PSY1
    ("Solyc06g069430.2", "Solyc06g051800.2", "activation", "Fujisawa2014"),  # FUL1 → EXP1
    ("Solyc06g069430.2", "Solyc10g080210.1", "activation", "Fujisawa2014"),  # FUL1 → PG2a
    ("Solyc03g114830.2", "Solyc01g095080.2", "activation", "Fujisawa2014"),  # FUL2 → ACS2
    ("Solyc03g114830.2", "Solyc03g031860.2", "activation", "Fujisawa2014"),  # FUL2 → PSY1
    ("Solyc03g114830.2", "Solyc06g051800.2", "activation", "Fujisawa2014"),  # FUL2 → EXP1

    # WOX13 targets (Jiang et al. 2024, ChIP-seq + RNA-seq, PMID 37995308)
    ("Solyc02g082670.2", "Solyc05g012020", "activation", "Jiang2024"),     # WOX13 → RIN
    ("Solyc02g082670.2", "Solyc10g006880.2", "activation", "Jiang2024"),   # WOX13 → NOR
    ("Solyc02g082670.2", "Solyc01g095080.2", "activation", "Jiang2024"),   # WOX13 → ACS2
    ("Solyc02g082670.2", "Solyc03g031860.2", "activation", "Jiang2024"),   # WOX13 → PSY1
]


# ──────────────────────────────────────────────────────────────────────
# Drought / stress response edges (well-established from literature)
# ──────────────────────────────────────────────────────────────────────

STRESS_EDGES_ARABIDOPSIS = [
    # DREB/CBF cascade (Yamaguchi-Shinozaki & Shinozaki 2006)
    ("CBF1", "COR15A", "activation", "YamaguchiShinozaki2006"),
    ("CBF1", "COR47", "activation", "YamaguchiShinozaki2006"),
    ("CBF1", "RD29A", "activation", "YamaguchiShinozaki2006"),
    ("CBF2", "COR15A", "activation", "YamaguchiShinozaki2006"),
    ("CBF3", "COR15A", "activation", "YamaguchiShinozaki2006"),
    ("CBF3", "RD29A", "activation", "YamaguchiShinozaki2006"),
    ("DREB2A", "RD29A", "activation", "YamaguchiShinozaki2006"),
    ("DREB2A", "RD29B", "activation", "YamaguchiShinozaki2006"),

    # ABA signaling
    ("ABI5", "RD29B", "activation", "Finkelstein2002"),
    ("ABI5", "EM1", "activation", "Finkelstein2002"),
    ("ABI5", "EM6", "activation", "Finkelstein2002"),
    ("ABF2", "RD29B", "activation", "Uno2000"),

    # WRKY defense (Birkenbihl et al. 2017)
    ("WRKY33", "PAD3", "activation", "Birkenbihl2017"),
    ("WRKY33", "CYP71A13", "activation", "Birkenbihl2017"),
    ("WRKY33", "ACS2", "activation", "Li2012"),
    ("WRKY33", "ACS6", "activation", "Li2012"),
]


def resolve_gene_id(conn, symbol_or_name, species):
    """Find the gene ID in our database matching a symbol or display_name."""
    # Try exact ID match first (for Solyc/Peaxi/AT IDs passed directly)
    row = conn.execute(
        "SELECT id FROM genes WHERE id = ? AND species = ?",
        (symbol_or_name, species),
    ).fetchone()
    if row:
        return row[0]

    # Try exact display_name match
    row = conn.execute(
        "SELECT id FROM genes WHERE display_name = ? AND species = ?",
        (symbol_or_name, species),
    ).fetchone()
    if row:
        return row[0]

    # Try exact symbol match
    row = conn.execute(
        "SELECT id FROM genes WHERE symbol = ? AND species = ?",
        (symbol_or_name, species),
    ).fetchone()
    if row:
        return row[0]

    # Try case-insensitive
    row = conn.execute(
        "SELECT id FROM genes WHERE UPPER(display_name) = UPPER(?) AND species = ?",
        (symbol_or_name, species),
    ).fetchone()
    if row:
        return row[0]

    row = conn.execute(
        "SELECT id FROM genes WHERE UPPER(symbol) = UPPER(?) AND species = ?",
        (symbol_or_name, species),
    ).fetchone()
    if row:
        return row[0]

    # Try name field (description) contains
    row = conn.execute(
        "SELECT id FROM genes WHERE species = ? AND name LIKE ? LIMIT 1",
        (species, f"%{symbol_or_name}%"),
    ).fetchone()
    if row:
        return row[0]

    return None


def load_edges(conn, edge_list, species, source_label):
    """Insert or update edges from a curated list."""
    inserted = 0
    updated = 0
    missing = []

    for tf_name, target_name, reg_type, pmid_ref in edge_list:
        tf_id = resolve_gene_id(conn, tf_name, species)
        target_id = resolve_gene_id(conn, target_name, species)

        if not tf_id:
            missing.append(f"TF:{tf_name}")
            continue
        if not target_id:
            missing.append(f"target:{target_name}")
            continue

        existing = conn.execute(
            "SELECT sources FROM interactions WHERE source_id = ? AND target_id = ?",
            (tf_id, target_id),
        ).fetchone()

        if existing:
            sources = json.loads(existing[0])
            if source_label not in sources:
                sources.append(source_label)
                conn.execute(
                    "UPDATE interactions SET sources = ?, regulation_type = ? "
                    "WHERE source_id = ? AND target_id = ?",
                    (json.dumps(sources), reg_type, tf_id, target_id),
                )
                updated += 1
        else:
            conn.execute(
                "INSERT INTO interactions "
                "(source_id, target_id, regulation_type, confidence, sources, pmids) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (tf_id, target_id, reg_type, 0.90,
                 json.dumps([source_label]), json.dumps([pmid_ref])),
            )
            inserted += 1

    return inserted, updated, missing


def fix_display_names(conn):
    """Fix display names for petunia and tomato genes."""
    fixed = 0
    all_names = {**PETUNIA_DISPLAY_NAMES, **TOMATO_DISPLAY_NAMES}
    for gene_id, name in all_names.items():
        existing = conn.execute(
            "SELECT display_name FROM genes WHERE id = ?", (gene_id,)
        ).fetchone()
        if existing is None:
            continue
        if existing[0] != name:
            conn.execute(
                "UPDATE genes SET display_name = ? WHERE id = ?",
                (name, gene_id),
            )
            fixed += 1
            print(f"  {gene_id} → {name}  (was: {existing[0]})")
    return fixed


def find_additional_petunia_genes(conn):
    """Search for petunia genes we might be able to map for edges."""
    missing_genes = {}
    for name in ["MYB27", "MYBx", "PH5", "PH3", "AN9", "3GT",
                  "F3H", "FLS", "5GT", "RT", "UFGT", "ANS",
                  "NOR-like1", "FUL1", "FUL2", "CNR", "TAGL1",
                  "AP2a", "ACS2", "ACS4", "ACO1", "PDS", "ZDS",
                  "PG", "CEL2", "TBG4", "SGR1", "EXP1", "PL",
                  "WOX13", "COR15A", "COR47", "RD29A", "RD29B",
                  "EM1", "EM6", "PAD3", "CYP71A13", "ACS6"]:
        for sp in ["petunia", "tomato", "arabidopsis"]:
            gid = resolve_gene_id(conn, name, sp)
            if gid:
                missing_genes[(name, sp)] = gid
    return missing_genes


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row

    print("=== Step 1: Fix petunia + tomato display names ===")
    fixed = fix_display_names(conn)
    print(f"  Fixed {fixed} display names")
    conn.commit()

    print("\n=== Step 2: Load petunia anthocyanin pathway edges ===")
    ins, upd, miss = load_edges(conn, PETUNIA_EDGES, "petunia", "Literature")
    print(f"  Inserted: {ins}, Updated: {upd}")
    if miss:
        print(f"  Missing genes: {sorted(set(miss))}")
    conn.commit()

    print("\n=== Step 3: Load tomato ripening edges ===")
    ins, upd, miss = load_edges(conn, TOMATO_EDGES, "tomato", "Literature")
    print(f"  Inserted: {ins}, Updated: {upd}")
    if miss:
        print(f"  Missing genes: {sorted(set(miss))}")
    conn.commit()

    print("\n=== Step 4: Load arabidopsis stress/defense edges ===")
    ins, upd, miss = load_edges(conn, STRESS_EDGES_ARABIDOPSIS, "arabidopsis", "Literature")
    print(f"  Inserted: {ins}, Updated: {upd}")
    if miss:
        print(f"  Missing genes: {sorted(set(miss))}")
    conn.commit()

    # Summary
    print("\n=== Summary ===")
    for sp in ["petunia", "tomato", "arabidopsis"]:
        lit = conn.execute(
            "SELECT COUNT(*) FROM interactions i "
            "JOIN genes g ON g.id = i.source_id "
            "WHERE g.species = ? AND i.sources LIKE '%Literature%'",
            (sp,),
        ).fetchone()[0]
        print(f"  {sp}: {lit} edges with Literature source")

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
