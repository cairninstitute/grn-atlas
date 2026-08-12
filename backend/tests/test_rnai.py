"""Unit tests for the dsRNA / RNAi silencing predictor (pure functions)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rnai  # noqa: E402


def test_revcomp():
    assert rnai.revcomp("AAAACGT") == "ACGTTTT"


def test_validate_dsrna_cleans_and_uppercases():
    assert rnai.validate_dsrna("acgt\n acgt", k=4) == "ACGTACGT"


def test_validate_dsrna_rejects_bad_and_bounds():
    import pytest
    with pytest.raises(ValueError):
        rnai.validate_dsrna("ACGTX", k=4)            # non-nucleotide
    with pytest.raises(ValueError):
        rnai.validate_dsrna("ACGT", k=21)            # shorter than k
    with pytest.raises(ValueError):
        rnai.validate_dsrna("A" * 6000, k=21)        # too long
    with pytest.raises(ValueError):
        rnai.validate_dsrna("   ", k=4)              # empty after cleaning


def test_query_kmers_both_strands():
    s = "A" * 21
    qk = rnai.query_kmers(s, k=21)
    assert "A" * 21 in qk and "T" * 21 in qk  # dsRNA => both strands diced


def _toy():
    # target shares a 21-mer with the dsRNA; paralog shares it too; unrelated doesn't.
    shared = "ACGTACGTACGTACGTACGTA"          # 21 nt
    return {
        "TARGET": shared + "GGGGCCCCAAAATTTT",
        "PARALOG": "TTTT" + shared + "CCCC",
        "UNRELATED": "GC" * 40,
    }, shared


def test_scan_on_and_off_target():
    tx, shared = _toy()
    r = rnai.scan(shared, tx, k=21, target_gene="TARGET")
    assert r["on_target_sites"] >= 1
    off = {o["gene_id"] for o in r["off_targets"]}
    assert "PARALOG" in off and "UNRELATED" not in off
    assert "TARGET" in r["silenced_genes"] and "PARALOG" in r["silenced_genes"]
    assert 0.0 <= r["specificity"] <= 1.0


def test_scan_specificity_perfect_when_no_offtargets():
    tx, shared = _toy()
    tx.pop("PARALOG")
    r = rnai.scan(shared, tx, k=21, target_gene="TARGET")
    assert r["off_target_gene_count"] == 0 and r["specificity"] == 1.0


def test_design_prefers_specific_window():
    # target has a shared (off-target) region and a unique region; design should
    # pick a window avoiding the shared region when possible.
    shared = "ACGTACGTACGTACGTACGTA"
    unique = "TTAGGCCTTAGGCCTTAGGCCTTAGGCCTTAGGCC" * 3
    tx = {"TARGET": shared + unique, "OTHER": "GG" + shared + "GG"}
    d = rnai.design("TARGET", tx, k=21, window=30, step=5)
    assert "sequence" in d and d["off_target_gene_count"] == 0


def test_screen_ranks_by_designability():
    shared = "ACGTACGTACGTACGTACGTA"
    unique = "TTAGGCCTTAGGCCTTAGGCCTTAGGCC" * 4
    tx = {
        "CLEAN": unique,                 # no shared k-mers -> designable
        "DIRTY": shared + "AAAACCCCGGGG",  # shares 21-mer with OTHER
        "OTHER": "GG" + shared + "GG",
    }
    r = rnai.screen(["CLEAN", "DIRTY"], tx, k=21, window=25, step=5)
    by = {d["gene_id"]: d for d in r}
    assert by["CLEAN"]["designable"] is True
    assert by["DIRTY"]["transcript_off_targets"] >= 1
    # cleanest-first ordering
    assert r[0]["gene_id"] == "CLEAN"


def test_design_and_screen_match_scan_for_reverse_complement_offtargets():
    tx = {
        "TARGET": "AAAAGGGG",
        "OTHER": "TTTTCCCC",
    }
    d = rnai.design("TARGET", tx, k=4, window=4, step=4)
    s = rnai.scan(d["sequence"], tx, k=4, target_gene="TARGET")
    batch = rnai.screen(["TARGET"], tx, k=4, window=4, step=4)[0]
    assert d["off_target_gene_count"] == 1
    assert s["off_target_gene_count"] == 1
    assert batch["best_window_off_targets"] == 1
    assert batch["transcript_off_targets"] == 1


def test_load_transcripts_gene_aggregation(tmp_path):
    import gzip
    fa = tmp_path / "transcripts_x.fasta.gz"
    with gzip.open(fa, "wt") as f:
        f.write(">GeneA.1 | GeneA\nACGTACGTAC\n>GeneA.2 | GeneA\nTTTTGGGG\n>GeneB.1 | GeneB\nCCCCAAAA\n")
    tx = rnai.load_transcripts(fa)
    assert set(tx) == {"GeneA", "GeneB"}
    assert tx["GeneA"].startswith("ACGTACGTAC") and "N" * 21 in tx["GeneA"]
