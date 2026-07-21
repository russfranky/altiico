# Source provenance

For each source feeding `data/vrm_index.db`, this document records what it
**proves** versus what it **asserts without proof**. The five proof axes are:

1. **NFT ownership** — does the source establish that the avatar is held as an
   NFT on a public chain (token id + contract + chain)?
2. **VRM existence** — does the source establish that a `.vrm` (or
   VRM-structured GLB) file actually exists at a resolvable URL?
3. **Metadata linkage** — does the source establish that the NFT's token
   metadata points to the VRM file (so the avatar is reachable from the
   token, not just hosted nearby)?
4. **License** — does the source contribute license terms, and at what
   confidence (embedded / collection / manual / unknown)?
5. **Marketing-only** — is the source's claim "this is a VRM NFT collection"
   a marketing claim that has not been independently verified?

A source that only asserts without proof is a **lead source**; its rows must
be re-validated by a proof source before they can be promoted to a confirmed
collection. The `tier` column on `collections` encodes the proof state:

| Tier | Meaning |
|---|---|
| A | VRM pointer present in token metadata and validated via partial-GLB extraction |
| B | VRM file exists off-chain (e.g. project website) but is not linked from token metadata |
| C | Lead only — name/description suggests 3D avatar; no VRM proof yet |
| `not_vrm` | Investigated and confirmed not VRM |
| `arweave` | Arweave-native (proof via transaction ID) |
| `infra` | Infrastructure, not an avatar collection |

## Proof sources

### `scripts/extract_vrm_meta.py` — partial-GLB VRM metadata extractor

The only source that **proves VRM existence**. It downloads the first bytes
of a GLB file, parses the JSON chunk without a full GLB parser, and confirms
the `VRM` extension is present. It also extracts VRM 0.x and VRM 1.0
metadata fields (author, license, allowed user, commercial usage, etc.).

- **NFT ownership**: does not prove. Operates on a URL, not a token.
- **VRM existence**: **proves**. The file is fetched and the VRM extension is
  verified in the binary. A 404 or non-GLB response is a negative result.
- **Metadata linkage**: does not prove. The URL must be supplied by a
  caller that already established the linkage (token metadata scanner,
  project website, or manual entry).
- **License**: contributes **embedded** license terms at the highest
  confidence level. See `docs/license-methodology.md`.
- **Marketing-only**: never. It is the verification step that converts a
  marketing claim into a proof.

### `scripts/discover_metadata_fields.py` — token-metadata VRM pointer scanner

Recursively scans a token metadata JSON object (case-insensitive) for field
names that look like VRM pointers (`vrm_url`, `vrm`, `avatar_url`, `model`,
`asset`, `files`, …) and validates each candidate URL via
`extract_vrm_meta.py`.

- **NFT ownership**: does not prove. Operates on a metadata JSON blob, not
  a token. The caller is responsible for establishing that the blob came
  from a specific token.
- **VRM existence**: **proves** when run with `--validate`. Without
  `--validate` it only lists candidate field names (a lead).
- **Metadata linkage**: **proves**. The whole point of this script is to
  establish that the NFT's metadata points to a VRM file. A validated hit
  promotes a collection from tier C to tier A.
- **License**: does not contribute. License terms come from the embedded
  VRM metadata extracted after a successful pointer hit.
- **Marketing-only**: no. This is the linkage proof step.

### `scripts/enrich_opensea.py` + `scripts/opensea_client.py` — OpenSea API v2

Fetches collection-level metadata (slug, name, description, image, supply,
floor, volume) and per-token metadata from OpenSea's API v2. Uses a TTL
cache (`source_cache` table, migration 008) and centralized rate limiting.

- **NFT ownership**: **proves**. OpenSea returns the contract address,
  chain, and token id for each asset. The shared-storefront contract
  (`0x495f…7b5e`) is special-cased — see `resolve_opensea_collections.py`.
- **VRM existence**: does not prove. OpenSea metadata may or may not
  contain a VRM pointer; this source only fetches the metadata.
- **Metadata linkage**: does not prove. It supplies the metadata blob that
  `discover_metadata_fields.py` then scans.
- **License**: contributes **collection**-level license terms at medium
  confidence (OpenSea `description` / `collection_metadata` fields). Lower
  confidence than embedded VRM metadata.
- **Marketing-only**: no. OpenSea is a primary on-chain indexer; the
  contract and token id are authoritative.

### `scripts/resolve_opensea_collections.py` — shared-storefront resolver

Disambiguates collections minted under OpenSea's shared ERC-1155 storefront
contract. The contract address alone is **not** a collection identifier; a
token id or slug is required. Uses
`data/opensea_collection_overrides.yaml` for manual overrides and the
OpenSea API for token-based resolution. Writes results to
`collection_identifiers` (migration 006) with a `resolution_source` column
(`override` / `opensea-slug` / `opensea-token` / `opensea-sweep` /
`unresolved`).

- **NFT ownership**: **proves** the collection identity for shared-storefront
  assets. Without this step, a shared-storefront contract address is
  ambiguous and must not be treated as a collection.
- **VRM existence**: does not prove.
- **Metadata linkage**: does not prove.
- **License**: does not contribute.
- **Marketing-only**: no. The `resolution_source` column records exactly
  how the collection was identified, so the decision is auditable.

### `sources/awesome_3d_avatar_collections.py` — A3AC registry importer

Imports the `itsmetamike/awesome-3D-avatar-collections` GitHub README,
recording the commit SHA for provenance. Each entry becomes a tier C
candidate (`source = 'a3ac-registry'`) unless independently promoted.

- **NFT ownership**: **asserts**. The README lists contract addresses, but
  the importer does not verify them on-chain. Treat contract addresses as
  leads until cross-checked against OpenSea or an RPC.
- **VRM existence**: does not prove. The README is a curated list; it does
  not fetch VRM files.
- **Metadata linkage**: does not prove.
- **License**: does not contribute. The README occasionally mentions
  licenses in prose, but the importer does not extract them.
- **Marketing-only**: **yes, by default**. A3AC entries are tier C leads.
  Promote to tier A only after `discover_metadata_fields.py` validates a
  VRM pointer in token metadata.

### `sources/opensourceavatars.py` — Open Source Avatars importer

Imports the `ToxSam/open-source-avatars` GitHub registry (projects.json +
per-project avatar data files), recording the commit SHA. The registry
declares CC0 licensing for its avatars.

- **NFT ownership**: **does not apply** for most entries. OSA is a CC0 VRM
  avatar registry, not an NFT collection registry. Entries that are also
  minted as NFTs are cross-referenced manually (`source = 'toxsam+curated'`).
- **VRM existence**: **proves** via the per-project avatar data files,
  which include direct VRM URLs. The importer does not re-fetch the VRM
  binary; run `extract_vrm_meta.py` for binary validation.
- **Metadata linkage**: does not apply (most OSA avatars are not NFTs).
- **License**: contributes **manual** license terms at medium confidence
  (the registry declares CC0). Lower confidence than embedded VRM
  metadata because the declaration is in the registry, not in the file.
- **Marketing-only**: no. OSA is a primary source for the avatars it
  hosts; the CC0 claim is the registry author's declaration.

### `sources/solana_metaplex.py` — Solana Metaplex scanner

Fetches Metaplex token metadata from a public Solana RPC (no API key),
decodes the metadata, and scans for VRM pointers. Rewrites IPFS/Arweave URIs
to HTTPS gateways with fallbacks.

- **NFT ownership**: **proves**. The mint address and Metaplex metadata
  account are on-chain and authoritative.
- **VRM existence**: **proves** when a VRM pointer is found and the
  gateway fetch succeeds. The scanner does not run partial-GLB extraction
  itself; pipe candidate URLs through `extract_vrm_meta.py` for binary
  validation.
- **Metadata linkage**: **proves**. The Metaplex metadata is the token's
  metadata; a VRM pointer found here is the linkage proof.
- **License**: contributes **embedded** license terms if the Metaplex
  metadata or the referenced VRM file carries them.
- **Marketing-only**: no. On-chain Metaplex metadata is authoritative.

### `sources/reservoir.py` — Reservoir EVM discovery + market data

Uses the Reservoir API to discover EVM collections whose name/description
mention VRM / 3D avatar terms, and to backfill market data (floor, volume)
for collections already in the DB.

- **NFT ownership**: **proves** for collections it returns. Reservoir
  indexes on-chain data; the contract address and chain are authoritative.
- **VRM existence**: does not prove. Name/description matches are leads
  only — a collection named "3D Avatars" may ship GLB, FBX, or nothing.
- **Metadata linkage**: does not prove. The script's `--validate` mode
  pipes candidate tokens through `discover_metadata_fields.py` to
  establish linkage; without `--validate` it is a lead source.
- **License**: does not contribute directly. License terms come from the
  token metadata that Reservoir returns, which is then processed by
  `normalize_licenses.py`.
- **Marketing-only**: **yes, by default**. Per the project methodology,
  name/description matches are leads only. A collection is only counted
  as VRM-bearing if a token-metadata VRM pointer validates via
  partial-GLB extraction. The script's docstring states this explicitly.

### `scripts/normalize_licenses.py` + `config/license-mapping.yaml` — license normalizer

Translates raw license terms from embedded VRM metadata, collection-level
fields, Creative Commons codes, and a16z "Can't Be Evil" variants into the
nine independent permission dimensions in `license_dimensions` (migration
010). Precedence: embedded > collection > manual > unknown. Unknown never
maps to green.

- **NFT ownership**: does not prove.
- **VRM existence**: does not prove.
- **Metadata linkage**: does not prove.
- **License**: **proves** the mapping from raw terms to dimensions, given
  that the raw terms themselves were proved by an upstream source. The
  confidence level (`embedded` / `collection` / `manual` / `unknown`)
  records which upstream source supplied the terms.
- **Marketing-only**: no. The mapping is mechanical and reviewable in the
  YAML file.

## Lead sources (no proof, triage only)

### `data/RESEARCH.md` — manual research notes

The original research document. Entries with `source = 'research-*'`
(`research-opensea`, `research-okx`, `research-rarible`, `research-magiceden`,
`research-daz3d`) came from this file. These are tier C leads collected
before the proof pipeline existed.

- **All five axes**: asserts only. Each `research-*` row must be re-verified
  via the proof pipeline before promotion to tier A or B.
- **Marketing-only**: **yes**. The research notes explicitly flag this:
  "name/description matches are leads only".

### `data/discovery_leads.yaml` — manual review queue

The triage queue for sources that cannot be imported mechanically: VRM
Consortium members, Hyperfy leads, VRoid Hub cross-checks, DappRadar
aggregator leads. Each entry carries a `review_state`; see the file header
for the vocabulary.

- **All five axes**: does not prove. This file is the input to a future
  proof pass, not the proof itself.
- **Marketing-only**: **yes**, by construction. A lead with
  `review_state: confirmed` has been promoted out of this file into the DB
  via a proof source.

### Manual curation (`source = 'curated'`, `'curated+verified'`)

Hand-curated entries from the original spreadsheet scrape. The
`curated+verified` variant indicates a human checked the project website
and OpenSea page; `curated` is unverified.

- **NFT ownership**: **asserts**. The contract addresses were transcribed
  by hand; treat as leads unless cross-checked.
- **VRM existence**: **asserts** for `curated+verified`, **does not prove**
  for `curated`.
- **Metadata linkage**: does not prove.
- **License**: contributes **manual** license terms at the lowest
  non-unknown confidence.
- **Marketing-only**: **yes** for `curated`; **no** for `curated+verified`
  (a human verified the avatar is VRM, but did not validate the binary).

## Proof flow

A collection moves from lead to confirmed through this chain:

```
lead source (A3AC / research / DappRadar / discovery_leads)
        │  asserts NFT ownership + maybe VRM existence
        ▼
resolve_opensea_collections.py  (shared-storefront disambiguation)
        │  proves collection identity
        ▼
enrich_opensea.py  (fetch token metadata)
        │  proves NFT ownership; supplies metadata blob
        ▼
discover_metadata_fields.py --validate  (scan metadata for VRM pointer)
        │  proves metadata linkage; emits candidate VRM URL
        ▼
extract_vrm_meta.py  (partial-GLB extraction)
        │  proves VRM existence; extracts embedded license terms
        ▼
normalize_licenses.py  (map raw terms to dimensions)
        │  proves license mapping; records confidence level
        ▼
tier A collection in vrm_index.db
```

A collection can stop at any stage and remain at the corresponding tier:

- Stops before `discover_metadata_fields.py` → tier C (lead only).
- `discover_metadata_fields.py` finds no pointer, but VRM file exists
  off-chain → tier B.
- `discover_metadata_fields.py` finds and validates a pointer → tier A.
- Investigated and no VRM found → `not_vrm`.

## Gaps and known limitations

- **URL-resolved licenses** (`resolve_url` in `normalize_licenses.py`)
  return dimensions only, not `reason_codes`. Documented in
  `tests/test_license_normalization.py`.
- **A3AC contract addresses** are not re-verified on-chain by the importer.
  A future enhancement would cross-check each address against an RPC or
  OpenSea before promoting from tier C.
- **OSA avatars** are not binary-validated by the importer. Run
  `extract_vrm_meta.py` against the imported URLs to confirm.
- **`research-*` rows** predate the proof pipeline and have not been
  systematically re-validated. They should be re-run through
  `discover_metadata_fields.py` in a future pass.
- **VRoid Hub** is policy-excluded (ToS prohibits NFT usage). It is
  recorded in `data/discovery_leads.yaml` as a cross-check source only,
  never as an import source.
