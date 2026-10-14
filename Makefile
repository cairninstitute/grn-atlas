# GRN Atlas — common tasks. See README.md / docs/DEVELOPMENT.md.
.PHONY: bootstrap setup fetch fetch-all infer db signs perturbation-truth allele-pwms chromatin-peaks knocktf knocktf-all external-regulation evidence-expansion qualify-evidence enrich tissue-weights verify-data validate benchmark validate-suite backend frontend test test-backend test-frontend test-skills clean-db help

help:
	@echo "make bootstrap      - release data setup from a fresh clone, including all external evidence and KnockTF species"
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
	@echo "make external-regulation - load CollecTRI, SIGNOR, and strict + expanded AGRIS evidence"
	@echo "make evidence-expansion - load ChIP-Atlas and TFLink; audit PCBase and literature sources"
	@echo "make qualify-evidence - build conflict-aware candidates and source qualification report"
	@echo "make verify-data    - fail unless all release data layers and minimum coverage are present"
	@echo "make enrich         - load ConnecTF edges+perturbations, curated pathway edges, display names (needs make db)"
	@echo "make tissue-weights - compute per-tissue coexpression weights (also run by make db)"
	@echo "make validate       - run gold-standard + population-level network validation"
	@echo "make benchmark      - run BEELINE-style AUROC/AUPRC benchmarks"
	@echo "make validate-suite - run the full roadmap validation suite and save validation_runs summaries"
	@echo "make backend        - run the FastAPI server on :8000"
	@echo "make frontend       - run the Vite dev server on :3001"
	@echo "make test           - run backend + frontend tests"
	@echo "make test-skills    - run agent skill tests (342 direct-mode tests)"

# One command to take a fresh clone to the verified release source-data profile. Each step is
# individually re-runnable. Some download stages self-skip on transient failures, but the final
# verifier rejects a degraded build that is missing a release-required layer.
bootstrap: setup fetch db external-regulation enrich knocktf-all evidence-expansion qualify-evidence allele-pwms chromatin-peaks verify-data
	@echo ""
	@echo "=== GRN Atlas bootstrap complete ==="
	@echo "Verify:  make test-backend"
	@echo "Run:     make backend        (API on :8000)   then   make frontend (UI on :3001)"

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

external-regulation:
	venv/bin/python backend/scripts/load_external_regulatory_sources.py all \
		--report backend/data/external_regulatory_benchmark.json

evidence-expansion:
	venv/bin/python backend/scripts/load_rice_id_aliases.py
	venv/bin/python backend/scripts/load_tflink.py
	venv/bin/python backend/scripts/load_chip_atlas.py
	venv/bin/python backend/scripts/load_expression_atlas_perturbations.py backend/source_manifests/expression_atlas_reviewed.json
	venv/bin/python backend/scripts/audit_pcbase.py --report backend/data/pcbase_qualification.json
	venv/bin/python backend/scripts/audit_literature_sources.py --report backend/data/literature_source_qualification.json

qualify-evidence:
	venv/bin/python backend/scripts/build_conserved_regulatory_evidence.py
	venv/bin/python backend/scripts/build_regulatory_candidates.py
	venv/bin/python backend/scripts/rank_cycle_closing_candidates.py
	venv/bin/python backend/scripts/qualify_regulatory_sources.py
	venv/bin/python backend/scripts/assess_agris_quality.py

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

clean-db:
	rm -f backend/data/grn.sqlite3
