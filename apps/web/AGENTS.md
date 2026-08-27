# Altiico project rules

Before each turn, read the ledger, product documents, brand guardrails, component language, asset inventory, and relevant ADRs.

Before catalog or adapter changes, also read `docs/migration/LEGACY_ALTIICO.md`, `docs/product/DATA_CONVERGENCE.md`, and `docs/architecture/UNIX_PHILOSOPHY.md`.

Before product-layout changes, also read `docs/brand/BENTO_LAYOUT.md`.

## Hard Unix architecture rules

Use these rules for every code change.

- `domain/` owns readonly product data meaning only. It has no concrete source identities, React, Next.js, I/O, or environment access.
- `ports/` owns narrow consumer interfaces only.
- `queries/` owns pure calculations only.
- `adapters/` owns source-specific I/O and conversion. It cannot import presentation.
- `runtime/` owns source-selection policy only.
- `integrations/legacy-altiico/` owns pure legacy evidence mapping only.
- `components/` and `screens/` own presentation only. They cannot import adapters, legacy integrations, or runtime source policy.
- App routes own framework orchestration only. Keep route pages under the enforced source-size ceiling.
- Network I/O in the web source belongs only in adapters.
- Relative imports cannot escape their top-level program source root.
- Deterministic layers cannot read environment state, browser globals, clocks, or randomness.
- Product and presentation layers cannot hard-code concrete adapter identities.
- Every source module must be reachable from an application or declared library entry point.
- Cross-language service data uses files under `contracts/`, not private application classes.
- Do not add module-level shared mutable state.
- Do not add a dependency cycle.
- Do not add a new mode to a unit when a new small unit gives the responsibility a clearer name.
- Do not promote code into `packages/` until a second real consumer exists. `check:shared` enforces this for UI exports.

Concrete adapter selection happens once in `features/avatar-catalog/runtime/catalog.ts`.

The root layout cannot import route-specific styles.

The browser consumes evidence. It does not own crawlers, blockchain indexing, secrets, binary VRM validation, or canonical research state.

If `/altiico` moves into this monorepo, its research and validation responsibilities belong under `services/catalog-evidence/`.

## Required checks

Run `pnpm check:unix` for architecture compliance.

That command enforces ADR review, local program boundaries, layer direction, deterministic purity, source neutrality, import cycles, module reachability, module sizes, shared-UI usage, and wire contracts.

Run the complete `pnpm check` before a deployable checkpoint.

If package installation is unavailable, run every source-level check that does not require installed framework dependencies and record the blocked checks in the ledger.

## Brand rule

The supplied Altiico reference remains authoritative.

The bento reference changes composition only. It does not change the Altiico palette or visual language.

`PolygonalMind/100Avatars` is approved for future illustration imports. Prefer Lalobot as the recurring robot anchor when imported.

## ADR rule

Every material architecture decision must include `## Unix philosophy check`.

The review must name single responsibility, composability, data boundary, failure behavior, and simplicity.
