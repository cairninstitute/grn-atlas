"""Tests for the gold standard validation framework."""
import json
import sqlite3
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="grn.sqlite3 not built")


def _gold_standard_species():
    return [p.stem.replace("gold_standard_", "")
            for p in DATA_DIR.glob("gold_standard_*.tsv")]


@pytest.fixture
def db():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


def test_gold_standard_files_parse():
    for sp in _gold_standard_species():
        path = DATA_DIR / f"gold_standard_{sp}.tsv"
        with open(path) as f:
            header = f.readline().strip().split("\t")
            assert "tf_symbol" in header
            assert "target_symbol" in header
            lines = [l for l in f if l.strip()]
            assert len(lines) > 0, f"{sp} gold standard is empty"
            for line in lines:
                parts = line.strip().split("\t")
                assert len(parts) >= 5, f"Malformed line in {sp}: {line.strip()}"


def test_gold_standard_has_negative_controls():
    """Each gold standard should include at least one negative control."""
    for sp in _gold_standard_species():
        path = DATA_DIR / f"gold_standard_{sp}.tsv"
        with open(path) as f:
            f.readline()
            has_neg = any("negative_control" in line for line in f)
        assert has_neg, f"{sp} gold standard has no negative controls"


@pytest.mark.parametrize("species", _gold_standard_species())
def test_gold_standard_symbols_resolve(db, species):
    """At least 50% of gold standard symbols should resolve to atlas gene IDs."""
    path = DATA_DIR / f"gold_standard_{species}.tsv"
    symbols = set()
    with open(path) as f:
        f.readline()
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                symbols.add(parts[0])
                symbols.add(parts[1])

    resolved = 0
    for sym in symbols:
        rows = db.execute(
            "SELECT COUNT(*) FROM genes WHERE species=? AND "
            "(symbol=? COLLATE NOCASE OR synonyms LIKE ?)",
            (species, sym, f"%{sym}%")).fetchone()
        if rows[0] > 0:
            resolved += 1
            continue
        reg_path = DATA_DIR / f"regulator_map_{species}.json"
        if reg_path.exists():
            regs = json.loads(reg_path.read_text())
            if any(r["name"].lower() == sym.lower() for r in regs):
                resolved += 1
                continue
        sym_path = DATA_DIR / f"curated_symbols_{species}.json"
        if sym_path.exists():
            syms = json.loads(sym_path.read_text())
            if any(info.get("symbol", "").lower() == sym.lower() for info in syms.values()):
                resolved += 1

    ratio = resolved / len(symbols) if symbols else 0
    assert ratio >= 0.5, (f"{species}: only {resolved}/{len(symbols)} "
                          f"({ratio:.0%}) gold standard symbols resolved")


@pytest.mark.parametrize("species", _gold_standard_species())
def test_quality_report_exists(species):
    report_path = DATA_DIR / f"quality_report_{species}.json"
    if not report_path.exists():
        pytest.skip(f"quality report not generated for {species}")
    report = json.loads(report_path.read_text())
    assert report["species"] == species
    gs = report["gold_standard"]
    assert gs["positive_total"] > 0
    assert 0.0 <= gs["recall"] <= 1.0


@pytest.mark.parametrize("species", _gold_standard_species())
def test_quality_report_has_all_sections(species):
    """Quality report should contain all validation sections."""
    report_path = DATA_DIR / f"quality_report_{species}.json"
    if not report_path.exists():
        pytest.skip(f"quality report not generated for {species}")
    report = json.loads(report_path.read_text())
    assert "gold_standard" in report
    assert "random_sample" in report
    assert "pathway_coherence" in report
    assert "false_positive_estimation" in report


@pytest.mark.parametrize("species", _gold_standard_species())
def test_false_positive_rate_below_threshold(species):
    """Random TF-gene pairs should have a low hit rate (< 10%)."""
    report_path = DATA_DIR / f"quality_report_{species}.json"
    if not report_path.exists():
        pytest.skip(f"quality report not generated for {species}")
    report = json.loads(report_path.read_text())
    fp = report["false_positive_estimation"]
    assert fp["combined_hit_rate"] < 0.10, (
        f"{species}: random pair hit rate {fp['combined_hit_rate']:.1%} >= 10%")


@pytest.mark.parametrize("species", _gold_standard_species())
def test_pathway_coherence_enrichment(species):
    """Anthocyanin pathway should show enrichment > 1.0 in interactions."""
    report_path = DATA_DIR / f"quality_report_{species}.json"
    if not report_path.exists():
        pytest.skip(f"quality report not generated for {species}")
    report = json.loads(report_path.read_text())
    coherence = report["pathway_coherence"]
    if "anthocyanin" in coherence and "enrichment_interactions" in coherence["anthocyanin"]:
        assert coherence["anthocyanin"]["enrichment_interactions"] > 1.0, (
            f"{species}: anthocyanin pathway not enriched in regulatory edges")
