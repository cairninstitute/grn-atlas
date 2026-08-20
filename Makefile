# GRN Atlas — common tasks. See README.md / docs/DEVELOPMENT.md.
.PHONY: setup fetch fetch-all infer db validate backend frontend test test-backend test-frontend test-skills clean-db help

help:
	@echo "make setup     - create venv + install backend & frontend deps"
	@echo "make fetch     - fetch source data (core+light tiers) into backend/data/"
	@echo "make fetch-all - fetch everything incl. heavy layers (needs kallisto/BLAST, slow)"
	@echo "make infer     - run GRNBoost2/GENIE3 inference on expression data (needs make db first)"
	@echo "make db        - (re)build backend/data/grn.sqlite3 from the fetched caches"
	@echo "make validate  - run gold-standard + population-level network validation"
	@echo "make backend   - run the FastAPI server on :8000"
	@echo "make frontend  - run the Vite dev server on :3001"
	@echo "make test      - run backend + frontend tests"
	@echo "make test-skills - run agent skill tests (252 direct-mode tests)"

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

validate:
	venv/bin/python backend/scripts/validate_regulation_quality.py
	venv/bin/python backend/scripts/validate_network_statistics.py

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
