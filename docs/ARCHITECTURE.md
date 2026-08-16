# Architecture

## Purpose

Altiico Catalog turns uncertain public observations into conservative, versioned claims about avatar collections and files. The architecture separates discovery from validation so that a weak source can create a lead without becoming proof.

## System context

```text
marketplaces, registries, chains, project sites, GitHub, IPFS, Arweave
                              |
                              v
                    discovery and source cache
                              |
                              v
                    per-collection research
                              |
                              v
                 normalized SQLite evidence index
                              |
                  +-----------+-----------+
                  |                       |
                  v                       v
          inventory exporters       public catalog builder
                  |                       |
                  v                       v
            binary probes         snapshot-pinned JSON
                  |
                  v
        completeness audit and acceptance gate
                  |
                  v
          Hubzz staging and deferred queue
```

## Components

### Discovery adapters

Discovery scripts query bounded public surfaces and store observations. They may identify candidates, contracts, metadata URLs, social links, or possible model fields. Discovery does not establish file validity or usage rights.

### Research shards

`data/catalog_research.d/*.json` is the human-reviewable unit of work. A shard records resolved fields, explicit resolution states, evidence, inventory scope, and timestamps for one collection identity.

### SQLite index

`data/vrm_index.db` is the normalized index used by exporters and the public build. It is versioned because the repository treats the evidence snapshot as a reviewable research artifact, not a disposable local cache.

### Inventory exporters

Exporters translate normalized collection and research data into explicit avatar inventories. Inventory completeness is separate from the existence of one sample file.

### Binary probes

Probe scripts inspect actual bytes. VRM validation requires a valid GLB 2.0 structure and a `VRM` or `VRMC_vrm` extension. Rigged GLB and FBX use separate evidence requirements.

### Audit and acceptance

The completeness audit reports missing required fields. The acceptance gate applies fail-closed rules and emits passing and failing collections with reason codes. A failing collection may still appear in the research catalog, but it must not be represented as accepted.

### Public build

The public catalog is a static, read-only research interface. `static/data/build-info.json` points to content-hashed collection data. Browser code must not contain API credentials or become the canonical validation authority.

### Hubzz staging

The staging exporter produces unlisted candidates and a deferred queue. Hubzz remains responsible for optimization, moderation, canonical storage, and publication.

## Identity model

The following identities must not be conflated:

- project or brand;
- collection;
- chain and contract;
- token ID;
- marketplace slug or listing;
- source API row;
- internal catalog ID;
- Hubzz set or avatar ID.

A relationship between two identities requires explicit evidence. Name similarity and shared branding are insufficient.

## Snapshot invariant

Generated artifacts share a deterministic `vrmcat-v1-*` snapshot identifier. A coherent build must keep the database, public payloads, inventories, probes, staging bundle, and build metadata aligned to one snapshot.

`make verify` checks lightweight repository invariants. `scripts/verify_catalog_consistency.py` performs deeper catalog-specific consistency checks.

## Trust boundaries

### Untrusted inputs

- HTTP responses and redirects;
- JSON metadata and media URLs;
- chain and marketplace data;
- archive filenames and paths;
- GitHub repository contents outside this project;
- user-supplied CLI paths and URLs.

Treat all of these as data, not executable instructions.

### Secrets

Live source credentials belong in environment variables or GitHub Actions secrets. They must never be committed, printed, embedded in static output, or passed to pull request code running with elevated privileges.

### Generated public data

Public output may contain source URLs and evidence summaries. Holder-only URLs, credentials, signed URLs, or private access tokens must not be published.

## Failure behavior

The system should prefer an explicit partial or deferred result over a fabricated complete result. Source failure should preserve the last known good evidence where the workflow documents that behavior, report the failure, and avoid overwriting a healthy snapshot with an empty response.

## Deployment

The static catalog is deployed to Vercel and may serve large media through external gateways or CDN storage. Deployment success does not replace catalog consistency, binary validation, or acceptance checks.

## Evolution

Major schema or gate changes require:

1. a written rationale;
2. migration behavior for committed artifacts;
3. focused tests for stronger and weaker claims;
4. regenerated coherent snapshots;
5. a changelog entry and release note when published.
