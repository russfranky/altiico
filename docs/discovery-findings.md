# Discovery: what works, what doesn't

## Historical broad sweeps, measured 2026-08-10

Six independent attempts tried to discover VRM collections beyond the catalog's
then-current 74 rows. All returned **zero new collections**. These results are
kept so the loop does not repeat exhausted searches.

| # | Vector | Scope tested | Result |
|---|---|---|---|
| 1 | Re-scan OpenSea candidate backlog via stored `metadata_url` | 168 candidates | 0: 133 no VRM pointer, 35 dead metadata URL |
| 2 | Re-scan the same backlog via fresh on-chain `tokenURI` | 147 candidates | 0: 75 no pointer, 56 no tokenURI |
| 3 | Arweave: enumerate the known VRM uploader's other files | 100 uploads | 0: all 100 already ours, the 300 100Avatars |
| 4 | Arweave: ArDrive `octet-stream` sweep, any owner | 100 recent + 45 validated | 0 |
| 5 | Arweave: `Content-Type` that names VRM | 29 `application/vrm` txs | 0: all are 2 KB PNGs with magic `0x474E5089`, mislabeled by one uploader |
| 6 | OpenSea `/collections` firehose, VRM keyword filter | 2,000 collections / 20 pages | 0 keyword hits; the index is dominated by spam with empty descriptions |

## Why the storage-layer approach fails

VRM files are uploaded as `application/octet-stream`, verified on the 100Avatars
ArDrive uploads with `App-Name: ArDrive-App` and
`Content-Type: application/octet-stream`. Nothing in the public tag space marks
them as VRM. The one content type that claims to, `application/vrm`, is attached
to mislabeled PNGs. A VRM is identifiable only by fetching its bytes and reading
the GLB header and JSON extension block. That works as a validator, not a search
filter.

## What has actually worked

Every useful result in this catalog came from one of four places:

1. **Curated registries**: Open Source Avatars,
   awesome-3D-avatar-collections, and the VIPE mirror.
2. **Known-contract metadata**: on-chain `tokenURI` or `uri` resolution for an
   explicit contract and token.
3. **Data already held**: the `avatars.model_file_url` inventory recovered
   collections that broader crawl paths had marked `no_url`.
4. **Direct documented metadata**: a registry-provided token metadata URL can
   expose a VRM even when a marketplace or low token-number sample misses it.

All four are contract-driven, evidence-driven, or curation-driven. None is an
untargeted storage or marketplace sweep.

## Measured recursive-crawler gain, 2026-08-11 UTC

The first production recursive crawl followed the documented Chuddies token 127
metadata and validated:

- Ethereum contract: `0x6b67b34dfded7cf3b32cab94045aa82da2cc4bd9`
- Metadata: `ipfs://bafybeiebycjasqhzuomax77otu7koswj5p4awgmw3hrgjk2vh4xiriv5a4/127`
- VRM: `ipfs://bafybeiaplpkifduvx7ma7d2x7zrhdszhubf7lj3jmb5wxujkxedxxpziiq/127.vrm`
- Validation: VRM 0.x, 449,908 bytes

This did not add a duplicate collection row. It converted the existing Chuddies
lead into a contract-associated, binary-validated, stageable set. The useful
catalog metrics increased by one validated collection, one validated asset, and
one verified contract association.

## Curated registry freshness, verified 2026-08-10 EDT

The two high-signal upstream registries were checked before starting another
discovery round:

| Registry | Upstream `main` | Catalog cached commit | Result |
|---|---|---|---|
| awesome-3D-avatar-collections | `efbe658aaa0a465266bf9e2be297d4865f778247` | `efbe658aaa0a465266bf9e2be297d4865f778247` | Current; no new upstream rows |
| Open Source Avatars | `0f9a1b2fd99894736563d55b2c9dc9125700d081` | `0f9a1b2fd99894736563d55b2c9dc9125700d081` | Current; no new upstream rows |

Do not spend another pass refreshing these registries until either upstream head
changes. Current effort should focus on binary-validating held avatar URLs,
retrying documented metadata paths, and resolving contracts for otherwise strong
leads.

## Measured Moralis candidate validation gain, 2026-08-12 UTC

A bounded byte-validation pass consumed concrete `.vrm` and `.glb` URLs already
surfaced by Moralis model discovery. It skipped collections that were already
stageable and used the same full GLB 2.0 + `VRM` / `VRMC_vrm` binary gate as the
recursive crawler.

Measured result:

- 127 unique candidate URLs validated from 280 candidate bindings
- 25 complete binary VRMs, all belonging to the existing `dickbuttverse` row
- 101 valid GLB files correctly retained as non-VRM
- 1 transport failure
- 27,285,868 bytes of validated VRM content
- 25 whole-file SHA-256 proofs stored without inventing avatar inventory
- DickButtVerse moved from deferred to `preview_ready`
- Hubzz staging increased from 13 to 14 sets
- `no_binary_validated_vrm` deferred sets decreased from 55 to 54

DickButtVerse resolved by its existing Ethereum identity, contract
`0xd47d8672e45a7204057baaa3622a3fa276d651e3`. The bounded sample is not treated
as a complete collection inventory: one validated sample is staged while all 25
binary proofs remain available as evidence for later inventory enumeration.

This validates a useful operating distinction: indexers can be high-value lead
generators when their concrete model URLs are passed through the catalog's byte
validator. Indexer model signals themselves remain insufficient proof.

## Operating conclusion

The population of VRM-bearing NFT collections is small and largely curated. The
catalog already covers most known candidates. Further expansion should proceed
in this order:

1. Binary-validate every concrete avatar URL already indexed.
2. Revisit documented metadata URLs with known VRM fields.
3. Resolve explicit contracts and sample real token IDs.
4. Use a contract indexer only when a new provider or key adds genuine coverage.
5. Avoid repeating blind storage scans and marketplace keyword firehoses.

For Hubzz staging, improving evidence and inventory completeness now has higher
expected value than repeating broad discovery methods that have already returned
zero.
