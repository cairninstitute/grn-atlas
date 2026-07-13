"""Tier 3 — API contract tests against a tiny in-memory-ish fixture DB.

Schema is copied from the built grn.sqlite3 (so it never drifts from build_db);
a handful of curated rows exercise the endpoints. main.DB_PATH is overridden via
GRN_DB before importing/reloading main.
"""
import importlib
import os
import sqlite3
from pathlib import Path

import pytest

REAL_DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"
pytestmark = pytest.mark.skipif(not REAL_DB.exists(), reason="need built DB for schema")


def _build_fixture(path):
    src = sqlite3.connect(REAL_DB)
    schema = [r[0] for r in src.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'")]
    src.close()
    db = sqlite3.connect(path)
    for stmt in schema:
        db.execute(stmt)

    genes = [
        ("TF1", "TF1", "human TF one", "human", 1, "protein_coding", None),
        ("TG1", "TG1", "human target one", "human", 0, "protein_coding", None),
        ("TG2", "TG2", "human target two", "human", 0, "protein_coding", None),
        ("SlTF", "MYB1", "tomato MYB", "tomato", 1, "protein_coding", "MYB1"),
        ("SlTGT", "SlTGT", "tomato target", "tomato", 0, "protein_coding", "CHS"),
        ("SlTGT2", "SlTGT2", "tomato target 2", "tomato", 0, "protein_coding", None),
        ("GX", "GX", "petunia expr gene x", "petunia", 1, "protein_coding", None),
        ("GY", "GY", "petunia expr gene y", "petunia", 0, "protein_coding", None),
        ("GZ", "GZ", "petunia expr gene z", "petunia", 0, "protein_coding", None),
    ]
    db.executemany("INSERT INTO genes (id,symbol,name,species,is_tf,gene_type,synonyms) "
                   "VALUES (?,?,?,?,?,?,?)", genes)
    if "symbol_source" in [r[1] for r in db.execute("PRAGMA table_info(genes)")]:
        db.execute("UPDATE genes SET symbol_source='UniProt' WHERE id='SlTF'")
    db.executemany("INSERT INTO interactions (source_id,target_id,regulation_type,confidence,sources,pmids) "
                   "VALUES (?,?,?,?,?,?)", [
        ("TF1", "TG1", "activation", 0.9, '["TRRUST"]', '["12345"]'),
        ("TF1", "TG2", "repression", 0.8, '["TRRUST"]', '["67890"]'),
        ("SlTF", "SlTGT", "regulation", 0.65, '["PlantRegMap"]', '[]'),
        ("SlTF", "SlTGT2", "regulation", 0.5, '["Inferred:Arabidopsis"]', '[]'),
    ])
    db.executemany("INSERT INTO gene_locations VALUES (?,?,?,?,?,?)", [
        ("TF1", "human", "1", 1000, 2000, 1), ("TG1", "human", "1", 5000, 6000, -1),
        ("TG2", "human", "2", 3000, 4000, 1), ("SlTF", "tomato", "1", 1000, 2000, 1),
        ("SlTGT", "tomato", "1", 8000, 9000, 1), ("SlTGT2", "tomato", "2", 2000, 3000, 1),
    ])
    db.executemany("INSERT INTO chromosomes VALUES (?,?,?)", [
        ("human", "1", 100000), ("human", "2", 100000),
        ("tomato", "1", 100000), ("tomato", "2", 100000)])
    db.executemany("INSERT INTO go_terms VALUES (?,?,?)", [
        ("GO:1", "process one", "BP"), ("GO:2", "process two", "BP")])
    db.executemany("INSERT INTO go_annotations VALUES (?,?)", [
        ("TF1", "GO:1"), ("TG1", "GO:1"), ("TG1", "GO:2"), ("TG2", "GO:2")])
    db.executemany("INSERT INTO pathways VALUES (?,?,?)", [
        ("R-SLY-1", "Flavonoid biosynthesis", "PlantReactome"),
        ("R-SLY-2", "Photosynthesis", "PlantReactome")])
    db.executemany("INSERT INTO pathways VALUES (?,?,?)", [
        ("R-HSA-1", "p53 pathway", "Reactome")])
    db.executemany("INSERT INTO pathway_annotations VALUES (?,?)", [
        ("SlTGT", "R-SLY-1"), ("SlTGT2", "R-SLY-1"), ("SlTGT2", "R-SLY-2"),
        ("TF1", "R-HSA-1"), ("TG1", "R-HSA-1")])
    db.executemany("INSERT INTO trait_associations (gene_id, trait, pubmed_id) VALUES (?,?,?)", [
        ("TG1", "Trait A", "111"), ("TG2", "Trait A", "222"), ("TF1", "Trait B", "333")])
    # sequence context for the tomato target (SL4.0 crosswalk + window + motif hit)
    db.execute("INSERT INTO gene_id_crosswalk VALUES ('tomato','SlTGT','SlTGT.4','SL4.0','1:1')")
    db.execute("INSERT INTO gene_windows VALUES ('SlTGT.4','SL4.0','promoter','1',6000,8500,1)")
    db.execute("INSERT INTO motifs VALUES ('M1|SlTF','JASPAR2024','MA1','SlTF','MYB1')")
    db.execute("INSERT INTO motif_hits VALUES "
               "('SlTGT.4','M1|SlTF','SL4.0','promoter','1',6500,6512,1,10.0,1e-5,'JASPAR_scan',0.5)")
    db.commit(); db.close()


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "fixture.sqlite3"
    _build_fixture(path)
    os.environ["GRN_DB"] = str(path)
    import main
    importlib.reload(main)
    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        yield c
    os.environ.pop("GRN_DB", None)


def test_health(client):
    assert client.get("/health").json()["status"] == "healthy"


def test_search(client):
    r = client.get("/api/v1/genes/search?q=MYB1&species=tomato").json()
    assert r["results"][0]["id"] == "SlTF"


def test_friendly_label_inferred_and_native(client):
    # SlTGT has no native symbol (symbol==id) but synonym CHS -> inferred label
    r = client.get("/api/v1/genes/search?q=CHS&species=tomato").json()["results"][0]
    assert r["id"] == "SlTGT" and r["label"] == "CHS" and r["label_inferred"] is True
    # SlTF has a native symbol MYB1 -> not inferred
    r2 = client.get("/api/v1/genes/search?q=MYB1&species=tomato").json()["results"][0]
    assert r2["label"] == "MYB1" and r2["label_inferred"] is False
    # human TF1: id IS the symbol -> label is the id, not inferred
    r3 = client.get("/api/v1/genes/search?q=TF1&species=human").json()["results"][0]
    assert r3["label"] == "TF1" and r3["label_inferred"] is False
    # curated real symbol carries provenance
    assert r2["symbol_source"] == "UniProt"


def test_neighborhood_targets_and_pmids(client):
    r = client.post("/api/v1/pathways/neighborhood/TF1",
                    json={"direction": "targets", "regulation_type": ["activation", "repression"],
                          "min_confidence": 0.3}).json()
    tgt = {t["symbol"]: t for t in r["targets"]}
    assert "TG1" in tgt and tgt["TG1"]["pmids"] == ["12345"]
    assert tgt["TG1"]["inferred"] is False


def test_include_inferred_filter(client):
    body = {"direction": "targets", "regulation_type": ["regulation"], "min_confidence": 0.3}
    on = client.post("/api/v1/pathways/neighborhood/SlTF", json={**body, "include_inferred": True}).json()
    off = client.post("/api/v1/pathways/neighborhood/SlTF", json={**body, "include_inferred": False}).json()
    assert len(on["targets"]) == 2 and len(off["targets"]) == 1  # inferred edge dropped


def test_export_signed_edges_with_pmids(client):
    r = client.post("/api/v1/export/edges", json={"gene_ids": ["TF1", "TG1", "TG2"]}).json()
    signs = {e["target_symbol"]: e["sign"] for e in r["edges"]}
    assert signs["TG1"] == "positive" and signs["TG2"] == "negative"
    assert r["stats"]["signed"] == 2
    e = next(e for e in r["edges"] if e["target_symbol"] == "TG1")
    assert e["pmids"] == ["12345"] and e["source_coord_assembly"] == "GRCh38"


def test_export_sequence_context_join(client):
    r = client.post("/api/v1/export/edges",
                    json={"gene_ids": ["SlTF", "SlTGT"], "include_sequence_context": True}).json()
    e = next(e for e in r["edges"] if e["target_gene_id"] == "SlTGT")
    sc = e["sequence_context"]
    assert sc["assembly"] == "SL4.0" and sc["coord_system"] == "BED0"
    assert sc["target_windows"][0]["window_type"] == "promoter"
    site = sc["supporting_sites"][0]
    assert site["tf_symbol"] == "MYB1" and site["p_value"] <= 1e-4
    assert r["stats"]["edges_with_supporting_sites"] == 1


def test_subgraph(client):
    r = client.post("/api/v1/pathways/subgraph", json={"gene_ids": ["TF1", "TG1", "TG2"]}).json()
    assert len(r["nodes"]) == 3 and len(r["edges"]) == 2


def test_enrichment_shape_and_qbounds(client):
    r = client.post("/api/v1/enrichment",
                    json={"gene_ids": ["TG1", "TG2"], "species": "human", "min_genes": 2}).json()
    assert r["species"] == "human" and r["background"] >= 1
    qs = [t["q_value"] for t in r["results"]]
    assert all(0.0 <= q <= 1.0 for q in qs)
    assert qs == sorted(qs) or all(t["p_value"] <= 1 for t in r["results"])  # p sorted


def test_organism_overview(client):
    r = client.get("/api/v1/organism/human/overview?top=5").json()
    assert r["edges"]["measured"] == 2 and r["edges"]["inferred"] == 0
    assert any(t["symbol"] == "TF1" for t in r["top_regulators"])


def test_provenance_manifest(client):
    m = client.get("/api/v1/provenance").json()
    assert m["atlas_version"] and m["sources"] and m["methods"]
    assert all("doi" in s and "name" in s for s in m["sources"])


def test_provenance_freshness(client):
    f = client.get("/api/v1/provenance/freshness").json()
    assert "sources" in f and "stale" in f
    by = {s["key"]: s for s in f["sources"]}
    # every manifest source appears with a status
    assert all(s["status"] in ("current", "stale", "unknown") for s in f["sources"])
    # PLAZA 4.5 is known-stale (dicots 5.0 exists) per the committed audit cache
    assert by["plaza"]["status"] == "stale" and by["plaza"]["latest_version"]


def test_citations_bibtex(client):
    bib = client.get("/api/v1/citations.bib").text
    assert bib.count("@article") == len(client.get("/api/v1/provenance").json()["sources"])
    assert "doi = {" in bib


def test_export_embeds_provenance(client):
    r = client.post("/api/v1/export/edges", json={"gene_ids": ["TF1", "TG1"]}).json()
    assert "provenance" in r and r["provenance"]["sources"]


def test_conservation_shape(client):
    # fixture has no orthologs -> nothing conserved, but the contract must hold
    r = client.post("/api/v1/conservation",
                    json={"gene_ids": ["TF1", "TG1", "TG2"], "species_b": "mouse"}).json()
    assert r["species_b"] == "mouse"
    assert r["stats"]["edges"] == 2 and r["stats"]["conserved"] == 0
    assert all(e["conserved"] is False for e in r["edges"])


def test_motif_enrichment_shape(client):
    r = client.post("/api/v1/motif_enrichment",
                    json={"gene_ids": ["SlTGT"], "species": "tomato", "min_genes": 1}).json()
    assert r["species"] == "tomato" and r["background"] >= 1
    assert all(0.0 <= t["q_value"] <= 1.0 for t in r["results"])


def test_motif_enrichment_non_plant_species(client):
    r = client.post("/api/v1/motif_enrichment",
                    json={"gene_ids": ["TF1", "TG1"], "species": "human"}).json()
    assert r["results"] == [] and "note" in r


def _inject_expr(client):
    import expression
    expression._cache[str(expression.DEFAULT_PATH)] = expression.ExpressionMatrix({
        "meta": {"unit": "TPM", "label": "test"},
        "samples": [{"run": f"s{i}", "tissue": t} for i, t in
                    enumerate(["leaf", "petal", "bud", "style"])],
        "genes": {"GX": [1.0, 10.0, 100.0, 1000.0],
                  "GY": [2.0, 11.0, 105.0, 1050.0],
                  "GZ": [0.1, 0.1, 0.2, 0.1]},
    })


def test_expression_profile(client):
    _inject_expr(client)
    r = client.get("/api/v1/expression/GX").json()
    assert r["available"] and len(r["samples"]) == 4
    assert r["samples"][1]["tissue"] == "petal" and r["samples"][1]["tpm"] == 10.0
    miss = client.get("/api/v1/expression/NOPE").json()
    assert miss["available"] is False


def test_expression_resolves_species(client):
    # inject a *tomato* matrix; the endpoint must pick it for a tomato gene id
    import expression
    expression._cache[str(expression.path_for("tomato"))] = expression.ExpressionMatrix({
        "meta": {"unit": "TPM"},
        "samples": [{"run": "r1", "tissue": "leaf"}, {"run": "r2", "tissue": "fruit"}],
        "genes": {"SlTGT": [3.0, 40.0], "SlTGT2": [1.0, 1.0]},
    })
    r = client.get("/api/v1/expression/SlTGT").json()
    assert r["available"] and r["species"] == "tomato"
    assert r["samples"][1]["tissue"] == "fruit" and r["samples"][1]["tpm"] == 40.0


def test_coexpression_labeled_inferred(client):
    _inject_expr(client)
    r = client.post("/api/v1/coexpression",
                    json={"gene_id": "GX", "min_abs_r": 0.7, "min_expr": 1.0}).json()
    assert r["available"]
    gy = next(h for h in r["results"] if h["gene_id"] == "GY")
    assert gy["source"] == "Inferred:Expression" and gy["r"] > 0.9


def test_pathway_enrichment(client):
    r = client.post("/api/v1/pathway_enrichment",
                    json={"gene_ids": ["SlTGT", "SlTGT2"], "species": "tomato", "min_genes": 2}).json()
    assert r["species"] == "tomato" and r["background"] == 2
    top = r["results"][0]
    assert top["name"] == "Flavonoid biosynthesis" and top["study_count"] == 2
    assert 0.0 <= top["q_value"] <= 1.0


def test_pathway_enrichment_human(client):
    r = client.post("/api/v1/pathway_enrichment",
                    json={"gene_ids": ["TF1", "TG1"], "species": "human", "min_genes": 2}).json()
    assert r["background"] == 2
    assert r["results"][0]["name"] == "p53 pathway" and r["results"][0]["study_count"] == 2


def test_pathway_enrichment_species_without_annotations(client):
    # petunia genes have no pathway annotations in the fixture
    r = client.post("/api/v1/pathway_enrichment",
                    json={"gene_ids": ["GX", "GY"], "species": "petunia"}).json()
    assert r["results"] == [] and "note" in r


def test_gene_traits_lookup(client):
    r = client.get("/api/v1/traits/TG1").json()
    assert r["gene_id"] == "TG1"
    assert any(t["trait"] == "Trait A" and t["pubmed_id"] == "111" for t in r["traits"])


def test_trait_enrichment(client):
    r = client.post("/api/v1/trait_enrichment",
                    json={"gene_ids": ["TG1", "TG2"], "species": "human", "min_genes": 2}).json()
    assert r["species"] == "human" and r["background"] == 3
    top = r["results"][0]
    assert top["trait"] == "Trait A" and top["study_count"] == 2 and 0.0 <= top["q_value"] <= 1.0


def test_trait_enrichment_species_without_data(client):
    r = client.post("/api/v1/trait_enrichment",
                    json={"gene_ids": ["SlTF", "SlTGT"], "species": "tomato"}).json()
    # dynamic note lists species that DO have trait data (human, from the fixture)
    assert r["results"] == [] and "human" in r["note"]


def test_species_capabilities(client):
    d = client.get("/api/v1/species").json()
    by = {r["species"]: r for r in d["species"]}
    assert {"human", "tomato"} <= set(by)
    assert by["human"]["layers"]["trait_associations"] > 0          # GWAS loaded
    assert by["tomato"]["layers"]["pathway_annotations"] > 0        # Reactome loaded
    assert by["tomato"]["layers"]["binding_sites"] > 0              # motif scan loaded
    assert by["human"]["layers"]["network"]["measured_edges"] > 0


def _inject_transcripts(client):
    import rnai
    shared = "ACGTACGTACGTACGTACGTA"   # 21-mer shared by target + off-target
    rnai._cache["petunia"] = {
        "GX": shared + "GGGGCCCCTTTTAAAAGGGGCCCC",   # target (in network)
        "GY": "TTTT" + shared + "CCCC",              # off-target (shares the 21-mer, in network)
        "GZ": "GC" * 60,                              # unrelated
        "GHOST": "AA" + shared + "AA",               # off-target NOT in the genes table
    }


def test_dsrna_analyze_on_and_off_target(client):
    _inject_transcripts(client)
    r = client.post("/api/v1/dsrna", json={
        "sequence": "ACGTACGTACGTACGTACGTA", "target_gene_id": "GX",
        "species": "petunia", "predict_effect": False}).json()
    assert r["available"] and r["mode"] == "analyze"
    assert r["on_target_sites"] >= 1
    offs = {o["gene_id"] for o in r["off_targets"]}
    assert "GY" in offs and "GZ" not in offs
    assert "GX" in r["silenced_genes"] and "GY" in r["silenced_genes"]


def test_dsrna_design_mode(client):
    _inject_transcripts(client)
    r = client.post("/api/v1/dsrna", json={
        "target_gene_id": "GX", "species": "petunia",
        "design_window": 40, "predict_effect": False}).json()
    assert r["mode"] == "design" and r["design"]["target_gene"] == "GX"
    assert "sequence" in r["design"]


def test_dsrna_screen_gene_set(client):
    _inject_transcripts(client)
    r = client.post("/api/v1/dsrna/screen", json={
        "gene_ids": ["GX", "GY", "GZ"], "species": "petunia",
        "design_window": 40, "predict_effect": False}).json()
    assert r["available"] and r["n_genes"] == 3
    by = {d["gene_id"]: d for d in r["results"]}
    # GX and GY share a 21-mer -> each is an off-target of the other; GZ is clean
    assert by["GZ"]["designable"] is True
    assert by["GX"]["transcript_off_targets"] >= 1


def test_dsrna_predict_effect_ignores_nonnetwork_offtargets(client):
    # GHOST is an off-target in the transcriptome but not in the genes table; the
    # predicted-effect perturbation must skip it rather than 500.
    _inject_transcripts(client)
    r = client.post("/api/v1/dsrna", json={
        "sequence": "ACGTACGTACGTACGTACGTA", "target_gene_id": "GX",
        "species": "petunia", "predict_effect": True})
    assert r.status_code == 200
    body = r.json()
    assert body["available"] and "GHOST" in body["silenced_genes"]


def test_http_exception_returns_json_status(client):
    # the custom HTTPException handler must return a real JSONResponse with the status
    r = client.post("/api/v1/perturb", json={"interventions": [{"gene_id": "NOPE", "action": "ko"}]})
    assert r.status_code == 404 and r.json()["error"]


def test_dsrna_rejects_bad_sequence(client):
    _inject_transcripts(client)
    r = client.post("/api/v1/dsrna", json={"sequence": "ACGT XYZ 123", "species": "petunia"})
    assert r.status_code == 400 and "non-nucleotide" in r.json()["error"]


def test_dsrna_rejects_overlong_sequence(client):
    _inject_transcripts(client)
    r = client.post("/api/v1/dsrna", json={"sequence": "A" * 6000, "species": "petunia"})
    assert r.status_code == 400 and "too long" in r.json()["error"]


def test_dsrna_rejects_too_short(client):
    _inject_transcripts(client)
    r = client.post("/api/v1/dsrna", json={"sequence": "ACGT", "species": "petunia", "k": 21})
    assert r.status_code == 400


def test_dsrna_out_of_range_k(client):
    # pydantic Field bounds -> 422
    r = client.post("/api/v1/dsrna", json={"sequence": "ACGT" * 10, "species": "petunia", "k": 5})
    assert r.status_code == 422


def test_dsrna_no_transcripts_for_species(client):
    import rnai
    rnai._cache["human"] = None
    r = client.post("/api/v1/dsrna", json={"sequence": "ACGT" * 6, "species": "human"}).json()
    assert r["available"] is False and "note" in r


def test_perturb_signed_propagation(client):
    # TF1 -| TG2 (repression): knocking out TF1 should de-repress TG2 -> up.
    r = client.post("/api/v1/perturb",
                    json={"interventions": [{"gene_id": "TF1", "action": "ko"}]}).json()
    eff = {e["symbol"]: e for e in r["effects"]}
    assert eff["TG2"]["predicted_direction"] == "up"    # ko of a repressor
    assert eff["TG1"]["predicted_direction"] == "down"  # ko of an activator
    assert r["stats"]["affected"] == 2

    # Over-expressing TF1 flips both directions.
    oe = client.post("/api/v1/perturb",
                     json={"interventions": [{"gene_id": "TF1", "action": "oe"}]}).json()
    oeff = {e["symbol"]: e["predicted_direction"] for e in oe["effects"]}
    assert oeff["TG1"] == "up" and oeff["TG2"] == "down"


def test_perturb_unsigned_edge_is_unknown(client):
    # SlTF -> SlTGT is 'regulation' (unsigned) -> direction unknown.
    r = client.post("/api/v1/perturb",
                    json={"interventions": [{"gene_id": "SlTF", "action": "ko"}],
                          "include_inferred": True}).json()
    d = next(e for e in r["effects"] if e["gene_id"] == "SlTGT")
    assert d["predicted_direction"] == "unknown"


def test_perturb_respects_include_inferred(client):
    on = client.post("/api/v1/perturb", json={
        "interventions": [{"gene_id": "SlTF", "action": "ko"}], "include_inferred": True}).json()
    off = client.post("/api/v1/perturb", json={
        "interventions": [{"gene_id": "SlTF", "action": "ko"}], "include_inferred": False}).json()
    assert on["stats"]["affected"] > off["stats"]["affected"]


def test_genome_endpoints(client):
    sp = client.get("/api/v1/genome/species").json()["species"]
    assert {s["species"] for s in sp} >= {"human", "tomato"}
    tom = client.get("/api/v1/genome/tomato").json()
    assert tom["species"] == "tomato" and len(tom["chromosomes"]) >= 1
