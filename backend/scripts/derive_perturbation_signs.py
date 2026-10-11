"""
Assign experiment-backed activation/repression signs from TF-perturbation data.

Expression correlation was validated as useless for sign (see validate_edge_signs.py), but
the ConnecTF inducible-TARGET DEGs are a *measured* directional signal: inducing a TF and
seeing a target go up means the TF activates it (down = represses). For edges that have such
an observation we set a directional sign from the DEG — a far stronger signal than correlation
(validated ~0.90 agreement with curated signs at |log2FC| >= 1 vs a ~0.77 base rate).

Signs are written as a distinct evidence tier so provenance stays explicit:

  - sign_evidence = 'measured'      : curated regulation_type (set by infer_edge_signs.py)
  - sign_evidence = 'perturbation'  : derived here from induction DEGs; trustworthy direction,
                                      but NOT independent of the ConnecTF observations, so the
                                      calibration scorer ignores this tier (no self-validation)
  - sign_evidence = 'unknown'       : no directional evidence

Conservative by design: only pairs whose mean induction log2FC has |value| >= MIN_ABS_LOG2FC
get a sign, and curated 'measured' signs are never overwritten.

Idempotent. Depends on perturbation_observations, so it runs in `make enrich` after
load_connectf_perturbations.py.

Usage:
    backend/venv/bin/python backend/scripts/derive_perturbation_signs.py
"""
import sqlite3
import statistics
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"
MIN_ABS_LOG2FC = 1.0
# Map each perturbation dataset to how its DEG log2FC relates to the regulatory sign:
#   gain-of-function (induction/overexpression): target UP  => TF activates it  (+1)
#   loss-of-function (knockout/knockdown):       target DOWN => TF activates it  (-1)
# The "activation score" of an observation is orientation * log2FC; a positive mean means
# activation, negative means repression.
DATASET_ORIENTATION = {
    "connectf_target": +1,   # ConnecTF inducible TARGET — gain of function
    "knocktf": -1,           # KnockTF knockdown/knockout — loss of function
}


def main():
    conn = sqlite3.connect(DB_PATH)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(interactions)")}
    if "sign_evidence" not in cols:
        print("sign columns missing — run infer_edge_signs.py first (part of make db).")
        return

    # Idempotent reset of our own tier only.
    conn.execute("UPDATE interactions SET sign = NULL, sign_evidence = 'unknown' "
                 "WHERE sign_evidence = 'perturbation'")
    conn.commit()

    labels = tuple(DATASET_ORIENTATION)
    placeholders = ",".join("?" * len(labels))
    agg = defaultdict(list)
    for tf, tgt, fc, label in conn.execute(
        f"SELECT perturbed_gene, affected_gene, observed_log2fc, dataset_label "
        f"FROM perturbation_observations "
        f"WHERE dataset_label IN ({placeholders}) AND observed_significant = 1", labels
    ):
        if fc is not None:
            # Orient to a common "activation score" so LOF and GOF evidence combine correctly.
            agg[(tf, tgt)].append(DATASET_ORIENTATION[label] * fc)

    updates = []
    for (tf, tgt), scores in agg.items():
        mean_score = statistics.mean(scores)
        if abs(mean_score) < MIN_ABS_LOG2FC:
            continue
        sign = "activation" if mean_score > 0 else "repression"
        updates.append((sign, tf, tgt))

    # Only fill edges that have no curated sign; never overwrite 'measured'.
    conn.executemany(
        "UPDATE interactions SET sign = ?, sign_evidence = 'perturbation' "
        "WHERE source_id = ? AND target_id = ? AND (sign_evidence IS NULL OR sign_evidence = 'unknown')",
        updates,
    )
    # Normalize any rows inserted after infer_edge_signs ran (e.g. ConnecTF edges from
    # `make enrich`) so the tier column stays clean: NULL -> 'unknown'.
    conn.execute("UPDATE interactions SET sign_evidence = 'unknown' WHERE sign_evidence IS NULL")
    conn.commit()

    summary = dict(conn.execute(
        "SELECT sign_evidence, COUNT(*) FROM interactions GROUP BY sign_evidence").fetchall())
    conn.close()
    print(f"Candidate directional pairs (|mean log2FC| >= {MIN_ABS_LOG2FC}): {len(updates):,}")
    print("Sign coverage after perturbation-derived signs:")
    for ev in ("measured", "perturbation", "unknown"):
        print(f"  {ev:12s}: {summary.get(ev, 0):>12,}")


if __name__ == "__main__":
    main()
