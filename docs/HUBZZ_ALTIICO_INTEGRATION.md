# Hubzz Altiico integration direction

Status: planning direction, not an implementation commitment.

## Naming

- **Altiico Catalog** means this repository, `russfranky/altiico`: the evidence pipeline, deterministic catalog snapshots, static research interface, and Hubzz staging exporter.
- **Hubzz Altiico** means the separate public and operator application that reads Hubzz production state.
- **Hubzz backend** means the canonical ingest, optimization, moderation, storage, and publication services.

The former repository name `vrm-catalog` appears only in historical context and should not be used for new interfaces or generated provenance.

## Goal

Make the useful evidence-backed discovery capabilities of Altiico Catalog available through Hubzz Altiico so users experience one coherent avatar product, while preserving strict validation and source provenance.

The browser must not become responsible for GitHub Actions, API secrets, blockchain indexing, canonical binary validation, or direct publication.

## Current responsibilities

### Altiico Catalog

- discovers avatar collections from public marketplace, chain, registry, project, GitHub, and storage surfaces;
- preserves observations, timestamps, conflicts, and exact identity bindings;
- validates GLB 2.0 bytes and requires `VRM` or `VRMC_vrm` for a VRM claim;
- builds exhaustive inventories where evidence supports them;
- produces deterministic SQLite and JSON evidence snapshots;
- exports conservative, unlisted Hubzz staging candidates and a deferred queue;
- deploys a static read-only research catalog.

### Hubzz Altiico

- public browse, search, profile, and inventory UI;
- operator preview, rig QA, thumbnail, and manifest workflows;
- reads canonical collection and avatar state from Hubzz services;
- may augment production records with catalog evidence;
- does not become the canonical discovery crawler or publication authority.

### Hubzz backend

- accepts approved imports through a guarded, auditable path;
- optimizes and stores canonical served assets;
- owns moderation, publication, listing, and production identity;
- protects published records from destructive evidence refreshes.

## Recommended architecture

```text
external discovery sources
        |
        v
Altiico Catalog evidence pipeline
        |
        v
binary validation, identity audit, and source consensus
        |
        v
versioned staging artifact and deferred queue
        |
        v
reviewed Hubzz backend importer
        |
        v
canonical Hubzz collection and avatar state
        |
        v
Hubzz Altiico browse, profile, search, and QA
```

## Phase 1: read-only evidence adapter

Add a read-only adapter in Hubzz Altiico that consumes a pinned Altiico Catalog artifact behind the existing service boundary.

Useful evidence fields include:

- exact collection identity, chain, and contract;
- separate API row ID and on-chain token ID;
- banner, PFP, and source media provenance;
- validated source file URL, format, spec, byte length, and hash;
- inventory coverage and validation scope;
- license and access classification with confidence and reason codes;
- evidence freshness and unresolved conflicts.

Hubzz production records remain authoritative. Catalog-only records may appear as research or discovery candidates without implying publication.

## Phase 2: shared conceptual model

Align catalog staging and Hubzz API concepts without forcing one storage system onto both products.

Collection concepts:

- stable catalog and production identifiers;
- chain and contract;
- name and description;
- banner and PFP;
- source and verification state;
- usage and access policy;
- stage and publish state;
- collection traits and statistics where coverage supports them.

Avatar concepts:

- production ID and on-chain token ID as separate values;
- original source and optimized served URLs;
- binary validation format, spec, byte length, and hash;
- thumbnails and normalized traits;
- source provenance and observation time;
- marketplace and purchase links;
- license and content metadata.

Never conflate marketplace, contract, token, source API, catalog, or production identities.

## Phase 3: guarded backend import

The durable production path is a backend importer that consumes a versioned staging artifact.

Required behavior:

- dry-run by default;
- explicit authorization for a live import;
- no automatic listing or publication;
- validated source file evidence required;
- conflicts and incomplete coverage remain visible;
- existing published records are protected from destructive overwrite;
- provenance, observation times, and source hashes survive import;
- before and after counts and exact changed identities are reported.

## Phase 4: retire duplicate public surfaces

The standalone catalog UI should be retired only after Hubzz Altiico reaches parity for evidence-backed browse, search, profile, and viewer behavior. At that point this repository can remain a pipeline, artifact, and diagnostic surface.

## Storage direction

The catalog's versioned SQLite and JSON model is appropriate for deterministic evidence snapshots. Large public binary and media assets may use R2 or another CDN-backed object store.

Live application state belongs in Hubzz services. A realtime database may be appropriate for favorites, conversations, sessions, presence, mutable operator workflows, or live ownership ingestion. It should not make evidence provenance opaque or replace exportable deterministic snapshots.

## First implementation slice

1. Define catalog adapter types in Hubzz Altiico.
2. Fetch one pinned, versioned catalog artifact read-only.
3. Join only on exact chain, contract, and token identity.
4. Expose verification, coverage, and source state on profiles.
5. Add tests proving catalog evidence cannot overwrite stronger production identity fields.
6. Move approved ingestion to the backend before treating the browser merge as production state.

## Non-negotiable evidence rule

No marketplace field, API response, filename, extension, URL pattern, or metadata string is sufficient to mark an asset as VRM. Promotion requires validated GLB 2.0 bytes containing `VRM` or `VRMC_vrm`, plus canonical URI and whole-file evidence.
