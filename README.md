# Altiico — VRM Avatar Catalog

Research-grade, evidence-backed catalog of NFT avatar collections with verified
VRM, FBX, and rigged GLB model inventories. Every claim in the catalog is
source-attributed; every accepted avatar file passes binary validation, not
URL or keyword heuristics.

Public catalog: <https://www.altii.co/>

Formerly `russfranky/vrm-catalog`. See `docs/HUBZZ_ALTIICO_INTEGRATION.md` for
the planned merge of the public-facing catalog into the Hubzz avatar product.

## What this is

A researcher needs to find VRM avatar sets and answer three questions fast:
**what is this, can I see it, does the file actually work.** This repository is
that tool:

- Discovers avatar/NFT collections from OpenSea, Moralis, Etherscan, Bitquery,
  RPC/indexer surfaces, project metadata, GitHub repos, and direct asset URLs.
- Preserves conflicting observations instead of silently overwriting them.
- Validates actual GLB 2.0 binaries and requires `VRM` or `VRMC_vrm` before a
  VRM claim is promoted; FBX claims require explicit rigging evidence.
- Maintains a versioned SQLite index (`data/vrm_index.db`) with generated
  evidence committed to the repository.
- Deploys a static read-only catalog to Vercel.

A generated Hubzz staging bundle separates stageable avatar sets from deferred
sets. Unsupported chains, unknown licenses, and partial inventories are never
silently coerced into stronger claims.

## Status

The catalog acceptance gate tracks how many collections fully satisfy the
evidence bar. Current state lives in `data/catalog_acceptance.json`:
passing collections, failing collections with per-field reasons, and
scope-missing collections that are documented in scope but not yet in the
completeness report.

The gate semantics are deliberately strict:

- Every must-have field carries a real value or an explicit, evidence-backed
  resolution state (`not_available`, `not_applicable`, `unrecoverable`,
  `sunset`, `holder_gated`).
- `project_status` is one of `active`, `dormant`, `sunset`, evidenced.
- `avatar_inventory` must be exhaustive: every enumerated asset is probed and
  must validate as VRM, rigged GLB, or evidence-backed rigged FBX.
- `file_access` records the access mode and ownership requirement with
  evidence.

## Repository layout

```
scripts/            pipeline stages: discovery, research, materialize,
                    export, probe, audit, enforce, build
scripts/crawler/    HTTP crawl engine (shared fetch/store primitives)
data/               SQLite index, research shards (catalog_research.d/),
                    probe results, acceptance reports, evidence cache
data/catalog_research.d/   per-collection research shards (the unit of work)
static/             generated deploy artifacts (content-hashed, snapshot-pinned)
static/data/        build-info.json, hashed collections, inventories, manifests
docs/               design notes and integration plans
.github/workflows/  scheduled scraper + integrity jobs (GitHub Actions)
tests/              pipeline test suite (pytest)
```

## How the pipeline works

```
discovery sources (OpenSea, Moralis, Etherscan, GitHub, IPFS, ...)
        |
        v
research shard per collection (data/catalog_research.d/*.json)
        |
        v
materialize -> export inventories -> probe (binary validation)
        |
        v
audit (completeness report) -> enforce (acceptance gate)
        |
        v
build (snapshot-pinned static artifacts -> Vercel)
```

Every artifact shares one deterministic snapshot identity
(`vrmcat-v1-…`, see `scripts/catalog_snapshot.py`) so the committed database,
exports, and deployed site are always provably in sync.

## Running locally

```bash
# regenerate research store + inventories from shards and the SQLite index
PYTHONPATH=. python3 scripts/build_catalog_research_store.py --output data/catalog_research_merged.json
PYTHONPATH=. python3 scripts/export_vrm_inventory.py --research data/catalog_research_merged.json --output static/data/vrm-inventory.json
PYTHONPATH=. python3 scripts/export_avatar_inventory.py --research data/catalog_research_merged.json --vrm-inventory static/data/vrm-inventory.json --openpage-assets data/openpage_asset_discovery.json --output static/data/avatar-inventory.json

# audit + enforce the acceptance gate
PYTHONPATH=. python3 scripts/audit_avatar_completeness.py --research data/catalog_research_merged.json --inventory static/data/avatar-inventory.json --tiers A,B,C --output data/catalog_completeness_report.json
PYTHONPATH=. python3 scripts/enforce_avatar_acceptance.py --report data/catalog_completeness_report.json --inventory static/data/avatar-inventory.json --probe data/avatar_inventory_probe.json --output data/catalog_acceptance.json

# tests
python3 -m pytest -p no:recording
```

The standard unit of work is one research shard per collection: enumerate the
full asset lane, probe every file, resolve every field with evidence, then
regenerate and verify the gate moved.

## Data and provenance

- Attribution and data sources: see `CREDITS.md` (includes ToxSam's
  open-source-avatars registry, OpenSea, Moralis, Etherscan, IPFS, and artist
  archives).
- Scope, success criteria, and boundary decisions: see `SCOPE.md`.
- The catalog is a research tool. It documents third-party collections; verify
  license and usage terms before reusing any avatar.

## License

Code: MIT (see `LICENSE`). Catalog data remains attribution-carrying research
output; where a source's own terms are stricter, theirs govern.