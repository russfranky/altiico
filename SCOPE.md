# SCOPE: altiico (formerly vrm-catalog)

Updated 2026-08-11 after the owner explicitly asked for the catalog to support
staging avatar sets in Hubzz pre-alpha. This supersedes the earlier statement
that Hubzz staging was out of scope. The public catalog remains a research tool;
the staging bundle is a separate machine-readable downstream artifact.

## Core problem

A researcher needs to find VRM avatar sets and answer three questions fast:
**what is this, can I see it, does the file actually work.** The same evidence
must be organized well enough to hand technically valid source avatars to Hubzz
pre-alpha without pretending they are already optimized or published.

## Success criteria

1. The catalog grows through defensible NFT-to-VRM evidence.
2. Every accepted VRM passes binary validation, not URL or keyword heuristics.
3. A generated Hubzz staging bundle separates stageable sets from deferred sets.
4. Every staged set has at least one validated source avatar and a canonical
   `status: staged`, `listed: false` set record.
5. Every deferred set has explicit blockers that can drive the next research pass.
6. Unsupported chains, unknown licenses, and partial inventories are never
   silently coerced into stronger claims.

## In scope

- **Collections**: art, name, description, license, supply, links, VRM status,
  and rolled-up avatar reachability.
- **VRM viewer**: loads a validated VRM in the browser and shows embedded metadata.
- **Search and plain-language filters** for the research catalog.
- **Reachability and binary VRM validation** at collection and avatar level.
- **Targeted recursive discovery** from curated registries, known contracts,
  token metadata, and explicit leads. Blind marketplace or storage sweeps remain
  excluded unless a genuinely new intake source exists.
- **Hubzz pre-alpha staging export** as a backend artifact only:
  - canonical staged set records matching the pre-alpha schema
  - source-avatar sidecars containing original validated VRM URLs
  - coverage, license-review, and chain-mapping warnings
  - an explicit deferred queue with machine-readable reasons
- **A guarded Hubzz importer** that dry-runs by default and may merge staged set
  rows into the Hubzz registry only with an explicit live flag and credentials.

## Explicitly out of scope

- Publishing a set to Hubzz or claiming optimization is complete.
- Uploading external VRMs as canonical served assets without the Hubzz optimizer.
- Setting `listed: true` from catalog evidence.
- Treating unknown licensing as permission.
- Coercing unsupported ownership chains to `null` merely to pass a schema.
- Replacing Hubzz's canonical avatar database, optimizer, moderation, or R2
  manifest generator.
- Adding staging state, readiness scores, or Hubzz pipeline vocabulary to the
  public catalog interface.

## Non-negotiables

- The catalog UI stays focused on research. Staging output is a separate artifact.
- A reachable GLB without `VRM` or `VRMC_vrm` is not a VRM.
- A shared storefront contract is not a collection identity without token or slug evidence.
- Names may suggest a match but never authorize an automatic merge by themselves.
- Unknown means unknown. It never becomes open, green, ungated, or published.
- Hubzz owns the canonical served URL. Catalog URLs are original-source provenance.
- Every staging run reports before/after counts and exact evidence paths.
- Verify the generated artifacts and downstream schema, not only the Python code.

## Historical cuts that remain correct

The 2026-08-10 UI audit removed readiness badges, Hubzz presence badges,
bookmarks, notes, pipeline tiers, the OpenSea candidate view, the avatars browser,
and duplicate table views. Those cuts remain correct. The owner has now requested
a staging **artifact**, not a staging dashboard inside the research catalog.

## Current handoff artifacts

- `static/data/avatar-manifest-v1.json`: legacy resolver manifest.
- `static/data/avatars-registry.json`: broad catalog projection, not a staging gate.
- `static/data/hubzz-prealpha-staging.json`: conservative stageable/deferred bundle.
- `static/data/hubzz-prealpha-source/*.json`: original validated source-avatar lists.
- `docs/hubzz-prealpha-staging.md`: human-readable staging summary.
- `data/live_discovery_report.json`: measured recursive discovery evidence.
