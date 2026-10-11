# GRN Atlas — common tasks. See README.md / docs/DEVELOPMENT.md.
.PHONY: bootstrap setup fetch fetch-all infer db signs perturbation-truth allele-pwms chromatin-peaks knocktf enrich tissue-weights validate benchmark validate-suite backend frontend test test-backend test-frontend test-skills clean-db help

help:
	@echo "make bootstrap      - ONE COMMAND: full data setup from a fresh clone (setup->fetch->db->enrich->knocktf->allele-pwms->chromatin-peaks)"
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
	@echo "make enrich         - load ConnecTF edges+perturbations, curated pathway edges, display names (needs make db)"
	@echo "make tissue-weights - compute per-tissue coexpression weights (also run by make db)"
	@echo "make validate       - run gold-standard + population-level network validation"
	@echo "make benchmark      - run BEELINE-style AUROC/AUPRC benchmarks"
	@echo "make validate-suite - run the full roadmap validation suite and save validation_runs summaries"
	@echo "make backend        - run the FastAPI server on :8000"
	@echo "make frontend       - run the Vite dev server on :3001"
	@echo "make test           - run backend + frontend tests"
	@echo "make test-skills    - run agent skill tests (342 direct-mode tests)"

# One command to take a fresh clone to a fully-populated atlas. Each step is individually
# re-runnable; the optional network layers (enrich/allele-pwms/chromatin-peaks) self-skip
# if a download is unavailable, so bootstrap never hard-fails on an offline extra.
bootstrap: setup fetch db enrich knocktf allele-pwms chromatin-peaks
	@echo ""
	@echo "=== GRN Atlas bootstrap complete ==="
	@echo "Verify:  make test-backend   (expect 342 passed)"
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
	venv/bin/python backend/scripts/derive_perturbation_signs.py
	venv/bin/python backend/scripts/validate_edge_signs.py

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
