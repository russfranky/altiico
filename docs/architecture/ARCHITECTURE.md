# Architecture

This repository is a pnpm workspace with explicit program boundaries.

## Top-level programs

- `apps/web` owns HTTP routes, page composition, metadata, and browser behavior.
- `services/catalog-evidence` is the future producer for research, binary validation, and deterministic evidence snapshots.
- `packages/brand` owns visual tokens only.
- `packages/ui` owns reusable visual primitives only.
- `contracts/catalog-evidence` owns language-neutral JSON wire contracts.
- `tests` owns executable contract and pure-function tests.
- `scripts` owns focused repository checks and test compilation tools.

A physical monorepo does not remove these program boundaries.

## Avatar catalog feature layers

`apps/web/src/features/avatar-catalog` uses a fixed dependency direction.

- `domain/` owns product records and value types.
- `ports/` owns narrow consumer interfaces.
- `queries/` owns pure calculations.
- `adapters/` owns source-specific data access and conversion.
- `integrations/legacy-altiico/` owns pure mapping from legacy wire contracts.
- `runtime/` owns adapter-selection policy.
- `components/` and `screens/` own presentation only.
- App routes orchestrate framework behavior only.

## Style locality

The root layout imports global tokens, shared UI styles, and the global shell stylesheet only.

Route groups own route composition styles.

## Evidence service boundary

The future `services/catalog-evidence/` service can own discovery, provenance, binary validation, acceptance gates, and deterministic snapshot production.

The web application consumes serialized evidence artifacts through an adapter.

Cross-language contracts live in `contracts/catalog-evidence/` as JSON Schema.

## Identity precedence

Product identity stays separate from source evidence.

Legacy evidence can fill empty source identity fields and replace evidence blocks.

It cannot overwrite product IDs, public slugs, API identity, display copy, readiness, or publication state.

## Automated architecture gates

The Unix gate checks imports, boundaries, deterministic purity, source neutrality, cycles, reachability, source size, shared UI use, wire contracts, ADRs, and catalog behavior tests.
