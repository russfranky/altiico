# AGENTS.md — superyeti

> **What this is:** A static catalog and discovery pipeline for VRM-bearing
> NFT collections across EVM and Solana chains. The output is a versioned
> `avatar-manifest-v1.json` that a downstream metaverse client (Hubzz)
> consumes to resolve avatars at runtime. The repo also ships a browsable
> static HTML catalog.

## Quick orientation

- **Language:** Python 3 stdlib preferred (no aiohttp in extractors; urllib +
  struct for GLB parsing). OpenSea client is async (aiohttp). Tests are
  pytest. Perf tests are a standalone Node `.mjs` file.
- **Database:** SQLite at `data/vrm_index.db` (10 tables, 74 collections,
  4,062 avatars, 216 OpenSea candidates). No ORM. Migrations are plain SQL
  applied manually via `sqlite3 data/vrm_index.db < migrations/NNN_*.sql`.
  There is no migration runner script.
- **Static catalog:** `static/index.html` + `app.js` + `app.css` + `sw.js`
  (service worker). Data is content-hashed JSON in `static/data/`, pointed
  to by `build-info.json`. No build step beyond `python scripts/build_catalog.py`.
- **Manifest handoff:** `static/data/avatar-manifest-v1.json` is the
  declarative contract for Hubzz. Schema at `static/schema/avatar-manifest-v1.schema.json`.
- **CLI:** `./sy` is the unified CLI (`sy ls`, `sy find`, `sy stats`,
  `sy enrich`, `sy build`, `sy db`). Run `./sy --help` for the full list.

## Repository layout

```
scripts/      Core pipeline: extract, enrich, normalize, build, export
sources/      Source importers: A3AC, OSA, Solana Metaplex, Reservoir
data/         SQLite DB, YAML configs (overrides, discovery leads), research notes
static/       Static HTML catalog + hashed JSON data + schemas
migrations/   Plain SQL migrations (006–010; 001–005 predate the restructure)
config/       cache_policy.yaml, license-mapping.yaml
docs/         license-methodology.md, source-provenance.md
tests/        pytest + catalog-performance.mjs
sy            Unified CLI
```

## How to run things

```bash
# Tests
source venv/bin/activate && python -m pytest tests/ -v
node tests/catalog-performance.mjs

# Build the static catalog (emits static/data/*.json)
python scripts/build_catalog.py

# Export the Hubzz manifest (validates against schema)
python scripts/export_hubzz_manifest.py --validate

# Enrich OpenSea (needs ~/.opensea/api_key)
python scripts/enrich_opensea.py

# Extract VRM metadata from a URL
python scripts/extract_vrm_meta.py <url>

# Enrich VRM metadata (dry run)
python scripts/enrich_vrm_metadata.py --dry-run

# Normalize licenses (dry run, force re-assess)
python scripts/normalize_licenses.py --dry-run --force

# Resolve a shared-storefront collection
python scripts/resolve_opensea_collections.py --contract 0x... --token-id 123

# Import A3AC / OSA registries
python sources/awesome_3d_avatar_collections.py --dry-run
python sources/opensourceavatars.py --dry-run

# Scan Solana Metaplex
python sources/solana_metaplex.py --mint <address> --dry-run

# Discover VRM pointers in token metadata
python scripts/discover_metadata_fields.py --json '{"vrm_url":"..."}' --validate

# Reservoir EVM discovery
python sources/reservoir.py --search "3d avatar" --validate --dry-run

# Regenerate synthetic VRM test fixtures
python tests/fixtures/generate_vrm_fixtures.py
```

## Key conventions

- **Python stdlib preferred.** `extract_vrm_meta.py` uses `urllib + struct`,
  not aiohttp. The OpenSea client is the exception (async aiohttp).
- **`sys.path` manipulation for sibling imports.** All scripts use
  `_REPO_ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0,
  str(_REPO_ROOT))` then `from scripts.foo import bar`. Use `_REPO_ROOT`
  (not `_SCRIPT_DIR`) on `sys.path` when importing `scripts.foo`.
- **YAML for reviewable mappings.** `license-mapping.yaml`,
  `cache_policy.yaml`, `opensea_collection_overrides.yaml`,
  `discovery_leads.yaml`. Nothing license-related is hard-coded in Python.
- **Content hashing.** First 12 hex of SHA-256 for static data files.
  `build-info.json` is unhashed (short TTL pointer to hashed files).
- **IPFS CIDs are case-sensitive.** Do NOT lowercase in `canonicalize_url`.
- **VRM 0.x field names have intentional misspellings** (`violentUssageName`,
  `sexualUssageName`, `commercialUssageName`). Read exactly as written.
- **License normalization:** unknown → gray, never green. Confidence levels:
  `embedded > collection > manual > unknown`. Precedence and conflict
  handling documented in `docs/license-methodology.md`.
- **Shared storefront** `0x495f947276749ce646f68ac8c248420045cb7b5e`:
  contract is NOT a collection identifier; need token_id or slug. See
  `scripts/resolve_opensea_collections.py` and
  `data/opensea_collection_overrides.yaml`.
- **Non-EVM chains** (solana, arweave) do NOT get `eip155:` CAIP ids.
  `_caip_id` returns `None`, falls back to slug id. Schema id pattern
  requires numeric chain ref after `eip155:`.
- **URL-resolved licenses** (`resolve_url`) return dimensions only, NOT
  `reason_codes` — known minor gap, documented in
  `tests/test_license_normalization.py`.
- **`NEVER_GREEN_FROM_UNKNOWN` guard** in `assess_collection` is defensive
  / unreachable via normal flow — documented in test.
- **No git remote, no deploy config, no CI.** The catalog is served
  locally; `static/` is the deployable artifact if a host is added.

## Commit message convention

```
Deliverable N: <short title>

<body explaining what and why>

Generated with [Devin](https://devin.ai)

Co-Authored-By: Devin <158243242+devin-ai-integration[bot]@users.noreply.github.com>
```

## Verification before declaring work done

1. `source venv/bin/activate && python -m pytest tests/ -q` — must be
   135/135 (or whatever the current count is; check prior runs).
2. `node tests/catalog-performance.mjs` — must be `ALL PASS` (8 assertions).
3. If you changed `build_catalog.py` or the DB, rebuild:
   `python scripts/build_catalog.py` and verify `build-info.json` is sane.
4. If you changed the manifest exporter:
   `python scripts/export_hubzz_manifest.py --validate`.

## DB schema overview

| Table | Rows | Purpose |
|---|---|---|
| `collections` | 74 | Primary collection records (tier, chain, license_category, etc.) |
| `contracts` | 69 | Contract addresses per collection (one collection may have multiple) |
| `avatars` | 4,062 | Individual avatar records with VRM URLs |
| `opensea_candidates` | 216 | OpenSea-discovered leads pending tier promotion |
| `collection_identifiers` | 131 | Multi-namespace IDs (slug, contract, token) per collection |
| `source_cache` | 0 | TTL cache for OpenSea API responses (migration 008) |
| `vrm_metadata` | 0 | Extracted VRM meta per URL (migration 007; ready for enrich_vrm_metadata.py) |
| `avatar_vrm` | 0 | Avatar-to-VRM-URL linkage (migration 007) |
| `license_dimensions` | 74 | Normalized 9-dimension license per collection (migration 010) |
| `sources` | — | Source provenance metadata |

`source_cache`, `vrm_metadata`, and `avatar_vrm` are empty and ready for
the enrichment scripts to populate. `license_dimensions` is backfilled
with `confidence='legacy'`; run `normalize_licenses.py --force` to
re-assess.

## Tier system

| Tier | Meaning |
|---|---|
| A | VRM pointer in token metadata, validated via partial-GLB extraction |
| B | VRM file exists off-chain, not linked from token metadata |
| C | Lead only — name/description suggests 3D avatar; no VRM proof |
| `not_vrm` | Investigated, confirmed not VRM |
| `arweave` | Arweave-native (proof via transaction ID) |
| `infra` | Infrastructure, not an avatar collection |

## Proof flow (lead → confirmed)

```
lead source (A3AC / research / DappRadar / discovery_leads)
  → resolve_opensea_collections.py  (shared-storefront disambiguation)
  → enrich_opensea.py               (fetch token metadata)
  → discover_metadata_fields.py     (scan metadata for VRM pointer)
  → extract_vrm_meta.py             (partial-GLB extraction)
  → normalize_licenses.py           (map raw terms to dimensions)
  → tier A collection in vrm_index.db
```

See `docs/source-provenance.md` for the full five-axis proof documentation
per source (NFT ownership / VRM existence / metadata linkage / license /
marketing-only).

## Remaining work (P3, lowest priority)

- `static/catalog-worker.js` — only if perf tests show >50ms long tasks
  (they don't — p75 is ~2ms)
- Top/trending discovery endpoints in `enrich_opensea.py` (§4 P2 of research doc)
- Per-chain `last_checked_at` on cross-chain leads

Completed P3 source scanners:

- `sources/nftscan.py` — Linea + Polygon zkEVM sweep; imports only validated
  binary VRM hits.
- `sources/objkt.py` — Tezos metadata scan; imports only validated binary
  VRM hits.

**Do NOT add sql.js or IndexedDB** at 74/4,062 records.

## Hubzz-side handoff (out of this repo)

The manifest at `static/data/avatar-manifest-v1.json` is the handoff
contract. Hubzz needs to:

1. Replace `AvatarApiClient.getOptimizedMap()` with `getAvatarManifest()` +
   `matchCollection()` + `resolveAvatar()`
2. Preserve `getOptimizedMap()` as a compat adapter
3. `AvatarVRMManager` accepts `ResolvedAvatar` with URL, hash, license/access
   mode, fallback reason
4. Add signed holder-gated VRM delivery for collections where
   redistribution is prohibited
5. Regenerate `~/.understand-anything/knowledge-graph.json` after adding
   manifest/resolver nodes
