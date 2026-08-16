PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python

.PHONY: help bootstrap status verify test build acceptance serve clean

help:
	@printf '%s\n' \
	  'bootstrap   Create .venv and install pinned dependencies' \
	  'status      Print catalog, staging, and public snapshot status' \
	  'verify      Run deterministic repository and syntax checks' \
	  'test        Run the full pytest suite' \
	  'build       Rebuild the static catalog from the committed database' \
	  'acceptance  Regenerate completeness and acceptance reports' \
	  'serve       Serve static/ at http://localhost:8000' \
	  'clean       Remove local Python and test caches'

bootstrap:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements.txt

status:
	$(PYTHON) scripts/project_status.py

verify:
	$(PYTHON) scripts/verify_repository.py
	$(PYTHON) -m compileall -q scripts sy
	@command -v node >/dev/null 2>&1 || { echo 'node is required for JavaScript checks' >&2; exit 1; }
	node --check static/app.js
	node --check static/discovery-overlay.js
	node --check static/sw.js
	$(PYTHON) -m pip check

test:
	$(PYTHON) -m pytest -p no:recording

build:
	PYTHONPATH=. $(PYTHON) scripts/build_catalog.py

acceptance:
	PYTHONPATH=. $(PYTHON) scripts/build_catalog_research_store.py --output data/catalog_research_merged.json
	PYTHONPATH=. $(PYTHON) scripts/export_vrm_inventory.py --research data/catalog_research_merged.json --output static/data/vrm-inventory.json
	PYTHONPATH=. $(PYTHON) scripts/export_avatar_inventory.py --research data/catalog_research_merged.json --vrm-inventory static/data/vrm-inventory.json --openpage-assets data/openpage_asset_discovery.json --output static/data/avatar-inventory.json
	PYTHONPATH=. $(PYTHON) scripts/audit_avatar_completeness.py --research data/catalog_research_merged.json --inventory static/data/avatar-inventory.json --tiers A,B,C --output data/catalog_completeness_report.json
	PYTHONPATH=. $(PYTHON) scripts/enforce_avatar_acceptance.py --report data/catalog_completeness_report.json --inventory static/data/avatar-inventory.json --probe data/avatar_inventory_probe.json --output data/catalog_acceptance.json

serve:
	$(PYTHON) -m http.server 8000 --directory static

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov
