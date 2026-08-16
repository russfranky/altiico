# Development guide

## Runtime

The supported development runtime is Python 3.11. The repository also uses Node.js for JavaScript syntax, UX, and performance checks.

## Bootstrap

```bash
make bootstrap
. .venv/bin/activate
```

Manual equivalent:

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Deterministic checks

These checks use committed data and do not require third-party credentials:

```bash
make status
make verify
make test
```

Run a focused test during development:

```bash
python -m pytest -q tests/test_catalog_acceptance.py
```

## Serving the catalog

```bash
make serve
```

The command serves `static/` at <http://localhost:8000/>. Opening `static/index.html` directly from a `file:` URL is not supported because the browser loads content-hashed JSON with `fetch`.

## Live source credentials

Live enrichment workflows may read the following environment variables:

| Source | Accepted variables |
|---|---|
| OpenSea | `OPENSEA_API_KEY` |
| Moralis | `MORALIS_API_KEY`, `MORALIS_KEY` |
| Etherscan | `ETHERSCAN_API_KEY`, `ETHERSCAN_KEY` |
| Bitquery | `BITQUERY_API_KEY`, `BITQUERY_TOKEN`, `BITQUERY_OAUTH_TOKEN` |
| OpenPage | `OPENPAGE_API_KEY` |

Never store real values in tracked files. Local `.env*` files are ignored, but shell environment variables or a dedicated secret manager are safer.

## Pipeline stages

### 1. Build the research store

```bash
PYTHONPATH=. python scripts/build_catalog_research_store.py \
  --output data/catalog_research_merged.json
```

### 2. Materialize normalized research

```bash
PYTHONPATH=. python scripts/materialize_catalog_research.py \
  --research data/catalog_research_merged.json
```

### 3. Export inventories

```bash
PYTHONPATH=. python scripts/export_vrm_inventory.py \
  --research data/catalog_research_merged.json \
  --output static/data/vrm-inventory.json

PYTHONPATH=. python scripts/export_avatar_inventory.py \
  --research data/catalog_research_merged.json \
  --vrm-inventory static/data/vrm-inventory.json \
  --openpage-assets data/openpage_asset_discovery.json \
  --output static/data/avatar-inventory.json
```

### 4. Audit and enforce

```bash
make acceptance
```

### 5. Build and verify public output

```bash
make build
python scripts/verify_catalog_consistency.py
make verify
```

## Research shard workflow

Work on one collection at a time:

1. identify the exact catalog ID, chain, and contract;
2. add or update its shard in `data/catalog_research.d/`;
3. cite primary evidence and observation timestamps;
4. enumerate the full relevant file lane;
5. probe every file claimed by the inventory;
6. rebuild normalized data and generated artifacts;
7. inspect acceptance reasons before and after;
8. run focused tests and the full verification suite.

Do not edit `data/catalog_acceptance.json`, inventory exports, or hashed public payloads by hand.

## Browser development

The public UI is plain HTML, CSS, and JavaScript under `static/`. Keep it deployable as static files. Use delegated events, preserve keyboard access and focus management, and avoid adding a build framework without a concrete product need.

Check JavaScript syntax:

```bash
node --check static/app.js
node --check static/discovery-overlay.js
node --check static/sw.js
```

## Dependency changes

Dependencies are pinned in `requirements.txt`. Explain why a dependency is needed, prefer maintained libraries, run `python -m pip check`, and let dependency review inspect the pull request.

Dependabot monitors Python and GitHub Actions dependencies. Do not merge an automated upgrade solely because CI is green. Review release notes and behavior changes.

## Troubleshooting

### Public catalog says data failed to load

Run `make build`, serve the `static/` directory over HTTP, and confirm that the content-hashed file referenced by `static/data/build-info.json` exists.

### A live source returns no data

Do not overwrite committed healthy evidence immediately. Check credentials, rate limits, response shape, source health, and the workflow's last-good preservation behavior.

### Snapshot mismatch

Regenerate all affected outputs from the same database and research state, then run `scripts/verify_catalog_consistency.py`.
