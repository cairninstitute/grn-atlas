"""Unit tests for the pure gene-label logic."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from genelabels import friendly_label, rank_synonym  # noqa: E402


def test_native_symbol_wins():
    assert friendly_label("AP3", "AT3G54340", None) == ("AP3", False)


def test_id_is_symbol_not_inferred():
    # human: id IS the symbol
    assert friendly_label("TP53", "TP53", None) == ("TP53", False)


def test_inferred_synonym_when_no_native_symbol():
    label, inferred = friendly_label("Peaxi162Scf00238g00125", "Peaxi162Scf00238g00125",
                                     ["BEN1", "DFR", "M318", "TT3"])
    assert label == "DFR" and inferred is True   # prefers the alphabetic short token


def test_rank_prefers_alpha_then_short():
    assert rank_synonym(["BEN1", "DFR", "M318"]) == "DFR"
    assert rank_synonym(["ABCDEF", "XY"]) == "XY"          # both alpha -> shorter wins
    assert rank_synonym(["A", "TOOLONGSYMBOL12"]) is None  # out of 2..10 length range


def test_falls_back_to_id_when_no_usable_synonym():
    assert friendly_label("locus1", "locus1", ["x", "123456789012"]) == ("locus1", False)
