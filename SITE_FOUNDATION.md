# Altiico

Altiico is the avatar identity and asset system for Hubzz.

This repository is a website-first implementation built from the supplied Altiico visual reference.

## Programs and contracts

- `apps/web` — Next.js product surfaces and browser behavior.
- `services/catalog-evidence` — reserved migration home for evidence discovery and binary validation.
- `packages/brand` — visual tokens only.
- `packages/ui` — reusable visual primitives only.
- `contracts/catalog-evidence` — language-neutral evidence snapshot schemas.
- `tests` — isolated behavior tests.
- `scripts` — focused repository checks and test tools.
- `docs` — product, architecture, migration, brand, ADR, and ledger records.

## Web feature structure

The avatar catalog uses explicit layers:

- `domain` — product data meaning.
- `ports` — consumer interfaces.
- `queries` — pure calculations.
- `adapters` — source-specific access and conversion.
- `integrations` — pure external evidence mapping.
- `runtime` — concrete adapter selection.
- `components` and `screens` — presentation.
- App Router files — framework orchestration.

Presentation does not import data sources.

Product records are readonly. Concrete source IDs stay in adapters and integrations.

The concrete catalog adapter is selected once in `features/avatar-catalog/runtime/catalog.ts`.

## Current product foundation

The repository has:

- the public Altiico homepage;
- avatar-set discovery;
- canonical avatar-set detail routes;
- canonical individual-avatar routes;
- separate product, source, API, contract, and token identities;
- a pure legacy evidence-convergence layer;
- deterministic reconciliation keys;
- language-neutral evidence wire contracts;
- a local fixture adapter behind the catalog port.

No live Hubzz or legacy `/altiico` catalog data is connected yet.

## Future `/altiico` merge

The existing `russfranky/altiico` repository is treated as an evidence producer, not UI source code.

Its research, validation, acceptance, and deterministic snapshot logic can move selectively into `services/catalog-evidence/`.

The web application will continue to consume versioned snapshot output through an adapter.

See `docs/migration/LEGACY_ALTIICO.md`.

## Unix architecture

Unix philosophy is enforced by code checks, not only documentation.

```bash
pnpm check:unix
```

This checks ADR compliance, program boundaries, dependency direction, deterministic purity, source neutrality, dependency cycles, module reachability, source-module size, shared-UI usage, and wire contracts.

The complete quality chain is:

```bash
pnpm check
```

## First commands

```bash
corepack enable
pnpm install
pnpm check
pnpm dev
```

Read `AGENTS.md` and `docs/ledger/LEDGER.md` before each implementation turn.
