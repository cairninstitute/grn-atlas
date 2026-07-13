"""Tier 1 — pure-function unit tests (no DB, no network)."""
import math

import numpy as np
import pytest

from motif_scan import score_pvalues, encode, scan, COMP
from build_db import norm_chrom
from fetch_tomato_seqctx import promoter_window as tomato_promoter
from fetch_seqctx import promoter_window as _generic_promoter


def petunia_promoter(start, end, strand):
    # generic PLAZA-identity promoter with the standard TSS -2000/+500 window
    return _generic_promoter(start, end, strand, 2000, 500)


# ---------- PWM p-value distribution ----------

def test_pvalues_monotone_and_normalized():
    ints = np.array([[40, -40, -40, -40]] * 8)   # 8bp poly-A motif
    thr, pval = score_pvalues(ints)
    scores = sorted(pval)
    # tail p(score>=s) is non-increasing in s
    for a, b in zip(scores, scores[1:]):
        assert pval[a] >= pval[b]
    assert pval[scores[0]] == pytest.approx(1.0, abs=1e-9)   # whole distribution
    assert pval[scores[-1]] == pytest.approx(0.25 ** 8, abs=1e-9)  # all-A probability
    # a threshold exists and everything at/above it clears p<=1e-4
    passing = [s for s in scores if s >= thr]
    assert passing and all(pval[s] <= 1e-4 for s in passing)


def test_scan_finds_planted_site():
    ints = np.array([[50, -50, -50, -50]] * 8)   # 8bp poly-A
    thr, pval = score_pvalues(ints)
    seq = "GGGG" + "A" * 8 + "TTTT"               # motif at offset 4
    hits = dict(scan(encode(seq), ints, thr, pval))
    assert 4 in hits
    assert hits[4] == 8 * 50                      # perfect match = max score
    # a non-matching window is not called
    assert 0 not in hits


def test_scan_ignores_N():
    ints = np.array([[50, -50, -50, -50]] * 8)
    thr, pval = score_pvalues(ints)
    seq = "NNNN" + "A" * 8 + "NNNN"
    hits = dict(scan(encode(seq), ints, thr, pval))
    assert 4 in hits and all(o == 4 for o in hits)  # only the clean window


# ---------- reverse complement ----------

def test_reverse_complement():
    assert "AACGT".translate(COMP)[::-1] == "ACGTT"
    assert "N".translate(COMP) == "N"


# ---------- promoter windows (BED0) ----------

def test_tomato_promoter_plus_strand():
    # gene start 5000 (1-based) -> TSS0 4999; [-2000,+500)
    assert tomato_promoter(5000, 8000, 1) == (2999, 5499)


def test_tomato_promoter_minus_strand():
    # minus: TSS at gene end; window [end-down, end+up)
    assert tomato_promoter(5000, 8000, -1) == (7500, 10000)


def test_promoter_clamped_at_zero():
    ws, we = tomato_promoter(100, 500, 1)   # start-1-2000 < 0
    assert ws == 0 and we == 99 + 500


def test_petunia_promoter_matches_tomato_logic():
    # same TSS-2000/+500 convention, both species
    assert petunia_promoter(5000, 8000, 1) == (2999, 5499)
    assert petunia_promoter(5000, 8000, -1) == (7500, 10000)


def test_window_lengths_are_constant():
    for strand in (1, -1):
        ws, we = tomato_promoter(50000, 60000, strand)
        assert we - ws == 2500     # 2000 + 500


# ---------- chromosome normalization ----------

@pytest.mark.parametrize("species,name,expected", [
    ("arabidopsis", "Chr1", "1"),
    ("arabidopsis", "1", "1"),
    ("arabidopsis", "ChrC", "C"),
    ("tomato", "SL2.50ch07", "7"),
    ("tomato", "SL4.0ch00", "0"),
    ("tomato", "SL2.50ch12", "12"),
    ("human", "1", "1"),
    ("mouse", "X", "X"),
    ("petunia", "Peaxi162Scf00047", "Peaxi162Scf00047"),
])
def test_norm_chrom(species, name, expected):
    assert norm_chrom(species, name) == expected


# ---------- hypergeometric survival function ----------

def _hyper():
    from main import _hypergeom_sf
    return _hypergeom_sf


def test_hypergeom_known_value():
    # N=10, K=5, n=5, k=5 -> P(all 5 drawn are successes) = 1/C(10,5)
    sf = _hyper()
    assert sf(5, 5, 5, 10) == pytest.approx(1 / math.comb(10, 5), rel=1e-9)


def test_hypergeom_k_zero_is_one():
    sf = _hyper()
    assert sf(0, 5, 5, 10) == pytest.approx(1.0, abs=1e-9)


def test_hypergeom_monotone_decreasing_in_k():
    sf = _hyper()
    vals = [sf(k, 8, 20, 100) for k in range(0, 9)]
    assert all(a >= b for a, b in zip(vals, vals[1:]))
    assert all(0.0 <= v <= 1.0 for v in vals)
