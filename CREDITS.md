# Credits & Attribution

This catalog is built on work published by others. Everything below is used with
attribution; where a source's own terms are stricter than ours, theirs govern.

## Data sources

### Open Source Avatars — ToxSam
- Repo: https://github.com/toxsam/open-source-avatars
- Site: https://www.opensourceavatars.com
- Maintainer: **ToxSam** ([@toxsam](https://github.com/toxsam))

**What we use:** the registry `data/projects.json` and the per-collection avatar
files under `data/avatars/`. These supply **4,274 individual avatar records** in
this catalog — names, thumbnails, and the direct `model_file_url` VRM links that
made the following collections resolvable: 100Avatars R1/R2/R3, VIPE Heroes
Genesis, Grifters Squaddies, ToxSam, Xmas Chibis, Halloween Rising,
NeonGlitch86.

**Importer:** `sources/opensourceavatars.py` (records the upstream commit SHA
with every import, so any record can be traced back to the exact source state).

The avatars themselves are published by their creators under their own licenses
(largely CC0, some CC-BY) — see each collection's license field. ToxSam's
registry curates and hosts the index, not the underlying IP.

### awesome-3D-avatar-collections — itsmetamike
- Repo: https://github.com/itsmetamike/awesome-3D-avatar-collections
- Maintainer: **Mike** ([@itsmetamike](https://github.com/itsmetamike))

**What we use:** the curated table of tokenized VRM avatar collections —
creator links, contract addresses, sample metadata URLs, and (most valuable) the
**"Metadata Param" column**, which documents *where inside each collection's
token metadata the VRM file is referenced* (e.g. `vrm_url`, `asset`, `files`).
That column is a hand-researched mapping that would otherwise take a scan of
every contract to reconstruct.

**Importer:** `sources/awesome_3d_avatar_collections.py`.

### VRM specification — VRM Consortium / vrm-c
- https://github.com/vrm-c/vrm-specification — the 0.x and VRMC_vrm-1.0 schemas
  behind our metadata extractor and license normalization
  (`docs/vrm-ecosystem.md` cites the exact schema files).

### three-vrm — pixiv
- https://github.com/pixiv/three-vrm (MIT) — powers the in-browser VRM viewer
  (`VRMLoaderPlugin`, `VRMUtils`), loaded from jsDelivr alongside
  [three.js](https://github.com/mrdoob/three.js) (MIT).

### Other services
- **OpenSea API v2** — collection metadata, stats, and token sampling.
- **Public RPC endpoints** (publicnode, Base, Polygon, Optimism, Arbitrum,
  Shape) — on-chain `tokenURI` / `totalSupply` reads, used to verify claims
  rather than trust them.
- **IPFS gateways** (ipfs.io, dweb.link, Cloudflare, Pinata) and **Arweave** —
  asset retrieval and reachability checks.
- **Wayback Machine** — recovering metadata for dead project sites.

## How to credit this catalog

If you use this data, please credit the upstream sources above — especially
ToxSam and itsmetamike, whose curation this catalog depends on.

## Corrections

If you maintain one of these sources and want attribution changed, an entry
removed, or a license corrected, open an issue — we will fix it promptly.
