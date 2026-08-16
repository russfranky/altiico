# Altiico Catalog

[![CI](https://github.com/russfranky/altiico/actions/workflows/ci.yml/badge.svg)](https://github.com/russfranky/altiico/actions/workflows/ci.yml)
[![CodeQL](https://github.com/russfranky/altiico/actions/workflows/codeql.yml/badge.svg)](https://github.com/russfranky/altiico/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](.python-version)

Altiico Catalog is an evidence-backed discovery and validation pipeline for NFT and on-chain avatar collections. It records collection identity, provenance, file access, license signals, and exhaustive avatar inventories where evidence supports them. Accepted files are validated from their binary contents rather than inferred from filenames or metadata strings.

**Public catalog:** <https://www.altii.co/>

> **Project maturity: alpha.** The software and data model are usable, but the catalog is intentionally fail-closed and many collections still require research. A collection appearing in the catalog does not mean it has passed the acceptance gate, is licensed for reuse, or is published by Hubzz.

## What this repository owns

This repository is the **Altiico Catalog pipeline and research interface**. It:

- discovers candidate avatar collections from public registries, marketplaces, chain data, project metadata, GitHub, IPFS, Arweave, and direct asset URLs;
- preserves source observations and conflicts instead of silently replacing them;
- validates GLB 2.0 files and requires `VRM` or `VRMC_vrm` for a VRM claim;
- accepts rigged GLB and evidence-backed rigged FBX only through explicit validation lanes;
- produces deterministic SQLite and JSON snapshots;
- exports conservative, unlisted staging candidates for Hubzz;
- deploys a static, read-only evidence catalog.

It does **not** optimize avatars, grant usage rights, publish Hubzz collections, replace Hubzz moderation, or treat an unknown field as a positive claim. See [SCOPE.md](SCOPE.md) for the authoritative boundary.

## Trust model

The catalog follows four rules:

1. **Identity is exact.** Contract, chain, token, marketplace, and internal row identities remain distinct.
2. **Files are inspected.** A URL, extension, marketplace field, or metadata string is not binary proof.
3. **Unknown stays unknown.** Missing licensing, access, or inventory evidence never becomes open, public, or complete by default.
4. **Generated artifacts move together.** The database, exports, probes, and public payload share one deterministic snapshot identity.

## Current status

The source of truth is generated, not hand-maintained:

- `data/catalog_acceptance.json` records passing and failing collections with reason codes.
- `static/data/hubzz-prealpha-staging.json` separates stageable and deferred Hubzz candidates.
- `static/data/build-info.json` identifies the deployed public snapshot.

Print the current status without relying on stale README numbers:

```bash
python scripts/project_status.py
python scripts/project_status.py --json
```

## Quick start

### Prerequisites

- Python 3.11
- SQLite 3
- Node.js for JavaScript syntax checks and browser-focused tests
- API credentials only for live enrichment jobs

### Set up the environment

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The equivalent shortcut is:

```bash
make bootstrap
```

### Verify the repository

```bash
make verify
make test
```

`make verify` runs deterministic repository checks that do not require third-party credentials. `make test` runs the full committed test suite.

### Run the public catalog locally

```bash
make serve
```

Then open <http://localhost:8000/>.

## Common commands

```bash
make help          # show supported commands
make status        # print catalog and staging status
make verify        # repository invariants, Python compile, and JS syntax
make test          # full pytest suite
make build         # rebuild the public catalog from the committed database
make acceptance    # regenerate and enforce the avatar acceptance gate
make serve         # serve static/ on localhost:8000
```

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for credentials, generated artifacts, and research workflow details.

## Pipeline

```text
public discovery sources
        |
        v
per-collection research shards
        |
        v
materialize SQLite and normalized research store
        |
        v
export inventories and probe every claimed asset
        |
        v
audit completeness and enforce acceptance
        |
        v
snapshot-pinned public catalog and Hubzz staging bundle
```

The standard unit of work is one research shard in `data/catalog_research.d/`. A high-quality change enumerates the relevant asset lane, records evidence for every required field, probes every claimed file, regenerates affected artifacts, and proves that the acceptance result changed for the right reason.

## Repository layout

```text
.github/                   contribution templates, CI, security, automation
config/                    cache and license normalization policy
data/                      SQLite index, evidence, probes, acceptance reports
data/catalog_research.d/   per-collection research shards
scripts/                   discovery, materialization, export, probe, audit tools
scripts/crawler/           shared crawl and persistence primitives
static/                    public catalog source and generated deployment data
static/data/               snapshot-pinned public payloads and staging exports
tests/                     Python and browser-focused verification
docs/                      architecture, development, integration, release notes
```

## Architecture and product boundary

- [Architecture](docs/ARCHITECTURE.md)
- [Development guide](docs/DEVELOPMENT.md)
- [Hubzz Altiico integration direction](docs/HUBZZ_ALTIICO_INTEGRATION.md)
- [Roadmap](ROADMAP.md)
- [Release process](docs/RELEASING.md)

The downstream Hubzz Altiico application is a separate product surface. This repository remains the evidence and staging authority until an explicit backend ingestion path replaces browser-side or manual coupling.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. Contributions must preserve provenance, exact identity binding, fail-closed semantics, and deterministic generated outputs.

Use the issue templates for bugs and feature proposals. Security vulnerabilities must follow [SECURITY.md](SECURITY.md), not a public issue.

## Versioning

The project is pre-1.0. Schema changes, acceptance semantics, and generated artifact contracts may still evolve. Releases follow Semantic Versioning where practical, with breaking pre-1.0 changes called out explicitly in [CHANGELOG.md](CHANGELOG.md).

## Data, attribution, and legal use

The MIT license covers repository code. Catalog data is attribution-carrying research output assembled from third-party sources. A source's own license and terms continue to govern its content. Verify rights before downloading, modifying, redistributing, or publishing any avatar.

See [CREDITS.md](CREDITS.md) for source attribution and [LICENSE](LICENSE) for the code license.
