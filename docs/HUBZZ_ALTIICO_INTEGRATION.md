# Hubzz altiico integration direction

Status: planning note, not an implementation commitment.

## Goal

Move the useful public-facing capabilities of `vrm-catalog` into `russfranky/hubzz-altiico` so users experience one Hubzz avatar discovery product instead of a standalone evidence catalog plus a separate altiico browser.

The merge should preserve the strongest property of `vrm-catalog`: evidence-backed, source-attributed VRM validation. It should also preserve the existing altiico boundary: altiico is the public/operator SPA, not the backend ingest/publish authority.

## Current responsibilities

### vrm-catalog

- discovers avatar/NFT collections from OpenSea, Moralis, Etherscan, Bitquery, RPC/indexer surfaces, project metadata and direct asset URLs
- preserves conflicting observations instead of silently overwriting them
- validates actual GLB 2.0 binaries and requires `VRM` or `VRMC_vrm` before a VRM claim is promoted
- builds Hubzz staging data, collection banners, source evidence and a versioned SQLite index
- persists generated evidence and `data/vrm_index.db` in GitHub
- deploys a static read-only catalog to Vercel

### hubzz-altiico

- public browse/search/profile/inventory UI
- operator VRM preview, rig QA, thumbnails and manifest export
- reads live avatar/collection state from `avatar-api`, with static fallback data
- does not ingest or publish production collection state directly

## Recommended merge architecture

```text
external discovery sources
  OpenSea / Moralis / Etherscan / Bitquery / RPC / IPFS / project sites
                    |
                    v
          vrm-catalog evidence pipeline
                    |
      binary validation + source consensus
                    |
          canonical staging artifact
                    |
          backend ingest / avatar-api
                    |
                    v
              hubzz-altiico
       browse / search / profile / QA
                    |
                    v
                 Hubzz
```

The browser should not become responsible for GitHub Actions, API secrets, blockchain indexing, or canonical VRM validation.

## Phase 1: consume the catalog in altiico

Add a read-only catalog adapter in altiico that can consume the generated `vrm-catalog` public artifact as an additional source behind `avatarService`.

Priority data to surface:

- collection identity and chain
- contract and token identity
- banner and PFP
- validated VRM URL/status/spec/hash
- evidence/verification status
- license/use classification
- marketplace/purchase URL
- normalized traits when available
- source freshness and conflicts

Altiico should prefer live `avatar-api` production records when they exist, then augment them with evidence fields from the catalog. Catalog-only validated collections can appear as discovery candidates without implying they are Hubzz-published.

## Phase 2: schema convergence

Create one shared conceptual model between catalog staging and `ApiCollection` / `ApiAvatar`.

Collection fields should converge around:

- stable slug/id
- chain + contract
- name/description
- `banner_url` + `pfp_url`
- source/evidence status
- license/use policy
- stage/publish status
- collection-level traits/stats

Avatar fields should converge around:

- API id and on-chain token id as separate fields
- original and optimized VRM URLs
- binary validation status/spec/hash
- thumbnails
- traits
- source provenance
- purchase/market links
- content/license metadata

Do not conflate marketplace identity, contract identity, API row identity or token id.

## Phase 3: backend ingest instead of browser coupling

The durable production path should be a backend importer that consumes the validated catalog staging artifact and upserts approved records into the backend used by altiico/Hubzz.

Rules:

- staging/import defaults to dry-run
- no automatic publication/listing
- binary-validated VRM evidence required
- conflicts remain visible for review
- existing published records are protected from destructive overwrite
- provenance and observation timestamps survive import

This work belongs in the Hubzz backend/avatar-api layer, even though altiico is the user-facing destination.

## Phase 4: retire duplicate public catalog UI

Once altiico exposes the same evidence-backed browse/search/profile capability, the standalone `vrm-catalog` site can become either:

1. a pipeline/evidence repository only, or
2. an internal diagnostic view for discovery quality and source conflicts.

The public destination should then be altiico.

## Storage direction

Current catalog storage is acceptable for the evidence pipeline:

- versioned SQLite + JSON evidence committed in GitHub
- R2/CDN for large binary/media assets
- Vercel for static delivery

Do not introduce SpacetimeDB solely to replace the catalog SQLite artifact.

Consider SpacetimeDB when Hubzz/altiico needs genuinely live mutable state such as:

- user favorites/preferences
- Avatar Match conversations/preferences
- live inventory/session state
- social/presence features
- mutable operator workflow state
- realtime ownership/event ingestion
- state that must be queryable immediately without a Git commit/deploy cycle

If adopted, SpacetimeDB should hold live application state. Evidence provenance and deterministic catalog snapshots should remain exportable/versioned rather than becoming opaque mutable rows.

## Product features unlocked by the merge

### Avatar Match

AI-assisted avatar discovery grounded only in reachable catalog/API data. User preferences are matched against traits, collection style, availability, license, chain, price context and validated VRM status. Recommendations should link to the avatar/collection profile and purchase location where available.

### Trait rarity

Minimal MMO-inspired trait rarity treatment in altiico. Calculate rarity only where collection inventory coverage is sufficient, using observed trait frequency. Keep trait rarity separate from market value.

Suggested labels: Common, Uncommon, Rare, Epic, Legendary.

## First implementation slice

The safest first code change in altiico is intentionally small:

1. define a `CatalogCollection` / `CatalogAvatar` adapter type
2. fetch a pinned/versioned catalog JSON artifact read-only
3. merge catalog evidence into `avatarService` results by chain + contract + token identity
4. expose verification and source state on collection/avatar profiles
5. add tests proving catalog data cannot overwrite stronger live production identity fields

After that works, move ingestion to the backend and stop relying on a browser-side merge for production state.

## Non-negotiable evidence rule

No OpenSea, Moralis, Etherscan, Bitquery, marketplace field, file suffix or metadata string is sufficient to mark an asset as VRM. Promotion still requires validated GLB 2.0 bytes containing `VRM` or `VRMC_vrm`, plus canonical URI and whole-file hash evidence.
