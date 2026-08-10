# Recursive catalog crawler

`vrm-catalog` now has a persistent, seed-driven crawler for following NFT
metadata to validated VRM assets. It is intentionally not a blind marketplace
or storage sweep. The repository's measured discovery work shows that useful
VRM discovery starts from curated records, known contracts, explicit tokens, or
metadata already held by the catalog.

## What it does

The crawler treats discovery as a typed graph:

```text
seed
  -> EVM token
  -> token metadata document
  -> nested metadata or manifest
  -> candidate model asset
  -> partial GLB validation
  -> VRM evidence
  -> transactional catalog materialization
```

Supported task types are:

- `evm_token`: resolve ERC-721 `tokenURI(uint256)` or ERC-1155 `uri(uint256)`
- `metadata`: fetch and recursively inspect JSON, JSON-LD, IPFS, Arweave, or
  JSON data URIs
- `asset`: read only the GLB header and JSON chunk, then require the `VRM` or
  `VRMC_vrm` extension

A URL is fetched once per crawl run. Any number of collections or avatars can
bind to the same task, so shared files do not cause duplicate network work and
do not lose provenance.

## Apply the migration

The CLI applies the crawler schema automatically. It can also be applied by
hand, matching the repository's existing migration convention:

```bash
sqlite3 data/vrm_index.db < migrations/022_recursive_crawler.sql
```

The migration adds:

- `crawl_runs`: run policy, request budget, status, and timestamps
- `crawl_tasks`: persistent frontier with leases, retries, depth, and priority
- `crawl_bindings`: explicit collection and avatar associations
- `crawl_edges`: parent-child discovery relationships and JSON paths
- `crawl_observations`: immutable evidence records
- `crawl_resources`: JSON response cache and validators
- `crawl_materializations`: audit log for canonical database writes

## Run against existing catalog data

Seed concrete metadata and VRM URLs already held in SQLite:

```bash
python scripts/crawl_catalog.py run \
  --seed-existing \
  --unresolved-only
```

Include every avatar's direct model URL:

```bash
python scripts/crawl_catalog.py run \
  --seed-existing \
  --include-avatars \
  --request-budget 10000
```

The crawler skips unresolved URL templates such as `{token_id}` rather than
pretending that token `1` represents the collection.

## Run from an explicit metadata document

An identity binding is optional for research, but required for automatic
catalog materialization:

```bash
python scripts/crawl_catalog.py run \
  --metadata-url ipfs://bafy.../42.json \
  --collection-id example-collection
```

Add `--build` to run `scripts/build_catalog.py` after the evidence has been
materialized:

```bash
python scripts/crawl_catalog.py run \
  --metadata-url https://example.test/42.json \
  --collection-id example-collection \
  --build
```

## Run from an explicit EVM token

```bash
python scripts/crawl_catalog.py run \
  --evm-token ethereum:0x0123456789abcdef0123456789abcdef01234567:42 \
  --collection-id example-collection
```

The resolver tries ERC-721 and ERC-1155 metadata methods. ERC-1155 `{id}`
templates are expanded as a lowercase, 64-character hexadecimal token ID.
Shared storefront contracts remain token-scoped. The crawler never treats a
shared contract address as a collection identity.

## Seed files

A seed file can be a JSON array or newline-delimited JSON. Records are explicit
and typed:

```json
[
  {
    "kind": "metadata",
    "url": "ipfs://CID/metadata/1.json",
    "collection_id": "collection-one",
    "source": "curated-registry"
  },
  {
    "kind": "asset",
    "url": "ar://TRANSACTION/avatar.vrm",
    "collection_id": "collection-two",
    "avatar_id": "avatar-7"
  },
  {
    "kind": "evm_token",
    "chain": "base",
    "contract": "0x0123456789abcdef0123456789abcdef01234567",
    "token_id": 7,
    "collection_id": "collection-three"
  }
]
```

Run it with:

```bash
python scripts/crawl_catalog.py run --seed-file data/my-seeds.json
```

Names are not accepted as identity evidence. A `collection_id` must already
exist before materialization. This prevents fuzzy matches or marketplace aliases
from silently creating or merging canonical collection rows.

## Resume and inspect

A request budget stops expansion without losing the frontier:

```bash
python scripts/crawl_catalog.py run \
  --seed-existing \
  --request-budget 500
```

Inspect the durable state:

```bash
python scripts/crawl_catalog.py status 12
```

Resume with a larger total budget:

```bash
python scripts/crawl_catalog.py run --resume 12 --request-budget 5000
```

Explain why a collection received its evidence:

```bash
python scripts/crawl_catalog.py explain 12 example-collection
```

Materialization can be rerun independently because it is transactional and
idempotent:

```bash
python scripts/crawl_catalog.py materialize 12
```

## Recursive link rules

The JSON walker follows only strong metadata and model signals:

- `.vrm` URLs
- `model/vrm`, `application/vrm`, and `application/vnd.vrm`
- `model/gltf-binary` as a candidate that still must validate as VRM
- known fields such as `vrm_url`, `model_file_url`, `model_url`, and `asset`
- metadata fields such as `metadata_url`, `token_uri`, and `manifest_url`
- JSON or JSON-LD URLs
- embedded JSON strings
- relative links resolved against HTTP, IPFS, IPNS, or Arweave parents

Generic project websites and arbitrary HTML links are not followed. This keeps
the mechanism focused on evidence rather than turning it into a noisy web
crawler.

## Safety and bounded work

Default limits are conservative and configurable:

- recursion depth: 5
- logical request budget: 2,000
- task cap: 20,000
- attempts per task: 3
- JSON document cap: 2 MB
- GLB JSON chunk cap: 4 MB
- links per document: 500
- redirects: 5

Before each HTTP request and redirect, the loader resolves the destination and
rejects loopback, private, link-local, multicast, reserved, and unspecified IP
addresses. Credential-bearing URLs and local paths are blocked.

IPFS and Arweave identities remain canonical even when alternate HTTPS gateways
are tried. Case-sensitive CIDs and paths are never lowercased.

## Materialization rules

A fetched file and a valid VRM are separate facts:

- transport success means bytes were reachable
- GLB success means the bytes were a valid glTF binary container
- VRM success requires `extensions.VRM` or `extensions.VRMC_vrm`

Only the last state can update catalog VRM fields.

The materializer:

1. Requires an explicit binding to an existing collection.
2. Never creates a collection from a name, URL, or marketplace slug.
3. Does not replace a different URL that is already confirmed as `ok_vrm`.
4. Writes all canonical changes in one SQLite transaction.
5. Runs `PRAGMA integrity_check` before commit.
6. Stores raw embedded VRM metadata in `vrm_metadata` when that table exists.
7. Updates `avatar_vrm` and avatar reachability for explicit avatar bindings.
8. Records field-level old and new values in `crawl_materializations`.

## Tests

The crawler tests are entirely offline:

```bash
python -m pytest tests/test_recursive_crawler.py -q
```

They cover cyclic documents, request budgets, recursion depth, shared assets,
multi-collection bindings, explicit identity gates, transactional
materialization, SSRF blocking, IPFS case preservation, data URIs, partial GLB
validation, ERC-1155 templates, and lease recovery.
