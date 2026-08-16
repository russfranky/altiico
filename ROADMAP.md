# Altiico Catalog roadmap

This roadmap describes direction, not a delivery commitment. Evidence quality and identity correctness take priority over collection count.

## Now

- Establish repository governance, security policy, deterministic CI, dependency automation, and release discipline.
- Enable protected `main` settings with required CI and CodeQL checks, review enforcement, automatic head-branch cleanup, and private vulnerability reporting.
- Make project maturity, product boundaries, and current acceptance status visible.
- Resolve the CyberBrokers and Genesis Mechs identity binding tracked in issue #24.
- Continue promoting collections one research shard at a time through the strict acceptance gate.
- Eliminate remaining legacy `vrm-catalog` and `superyeti` product naming from maintained source surfaces without breaking compatibility.

## Next

- Publish a versioned `0.1.x` schema and artifact contract for the public catalog and Hubzz staging bundle.
- Add a credential-free fixture pipeline that rebuilds a representative snapshot end to end in CI.
- Document every external source adapter, rate limit, cache policy, and failure mode.
- Raise accepted coverage while keeping exhaustive inventory and rights evidence requirements unchanged.
- Add machine-readable provenance links from public collection records to normalized evidence summaries.
- Define and test migration rules for chain, contract, token, and internal row identities.

## Later

- Move approved staging ingestion into the Hubzz backend rather than coupling production state to the browser.
- Expose catalog evidence in Hubzz Altiico while protecting stronger production identity fields from overwrite.
- Retire the standalone public catalog only after the downstream product reaches evidence, search, profile, and viewer parity.
- Add signed release manifests and stronger supply-chain provenance for published snapshots.

## Non-goals

- weakening acceptance rules to improve headline metrics;
- treating unknown licensing as permission;
- publishing or listing Hubzz sets automatically;
- using marketplace names as canonical identity;
- replacing deterministic evidence snapshots with opaque mutable application state.
