"""
One-time migration: add display_name column to genes table and populate it
from Arabidopsis ortholog symbols for plant genes whose symbol == id.
"""
import sqlite3
import sys
import re

DB_PATH = "data/grn.sqlite3"
LOCUS_RE = re.compile(
    r'^(AT[1-5CM]G\d{5}|Solyc\d+g\d+\.\d+|Peaxi\d+Scf\d+g\d+|'
    r'PGSC\d+DMG\d+|LOC_Os\d+g\d+|Nitab\d+g\d+)'
)

PLANT_SPECIES = {"tomato", "petunia", "potato", "rice", "pepper", "tobacco"}


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")

    # Add column if missing
    cols = {r[1] for r in conn.execute("PRAGMA table_info(genes)").fetchall()}
    if "display_name" not in cols:
        conn.execute("ALTER TABLE genes ADD COLUMN display_name TEXT")
        print("Added display_name column")
    else:
        print("display_name column already exists")

    # Build lookup: arabidopsis gene_id -> readable symbol
    arab_symbols = {}
    for gid, sym in conn.execute(
        "SELECT id, symbol FROM genes WHERE species = 'arabidopsis' AND symbol != id"
    ):
        arab_symbols[gid] = sym
    print(f"Arabidopsis readable symbols: {len(arab_symbols)}")

    # For each plant species, find orthologs to arabidopsis
    updated = 0
    for species in PLANT_SPECIES:
        # Get plant genes that need a display name (symbol is a locus ID)
        plant_genes = {}
        for gid, sym in conn.execute(
            "SELECT id, symbol FROM genes WHERE species = ?", (species,)
        ):
            if sym == gid or LOCUS_RE.match(sym):
                plant_genes[gid] = sym

        if not plant_genes:
            print(f"{species}: no locus-ID genes to resolve")
            continue

        # Find orthologs: arabidopsis -> this species
        ortho_map = {}
        rows = conn.execute(
            """SELECT gene_a, gene_b FROM orthologs
               WHERE species_a = 'arabidopsis' AND species_b = ?""",
            (species,),
        ).fetchall()
        for arab_id, plant_id in rows:
            if plant_id in plant_genes and arab_id in arab_symbols:
                existing = ortho_map.get(plant_id)
                candidate = arab_symbols[arab_id]
                if existing is None or len(candidate) < len(existing):
                    ortho_map[plant_id] = candidate

        # Also check reverse direction
        rows2 = conn.execute(
            """SELECT gene_b, gene_a FROM orthologs
               WHERE species_b = 'arabidopsis' AND species_a = ?""",
            (species,),
        ).fetchall()
        for arab_id, plant_id in rows2:
            if plant_id in plant_genes and arab_id in arab_symbols:
                existing = ortho_map.get(plant_id)
                candidate = arab_symbols[arab_id]
                if existing is None or len(candidate) < len(existing):
                    ortho_map[plant_id] = candidate

        # Batch update
        batch = [(name, gid) for gid, name in ortho_map.items()]
        conn.executemany(
            "UPDATE genes SET display_name = ? WHERE id = ?", batch
        )
        updated += len(batch)
        print(f"{species}: {len(batch)}/{len(plant_genes)} genes got display names")

    # Also set display_name for arabidopsis genes that have readable symbols
    arab_batch = [(sym, gid) for gid, sym in arab_symbols.items()]
    conn.executemany(
        "UPDATE genes SET display_name = ? WHERE id = ?", arab_batch
    )
    updated += len(arab_batch)
    print(f"arabidopsis: {len(arab_batch)} genes got display names from own symbols")

    # Set display_name = symbol for human/mouse (already readable)
    for sp in ["human", "mouse"]:
        res = conn.execute(
            "UPDATE genes SET display_name = symbol WHERE species = ? AND symbol != id",
            (sp,),
        )
        print(f"{sp}: {res.rowcount} genes got display names")
        updated += res.rowcount

    conn.commit()
    conn.close()
    print(f"\nDone. Total genes updated: {updated}")


if __name__ == "__main__":
    main()
