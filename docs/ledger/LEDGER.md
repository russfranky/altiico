# Altiico build ledger

## Current state
- Phase: Unix-structured public product foundation.
- Branch: `site-foundation` from `russfranky/altiico/main`.
- Legacy evidence pipeline: preserved at repository root.
- Web product: `apps/web`.
- Runtime catalog source: local fixture adapter.
- Live evidence adapter: not connected.

## Goals
- Preserve the supplied Altiico brand system.
- Keep Unix philosophy mechanically enforced.
- Build public discovery, set detail, and avatar detail on source-neutral contracts.
- Keep product identity separate from source, API, chain, contract, and token identities.
- Preserve the legacy `/altiico` research and VRM validation strengths for a later selective migration.
- Apply the approved bento composition without changing the brand palette.

## Turn log

### T-001 through T-003
Established the workspace, brand primitives, homepage narrative, accessibility baseline, and route boundaries.

### T-004
Added public avatar-set discovery behind `AvatarCatalogPort`, local fixtures, filters, and explicit route states.

### T-005
Added canonical set-detail routes and reserved `services/catalog-evidence/` for a later evidence-pipeline migration.

### T-006
Added canonical individual-avatar routes with product, source, API, contract, and token identity separation.

### T-007
Added pure legacy evidence convergence, deterministic reconciliation keys, source-neutral provenance, immutable records, wire schemas, behavior tests, and strict Unix architecture checks.

### Governance checkpoint
Unix philosophy became a hard architecture requirement. Repository checks now enforce small modules, explicit boundaries, deterministic pure layers, source neutrality, no cycles, no dead modules, no premature shared abstractions, visible failure, and language-neutral service contracts.

### Repository branch checkpoint
Created `site-foundation` from `russfranky/altiico/main`. The new web program is added beside the existing evidence pipeline. `main` remains untouched.

## Current risks
- The web app still uses local catalog fixtures.
- Full framework verification depends on package installation.
- The large design-reference PNGs are not required runtime assets and can be added later through normal Git/LFS workflow.

## Next recommended turn

`T-008 — Discovery bento composition + evidence UI pass`

Apply the approved bento layout to discovery, set detail, and avatar detail without changing stable data contracts.
