"""
Validate the expression-correlation sign-inference rule against curated signs.

The inferred-sign layer (infer_edge_signs.py) assigns activation/repression from the
Pearson correlation of TF and target expression. This script measures how trustworthy
that rule is by testing it on edges where we ALSO have a curated measured sign
(DoRothEA / TRRUST / literature) in the three expression-bearing plant species.

For every such edge it recomputes the TF-target correlation, predicts a sign with the
same rule the inference step uses, and compares to the curated truth. It reports
accuracy across a sweep of |r| thresholds so we can see what cutoff makes the inferred
signs defensible, and writes a committed report artifact.

Usage:
    backend/venv/bin/python backend/scripts/validate_edge_signs.py
"""
import gzip
import json
import math
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"
OUT_PATH = DATA_DIR / "sign_validation_report.json"
SPECIES_WITH_EXPR = ("arabidopsis", "tomato", "petunia")
THRESHOLDS = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6)


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
    return json.loads(gzip.open(path, "rt").read()).get("genes")


def validate_perturbation_signs(conn_path, baseline, min_abs=1.0):
    """Agreement between perturbation-derived sign and curated signs (method check).

    Combines gain-of-function (ConnecTF induction) and loss-of-function (KnockTF) evidence by
    orienting each to a common activation score (see derive_perturbation_signs.py)."""
    orientation = {"connectf_target": +1, "knocktf": -1}
    conn = sqlite3.connect(conn_path)
    try:
        cur = {(s, t): sign for s, t, sign in conn.execute(
            "SELECT source_id, target_id, sign FROM interactions "
            "WHERE sign_evidence='measured' AND sign IN ('activation','repression')")}
        placeholders = ",".join("?" * len(orientation))
        rows = conn.execute(
            f"SELECT perturbed_gene, affected_gene, observed_log2fc, dataset_label "
            f"FROM perturbation_observations "
            f"WHERE dataset_label IN ({placeholders}) AND observed_significant=1",
            tuple(orientation)).fetchall()
    except sqlite3.OperationalError:
        return {"evaluated": 0, "note": "no perturbation observations loaded"}
    conn.close()
    if not rows:
        return {"evaluated": 0, "note": "no perturbation observations loaded"}
    from collections import defaultdict
    acc = defaultdict(list)
    for tf, tgt, fc, label in rows:
        if fc is not None:
            acc[(tf, tgt)].append(orientation[label] * fc)
    all_m = all_t = strong_m = strong_t = 0
    for pair, sign in cur.items():
        if pair not in acc:
            continue
        score = sum(acc[pair]) / len(acc[pair])
        pert = "activation" if score > 0 else "repression"
        all_t += 1
        all_m += int(pert == sign)
        if abs(score) >= min_abs:
            strong_t += 1
            strong_m += int(pert == sign)
    return {
        "datasets": list(orientation),
        "evaluated": all_t,
        "agreement_all": round(all_m / all_t, 4) if all_t else None,
        "agreement_strong_log2fc_ge_1": round(strong_m / strong_t, 4) if strong_t else None,
        "n_strong": strong_t,
        "baseline": round(baseline, 4),
        "verdict": "experiment-backed; used as the 'perturbation' sign tier at |log2FC|>=1",
    }


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    pairs = []  # (species, tf, target, measured_sign)
    for sp in SPECIES_WITH_EXPR:
        rows = conn.execute(
            "SELECT DISTINCT i.source_id, i.target_id, i.sign "
            "FROM interactions i JOIN genes g ON g.id = i.source_id "
            "WHERE g.species = ? AND i.sign_evidence = 'measured' "
            "AND i.sign IN ('activation','repression')",
            (sp,),
        ).fetchall()
        pairs.append((sp, rows))
    conn.close()

    # Evaluate correlation vs curated sign.
    records = []  # (abs_r, correct_bool, measured_sign)
    per_species = {}
    for sp, rows in pairs:
        genes = load_expression(sp)
        if not genes:
            continue
        evaluated = correct = 0
        for r in rows:
            xe, ye = genes.get(r["source_id"]), genes.get(r["target_id"])
            if not xe or not ye or len(xe) != len(ye) or len(xe) < 4:
                continue
            rr = pearson(xe, ye)
            pred = "activation" if rr > 0 else "repression"
            ok = (pred == r["sign"])
            records.append((abs(rr), ok, r["sign"]))
            evaluated += 1
            correct += int(ok)
        per_species[sp] = {"evaluated": evaluated, "correct": correct,
                           "accuracy": round(correct / evaluated, 4) if evaluated else None}

    # Threshold sweep: among edges with |r| >= t, how many does the rule get right,
    # and how much of the curated set is still covered at that cutoff?
    total = len(records)
    sweep = []
    for t in THRESHOLDS:
        kept = [(ok, sign) for ar, ok, sign in records if ar >= t]
        n = len(kept)
        corr = sum(1 for ok, _ in kept if ok)
        act = [(ok) for ok, s in kept if s == "activation"]
        rep = [(ok) for ok, s in kept if s == "repression"]
        sweep.append({
            "min_abs_r": t,
            "edges_covered": n,
            "coverage_frac": round(n / total, 4) if total else 0.0,
            "accuracy": round(corr / n, 4) if n else None,
            "activation_accuracy": round(sum(act) / len(act), 4) if act else None,
            "repression_accuracy": round(sum(rep) / len(rep), 4) if rep else None,
            "n_activation": len(act),
            "n_repression": len(rep),
        })

    baseline = sum(1 for _, _, s in records if s == "activation") / total if total else 0.0

    # --- Perturbation-derived sign validation: ConnecTF induction DEG direction vs curated. ---
    pert = validate_perturbation_signs(conn_path=DB_PATH, baseline=max(baseline, 1 - baseline))

    report = {
        "description": "Edge-sign methods validated against curated measured signs "
                       "in arabidopsis/tomato/petunia.",
        "total_measured_edges_evaluated": total,
        "majority_class_baseline_accuracy": round(max(baseline, 1 - baseline), 4),
        "correlation_rule": {"per_species": per_species, "threshold_sweep": sweep,
                             "verdict": "uninformative — at/below base rate; not used as a sign"},
        "perturbation_rule": pert,
        "current_inference_threshold": 0.3,
        "caveats": [
            "Expression panels are shallow (18-43 samples); correlation is a weak estimator.",
            "Curated signs are activation-heavy, so accuracy near the majority-class baseline is weak evidence.",
            "The perturbation-vs-curated overlap is small; treat its agreement as indicative.",
        ],
    }
    OUT_PATH.write_text(json.dumps(report, indent=2))

    print(f"Evaluated {total} curated-sign plant edges against the correlation rule")
    print(f"Majority-class baseline accuracy: {report['majority_class_baseline_accuracy']}")
    print(f"Per species: {per_species}")
    print("\n|r|>=   edges   cov     acc     act_acc  rep_acc")
    for s in sweep:
        print(f"  {s['min_abs_r']:.1f}   {s['edges_covered']:>6} {s['coverage_frac']:.2f}   "
              f"{str(s['accuracy']):>6}  {str(s['activation_accuracy']):>6}  {str(s['repression_accuracy']):>6}")
    print(f"\nReport written to {OUT_PATH}")


if __name__ == "__main__":
    main()
