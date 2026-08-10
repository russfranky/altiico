# Discovery: what works, what doesn't (measured 2026-08-10)

Five independent attempts to discover VRM collections beyond the catalog's 74.
All returned **zero** new collections. Recorded so the loop stops re-running them.

| # | Vector | Scope tested | Result |
|---|---|---|---|
| 1 | Re-scan OpenSea candidate backlog via stored `metadata_url` | 168 candidates | 0 — 133 no VRM pointer, 35 dead metadata URL |
| 2 | Re-scan the same backlog via fresh on-chain `tokenURI` | 147 candidates | 0 — 75 no pointer, 56 no tokenURI |
| 3 | Arweave: enumerate the known VRM uploader's other files | 100 uploads | 0 — all 100 already ours (the 300 100Avatars) |
| 4 | Arweave: ArDrive `octet-stream` sweep, any owner | 100 recent + 45 validated | 0 |
| 5 | Arweave: `Content-Type` that names VRM | 29 `application/vrm` txs | 0 — **all are 2 KB PNGs** (magic `0x474E5089`) mislabeled by one uploader |
| 6 | OpenSea `/collections` firehose, VRM keyword filter | 2,000 collections / 20 pages | 0 keyword hits — the index is dominated by spam with empty descriptions |

## Why the storage-layer approach fails
VRM files are uploaded as `application/octet-stream` (verified on the 100Avatars
ArDrive uploads: `App-Name: ArDrive-App`, `Content-Type: application/octet-stream`).
Nothing in the public tag space marks them as VRM, and the one content-type that
claims to (`application/vrm`) is mislabeled PNGs. A VRM is only identifiable by
**fetching its bytes and reading the GLB header** — which cannot be used as a
search filter, only as a validator.

## What has actually worked
Every collection discovered in this catalog came from one of three places:
1. **Curated registries** — Open Source Avatars, awesome-3D-avatar-collections,
   the VIPE mirror. Human curation, not crawling.
2. **On-chain `tokenURI` metadata scan of a KNOWN contract** — found MisfitPIXELS
   and both NeonGlitch86 sides.
3. **Data already held** — the `avatars` table's `model_file_url` resolved five
   collections that the crawl paths had marked `no_url`.

All three are *contract-driven or curation-driven*. None is an untargeted sweep.

## Conclusion
The population of VRM-bearing NFT collections is small, largely curated, and this
catalog already holds most of it. Further discovery needs **contract-level intake
at scale** (an indexer: Reservoir / Alchemy / Moralis — enumerate contracts, scan
each `tokenURI` for a VRM pointer), not more crawling of storage layers or
marketplace indexes.

Until such a key exists, effort is better spent converting the collections we
have into onboardable sets than searching for more.
