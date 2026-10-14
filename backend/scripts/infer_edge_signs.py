"""
Populate edge sign + coexpression context on the interactions table.

IMPORTANT (validated): expression-correlation does NOT reliably predict regulatory
sign on the atlas's shallow expression panels. validate_edge_signs.py shows the
correlation rule only matches the activation base rate (~0.69 precision for
"activation", i.e. no lift) and is wrong more often than not for "repression"
(~0.35-0.50 precision). See backend/data/sign_validation_report.json.

Therefore this step is deliberately conservative and honest:

  - sign_evidence = 'measured'  : regulation_type was already activation/repression
                                  (curated DoRothEA / TRRUST / literature). sign is set.
  - sign_evidence = 'unknown'   : everything else. sign stays NULL — we do NOT assert a
                                  direction we cannot defend.

For context only, `sign_r` stores the TF-target expression correlation where it can be
computed (the 3 plant species with expression). It is a COEXPRESSION value, not a
directional claim, and must never be presented as a sign. Consumers use it only as weak
supporting context alongside a clearly-labeled caveat.

Idempotent: resets the three columns each run.

Usage:
    backend/venv/bin/python backend/scripts/infer_edge_signs.py
"""
import gzip
import json
import math
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"

SPECIES_WITH_EXPR = ("arabidopsis", "tomato", "petunia")
MIN_SAMPLES = 4


def pearson(x, y):
    n = len(x)
    if n < 2:
        return 0.0
    mx, my = sum(x) / n, sum(y) / n
    dx = [a - mx for a in x]
    dy = [a - my for a in y]
    num = sum(a * b for a, b in zip(dx, dy))
    d1 = math.sqrt(sum(a * a for a in dx))
    d2 = math.sqrt(sum(a * a for a in dy))
    return num / (d1 * d2) if d1 and d2 else 0.0


def load_expression(species):
    path = DATA_DIR / f"expression_{species}.json.gz"
    if not path.exists():
        return None
    genes = json.loads(gzip.open(path, "rt").read()).get("genes") or {}
    # PLAZA releases can advance transcript/gene-model suffixes while the stable
    # locus remains unchanged (for example Solyc...2 -> Solyc...4).
    for gene_id, values in list(genes.items()):
        genes.setdefault(gene_id.rsplit(".", 1)[0], values)
    return genes


def ensure_columns(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(interactions)")}
    for col, decl in (("sign", "TEXT"), ("sign_evidence", "TEXT"), ("sign_r", "REAL")):
        if col not in cols:
            conn.execute(f"ALTER TABLE interactions ADD COLUMN {col} {decl}")
    conn.commit()


def main():
    conn = sqlite3.connect(DB_PATH)
    ensure_columns(conn)

    conn.execute("UPDATE interactions SET sign = NULL, sign_evidence = 'unknown', sign_r = NULL")
    conn.commit()

    # Measured signs: the only directional claim we assert.
    measured = conn.execute(
        "UPDATE interactions SET sign = regulation_type, sign_evidence = 'measured' "
        "WHERE regulation_type IN ('activation', 'repression')"
    ).rowcount
    conn.commit()
    print(f"Measured signs (curated regulation_type): {measured:,} edge rows")

    # Coexpression context (NOT a sign) for edges in expression-bearing species.
    ctx_rows = 0
    for species in SPECIES_WITH_EXPR:
        genes = load_expression(species)
        if not genes:
            print(f"  {species}: no expression panel, skipping coexpression context")
            continue
        pairs = conn.execute(
            "SELECT DISTINCT i.source_id, i.target_id "
            "FROM interactions i JOIN genes g ON g.id = i.source_id WHERE g.species = ?",
            (species,),
        ).fetchall()
        updates = []
        for tf, tgt in pairs:
            xe = genes.get(tf) or genes.get(tf.rsplit(".", 1)[0])
            ye = genes.get(tgt) or genes.get(tgt.rsplit(".", 1)[0])
            if not xe or not ye or len(xe) != len(ye) or len(xe) < MIN_SAMPLES:
                continue
            updates.append((round(pearson(xe, ye), 4), tf, tgt))
        conn.executemany(
            "UPDATE interactions SET sign_r = ? WHERE source_id = ? AND target_id = ?",
            updates,
        )
        conn.commit()
        print(f"  {species}: coexpression context stored for {len(updates):,} edge pairs")
        ctx_rows += len(updates)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_interactions_sign ON interactions(sign_evidence)")
    conn.commit()

    summary = dict(conn.execute(
        "SELECT sign_evidence, COUNT(*) FROM interactions GROUP BY sign_evidence"
    ).fetchall())
    total = conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
    conn.close()

    print("\nSign coverage (directional claims only come from measured evidence):")
    for ev in ("measured", "unknown"):
        n = summary.get(ev, 0)
        print(f"  {ev:9s}: {n:>12,}  ({100.0 * n / total:.1f}%)")
    print(f"  coexpression context values stored on {ctx_rows:,} edge rows (context only, not a sign)")


if __name__ == "__main__":
    main()
