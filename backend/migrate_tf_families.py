#!/usr/bin/env python3
"""
Classify TFs into families (MYB, bHLH, WRKY, NAC, etc.) by parsing
symbols and names, then propagate via orthologs from Arabidopsis.
Adds a `tf_family` column to the genes table.
"""
import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "grn.sqlite3"

# Ordered: longer/more specific patterns first to avoid mis-classification
FAMILY_PATTERNS = [
    # MYB superfamily
    (re.compile(r'\bMYB[-_]?R?\d|myb domain|myb.related|MYB transcription|myb[-_ ]?like', re.I), "MYB"),
    (re.compile(r'\bMYB\b', re.I), "MYB"),
    # bHLH
    (re.compile(r'\bbHLH|basic helix.loop.helix', re.I), "bHLH"),
    # WRKY
    (re.compile(r'\bWRKY', re.I), "WRKY"),
    # NAC
    (re.compile(r'\bNAC\b|NAC domain|no apical meristem', re.I), "NAC"),
    # AP2/ERF
    (re.compile(r'\bAP2|APETALA2|\bERF\b|\bDREB\b|ethylene.responsive|ethylene response factor', re.I), "AP2/ERF"),
    # bZIP
    (re.compile(r'\bbZIP|basic.leucine zipper|ABRE.binding|TGA\d', re.I), "bZIP"),
    # C2H2 zinc finger
    (re.compile(r'\bC2H2|zinc finger protein|Dof.type|DOF\d|\bDOF\b|salt tolerance zinc', re.I), "C2H2/ZF"),
    # Homeodomain / HD-ZIP
    (re.compile(r'\bHD.ZIP|homeobox|homeodomain|HB\d|HB-\d|homeobox.leucine|KNOTTED|KNOX|BEL', re.I), "HD-ZIP"),
    # GRAS
    (re.compile(r'\bGRAS\b|SCARECROW|DELLA|GAI\b|RGA\b|SCR\b|SHR\b', re.I), "GRAS"),
    # TCP
    (re.compile(r'\bTCP\d|\bTCP\b', re.I), "TCP"),
    # ARF
    (re.compile(r'\bARF\d|\bARF\b|auxin response factor', re.I), "ARF"),
    # GATA
    (re.compile(r'\bGATA\d|\bGATA\b', re.I), "GATA"),
    # SPL
    (re.compile(r'\bSPL\d|\bSPL\b|squamosa promoter', re.I), "SPL"),
    # MADS-box
    (re.compile(r'\bMADS|AGAMOUS|PISTILLATA|APETALA1|SEPALLATA|FLC\b|SOC1|AGL\d', re.I), "MADS"),
    # Trihelix
    (re.compile(r'\btrihelix|GT.factor|GTL\d', re.I), "Trihelix"),
    # HSF
    (re.compile(r'\bHSF\d|\bHSF\b|heat.shock factor|heat stress', re.I), "HSF"),
    # LOB/LBD
    (re.compile(r'\bLOB\b|\bLBD\d|lateral organ boundaries', re.I), "LBD"),
    # TALE (BELL + KNOX)
    (re.compile(r'\bTALE\b|\bBELL?\d', re.I), "TALE"),
    # WOX
    (re.compile(r'\bWOX\d|\bWUS\b|WUSCHEL', re.I), "WOX"),
    # SBP
    (re.compile(r'\bSBP\b', re.I), "SBP"),
    # E2F
    (re.compile(r'\bE2F\b|\bE2F\d', re.I), "E2F"),
    # NF-Y
    (re.compile(r'\bNF.Y|\bHAP\d|\bNF-Y', re.I), "NF-Y"),
    # Whirly
    (re.compile(r'\bWHIRLY|\bWHY\d', re.I), "Whirly"),
    # GeBP
    (re.compile(r'\bGeBP', re.I), "GeBP"),
    # CPP
    (re.compile(r'\bCPP\b|cysteine.rich polycomb', re.I), "CPP"),
    # SRS
    (re.compile(r'\bSRS\d|\bSTY\d', re.I), "SRS"),
    # General TF terms (low priority)
    (re.compile(r'zinc finger|C3H.type', re.I), "ZF-other"),
    (re.compile(r'Integrase.type DNA.binding', re.I), "AP2/ERF"),
]

# Direct symbol → family for well-known genes
SYMBOL_TO_FAMILY = {
    "PAP1": "MYB", "PAP2": "MYB", "MYB75": "MYB", "MYB90": "MYB",
    "GL1": "MYB", "GL3": "bHLH", "EGL3": "bHLH", "TT8": "bHLH",
    "TT2": "MYB", "TTG1": "WD40", "TTG2": "WRKY",
    "AN2": "MYB", "AN1": "bHLH", "AN11": "WD40",
    "JAF13": "bHLH", "DPL": "MYB", "PHZ": "MYB",
    "PIF3": "bHLH", "PIF4": "bHLH", "PIF5": "bHLH", "PIL5": "bHLH",
    "HY5": "bZIP", "HYH": "bZIP",
    "CRF4": "AP2/ERF", "CEJ1": "AP2/ERF",
    "ABF3": "bZIP", "ABF4": "bZIP",
    "STZ": "C2H2/ZF", "LZF1": "C2H2/ZF",
    "SMB": "NAC", "NAP": "NAC",
    "NST1": "NAC", "BIM2": "bHLH",
    "RTV1": "C2H2/ZF",
}


def classify_tf(symbol, name):
    if symbol in SYMBOL_TO_FAMILY:
        return SYMBOL_TO_FAMILY[symbol]
    text = f"{symbol} {name or ''}"
    for pattern, family in FAMILY_PATTERNS:
        if pattern.search(text):
            return family
    return None


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")

    try:
        conn.execute("ALTER TABLE genes ADD COLUMN tf_family TEXT")
        print("Added tf_family column")
    except sqlite3.OperationalError:
        print("tf_family column already exists")

    tfs = conn.execute("SELECT id, symbol, name, species FROM genes WHERE is_tf = 1").fetchall()
    print(f"Total TFs: {len(tfs)}")

    classified = 0
    unclassified = []
    for gene_id, symbol, name, species in tfs:
        family = classify_tf(symbol, name)
        if family:
            conn.execute("UPDATE genes SET tf_family = ? WHERE id = ?", (family, gene_id))
            classified += 1
        else:
            unclassified.append((gene_id, symbol, name, species))

    conn.commit()
    print(f"Classified by name/symbol: {classified}")
    print(f"Unclassified: {len(unclassified)}")

    # Propagate via orthologs: if an unclassified TF has an ortholog with a family, use it
    propagated = 0
    for gene_id, symbol, name, species in unclassified:
        row = conn.execute("""
            SELECT g.tf_family FROM orthologs o
            JOIN genes g ON (g.id = o.gene_a OR g.id = o.gene_b)
            WHERE (o.gene_a = ? OR o.gene_b = ?) AND g.tf_family IS NOT NULL AND g.id != ?
            LIMIT 1
        """, (gene_id, gene_id, gene_id)).fetchone()
        if row and row[0]:
            conn.execute("UPDATE genes SET tf_family = ? WHERE id = ?", (row[0], gene_id))
            propagated += 1

    conn.commit()
    print(f"Propagated via orthologs: {propagated}")

    still_unclassified = conn.execute(
        "SELECT COUNT(*) FROM genes WHERE is_tf = 1 AND tf_family IS NULL"
    ).fetchone()[0]
    print(f"Still unclassified: {still_unclassified}")

    # Summary
    print("\nTF family distribution:")
    for row in conn.execute("""
        SELECT tf_family, COUNT(*) as cnt FROM genes
        WHERE is_tf = 1 AND tf_family IS NOT NULL
        GROUP BY tf_family ORDER BY cnt DESC
    """):
        print(f"  {row[0]:12} {row[1]:>5}")

    print("\nPer-species coverage:")
    for row in conn.execute("""
        SELECT species,
               COUNT(*) as total,
               SUM(CASE WHEN tf_family IS NOT NULL THEN 1 ELSE 0 END) as classified
        FROM genes WHERE is_tf = 1
        GROUP BY species ORDER BY total DESC
    """):
        pct = row[2] / row[1] * 100 if row[1] else 0
        print(f"  {row[0]:12} {row[2]:>5}/{row[1]:<5} ({pct:.0f}%)")

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
