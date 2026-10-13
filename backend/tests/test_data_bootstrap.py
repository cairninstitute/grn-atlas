import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch_arabidopsis_regulation.py"
SPEC = importlib.util.spec_from_file_location("fetch_arabidopsis_regulation", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_plantregmap_confidence_tiers():
    assert MODULE.plantregmap_confidence("motif") is None
    assert MODULE.plantregmap_confidence("FunTFBS, motif") == 0.65
    assert MODULE.plantregmap_confidence("ChIP-seq (seedling)") == 0.80
    assert MODULE.plantregmap_confidence("ChIP-seq, FunTFBS") == 0.85
    assert MODULE.plantregmap_confidence("literature") == 0.90
    assert MODULE.plantregmap_confidence("FunTFBS, literature") == 0.95


def test_plantregmap_normalization_keeps_release_supplement(tmp_path):
    source = tmp_path / "merged.tsv"
    source.write_text(
        "AT1G01060\tregulates\tAT1G01470\tArabidopsis thaliana\tmotif\n"
        "AT1G01060\tregulates\tAT1G20030\tArabidopsis thaliana\tFunTFBS, motif\n"
        "AT1G01060\tregulates\tAT1G04400\tArabidopsis thaliana\tliterature\n"
    )
    output = tmp_path / "regulation.tsv"
    count = MODULE.normalize_plantregmap(source, output)
    rows = output.read_text().splitlines()

    assert count == 2 + len(MODULE.ATLAS_SUPPLEMENT)
    assert "AT1G01060\tAT1G01470" not in output.read_text()
    assert rows[0] == "AT1G01060\tAT1G20030\tregulation\t0.65\tFunTFBS, motif"
    assert rows[-1] == "AT2G47460\tAT4G22880\tregulation\t0.85\tliterature"
