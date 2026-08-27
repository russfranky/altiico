# ADR 0006 — Avatar-set detail route and legacy catalog seam
**Status:** Accepted

Use `/explore/avatar-sets/[slug]` as the canonical set-detail route. Reserve `services/catalog-evidence/` for a later selective migration of the legacy evidence pipeline.

## Unix philosophy check
- **Single responsibility:** Set pages present product detail; the evidence service researches and validates assets.
- **Composability:** `AvatarCatalogPort` and versioned evidence artifacts connect them.
- **Data boundary:** Canonical set contracts and deterministic snapshots cross the boundary.
- **Failure behavior:** Unsupported evidence remains visible instead of being promoted.
- **Simplicity:** Physical co-location does not merge browser and evidence responsibilities.
