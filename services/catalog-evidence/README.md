# Catalog evidence service boundary

This directory is reserved for a later selective migration of the existing Altiico research and VRM-validation pipeline.

It will own discovery, source consensus, binary validation, acceptance gates, deterministic snapshots, and provenance.

It will not own public product routes, UI state, or Hubzz publication state.

The web application consumes serialized snapshot output through `AvatarCatalogPort` and schemas under `contracts/catalog-evidence/`.
