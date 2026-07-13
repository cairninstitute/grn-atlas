"""Unit tests for the co-expression logic (pure functions, no DB / no server)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from expression import ExpressionMatrix  # noqa: E402


def _mx():
    # 4 samples. gA & gB rise together; gC is the mirror of gA; gD is flat/low.
    return ExpressionMatrix({
        "meta": {"unit": "TPM"},
        "samples": [{"run": f"s{i}", "tissue": t} for i, t in
                    enumerate(["leaf", "petal", "bud", "style"])],
        "genes": {
            "gA": [1.0, 10.0, 100.0, 1000.0],
            "gB": [2.0, 12.0, 110.0, 1100.0],   # tracks gA
            "gC": [1000.0, 100.0, 10.0, 1.0],   # anti-correlated with gA
            "gD": [0.1, 0.1, 0.2, 0.1],         # low / near-flat
        },
    })


def test_profile_shape():
    p = _mx().profile("gA")
    assert p["gene_id"] == "gA" and len(p["samples"]) == 4
    assert p["samples"][1]["tissue"] == "petal" and p["samples"][1]["tpm"] == 10.0
    assert p["max_tpm"] == 1000.0


def test_positive_coexpression():
    hits = _mx().coexpressed("gA", top=10, min_abs_r=0.7, min_expr=1.0)
    by = {h["gene_id"]: h for h in hits}
    assert by["gB"]["relationship"] == "co-expressed" and by["gB"]["r"] > 0.9


def test_anti_correlation_detected():
    hits = _mx().coexpressed("gA", top=10, min_abs_r=0.7, min_expr=1.0)
    by = {h["gene_id"]: h for h in hits}
    assert "gC" in by and by["gC"]["relationship"] == "anti-correlated" and by["gC"]["r"] < 0


def test_min_expr_filters_low_genes():
    hits = _mx().coexpressed("gA", top=10, min_abs_r=0.0, min_expr=5.0)
    assert all(h["gene_id"] != "gD" for h in hits)  # gD too low-expressed


def test_missing_gene_returns_empty():
    assert _mx().coexpressed("nope") == []
    assert _mx().profile("nope") is None
