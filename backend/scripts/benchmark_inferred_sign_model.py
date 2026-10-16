#!/usr/bin/env python3
"""Evaluate whether perturbation and binding features can infer global edge signs."""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "backend" / "data" / "grn.sqlite3"
REPORT = ROOT / "docs" / "benchmarks" / "inferred-sign-model.json"
MODEL_VERSION = "binding-perturbation-logistic-v1"


def features(row) -> list[float]:
    return [
        float(row[5]),
        float(row[6]),
        float(row[7]),
        math.log1p(int(row[8])),
        math.log1p(int(row[9])),
        0.0 if row[10] == "[]" else 1.0,
    ]


def metrics(y_true, y_pred, probabilities=None) -> dict:
    result = {
        "cases": int(len(y_true)),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, y_pred)), 4),
        "activation_precision": round(float(precision_score(y_true, y_pred, pos_label=1, zero_division=0)), 4),
        "repression_precision": round(float(precision_score(y_true, y_pred, pos_label=0, zero_division=0)), 4),
    }
    if probabilities is not None and len(set(y_true)) == 2:
        result["roc_auc"] = round(float(roc_auc_score(y_true, probabilities)), 4)
    return result


def benchmark(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("""
        SELECT c.species,c.source_id,c.target_id,c.relation_type,
               COALESCE(i.sign,i.regulation_type) observed_sign,
               c.mean_activation_score,c.mean_abs_effect,c.sign_consistency,
               c.experiment_count,c.dataset_count,c.direct_binding_sources
        FROM perturbation_sign_consensus c
        JOIN interactions i ON i.source_id=c.source_id AND i.target_id=c.target_id
        WHERE c.status='accepted' AND i.sign_evidence='measured'
          AND COALESCE(i.sign,i.regulation_type) IN ('activation','repression')
        ORDER BY c.species,c.source_id,c.target_id
    """).fetchall()
    X = np.asarray([features(row) for row in rows], dtype=float)
    y = np.asarray([1 if row[4] == "activation" else 0 for row in rows], dtype=int)
    groups = np.asarray([f"{row[0]}:{row[1]}" for row in rows])
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=2_000, class_weight="balanced", random_state=17),
    )
    folds = min(5, len(set(groups)))
    grouped = None
    if folds >= 2 and len(set(y)) == 2:
        cv = GroupKFold(n_splits=folds)
        probabilities = cross_val_predict(
            model, X, y, groups=groups, cv=cv, method="predict_proba",
        )[:, 1]
        grouped = metrics(y, (probabilities >= 0.5).astype(int), probabilities)

    species_holdout = {}
    for held_out in sorted({row[0] for row in rows}):
        train = np.asarray([row[0] != held_out for row in rows])
        test = ~train
        if test.sum() < 20 or len(set(y[train])) < 2 or len(set(y[test])) < 2:
            continue
        model.fit(X[train], y[train])
        probabilities = model.predict_proba(X[test])[:, 1]
        species_holdout[held_out] = metrics(
            y[test], (probabilities >= 0.5).astype(int), probabilities,
        )

    majority_accuracy = max(float(y.mean()), 1.0 - float(y.mean())) if len(y) else 0.0
    all_evaluations = [value for value in [grouped, *species_holdout.values()] if value]
    passes = bool(all_evaluations) and all(
        value["balanced_accuracy"] >= 0.70
        and value["activation_precision"] >= 0.65
        and value["repression_precision"] >= 0.65
        for value in all_evaluations
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_version": MODEL_VERSION,
        "features": [
            "mean_activation_score", "mean_absolute_effect", "sign_consistency",
            "log_experiment_count", "log_dataset_count", "direct_binding_present",
        ],
        "leakage_controls": [
            "literature-derived observations excluded upstream",
            "cross-validation groups all targets from the same TF",
            "species-held-out evaluation reported when both classes have at least 20 cases",
        ],
        "cases": len(rows),
        "activation_majority_baseline": round(majority_accuracy, 4),
        "tf_grouped_cross_validation": grouped,
        "species_holdout": species_holdout,
        "promotion_gate": {
            "minimum_balanced_accuracy": 0.70,
            "minimum_precision_each_sign": 0.65,
            "passed": passes,
        },
        "deployment_status": "eligible" if passes else "rejected_no_predictions_emitted",
        "interpretation": (
            "Failure means these features do not support a generic global sign model. "
            "Binding and ordinary expression context remain evidence, not direction calls."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        report = benchmark(conn)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
