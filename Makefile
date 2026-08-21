# GRN Atlas — common tasks. See README.md / docs/DEVELOPMENT.md.
.PHONY: setup fetch fetch-all infer db tissue-weights validate benchmark validate-suite backend frontend test test-backend test-frontend test-skills clean-db help

help:
	@echo "make setup          - create venv + install backend & frontend deps"
	@echo "make fetch          - fetch source data (core+light tiers) into backend/data/"
	@echo "make fetch-all      - fetch everything incl. heavy layers (needs kallisto/BLAST, slow)"
	@echo "make infer          - run GRNBoost2/GENIE3 inference on expression data (needs make db first)"
	@echo "make db             - (re)build backend/data/grn.sqlite3 from the fetched caches"
	@echo "make tissue-weights - compute per-tissue coexpression weights (needs make db + expression data)"
	@echo "make validate       - run gold-standard + population-level network validation"
	@echo "make benchmark      - run BEELINE-style AUROC/AUPRC benchmarks"
	@echo "make validate-suite - run the full roadmap validation suite and save validation_runs summaries"
	@echo "make backend        - run the FastAPI server on :8000"
	@echo "make frontend       - run the Vite dev server on :3001"
	@echo "make test           - run backend + frontend tests"
	@echo "make test-skills    - run agent skill tests (252 direct-mode tests)"

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
