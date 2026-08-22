"""
HTTP integration tests against a live GRN Atlas server.

These tests require a running server at the URL specified by the
GRN_ATLAS_URL environment variable (default: http://127.0.0.1:8000).

Run:
    GRN_ATLAS_URL=http://127.0.0.1:8000 python -m pytest tests/test_http_integration.py -v

Skip when no server is available:
    Tests are automatically skipped if the server is unreachable.
"""
import os
import json
import pytest
import urllib.request
import urllib.error

BASE = os.environ.get("GRN_ATLAS_URL", "http://127.0.0.1:8000")


def _get(path):
    req = urllib.request.Request(f"{BASE}{path}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read()), resp.status


def _post(path, body, timeout=30):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}{path}", data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read()), resp.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code


def _server_reachable():
    try:
        urllib.request.urlopen(f"{BASE}/health", timeout=5)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _server_reachable(),
    reason=f"GRN Atlas server not reachable at {BASE}",
)


# ─── Core endpoints ───


class TestHealth:
    def test_health(self):
        data, status = _get("/health")
        assert status == 200
        assert data["status"] == "healthy"


class TestGeneSearch:
    def test_search_by_symbol(self):
        data, status = _get("/api/v1/genes/search?q=MYB&limit=5")
        assert status == 200
        assert len(data["results"]) > 0

    def test_search_no_results(self):
        data, status = _get("/api/v1/genes/search?q=XYZZY_NONEXISTENT_999&limit=5")
        assert status == 200
        assert len(data["results"]) == 0


class TestSpecies:
    def test_species_list(self):
        data, status = _get("/api/v1/species")
        assert status == 200
        assert len(data["species"]) >= 5

    def test_stats(self):
        data, status = _get("/api/v1/stats")
        assert status == 200
        assert data["genes"] > 0
        assert data["interactions"] > 0


# ─── Network & Regulon ───


class TestNetwork:
    def test_neighborhood(self):
        data, status = _post("/api/v1/pathways/neighborhood/AT1G56650", {})
        assert status == 200

    def test_regulon(self):
        data, status = _post("/api/v1/regulon", {"gene_id": "AT1G56650"})
        assert status == 200
        assert "genes" in data

    def test_regulon_compare(self):
        data, status = _post("/api/v1/regulon/compare", {
            "tf_a": "AT1G56650", "tf_b": "AT5G42910",
        })
        assert status == 200
        assert "jaccard" in data

    def test_upstream_regulators(self):
        data, status = _post("/api/v1/upstream-regulators", {
            "gene_ids": ["AT1G56650", "AT5G42910", "AT3G23230"],
            "species": "arabidopsis",
        })
        assert status == 200
        assert "regulators" in data

    def test_subgraph(self):
        data, status = _post("/api/v1/pathways/subgraph", {
            "gene_ids": ["AT1G56650", "AT5G42910"],
        })
        assert status == 200


class TestPathfinding:
    def test_path(self):
        data, status = _post("/api/v1/pathways/pathfinding", {
            "source_gene_id": "AT1G56650", "target_symbol": "AT5G42910",
        })
        assert status == 200


# ─── Enrichment & Activity ───


class TestEnrichment:
    def test_go_enrichment(self):
        data, status = _post("/api/v1/enrichment", {
            "gene_ids": ["AT1G56650", "AT5G42910", "AT3G23230"],
            "type": "go", "species": "arabidopsis",
        })
        assert status == 200
        assert "results" in data

    def test_tf_activity(self):
        data, status = _post("/api/v1/activity/tf", {
            "gene_values": {"AT1G56650": 3.0, "AT5G42910": -2.0, "AT3G23230": 1.5, "AT1G01010": 0.5},
            "species": "arabidopsis",
        })
        assert status == 200
        assert "regulators" in data

    def test_pathway_activity(self):
        data, status = _post("/api/v1/activity/pathway", {
            "gene_values": {"AT1G56650": 3.0, "AT5G42910": -2.0, "AT3G23230": 1.5},
            "species": "arabidopsis",
        })
        assert status == 200


# ─── Network Structure ───


class TestNetworkStructure:
    def test_patterns(self):
        data, status = _post("/api/v1/network/patterns", {
            "species": "arabidopsis",
        })
        assert status == 200

    def test_centrality(self):
        data, status = _post("/api/v1/network/centrality", {
            "species": "arabidopsis",
        })
        assert status == 200

    def test_modules(self):
        data, status = _post("/api/v1/network/modules", {
            "species": "arabidopsis",
        })
        assert status == 200

    def test_motif_query(self):
        data, status = _post("/api/v1/motif/query", {
            "gene_id": "AT1G56650", "species": "arabidopsis",
        })
        assert status == 200


# ─── dsRNA / CRISPR ───


class TestSequenceDesign:
    def test_dsrna_design(self):
        data, status = _post("/api/v1/dsrna", {
            "target_gene_id": "AT1G56650", "species": "arabidopsis",
        }, timeout=120)
        assert status == 200

    def test_crispr_offtargets(self):
        data, status = _post("/api/v1/crispr/offtargets", {
            "guide_sequence": "ATGGCTAGCTAGCTAGCTAG",
            "species": "arabidopsis", "max_mismatches": 2,
        }, timeout=120)
        assert status == 200
        assert "offtargets" in data

    def test_crispr_compare(self):
        data, status = _post("/api/v1/crispr/compare", {
            "gene_id": "AT1G56650",
        })
        assert status in (200, 404)


# ─── Omics Import ───


class TestOmicsImport:
    def test_import_and_list(self):
        data, status = _post("/api/v1/import/omics", {
            "name": "http_integration_test", "species": "arabidopsis",
            "data_type": "bulk",
            "gene_values": {"AT1G56650": [5.0], "AT5G42910": [3.0]},
        })
        assert status == 200
        assert "dataset_id" in data
        ds_id = data["dataset_id"]

        data2, status2 = _get(f"/api/v1/import/{ds_id}")
        assert status2 == 200
        assert data2["name"] == "http_integration_test"

        data3, status3 = _get("/api/v1/import/list/all")
        assert status3 == 200
        assert any(d["dataset_id"] == ds_id for d in data3["datasets"])


# ─── Cell-type & Chromatin ───


class TestCelltypeChromatin:
    def test_celltype_regulation(self):
        data, status = _post("/api/v1/celltype/regulation", {
            "species": "arabidopsis",
        })
        assert status == 200

    def test_chromatin_gene_support(self):
        data, status = _get("/api/v1/chromatin/gene/AT1G01010")
        assert status == 200
        assert "linked_peaks" in data


# ─── Trajectory ───


class TestTrajectory:
    def test_trajectory_drivers(self):
        data, status = _post("/api/v1/trajectory/drivers", {
            "dataset_id": "none", "contrasts": ["c1"],
            "species": "arabidopsis",
        })
        assert status in (200, 404)

    def test_transition_drivers(self):
        data, status = _post("/api/v1/transition/drivers", {
            "species": "arabidopsis",
            "gene_ids": ["AT1G56650", "AT5G42910", "AT3G23230", "AT1G01010"],
        })
        assert status == 200
        assert "drivers" in data


# ─── Perturbation & Signaling ───


class TestPerturbationSignaling:
    def test_perturbation_calibration(self):
        data, status = _get("/api/v1/perturbation/calibration")
        assert status == 200

    def test_signaling_to_tf(self):
        data, status = _post("/api/v1/signaling/to-tf", {
            "species": "arabidopsis", "receptor_gene": "AT1G56650",
        })
        assert status == 200

    def test_ligand_receptor(self):
        data, status = _post("/api/v1/signaling/ligand-receptor", {
            "species": "arabidopsis",
        })
        assert status == 200


# ─── Cross-species ───


class TestCrossSpecies:
    def test_transfer_risk(self):
        data, status = _post("/api/v1/orthology/transfer-risk", {
            "gene_id": "AT1G56650", "target_species": "tomato",
        })
        assert status in (200, 404)

    def test_family_rescue(self):
        data, status = _post("/api/v1/family-rescue", {
            "gene_id": "AT1G56650",
        })
        assert status in (200, 404)

    def test_species_onboarding(self):
        data, status = _get("/api/v1/species/onboarding/arabidopsis")
        assert status == 200
        assert data["species"] == "arabidopsis"
        assert "readiness_score" in data


# ─── Workflows ───


class TestWorkflows:
    def test_list_workflows(self):
        data, status = _get("/api/v1/workflows/list")
        assert status == 200
        assert len(data["workflows"]) >= 3

    def test_deg_to_regulators(self):
        data, status = _post("/api/v1/workflows/run", {
            "workflow_type": "deg-to-regulators",
            "species": "arabidopsis",
            "gene_ids": ["AT1G56650", "AT5G42910", "AT3G23230"],
        })
        assert status == 200
        assert data["workflow"] == "deg-to-regulators"


# ─── Roadmap Phase 1: Cis-Support, Enhancer, CRISPR vs dsRNA, Edit Consequence ───


class TestCisSupport:
    def test_cis_support_audit(self):
        data, status = _post("/api/v1/cis-support/audit", {
            "source_id": "AT1G56650", "target_id": "AT5G42910",
        })
        assert status in (200, 404)
        if status == 200:
            assert "confidence_tier" in data
            assert "layers" in data

    def test_cis_support_audit_missing_edge(self):
        data, status = _post("/api/v1/cis-support/audit", {
            "source_id": "FAKE_TF", "target_id": "FAKE_TARGET",
        })
        assert status == 404


class TestEnhancerNetwork:
    def test_enhancer_network(self):
        data, status = _post("/api/v1/enhancer/network", {
            "gene_id": "AT1G56650",
        })
        assert status in (200, 404)
        if status == 200:
            assert "linked_peaks" in data
            assert "enhancer_regulators" in data

    def test_enhancer_network_not_found(self):
        data, status = _post("/api/v1/enhancer/network", {
            "gene_id": "TOTALLY_FAKE_GENE",
        })
        assert status == 404


class TestPeakGeneLinkage:
    def test_by_peak_id(self):
        data, status = _post("/api/v1/peak-gene/linkage", {
            "peak_id": "chr1:1000-2000",
        })
        assert status == 200
        assert "linked_genes" in data

    def test_by_region(self):
        data, status = _post("/api/v1/peak-gene/linkage", {
            "region": "chr1:1000-2000", "species": "arabidopsis",
        })
        assert status == 200
        assert "peaks" in data

    def test_no_input(self):
        data, status = _post("/api/v1/peak-gene/linkage", {})
        assert status == 400


class TestCrisprVsDsrna:
    def test_compare(self):
        data, status = _post("/api/v1/compare/crispr-vs-dsrna", {
            "gene_ids": ["AT1G56650"], "species": "arabidopsis",
        })
        assert status == 200
        assert "comparisons" in data
        c = data["comparisons"][0]
        assert "crispr" in c
        assert "dsrna" in c
        assert "recommendation" in c


class TestEditConsequence:
    def test_promoter(self):
        data, status = _post("/api/v1/edit/consequence", {
            "gene_id": "AT1G56650", "edit_type": "promoter_disruption",
        })
        assert status in (200, 404)
        if status == 200:
            assert "consequences" in data

    def test_coding(self):
        data, status = _post("/api/v1/edit/consequence", {
            "gene_id": "AT1G56650", "edit_type": "coding_disruption",
        })
        assert status in (200, 404)

    def test_not_found(self):
        data, status = _post("/api/v1/edit/consequence", {
            "gene_id": "FAKE_GENE_999",
        })
        assert status == 404


# ─── Roadmap Phase 2: Celltype Regulon, Transition Drivers, Multiome Audit ───


class TestCelltypeRegulon:
    def test_without_dataset(self):
        data, status = _post("/api/v1/celltype/regulon", {
            "gene_id": "AT1G56650",
        })
        assert status in (200, 404)
        if status == 200:
            assert "global_regulon_size" in data
            assert "state_targets" in data


class TestTransitionDrivers:
    def test_with_genes(self):
        data, status = _post("/api/v1/transition/drivers", {
            "species": "arabidopsis",
            "gene_ids": ["AT1G56650", "AT5G42910", "AT3G23230", "AT1G01010"],
        })
        assert status == 200
        assert "drivers" in data

    def test_no_genes(self):
        data, status = _post("/api/v1/transition/drivers", {
            "species": "arabidopsis",
        })
        assert status == 200
        assert data.get("status") == "ready"


class TestMultiomeAudit:
    def test_audit(self):
        data, status = _post("/api/v1/multiome/audit", {
            "source_id": "AT1G56650", "target_id": "AT5G42910",
        })
        assert status == 200
        assert "layers" in data
        assert "n_supporting_layers" in data
        assert "evidence_weight" in data
        layers = set(data["layers"].keys())
        assert layers == {"network", "motif", "chromatin", "expression", "perturbation"}


# ─── Roadmap Phase 3: Literature Grounding, Intervention Ranker ───


class TestLiteratureGrounding:
    def test_grounding(self):
        data, status = _post("/api/v1/literature/grounding", {
            "terms": ["MYB75", "AN2", "NONEXISTENT_XYZZY"],
        })
        assert status == 200
        assert "mappings" in data
        assert "resolution_rate" in data
        assert data["n_terms"] == 3

    def test_all_unresolved(self):
        data, status = _post("/api/v1/literature/grounding", {
            "terms": ["TOTALLY_FAKE_1", "TOTALLY_FAKE_2"],
        })
        assert status == 200
        assert data["resolution_rate"] == 0.0


class TestInterventionRanker:
    def test_rank_knockdown(self):
        data, status = _post("/api/v1/intervention/rank", {
            "gene_ids": ["AT1G56650"], "species": "arabidopsis",
            "intent": "knockdown", "budget": "low",
        })
        assert status == 200
        assert "candidates" in data
        if data["candidates"]:
            c = data["candidates"][0]
            assert "strategies" in c
            assert "recommended" in c
            assert len(c["strategies"]) >= 2

    def test_rank_knockout(self):
        data, status = _post("/api/v1/intervention/rank", {
            "gene_ids": ["AT1G56650"], "species": "arabidopsis",
            "intent": "knockout", "budget": "moderate",
        })
        assert status == 200
        if data["candidates"]:
            assert data["candidates"][0]["recommended"] == "CRISPR_KO"


# ─── Benchmark & Validation ───


class TestBenchmark:
    def test_benchmark_status(self):
        data, status = _get("/api/v1/benchmark/status")
        assert status == 200
        assert "atlas_summary" in data
        assert data["atlas_summary"]["genes"] > 0

    def test_provenance(self):
        data, status = _get("/api/v1/provenance")
        assert status == 200
