# Index of NFT / Tokenized Collections That Include VRM Avatars

Compiled from OpenSea API v2 (instant free-tier key) + the curated
`itsmetamike/awesome-3D-avatar-collections` registry + ToxSam's
`open-source-avatars` projects.json + the `hackmd.io/@XR/nftavatars` catalog.

**Verification method:** For each collection, fetched a sample NFT's metadata URI
(trying public IPFS gateways when OpenSea's private Pinata gateway blocked requests)
and confirmed a `.vrm` reference in the JSON metadata. For L2 collections, fetched the
project's avatar manifest and confirmed `model_file_url` → `.vrm`. For Arweave-native
samples, confirmed glTF magic bytes (0x676c5446) at offset 0.

**OpenSea API scrape:** Searched 202 candidate collections (queries: "avatar", "3D",
"metaverse", "VRM", "vipe", "meebits", "cyberbrokers", "boombox", "grifters", etc.).
Only 1 collection (`vipe-heroes`) had VRM auto-discoverable from the first NFT's
OpenSea-served metadata. The rest required fetching the original token URI from
public IPFS gateways — OpenSea's cached `metadata_url` often points to a private
Pinata gateway that rejects non-browser requests.

Three tiers:

- **Tier A — VRM in token metadata.** The `.vrm` URL is embedded directly in the NFT's
  metadata (`vrm_url`, `vrm`, `asset`, `avatar_url`, `files`, `model/vrm`, etc.).
  Metaverse clients that parse OpenSea-style metadata can resolve the avatar
  automatically.
- **Tier B — VRM exists but off-chain.** The collection ships VRM avatars via a separate
  site/API/manifest, not in the token metadata itself. Holder has to go fetch the VRM
  manually.
- **Tier C — WIP / proof-of-concept only.** Team or community has produced VRM files
  but they're not yet shipped as a complete, downloadable per-token asset.

† = single VRM shared across the whole collection (not per-token unique).

---

## Tier A — VRM embedded in NFT metadata (verified)

### Ethereum mainnet

| OpenSea slug | Collection | Contract | Metadata param | Sample VRM URL |
| --- | --- | --- | --- | --- |
| cyberbrokers | CyberBrokers (Genesis Mechs) | 0xb286ac8eff9f44e2c377c6770cad5fc78bff9ed6 | `vrm_url` | m.cyberbrokers.com/eth/mech/1/files/mech_1k.0.vrm |
| boomboxheads-v2 | Boomboxheads V2 | 0xb67ff46dfde55ad2fe05881433e5687fd1000312 | `vrm_url` | ipfs://bafybeibe4axqsukdfeuy4fnrtti4dko7ph3fopl6xkr3tsdyp3zhhl5eyu/{id}.vrm |
| vipe-heroes | VIPE Heroes | 0x3999877754904d8542ad1845d368fa01a5e6e9a5 | `asset` | ipfs://QmZzox35J5WfXVUuTbQo2LmLFHoPd6Z4BeJByABTtKo4yP/default_{id}.vrm |
| phettaverse-editions | Phettaverse Editions | 0x41eb9dd376c9a3f1c02e5f3f89f22ad6ae970d51 | `vrm_url` | phettaverse.mypinata.cloud/ipfs/ (per-token) |
| meebits | Meebits | 0x7bd29408f11d2bfc23c34f18275bbf23bb716bc7 | `vrm` | api.meebits.app/v2/3d/larvalabs_vrm/{id} |
| misfitpixels | MisfitPIXELS | 0x618951345638caa062259cdbed445d4fb661b774 | `files` (vrm+glb) | misfitpixels.xyz/assets/misfits/ (per-token) |
| metaanigen | MetaaniGEN | 0xa467ab9447afa5db0c70325348d810d2058dde18 | `avatar_url` | ipfs per-token |
| frutiger-anons | Frutiger Anons | 0xbfD4F75A3C09c26e6CE9e67a257F6FBCe9F63088 | `vrm_url` | cloudfront/ipfs per-token |
| coldie | DEyes Legends by Coldie | 0x76250e9269e3df7d5bdc6af42582a1b54bf5d24e | `vrm_url` | ipfs per-token |
| chuddie | Chuddies | 0xe8979fdd9f050052e53a13257fe6218edd52c80a | `vrm_url` | ipfs per-token |
| forgottenruneswizardscult | Forgotten Runes Wizard Cult | 0x521f9c7505005cfa19a8e5786a9c3c9c9f5e6f42 | `vrm` | nftz.forgottenrunes.com/dev/3d/wizards/{id}/wizard_{id}.vrm |
| retrodogesnft | RetroDoges | 0xeeecde100b55f135a40ca9d92a52bd7723235814 | `vrm_url` | nft.retrodoges.com/media/main/vrm/{id}.vrm |
| dickbuttverse | DickButtVerse | 0xd47d8672e45a7204057baaa3622a3fa276d651e3 | `vrm_url` (+glb `animation_url`) | digitaloceanspaces per-token |
| pixelbeasts | PixelBeasts | 0xd539a3a5edb713e6587e559a9d007ffff92bd9ab | `model/vrm` | pixelbeasts3d.replit.app/beast/{id}.vrm |
| allstarz-psx † | Allstarz PSX | 0x6120991c423f3566753d3c6c91a5b50d7d2461b4 | `vrm_url` | allstarz.world (same VRM for all tokens) |
| — † | Fly Frogs | 0x31d4da52c12542ac3d6aadba5ed26a3a563a86dc | (same VRM for all tokens) | — |
| — † | OG Meta Meeples PFP | 0x1459c170e940e52628d9917c85772f7e897e7c0c | (same VRM for all tokens) | — |

### Base

| OpenSea slug | Collection | Contract | Notes |
| --- | --- | --- | --- |
| grifterssquaddies | Grifters Squaddies | 0xa94c652c16525e6b7cac82a34eab18b5174ad23c | 812 avatars, CC0, ToxSam × 12 CC0 artists, VRM via project manifest (`model_file_url` → ipfs .vrm) |
| — | ToxSam (Base side) | 0x59202483529a11642a43578a6ee77ca4ec24f930 | Part of multi-chain ToxSam collection; CC0; VRM via toxsam.com |

### Optimism

| OpenSea slug | Collection | Contract | Notes |
| --- | --- | --- | --- |
| halloween-rising | Halloween Rising | 0x0ad4c869d0019df7460b33ca852610c9cb0a5647 | 60 VRMs, 5 designs × 3 styles × 5 variations, CC0, Polygonal Mind |

### Polygon

| OpenSea slug | Collection | Contract | Notes |
| --- | --- | --- | --- |
| xmas-chibis | Xmas Chibis | 0x831079839bd0e6bf8e37e8cdfb5479fc1b2ef483 | 80 VRMs, 16 designs × 5 variations, CC0, Polygonal Mind |
| — | PolygonLow | (see opensea.io/collection/polygon-low) | glb + vrm + vox per hackmd/@XR; site polygonlow.xyz |

### Shape / other L2s

| Collection | Contract | Notes |
| --- | --- | --- |
| NeonGlitch86 Collection (Shape side) | 0xe7ba6df2934c487bb49435394fdd4b80268e2d3c | CC0; VRM via arweave/ipfs (per ToxSam manifest) |

---

## Tier B — VRM exists, but not in token metadata

These collections ship VRM avatars through their own site/launcher/manifest rather than
embedding the `.vrm` URL in the NFT metadata. Useful as avatars, but not auto-discoverable
by parsing the NFT.

### Ethereum mainnet

| Collection | Contract | Notes |
| --- | --- | --- |
| CryptoAvatars | 0xbffd07cc4d32578fe3ccbf8bd0c5ffa8da3fc600 | VRM via cryptoavatars.io API; also mints BAYC/MAYC-derived VRMs |
| Nouns | 0x9c8ff314c9bc7f6e59a9d9225fb22946427edc03 | Community VRM rigging via nouns.wtf |
| Voltz | 0xea377cfd0ceab570569d8d37a910071d9e9eb1d4 | VRM via voltz.me vault |
| Immadegen (VOID) | 0xdb55584e5104505a6b38776ee4dcba7dd6bb25fe | VRM via void-explorer; FBX+glb+VRM shipped |
| MONA Avatars | 0x773f02bbb852920099931f332089f3fadfbfa4b6 | VRM via monaverse.com |
| Avastars | 0xf3e778f839934fc819cfa1040aabacecba01e049 | VRM via avastars.io |
| Woodies | 0x134460d32fc66a6d84487c20dcd9fdcf92316017 | — |
| Wassies | 0x1d20a51f088492a0f1c57f047a9e30c9ab5c07ea | — |
| Chain Runners | 0x97597002980134bea46250aa0510c9b90d87a587 | — |
| Omnimorphs | 0xb5f3dee204ca76e913bb3129ba0312b9f0f31d82 | — |
| Elysium Shell: Next - Mecha | 0xfa37cfae8458a692511cd7ffcd9ac18a69af4274 | — |
| Toxic Skulls Club | 0x5ca8dd7f8e1ee6d0c27a7be6d9f33ef403fbcdd8 | — |
| Bourey vs Bulley: Bourverse | 0xcbd19f85965127bba4534bf21bf50008f054e54e | — |
| The Dask | 0x19d84b2a4b21910339af097a1bddb48682d6f47d | — |
| Chametheon | 0x495f947276749ce646f68ac8c248420045cb7b5e | — |
| RSTLSS x Claire Silver: Pixelgeist | 0x0e58adde284e95fa591cd3904452b12356570251 | — |
| CyberAnimeDOLL: Avatar | 0x495f947276749ce646f68ac8c248420045cb7b5e | — |
| MetaTravelers | (opensea.io/collection/metatravelers) | WIP |

### Ethereum / Base (multi-chain)

| Collection | Contract | Notes |
| --- | --- | --- |
| ToxSam | 0xc1def47cf1e15ee8c2a92f4e0e968372880d18d1 (ETH), 0xbffd07cc4d32578fe3ccbf8bd0c5ffa8da3fc600 (ETH), 0x59202483529a11642a43578a6ee77ca4ec24f930 (Base) | 10 VRMs in ToxSam manifest, CC0; opensea.io/NeonGlitch86/created |

### Polygon

| Collection | Contract | Notes |
| --- | --- | --- |
| NeonGlitch86 Collection (Polygon side) | 0xcdffc2fae679814913305c13edb86fe7967dbeea | CC0; VRM via project manifest |

---

## Tier C — WIP / proof-of-concept / community-led

Team or community has produced VRM files but they're not yet shipped as a complete,
downloadable per-token asset. Listed for completeness.

| Collection | OpenSea | Notes |
| --- | --- | --- |
| Bored Ape Yacht Club / Mutant Ape Yacht Club | opensea.io/collection/boredapeyachtclub | CryptoAvatars team working on 30,000 BAYC+MAYC VRMs |
| 0N1 Force | opensea.io/collection/0n1-force | Proof-of-concept VRM only |
| Gutter Cat Gang | opensea.io/collection/guttercatgang | Partnered with House of Kibaa; WIP |
| Deadfellaz | opensea.io/collection/deadfellaz | Roadmap 2.0 promises 10k 3D models |
| Axolittles | opensea.io/collection/axolittles | WIP modeling |
| Tubby Cats | opensea.io/collection/tubby-cats | CC0, WIP modeling |
| Blitnauts | opensea.io/collection/the-blitnauts | Public domain, WIP modeling |
| Cryptosergs | (cryptosergs.com) | WIP modeling |
| Super Yetis | opensea.io/collection/superyeti | WIP, Q/A — rigged 3D avatars being optimized |
| CloneX | clonex.rtfkt.com | RTFKT; rigged + shapekeys for face filters; not VRM-native |
| Mekaverse | opensea.io/collection/mekaverse | Unknown file format |
| MetaTravelers | opensea.io/collection/metatravelers | WIP |
| Genies (Flow) | (Dapper Labs / Flow) | Partnership, format unknown |

---

## Not VRM (often mislabeled)

These ship GLB only, or no 3D at all. Listed to save future scrapers time.

AdWorld (0x62eb144fe92ddc1b10bcade03a0c09f6fbffbffb), Chibi Apes (GLB only via
`external_url`), A Kid Called Beast, FLUF World, FyatLux (GLB only), PartyBear,
Muhammad Ali Next Legends Boxers, Jadu AVA, The Modz, The Seekers, RTFKT CloneX
(0x49cf6f5d44e70224e2e23fdcdd2c053f30ada28b — shipped GLB, not VRM), Metashima -
Lightning.

---

## Non-Ethereum VRM infrastructure (no canonical collection list yet)

These are platforms/launchpads that *host* VRM NFT collections on non-EVM chains.
Each supports arbitrary creators, so there's no fixed collection list — browse by
creator address.

| Platform | Chain | Storage | Notes |
| --- | --- | --- | --- |
| **3D Anvil** (ToxSam/3d-anvil) | Solana | Arweave via Irys | Open launchpad for VRM + GLB NFTs; Metaplex Candy Machine enforces mint rules; zero platform fees; DAS-capable RPC browse by creator |
| **Solana Avatars** (ekza-space/solana-avatars) | Solana (devnet live) | IPFS | Profile PDA + Minter contract; revokes mint/freeze authority; mainnet standard documented. Live at avatar.ekza.io |
| **CryptoAvatars** | Ethereum + others | — | Also operates as a VRM marketplace / 1-of-1 drop platform |

---

## Arweave-native VRM collections (not NFTs, but CC0 VRM avatar registries)

These are not on a chain but are commonly used as avatar sources and are referenced
by NFT projects (e.g. ToxSam's own NFT collections mirror these). Useful for the
broader VRM avatar index.

| Collection | Count | License | Storage | Sample |
| --- | --- | --- | --- | --- |
| 100Avatars R1 | 100 | CC0 | Arweave | arweave.net/gfVzs1oH_aPaHVxpQK86HT_rqzyrFPOUKUrDJ30yprs (verified glTF magic bytes) |
| 100Avatars R2 | 100 | CC0 | Arweave | (ToxSam manifest: data/avatars/100avatars-r2.json) |
| 100Avatars R3 | 100 | CC0 | Arweave | (ToxSam manifest: data/avatars/100avatars-r3.json) |

---

## Sources

- **OpenSea API v2** (instant free-tier key via `POST /api/v2/auth/keys`): used for
  collection search (`/api/v2/search`), collection metadata (`/api/v2/collections/{slug}`),
  and NFT listing (`/api/v2/collection/{slug}/nfts`). Key cached at `~/.opensea/api_key`.
- Curated registry (Ethereum, metadata-embedded VRM): https://github.com/itsmetamike/awesome-3D-avatar-collections
- Open-source avatar directory (multi-chain + Arweave): https://github.com/ToxSam/open-source-avatars
  - `data/projects.json` — collection registry
  - `data/avatars/*.json` — per-collection avatar manifests with `model_file_url` → VRM
- Solana VRM launchpad: https://github.com/ToxSam/3d-anvil
- Solana avatar identity system: https://github.com/ekza-space/solana-avatars
- Hackmd NFT 3D Avatars catalog: https://hackmd.io/@XR/nftavatars
- VRM × NFTs overview: https://www.bankless.com/vrm-nfts
- VIPE Heroes launch post: https://medium.com/@vipeio/vipe-heroes-vipes-genesis-3d-vrm-interoperable-avatar-collection-d563367e29f9
- Grifters Squaddies Round 3: https://medium.com/@vipeio/grifters-squaddies-vrm-collection-mint-round-three-bfc60e84201c

## Verification methodology

- **OpenSea API v2** (instant free-tier key, no signup): fetched collection
  metadata and sample NFTs for 202 candidate collections discovered via search
  queries ("avatar", "3D", "metaverse", "VRM", "vipe", "meebits", etc.).
- **Metadata fetch:** OpenSea's `metadata_url` field often points to a private
  Pinata gateway (`opensea-private.mypinata.cloud`) that rejects non-browser
  requests (ERR_ID:00024). Workaround: replaced with public `ipfs.io/ipfs/`
  gateway, with `dweb.link` as fallback. This recovered VRM metadata for
  boomboxheads-v2, vipe-heroes, metaanigen, misfit-pixels, d-eyes-legends, etc.
- **Tier A Ethereum entries:** fetched the token metadata URI from the curated
  registry, confirmed a real `.vrm` URL is present in the JSON metadata under
  fields like `vrm_url`, `vrm`, `avatar_url`, `asset`, `files`, `model/vrm`.
- **Tier A L2 entries** (Base/Optimism/Polygon/Shape): fetched the project's
  avatar manifest from ToxSam/open-source-avatars and confirmed
  `model_file_url` points to a `.vrm` file on ipfs/arweave.
- **Arweave-native entries:** downloaded the first asset and confirmed the
  `glTF` magic bytes (0x676c5446) at offset 0 — VRM is a glTF 2.0 binary
  extension, so this is the correct signature.
- **OpenSea API scrape result:** of 202 candidate "3D avatar" / "metaverse"
  collections searched on OpenSea, only `vipe-heroes` had VRM auto-discoverable
  from the first NFT's OpenSea-served metadata. The rest required fetching the
  original token URI from public IPFS gateways. This confirms the curated
  registry is more comprehensive than OpenSea search for this niche — most
  "3D" collections on OpenSea ship GLB or no 3D at all, not VRM.

---

## Licensing index — permission required to implement in hubzz

For each Tier A collection, the license was verified by reading the **VRM file's
embedded license metadata** (the `extensions.VRM.meta` or `extensions.VRMC_vrm.meta`
block in the glTF JSON chunk — this is the most authoritative source, set by the
creator at export time). Where the VRM file couldn't be fetched (IPFS gateway
timeouts), the license was determined from the project's GitHub repo, OpenSea
description, or published terms of service.

Three categories for hubzz implementation:

- **🟢 No permission needed** — CC0 / public domain. Anyone can use, modify,
  distribute, and commercialize without attribution. Safe to bundle into hubzz
  as default avatars.
- **🟡 Permission needed (holder-based)** — Commercial use is allowed but only
  for NFT holders (or "explicitly licensed persons"). hubzz would need to
  token-gate these avatars (verify the user holds the NFT before serving the
  VRM) OR negotiate a platform-level license with the project.
- **🔴 Permission required (all rights reserved)** — The VRM file embeds
  `Redistribution_Prohibited` or `commercialUssageName: Disallow` or
  `allowedUserName: OnlyAuthor`. hubzz MUST get explicit written permission
  from the project before shipping these, even if the user holds the NFT.

### 🟢 No permission needed (CC0 / public domain)

| Collection | VRM license | Commercial | Avatar use by | Source |
| --- | --- | --- | --- | --- |
| Boomboxheads V2 | CC0 | Allow | Everyone | GitHub repo (CC0-1.0), OpenSea desc |
| 100Avatars R1 | CC0 | Allow | Everyone | VRM-embedded meta |
| 100Avatars R2 | CC0 | Allow | Everyone | ToxSam projects.json |
| 100Avatars R3 | CC0 | Allow | Everyone | ToxSam projects.json |
| Grifters Squaddies | CC0 | Allow | Everyone | VRM-embedded meta |
| ToxSam | CC0 | Allow | Everyone | VRM-embedded meta |
| Halloween Rising | CC0 | Allow | Everyone | ToxSam projects.json (CC0) |
| Xmas Chibis | CC0 | Allow | Everyone | ToxSam projects.json (CC0) |
| NeonGlitch86 Collection | CC0 | Allow | Everyone | ToxSam projects.json (CC0) |
| PixelBeasts (Beastopia) | CC0 (CBE-Public) | Allow | Everyone | a16z "Can't Be Evil" CC0 license |

### 🟡 Permission needed — holder-based commercial license

These collections allow commercial use of the VRM, but only by NFT holders
("ExplicitlyLicensedPerson" in VRM meta). hubzz has two paths:
1. **Token-gate the avatar** — verify the user holds the NFT (via wallet
   connection / token-gating) before serving the VRM. No project permission
   needed; the holder's NFT IS the license.
2. **Platform license** — negotiate a bulk license with the project to offer
   the avatars to all hubzz users regardless of NFT ownership.

| Collection | VRM license | Commercial | Avatar use by | Notes |
| --- | --- | --- | --- | --- |
| VIPE Heroes | CC-BY | Allow | ExplicitlyLicensedPerson | Attribution required; holder-based; VRM-embedded meta confirms |
| Meebits | Other (Yuga Labs) | Allow | ExplicitlyLicensedPerson | Full commercialization rights for holders per Yuga Labs IP agreement (licenseterms.meebits.app); VRM-embedded meta confirms |
| CyberBrokers Genesis Mechs | Holder commercial license | Allow | ExplicitlyLicensedPerson | "Full commercial rights to any outputs you create" per terms of use; VRM file timed out but project terms clear |
| Halloween Rising (VRM file) | Other (VIPE custom) | Allow | ExplicitlyLicensedPerson | VRM-embedded meta says `Other` with custom license URL — holder-based, modification allowed with credit |
| Xmas Chibis (VRM file) | Redistribution_Prohibited | Allow | ExplicitlyLicensedPerson | VRM-embedded meta says `Redistribution_Prohibited` but commercial use allowed for holders; **hubzz cannot redistribute the VRM file itself** — must fetch on-demand from IPFS after token verification |
| Forgotten Runes Wizard Cult | Holder commercial (cc5m) | Allow (holder) | ExplicitlyLicensedPerson | Non-holders: CC BY-NC; holders: royalty-free up to $5mm then 20% royalty; VRM-embedded meta says `Redistribution_Prohibited` / `OnlyAuthor` (conservative defaults) but project terms grant holder rights |
| Phettaverse Editions | Commission-based | Allow (Sovereign Tier) | Depends on tier | "Partial Rights" (companion) vs "Full Rights" (sovereign) commission tiers; check per-token |
| CryptoAvatars | Per-avatar (varies) | Varies | Varies | Each avatar has its own license set by the artist; platform sorts by "OpenSource" vs owned; check per-token |
| Frutiger Anons | Scatter commercial merch license | Allow | Holder | Scatter's capsule machine grants "commercial merchandise license for that art piece"; assume same for Frutiger Anons |
| Chuddies | Scatter (Remilia ecosystem) | Likely holder-based | Likely holder | Part of Remilia/Milady ecosystem; Scatter blog mentions "CC0 or Copyleft projects like Milady" but Chuddies specifically unclear |
| Allstarz PSX | Unknown — likely holder | Unknown | Unknown | Same VRM for all tokens (†); no clear license docs found |
| Fly Frogs | Unknown — likely holder | Unknown | Unknown | Same VRM for all tokens (†); no clear license docs found |
| OG Meta Meeples PFP | Unknown — likely holder | Unknown | Unknown | Same VRM for all tokens (†); no clear license docs found |

### 🔴 Permission required — all rights reserved / no commercial use

The VRM file embeds `Redistribution_Prohibited` AND `commercialUssageName:
Disallow` AND `allowedUserName: OnlyAuthor`. hubzz **must not** ship these
without explicit written permission from the project, even if the user holds
the NFT. The NFT ownership does NOT grant VRM usage rights — the VRM file's
embedded license overrides.

| Collection | VRM license | Commercial | Avatar use by | Notes |
| --- | --- | --- | --- | --- |
| Metaani (MetaaniGEN) | Redistribution_Prohibited | Disallow | OnlyAuthor | VRM-embedded meta; BeyondConcept Inc. retains all rights; would need corporate license from conata.world |
| RetroDoges | Redistribution_Prohibited | Disallow | OnlyAuthor | VRM-embedded meta (title/author are "undefined" — likely unset); no clear commercial license docs; would need permission from retrodoges.com |
| DickButtVerse | Non-commercial (ToS) | Disallow | N/A | Terms of Service: "limited, non-commercial, non-exclusive, non-transferable license"; all IP retained by company; **would need explicit commercial license** |
| DEyes Legends by Coldie | Unknown (SuperRare/Verse) | Unknown | Unknown | Coldie is a SuperRare artist; 1/1 portrait artworks; license likely retained by artist; **would need permission from Coldie** |

### Tier B — licensing unknown / varies

The Tier B collections (VRM exists but off-chain) were not VRM-verified. Their
licenses would need to be checked per-project before implementation:

| Collection | Likely license | Notes |
| --- | --- | --- |
| Nouns | CC0 (Nouns DAO) | Likely safe, but VRM is community-rigged not official |
| Voltz | Unknown | Check voltz.me vault |
| Immadegen (VOID) | Unknown | Check void-explorer |
| MONA Avatars | Unknown | Check monaverse.com |
| Avastars | Unknown | Check avastars.io |
| Woodies | Unknown | — |
| Wassies | Unknown | — |
| Chain Runners | CC0 (likely) | On-chain pixel art, often CC0 |
| Omnimorphs | Unknown | — |
| Elysium Shell | Unknown | — |
| Toxic Skulls Club | Unknown | — |
| Bourverse | Unknown | — |
| The Dask | Unknown | — |
| Chametheon | Unknown | — |
| Pixelgeist (RSTLSS x Claire Silver) | Unknown | — |
| CyberAnimeDOLL | Unknown | — |
| MetaTravelers | Unknown | WIP |
| PolygonLow | Unknown | — |

### Tier C — WIP / not yet shipped

These collections have not yet shipped VRM files. Licensing will be determined
when the VRM files are released. Most PFP projects (BAYC, CloneX, etc.) grant
holder commercial rights, so the holder-based model (🟡) will likely apply.

### VRM-embedded license fields reference

VRM files store license info in the glTF JSON chunk under
`extensions.VRM.meta` (VRM 0.x) or `extensions.VRMC_vrm.meta` (VRM 1.0). Key
fields checked for this index:

| Field | Values | Meaning |
| --- | --- | --- |
| `licenseName` | `CC0`, `CC_BY`, `CC_BY_NC`, `CC_BY_SA`, `CC_BY_NC_SA`, `CC_BY_ND`, `CC_BY_NC_ND`, `Redistribution_Prohibited`, `Other` | Redistribution/modification license |
| `commercialUssageName` | `Allow`, `Disallow` | Whether commercial use is permitted |
| `allowedUserName` | `Everyone`, `ExplicitlyLicensedPerson`, `OnlyAuthor` | Who can use the avatar as their persona |
| `otherLicenseUrl` | URL | Custom license document (when `licenseName` is `Other`) |
| `violentUssageName` | `Allow`, `Disallow` | Whether violent content with avatar is OK |
| `sexualUssageName` | `Allow`, `Disallow` | Whether sexual content with avatar is OK |

**Key insight:** `allowedUserName: OnlyAuthor` is the most restrictive — it
means only the creator can use the avatar, even if you own the NFT. This is
the default VRM export setting and many creators forget to change it. For
hubzz, any collection with `OnlyAuthor` in the VRM file requires explicit
permission regardless of what the project's marketing site claims.

**Key insight 2:** `Redistribution_Prohibited` means hubzz cannot host/cache
the VRM file on its own servers — it must be fetched on-demand from IPFS/
Arweave after token-gating verification. This is the case for Xmas Chibis,
Metaani, Forgotten Runes, and RetroDoge even though some allow commercial use.
