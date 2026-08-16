# Contributing to Altiico Catalog

Thank you for improving the catalog, pipeline, or public research interface. The project values evidence quality over raw collection count.

## Before you start

Please read:

- [README.md](README.md) for the project boundary and trust model
- [SCOPE.md](SCOPE.md) for authoritative scope decisions
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for data flow and invariants
- [SECURITY.md](SECURITY.md) before reporting a vulnerability

Search existing issues before opening a new one. Use a discussion in an issue when a proposed change would alter acceptance semantics, collection identity, generated schemas, or the Hubzz staging contract.

## Development setup

Altiico Catalog targets Python 3.11.

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
make verify
```

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for optional API credentials and live enrichment jobs.

## Contribution types

### Research and catalog data

Use one shard in `data/catalog_research.d/` per collection. A complete research contribution should:

1. bind evidence to the exact collection identity;
2. resolve each required field with a sourced value or an explicit evidence-backed resolution state;
3. enumerate the full relevant avatar lane when claiming inventory completeness;
4. probe every claimed file through the appropriate binary validation path;
5. preserve conflicting observations and timestamps;
6. regenerate every affected snapshot-pinned artifact;
7. explain the acceptance result before and after the change.

Do not copy a file claim between related projects, contracts, marketplace listings, or similarly named collections without explicit identity evidence.

### Pipeline code

Keep discovery, materialization, probing, auditing, and enforcement separate. New source adapters should fail closed, use bounded requests, preserve raw observations, and expose errors rather than silently returning successful empty data.

### Public catalog

The public interface is a research surface. Keep operator workflow, Hubzz staging vocabulary, unpublished readiness state, and private credentials out of the browser bundle.

## Generated files

Many JSON files and the SQLite index are committed intentionally. Do not hand-edit generated output. Change the source data or generator, rebuild, and commit the coherent result.

Before committing generated artifacts:

```bash
make verify
python scripts/verify_catalog_consistency.py
```

A generated change should carry one snapshot identity across the database and exports.

## Tests and checks

Run the narrowest relevant tests while developing, then the full checks before opening a pull request:

```bash
make verify
make test
```

Changes to browser code should also pass the existing UX and performance checks. Changes to acceptance logic should include focused tests for both passing and failing cases.

## Style

- Target Python 3.11.
- Prefer standard-library solutions in core validation paths when practical.
- Keep network access behind explicit functions and timeouts.
- Use precise names for collection, contract, token, API row, and source identity.
- Do not weaken a gate merely to increase a metric.
- Keep secrets and local credential files out of the repository.

## Pull requests

Create a focused branch and use the pull request template. The description must cover:

- what changed;
- why the change is needed;
- the data or user impact;
- the validation performed;
- generated artifacts and snapshot changes;
- known limitations or follow-up work.

Small, coherent pull requests are easier to verify than broad mixes of research, UI, schema, and pipeline changes.

## Commit messages

Use an imperative, specific subject. Examples:

- `Document public file access for Example Collection`
- `Reject cross-contract metadata bindings`
- `Add deterministic repository verification`

## Licensing and provenance

By contributing, you confirm that you have the right to submit the code and evidence. Preserve attribution for third-party data. Do not upload avatar binaries or copyrighted media unless the repository has a documented right and reason to carry them.
