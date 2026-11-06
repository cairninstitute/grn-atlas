# GRN Atlas — common tasks. See README.md / docs/DEVELOPMENT.md.
.PHONY: bootstrap bootstrap-gpu bootstrap-api setup fetch fetch-all infer db signs perturbation-truth allele-pwms chromatin-peaks knocktf knocktf-all perturbation-evidence discover-plant-perturbations cross-species-transfer benchmark-plant-transfer external-regulation evidence-expansion direct-binding qualify-evidence enrich tissue-weights clonelab-data verify-clonelab-data validate-clonelab-release verify-data validate benchmark validate-suite connectf-api jaspar-vertebrate ortholog-signs planttfdb-edges remap-binding unibind-binding omnipath-refresh promote-evidence rebuild-derived esm2-embeddings alphafold-features structural-predictions directed-inference scrna-data geneformer-embeddings celltype-regulation evo2-scores grassius-data cistrome-data data-expansion backend frontend test test-backend test-frontend test-skills clean-db help

help:
	@echo "make bootstrap      - full CPU/network-backed atlas from a fresh clone (sources → promotion → derived → verify)"
	@echo "make bootstrap-gpu  - GPU layers: ESM2 embeddings + Geneformer cell embeddings"
	@echo "make bootstrap-api  - API layers: Evo2 scores + structural predictions + AlphaFold features"
	@echo "make setup          - create venv + install backend & frontend deps"
	@echo "make fetch          - fetch source data (core+light tiers) into backend/data/"
	@echo "make fetch-all      - fetch everything incl. heavy layers (needs kallisto/BLAST, slow)"
	@echo "make infer          - run GRNBoost2/GENIE3 inference on expression data (needs make db first)"
	@echo "make db             - (re)build backend/data/grn.sqlite3 from caches (incl. edge signs + perturbation ground-truth)"
	@echo "make signs          - set measured edge signs + coexpression context, then validate (part of make db)"
	@echo "make perturbation-truth - load literature-grounded perturbation observations (part of make db)"
	@echo "make allele-pwms    - cache JASPAR PWMs for grn-allele-affinity (needs make db + network)"
	@echo "make chromatin-peaks - download+load Arabidopsis DAP-seq peaks (Plant Cistrome, needs make db + network)"
	@echo "make knocktf        - download+load KnockTF LOF perturbations, re-derive signs (needs make db + network)"
	@echo "make knocktf-all    - stream/load KnockTF for Arabidopsis, human, and mouse (large download)"
	@echo "make perturbation-evidence - aggregate context-aware perturbation signs into candidate evidence"
	@echo "make discover-plant-perturbations - refresh reviewed-candidate report from Expression Atlas"
	@echo "make cross-species-transfer - build and calibrate orthology/synteny edge transfers"
	@echo "make benchmark-plant-transfer - summarize supported/exploratory plant transfer growth"
	@echo "make external-regulation - load CollecTRI, SIGNOR, and strict + expanded AGRIS evidence"
	@echo "make evidence-expansion - load ChIP-Atlas and TFLink; audit PCBase and literature sources"
	@echo "make direct-binding  - fetch+load direct TF-binding data (GTRD, Cistrome, GEO) for all species"
	@echo "make qualify-evidence - build conflict-aware candidates and source qualification report"
	@echo "make verify-data    - fail unless all release data layers and minimum coverage are present"
	@echo "make clonelab-data  - fetch/index CloneLab plasmid, transcript, Arabidopsis, and petunia references"
	@echo "make verify-clonelab-data - verify registered CloneLab reference checksums"
	@echo "make validate-clonelab-release - validate gel calibration and both species demonstrations"
	@echo "make enrich         - load ConnecTF edges+perturbations, curated pathway edges, display names (needs make db)"
	@echo "make tissue-weights - compute per-tissue coexpression weights (also run by make db)"
	@echo "make validate       - run gold-standard + population-level network validation"
	@echo "make benchmark      - run BEELINE-style AUROC/AUPRC benchmarks"
	@echo "make validate-suite - run the full roadmap validation suite and save validation_runs summaries"
	@echo "make backend        - run the FastAPI server on :8000"
	@echo "make frontend       - run the Vite dev server on :3001"
	@echo "make test           - run backend + frontend tests"
	@echo "make test-skills    - run agent skill tests (342 direct-mode tests)"
	@echo "make connectf-api   - fetch ConnecTF TF-target edges via API + load into atlas"
	@echo "make jaspar-vertebrate - fetch JASPAR 2024 vertebrate motifs + scan human/mouse promoters"
	@echo "make ortholog-signs - transfer signed edges across species via ortholog mapping"
	@echo "make esm2-embeddings - generate ESM2 protein embeddings for all TFs (needs GPU + pip install -r backend/requirements-gpu.txt)"
	@echo "make alphafold-features - fetch AlphaFold pLDDT/disorder features for TF proteins"
	@echo "make structural-predictions - run Boltz-2 structural binding predictions (needs NVIDIA_NIM_API_KEY)"
	@echo "make planttfdb-edges - fetch PlantTFDB/PlantRegMap regulatory edges (arabidopsis, rice, tomato)"
	@echo "make remap-binding  - load ReMap 2022 ChIP-seq TF binding (human, mouse, arabidopsis)"
	@echo "make unibind-binding - load UniBind 2022 motif-validated binding (human, mouse, arabidopsis)"
	@echo "make promote-evidence - promote all evidence sources into the interactions table"
	@echo "make directed-inference - run perturbation-supervised directed GRN inference"
	@echo "make scrna-data     - fetch public scRNA-seq datasets (human PBMC, mouse marrow, arabidopsis root)"
	@echo "make geneformer-embeddings - generate Geneformer cell embeddings from scRNA-seq (needs GPU)"
	@echo "make celltype-regulation - derive cell-type-specific regulatory edges from scRNA-seq"
	@echo "make evo2-scores    - score promoters with Evo2 DNA model (needs NVIDIA_NIM_API_KEY + make structural-predictions first)"
	@echo "make grassius-data  - load GRASSIUS grass TF regulatory data (rice, maize)"
	@echo "make cistrome-data  - load Cistrome DB ChIP-seq TF binding (human, mouse)"
	@echo "make omnipath-refresh - re-fetch CollecTRI + SIGNOR edges with citations from OmniPath"
	@echo "make data-expansion - load all expansion sources (before promotion/derived layers)"
	@echo "make rebuild-derived - rebuild promotion, tissue weights, directed inference, cell-type edges"

.NOTPARALLEL:

# One command to take a fresh clone to the verified release source-data profile. Each step is
# individually re-runnable and must be run sequentially (SQLite is single-writer).
# Phase 1: core DB + all source ingestion (before any promotion or derived layers)
# Phase 2: promotion + derived layers (after all sources are loaded)
# Phase 3: verification (last)
bootstrap: setup fetch db external-regulation enrich knocktf-all evidence-expansion direct-binding allele-pwms chromatin-peaks data-expansion rebuild-derived qualify-evidence verify-data
	@echo ""
	@echo "=== GRN Atlas bootstrap complete ==="
	@echo "Verify:  make test-backend"
	@echo "Run:     make backend        (API on :8000)   then   make frontend (UI on :3001)"
	@echo "GPU:     make bootstrap-gpu  (ESM2 + Geneformer; requires pip install -r backend/requirements-gpu.txt)"
	@echo "API:     make bootstrap-api  (Evo2 + structural predictions; requires NVIDIA_NIM_API_KEY)"

bootstrap-gpu: geneformer-embeddings esm2-embeddings

bootstrap-api: structural-predictions alphafold-features evo2-scores

setup:
	python3 -m venv venv
	ln -sfn ../venv backend/venv
	venv/bin/pip install -r backend/requirements.txt -r backend/requirements-dev.txt
	npm install

fetch:
	venv/bin/python backend/scripts/fetch_sources.py --tier light

fetch-all:
	venv/bin/python backend/scripts/fetch_sources.py --tier all

infer:
	venv/bin/python backend/scripts/infer_grn.py --all

db:
	venv/bin/python backend/scripts/build_db.py
	venv/bin/python backend/scripts/infer_edge_signs.py
	venv/bin/python backend/scripts/validate_edge_signs.py
	venv/bin/python backend/scripts/load_perturbation_truth.py
	venv/bin/python backend/scripts/compute_tissue_weights.py

signs:
	venv/bin/python backend/scripts/infer_edge_signs.py
	venv/bin/python backend/scripts/validate_edge_signs.py

perturbation-truth:
	venv/bin/python backend/scripts/load_perturbation_truth.py

allele-pwms:
	venv/bin/python backend/scripts/cache_motif_pwms.py

chromatin-peaks:
	@if [ ! -f /tmp/GSE60143_RAW.tar ]; then \
		echo "--- Downloading Plant Cistrome DAP-seq peaks (GSE60143, ~74 MB) ---"; \
		curl -L -o /tmp/GSE60143_RAW.tar "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE60nnn/GSE60143/suppl/GSE60143_RAW.tar"; \
	fi
	venv/bin/python backend/scripts/load_dapseq_peaks.py /tmp/GSE60143_RAW.tar

knocktf:
	venv/bin/python backend/scripts/load_knocktf_perturbations.py
	venv/bin/python backend/scripts/derive_perturbation_signs.py --species arabidopsis
	venv/bin/python backend/scripts/validate_edge_signs.py

knocktf-all:
	venv/bin/python backend/scripts/load_knocktf_perturbations.py --species all
	venv/bin/python backend/scripts/derive_perturbation_signs.py --species arabidopsis
	venv/bin/python backend/scripts/validate_edge_signs.py

perturbation-evidence:
	venv/bin/python backend/scripts/build_perturbation_evidence.py
	venv/bin/python backend/scripts/calibrate_perturbation_signs.py
	venv/bin/python backend/scripts/benchmark_inferred_sign_model.py

discover-plant-perturbations:
	venv/bin/python backend/scripts/discover_plant_perturbations.py \
		--output docs/benchmarks/plant-perturbation-discovery.json

cross-species-transfer:
	venv/bin/python backend/scripts/build_perturbation_evidence.py
	venv/bin/python backend/scripts/calibrate_perturbation_signs.py
	venv/bin/python backend/scripts/build_conserved_regulatory_evidence.py
	venv/bin/python backend/scripts/calibrate_cross_species_transfer.py
	venv/bin/python backend/scripts/build_regulatory_candidates.py
	venv/bin/python backend/scripts/rank_cycle_closing_candidates.py
	venv/bin/python backend/scripts/benchmark_cross_species_transfer.py
	venv/bin/python backend/scripts/benchmark_plant_transfer_expansion.py \
		--baseline docs/benchmarks/plant-transfer-expansion-baseline.json
	venv/bin/python backend/scripts/verify_cross_species_transfer.py

benchmark-plant-transfer:
	venv/bin/python backend/scripts/benchmark_plant_transfer_expansion.py \
		--baseline docs/benchmarks/plant-transfer-expansion-baseline.json

external-regulation:
	venv/bin/python backend/scripts/load_external_regulatory_sources.py all \
		--report backend/data/external_regulatory_benchmark.json

evidence-expansion:
	venv/bin/python backend/scripts/load_rice_id_aliases.py || venv/bin/python backend/scripts/load_rice_rap_aliases.py
	venv/bin/python backend/scripts/load_tflink.py
	venv/bin/python backend/scripts/load_chip_atlas.py
	venv/bin/python backend/scripts/load_expression_atlas_perturbations.py backend/source_manifests/expression_atlas_reviewed.json
	venv/bin/python backend/scripts/audit_pcbase.py --report backend/data/pcbase_qualification.json
	venv/bin/python backend/scripts/audit_literature_sources.py --report backend/data/literature_source_qualification.json

direct-binding:
	venv/bin/python backend/scripts/fetch_direct_binding.py
	venv/bin/python backend/scripts/load_direct_binding.py
	venv/bin/python backend/scripts/promote_evidence_to_interactions.py

qualify-evidence:
	venv/bin/python backend/scripts/build_perturbation_evidence.py
	venv/bin/python backend/scripts/calibrate_perturbation_signs.py
	venv/bin/python backend/scripts/build_conserved_regulatory_evidence.py
	venv/bin/python backend/scripts/calibrate_cross_species_transfer.py
	venv/bin/python backend/scripts/build_regulatory_candidates.py
	venv/bin/python backend/scripts/rank_cycle_closing_candidates.py
	venv/bin/python backend/scripts/qualify_regulatory_sources.py
	venv/bin/python backend/scripts/assess_agris_quality.py
	venv/bin/python backend/scripts/verify_perturbation_release.py
	venv/bin/python backend/scripts/verify_cross_species_transfer.py

verify-data:
	venv/bin/python backend/scripts/verify_release_data.py

enrich:
	@if [ ! -d /tmp/connectf_data_release_v1 ]; then \
		echo "--- Downloading ConnecTF data (~200 MB, one-time) ---"; \
		curl -L -o /tmp/connectf_data.tar.gz https://connectf.s3.amazonaws.com/connectf_data_release_v1.tar.gz \
			&& tar xzf /tmp/connectf_data.tar.gz -C /tmp || echo "  ConnecTF download failed; continuing without it."; \
	fi
	@echo "--- Loading ConnecTF edges + TF-perturbation observations ---"
	@if [ -d /tmp/connectf_data_release_v1 ]; then \
		cd backend && ../venv/bin/python scripts/load_connectf.py /tmp/connectf_data_release_v1; \
		../venv/bin/python scripts/load_connectf_perturbations.py /tmp/connectf_data_release_v1; \
		../venv/bin/python scripts/load_connectf_evidence.py /tmp/connectf_data_release_v1; \
		../venv/bin/python scripts/derive_perturbation_signs.py; \
		../venv/bin/python scripts/validate_edge_signs.py; \
	else \
		echo "  Skipped: ConnecTF data unavailable (network?). Atlas still works without it."; \
	fi
	@echo "--- Building display names ---"
	cd backend && ../venv/bin/python scripts/build_display_names.py
	@echo "--- Loading curated pathway edges + display name fixes ---"
	cd backend && ../venv/bin/python scripts/load_curated_pathway_edges.py

tissue-weights:
	venv/bin/python backend/scripts/compute_tissue_weights.py

clonelab-data:
	venv/bin/python backend/scripts/fetch_clonelab_references.py
	venv/bin/python backend/scripts/fetch_clonelab_genomes.py --species all
	venv/bin/python backend/scripts/build_clonelab_reference_manifest.py

verify-clonelab-data:
	venv/bin/python backend/scripts/verify_clonelab_references.py

validate-clonelab-release: verify-clonelab-data
	venv/bin/python backend/scripts/validate_clonelab_gel_calibration.py
	venv/bin/python backend/scripts/run_clonelab_demonstrations.py

validate:
	venv/bin/python backend/scripts/validate_regulation_quality.py
	venv/bin/python backend/scripts/validate_network_statistics.py

benchmark:
	venv/bin/python backend/scripts/benchmark_beeline.py

validate-suite:
	venv/bin/python backend/scripts/run_validation_suite.py

backend:
	cd backend && ../venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000

frontend:
	npm run dev

test: test-backend test-frontend

test-backend:
	venv/bin/python -m pytest backend -q

test-frontend:
	npm run test

test-skills:
	venv/bin/python .agents/skills/_test_all_skills.py

connectf-api:
	venv/bin/python backend/scripts/fetch_connectf.py
	venv/bin/python backend/scripts/load_direct_binding.py

jaspar-vertebrate:
	venv/bin/python backend/scripts/fetch_jaspar_vertebrate.py

ortholog-signs:
	venv/bin/python backend/scripts/transfer_ortholog_signs.py

planttfdb-edges:
	venv/bin/python backend/scripts/fetch_planttfdb_edges.py

remap-binding:
	venv/bin/python backend/scripts/load_remap.py

unibind-binding:
	venv/bin/python backend/scripts/load_unibind.py

promote-evidence:
	venv/bin/python backend/scripts/promote_evidence_to_interactions.py

esm2-embeddings:
	@if venv/bin/python -c "import torch" 2>/dev/null; then \
		venv/bin/python backend/scripts/generate_esm2_embeddings.py; \
	else \
		echo "torch not installed. Run: venv/bin/pip install -r backend/requirements-gpu.txt"; \
		echo "Skipping ESM2 embeddings (optional GPU step)."; \
	fi

alphafold-features:
	venv/bin/python backend/scripts/fetch_alphafold_features.py

structural-predictions:
	@if [ -z "$${NVIDIA_NIM_API_KEY:-}" ] && [ -f ~/.secrets.env ]; then \
		. ~/.secrets.env 2>/dev/null; \
	fi; \
	if [ -z "$${NVIDIA_NIM_API_KEY:-}" ]; then \
		echo "NVIDIA_NIM_API_KEY not set. Get a free key at https://build.nvidia.com"; \
		echo "Skipping structural predictions (optional)."; \
	else \
		venv/bin/python backend/scripts/predict_structural_binding.py --tier all --max-edges 500; \
	fi

directed-inference:
	venv/bin/python backend/scripts/infer_directed_grn.py --all

scrna-data:
	venv/bin/python backend/scripts/fetch_scrna_data.py --species all

geneformer-embeddings:
	@if venv/bin/python -c "import torch" 2>/dev/null; then \
		venv/bin/python backend/scripts/run_geneformer.py --species all; \
	else \
		echo "torch not installed. Run: venv/bin/pip install -r backend/requirements-gpu.txt"; \
		echo "Skipping Geneformer embeddings (optional GPU step)."; \
	fi

celltype-regulation: scrna-data
	venv/bin/python backend/scripts/derive_celltype_regulation.py --species all

evo2-scores:
	@if [ -z "$${NVIDIA_NIM_API_KEY:-}" ] && [ -f ~/.secrets.env ]; then \
		. ~/.secrets.env 2>/dev/null; \
	fi; \
	if [ -z "$${NVIDIA_NIM_API_KEY:-}" ]; then \
		echo "NVIDIA_NIM_API_KEY not set. Get a free key at https://build.nvidia.com"; \
		echo "Skipping Evo2 promoter scoring (optional)."; \
	else \
		venv/bin/python backend/scripts/score_evo2_promoters.py --species all; \
	fi

grassius-data:
	venv/bin/python backend/scripts/load_grassius.py

cistrome-data:
	venv/bin/python backend/scripts/load_cistrome.py

omnipath-refresh:
	venv/bin/python backend/scripts/fetch_collectri_signor.py

data-expansion: connectf-api jaspar-vertebrate ortholog-signs planttfdb-edges remap-binding unibind-binding omnipath-refresh scrna-data
	@echo "Data expansion sources loaded."

rebuild-derived: promote-evidence tissue-weights directed-inference celltype-regulation
	@echo "Derived layers rebuilt."

clean-db:
	rm -f backend/data/grn.sqlite3
